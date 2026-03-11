from celery import Celery
import os
from app.services.registry import AgentRegistry
from app.services.agent_spawner import AgentSpawner
from app.services.openai_service import OpenAIService
from app.services.search_service import SearchService
from app.services.memory_manager import MemoryManager
import time, json

CELERY_BROKER = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://redis:6379/0'))
CELERY_BACKEND = os.getenv('CELERY_RESULT_BACKEND', CELERY_BROKER)

celery = Celery('amas', broker=CELERY_BROKER, backend=CELERY_BACKEND)
celery.conf.task_routes = {
    'app.celery_worker.run_coordinator_task': {'queue': 'coordinator'},
    'app.celery_worker.agent_think_step': {'queue': 'coordinator'},
    'app.celery_worker.agent_store_memory': {'queue': 'coordinator'},
    'app.celery_worker.agent_plan_goal': {'queue': 'coordinator'},
}

@celery.task(name='app.celery_worker.run_coordinator_task')
def run_coordinator_task(task_id, goal, requirements, constraints):
    # Very high-level orchestration pipeline – representative of production process.
    registry = AgentRegistry()
    spawner = AgentSpawner()
    openai = OpenAIService()
    search = SearchService()
    memory = MemoryManager()

    # 1. Coordinator picks core agents from registry
    agents = registry.list_agents()

    # If no agents, attempt to spawn core agents (best-effort)
    if not agents:
        core = ['ResearchAgent','WriterAgent','ReviewerAgent','CoordinatorAgent','MemoryAgent','SearchAgent','AnalyzerAgent']
        for name in core:
            try:
                info = spawner.spawn_agent_container(name=name, role=name, image=os.getenv('AGENT_DEFAULT_IMAGE'))
                if info:
                    registry.register(info['agent_id'], name, name, {}, info['container_id'])
            except Exception:
                # Do not fail the workflow if spawning is unavailable.
                pass

    # 2. Research step: use search service (best-effort)
    results = []
    search_error = None
    try:
        results = search.search(goal, num=5)
    except Exception as e:
        search_error = repr(e)
        results = []

    def _fallback_answer_from_search(r):
        """Best-effort answer derived from search results when OpenAI is unavailable.

        Supports:
        - SerpAPI organic_results (list of dicts)
        - DuckDuckGo RelatedTopics (list)
        """
        try:
            if not r:
                return None

            first = r[0]
            if isinstance(first, dict):
                # SerpAPI commonly provides: title, snippet, link
                title = str(first.get('title') or '').strip()
                snippet = str(first.get('snippet') or first.get('text') or '').strip()
                link = str(first.get('link') or first.get('firstURL') or '').strip()

                parts = []
                if title:
                    parts.append(title)
                if snippet:
                    parts.append(snippet)
                if link:
                    parts.append(f"Source: {link}")
                if parts:
                    return "\n".join(parts)

            # DuckDuckGo RelatedTopics can be nested; best-effort stringify
            return str(first)
        except Exception:
            return None

    # 3. Reason over results via OpenAI (optional)
    use_openai = True
    try:
        if isinstance(constraints, dict) and constraints.get('use_openai') is False:
            use_openai = False
    except Exception:
        use_openai = True

    openai_error = None
    analysis = None

    if use_openai:
        prompt = f"""You are the Coordinator. Goal: {goal}\nSearch results: {results[:3]}\nConstraints: {constraints}\nRequirements: {requirements}"""
        try:
            resp = openai.completion(prompt, model='gpt-4o-mini', max_tokens=800)
            analysis = resp.get('choices',[{}])[0].get('message',{}).get('content','')
        except Exception as e:
            openai_error = f"OpenAI error: {e}"
            analysis = None

    # If OpenAI is skipped or failed, fall back to search-based answer.
    if not analysis:
        fallback = _fallback_answer_from_search(results)
        if fallback:
            analysis = fallback
        elif openai_error:
            analysis = openai_error
        else:
            analysis = "No answer available (no OpenAI result and no usable search results)."

    # 4. Save memory (best-effort)
    try:
        memory.save('coordinator', 'analysis', {
            'goal': goal,
            'analysis': analysis,
            'search_head': results[:3],
            'search_error': search_error,
            'openai_error': openai_error,
            'use_openai': use_openai,
        })
    except Exception:
        pass

    # 5. Notify via Redis pub/sub that workflow completed (best-effort)
    try:
        import redis
        r = redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'))
        r.publish('workflow.completed', json.dumps({'task_id': task_id, 'result_preview': analysis[:200]}))
    except Exception:
        pass

    return {
        'task_id': task_id,
        # 'analysis' is the primary human-readable output.
        # It may be generated by OpenAI or derived from search results as a fallback.
        'analysis': analysis,
        # Alias for clients that prefer an explicit key name.
        'answer': analysis,
        'analysis_preview': (analysis or '')[:300],
        'search_head': results[:3],
        'search_error': search_error,
        'openai_error': openai_error,
        'use_openai': use_openai,
    }


def _safe_json_obj(content: str):
    try:
        obj = json.loads(content)
        if isinstance(obj, dict):
            return obj
        return {"value": obj}
    except Exception:
        return None


@celery.task(name='app.celery_worker.agent_think_step')
def agent_think_step(agent_id: str, agent_name: str, agent_role: str, state: dict, observation: dict):
    """Compute a next-action decision for an agent.

    This is intentionally small and purely computational so it can run in the celery-worker
    container while the agent container remains a persistent runtime loop.
    """
    openai = OpenAIService()

    allowed_actions = [
        {"type": "sleep", "payload": {"seconds": "number"}},
        {"type": "publish", "payload": {"channel": "string", "message": "json"}},
        {"type": "spawn_agent", "payload": {"name": "string", "role": "string", "metadata": "object"}},
        {"type": "run_coordinator_task", "payload": {"goal": "string", "requirements": "list", "constraints": "object"}},
        {"type": "add_goal", "payload": {"description": "string", "priority": "number", "parent_goal_id": "string|null"}},
        {"type": "create_subgoal", "payload": {"parent_goal_id": "string", "description": "string", "priority": "number"}},
        {"type": "complete_goal", "payload": {"goal_id": "string"}},
        {"type": "fail_goal", "payload": {"goal_id": "string"}},
        {"type": "plan_goal", "payload": {"goal_id": "string (optional)"}},
        {"type": "complete_plan_step", "payload": {"goal_id": "string (optional)", "step_id": "string (optional)"}},
        {"type": "fail_plan_step", "payload": {"goal_id": "string (optional)", "step_id": "string (optional)", "reason": "string (optional)"}},
        {"type": "send_message", "payload": {"recipient_agent_id": "string", "content": "string", "metadata": "object"}},
        {"type": "broadcast_message", "payload": {"content": "string", "metadata": "object"}},
        {"type": "delegate_task", "payload": {"recipient_agent_id": "string", "task": "object"}},
        {"type": "status_update", "payload": {"status": "string", "details": "object", "broadcast": "bool", "recipient_agent_id": "string|null"}},
        {"type": "noop", "payload": {}},
    ]

    role_norm = (str(agent_role or "").strip().lower().replace("_", "").replace("-", ""))
    if role_norm.endswith("agent"):
        role_norm = role_norm[: -len("agent")]

    role_instructions = ""
    if role_norm == "planner":
        role_instructions = (
            "ROLE: PlannerAgent. Focus on planning, decomposition, delegation, and coordination. "
            "Avoid claiming to execute work directly; delegate tasks to executors.\n\n"
        )
    elif role_norm == "executor":
        role_instructions = (
            "ROLE: ExecutorAgent. Focus on executing the current plan step or delegated tasks and reporting progress. "
            "Avoid broad replanning unless blocked.\n\n"
        )
    elif role_norm == "critic":
        role_instructions = (
            "ROLE: CriticAgent. Focus on critique, spotting failures/misalignment, and advising replans/subgoals. "
            "Avoid doing execution yourself.\n\n"
        )

    prompt = (
        "You are an autonomous agent in a multi-agent system. "
        "Return STRICT JSON only.\n\n"
        f"Agent identity: id={agent_id} name={agent_name} role={agent_role}\n\n"
        + role_instructions
        + f"State (json): {json.dumps(state)}\n\n"
        + f"Observation (json): {json.dumps(observation)}\n\n"
        + f"Allowed actions: {json.dumps(allowed_actions)}\n\n"
        + "Return JSON with keys: thought (string), action (object with type,payload), sleep_seconds (number, optional)."
    )

    try:
        resp = openai.completion(prompt, model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'), max_tokens=int(os.getenv('OPENAI_MAX_TOKENS', '500')))
        content = resp.get('choices',[{}])[0].get('message',{}).get('content','')
        decision = _safe_json_obj(content)
        if decision is None:
            return {
                'thought': 'OpenAI returned non-JSON; defaulting to sleep',
                'action': {'type': 'sleep', 'payload': {'seconds': 2}},
                'sleep_seconds': 2,
                'raw': content[:200],
            }
        return decision
    except Exception as e:
        return {
            'thought': f'OpenAI error: {e}',
            'action': {'type': 'sleep', 'payload': {'seconds': 5}},
            'sleep_seconds': 5,
        }


@celery.task(name='app.celery_worker.agent_store_memory')
def agent_store_memory(agent_id: str, mtype: str, payload: dict):
    """Persist an agent memory record.

    Backward compatible with the original storage-oriented behavior, with additive cognitive features:
    - working memory: agent:working_memory:<agent_id> (Redis)
    - episodic memory: action/outcome extracted from agent_loop_tick
    - semantic memory: summaries emitted periodically

    Primary path: Postgres via MemoryManager.
    Fallback: Redis list agent:memory:<agent_id>
    """

    # Handle working memory explicitly (so it always ends up in Redis as well)
    if mtype == getattr(MemoryManager, 'WORKING', 'working'):
        try:
            mm = MemoryManager()
            mm.set_working_memory(agent_id, payload or {}, ttl_seconds=int(os.getenv('WORKING_MEMORY_TTL_SECONDS', '0') or 0) or None)
            return {'status': 'ok'}
        except Exception as e:
            # fallback: set redis key directly
            try:
                import redis as _redis
                r = _redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'), decode_responses=True)
                r.set(f'agent:working_memory:{agent_id}', json.dumps(payload or {}))
                return {'status': 'fallback_redis', 'error': repr(e)}
            except Exception as e2:
                return {'status': 'error', 'error': repr(e), 'fallback_error': repr(e2)}

    try:
        mm = MemoryManager()
        mm.save(agent_id, mtype, payload)

        # If this is a legacy episodic record, also materialize an explicit episodic entry.
        if mtype == getattr(MemoryManager, 'LEGACY_EPISODIC', 'agent_loop_tick') and isinstance(payload, dict):
            try:
                mm.save_episodic(
                    agent_id,
                    action=payload.get('decision') or {},
                    outcome=payload.get('action_result') or {},
                    reflection=payload.get('reflection') or {},
                    context=payload.get('observation') or {},
                )
            except Exception:
                pass

            # Update working memory from observation context (best-effort)
            try:
                obs = payload.get('observation') or {}
                wm = {
                    'ts': payload.get('ts'),
                    'iteration': payload.get('iteration'),
                    'active_goal': obs.get('active_goal'),
                    'current_plan_step': obs.get('current_plan_step'),
                    'planning_enabled': obs.get('planning_enabled'),
                }
                mm.set_working_memory(agent_id, wm, ttl_seconds=int(os.getenv('WORKING_MEMORY_TTL_SECONDS', '0') or 0) or None)
            except Exception:
                pass

            # Summarize every N steps (best-effort)
            try:
                every_n = int(os.getenv('MEMORY_SUMMARIZE_EVERY_N', '10') or 10)
                window = int(os.getenv('MEMORY_SUMMARY_EPISODE_WINDOW', '20') or 20)
                mm.maybe_summarize(agent_id, iteration=int(payload.get('iteration') or 0) + 1, every_n_steps=every_n, episode_window=window)
            except Exception:
                pass

        return {'status': 'ok'}

    except Exception as e:
        # DB path failed, fall back to Redis list
        try:
            import redis as _redis
            r = _redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'), decode_responses=True)
            r.lpush(f'agent:memory:{agent_id}', json.dumps({'type': mtype, 'payload': payload, 'error': repr(e)}))
            r.ltrim(f'agent:memory:{agent_id}', 0, 199)

            # Best-effort: maintain working memory even without DB
            if mtype == 'agent_loop_tick' and isinstance(payload, dict):
                try:
                    obs = payload.get('observation') or {}
                    wm = {
                        'ts': payload.get('ts'),
                        'iteration': payload.get('iteration'),
                        'active_goal': obs.get('active_goal'),
                        'current_plan_step': obs.get('current_plan_step'),
                        'planning_enabled': obs.get('planning_enabled'),
                    }
                    r.set(f'agent:working_memory:{agent_id}', json.dumps(wm))
                except Exception:
                    pass

            return {'status': 'fallback_redis', 'error': repr(e)}
        except Exception as e2:
            return {'status': 'error', 'error': repr(e), 'fallback_error': repr(e2)}

@celery.task(name='app.celery_worker.agent_plan_goal')
def agent_plan_goal(goal_id: str, goal_description: str, context: dict = None):
    """Decompose a high-level goal into ordered sub-tasks.

    This is optional and agent-driven; existing workflow execution remains untouched.
    """
    try:
        from planning.planner import Planner

        planner = Planner(model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'), max_tokens=int(os.getenv('OPENAI_MAX_TOKENS', '800')))
        plan = planner.plan(goal_id=goal_id, goal_description=goal_description, context=context or {})
        return plan.to_dict()
    except Exception as e:
        # Return minimal plan so agents can continue
        return {
            'goal_id': goal_id,
            'goal_description': goal_description,
            'steps': [{'order': 1, 'description': f'Work on goal: {goal_description}', 'status': 'pending'}],
            'current_step_index': 0,
            'error': repr(e),
        }

