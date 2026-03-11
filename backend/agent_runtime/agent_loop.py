from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import redis

from goals.goal_manager import GoalManager
from planning.planner import Planner
from communication.message_bus import MessageBus
from communication.protocols import (
    AgentMessage,
    MessageTypes,
    make_broadcast_message,
    make_direct_message,
    make_status_update,
    make_task_delegation,
)
from agent_runtime.roles.base_agent import AgentIdentity
from agent_runtime.roles.factory import load_role_agent


JsonDict = Dict[str, Any]


def _truthy(v: Optional[str]) -> bool:
    if v is None:
        return False
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_json_loads(s: str) -> Optional[JsonDict]:
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
        return {"value": obj}
    except Exception:
        return None


@dataclass
class AgentLoopConfig:
    redis_url: str

    # Loop timing
    tick_seconds: float = 2.0
    min_sleep_seconds: float = 0.25

    # "Think" step (OpenAI)
    model: str = "gpt-4o-mini"
    max_tokens: int = 500
    think_timeout_seconds: float = 30.0

    # Planning (optional)
    planning_enabled: bool = False
    planning_model: str = "gpt-4o-mini"
    planning_max_tokens: int = 800
    planning_min_description_chars: int = 120

    # Reflection (lightweight; OpenAI optional)
    reflection_use_openai: bool = False
    reflection_openai_on_failure_only: bool = True
    reflection_openai_every_n: int = 0
    reflection_max_tokens: int = 120

    # Optional: allow reflection to create subgoals on repeated failure signals
    reflection_auto_subgoal_on_failure: bool = False
    reflection_subgoal_priority_boost: int = 1

    # Safety / environment awareness (all optional, env-configurable)
    safety_enabled: bool = True

    # Loop limits
    loop_max_iterations: int = 0  # 0 = unlimited

    # Health monitoring
    health_key_prefix: str = "agent:health:"
    health_ttl_seconds: int = 60

    # Kill switch
    kill_key_prefix: str = "agent:kill:"  # set agent:kill:<agent_id> to truthy to stop
    kill_switch_env: str = "AGENT_KILL_SWITCH"  # if env var is truthy, stop

    # Failure detection
    max_consecutive_failures: int = 5

    # Stuck detection (no progress)
    max_consecutive_no_progress: int = 12

    # Retry/backoff (applies as sleep override on failures)
    failure_backoff_base_seconds: float = 1.0
    failure_backoff_max_seconds: float = 30.0
    failure_backoff_jitter_seconds: float = 0.25

    # Escalation/delegation
    escalation_cooldown_seconds: float = 30.0
    escalate_broadcast: bool = True
    escalate_delegate: bool = True

    # Persistence
    state_key_prefix: str = "agent:state:"
    inbox_key_prefix: str = "agent:inbox:"
    memory_key_prefix: str = "agent:memory:"
    plan_key_prefix: str = "agent:plan:"


@dataclass
class AgentState:
    agent_id: str
    agent_name: str
    agent_role: str

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: float = field(default_factory=lambda: time.time())
    iteration: int = 0

    # Safety tracking
    consecutive_failures: int = 0
    consecutive_no_progress: int = 0
    last_progress_at: float = 0.0
    last_escalation_at: float = 0.0

    last_observation: JsonDict = field(default_factory=dict)
    last_decision: JsonDict = field(default_factory=dict)
    last_action_result: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "run_id": self.run_id,
            "started_at": float(self.started_at),
            "iteration": int(self.iteration),
            "consecutive_failures": int(self.consecutive_failures),
            "consecutive_no_progress": int(self.consecutive_no_progress),
            "last_progress_at": float(self.last_progress_at or 0.0),
            "last_escalation_at": float(self.last_escalation_at or 0.0),
            "last_observation": self.last_observation,
            "last_decision": self.last_decision,
            "last_action_result": self.last_action_result,
        }

    @staticmethod
    def from_dict(d: JsonDict) -> "AgentState":
        return AgentState(
            agent_id=str(d.get("agent_id") or ""),
            agent_name=str(d.get("agent_name") or ""),
            agent_role=str(d.get("agent_role") or ""),
            run_id=str(d.get("run_id") or str(uuid.uuid4())),
            started_at=float(d.get("started_at") or time.time()),
            iteration=int(d.get("iteration") or 0),
            consecutive_failures=int(d.get("consecutive_failures") or 0),
            consecutive_no_progress=int(d.get("consecutive_no_progress") or 0),
            last_progress_at=float(d.get("last_progress_at") or 0.0),
            last_escalation_at=float(d.get("last_escalation_at") or 0.0),
            last_observation=dict(d.get("last_observation") or {}),
            last_decision=dict(d.get("last_decision") or {}),
            last_action_result=dict(d.get("last_action_result") or {}),
        )


class AgentLoop:
    """Autonomous Observe→Think→Decide→Act→Reflect→Store Memory loop.

    Designed to run persistently inside an agent container.

    Integration points:
    - Uses Redis for observation/inbox and for state persistence.
    - Uses OpenAI via app.services.openai_service.OpenAIService when possible.
    - Can offload the Think/Memory steps to Celery via tasks in app.celery_worker.
    - Requests new agents via orchestrator by publishing to Redis channel agent.spawn.request.
    """

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        agent_role: str,
        config: AgentLoopConfig,
    ):
        self.config = config
        self.r = redis.from_url(self.config.redis_url, decode_responses=True)

        self.state_key = f"{self.config.state_key_prefix}{agent_id}"
        self.inbox_key = f"{self.config.inbox_key_prefix}{agent_id}"
        self.memory_key = f"{self.config.memory_key_prefix}{agent_id}"

        # Agent-owned goal management (persisted in Redis)
        self.goals = GoalManager(self.r, agent_id=agent_id)

        # Agent-to-agent communication
        self.bus = MessageBus(
            redis_url=self.config.redis_url,
            agent_id=agent_id,
            agent_name=agent_name,
            agent_role=agent_role,
        )

        # Role specialization (swappable via configuration)
        self.role_agent = load_role_agent(
            AgentIdentity(agent_id=agent_id, agent_name=agent_name, agent_role=(agent_role or "")),
            self.bus,
        )

        loaded = self._load_state()
        if loaded is not None:
            self.state = loaded
            # Ensure identity matches env (env wins)
            self.state.agent_id = agent_id
            self.state.agent_name = agent_name
            self.state.agent_role = agent_role
        else:
            self.state = AgentState(agent_id=agent_id, agent_name=agent_name, agent_role=agent_role)

        self._celery_tasks = None

    @staticmethod
    def from_env() -> "AgentLoop":
        agent_id = os.getenv("AGENT_ID") or f"agent-{uuid.uuid4()}"
        agent_name = os.getenv("AGENT_NAME") or "GenericAgent"
        agent_role = os.getenv("AGENT_ROLE") or ""

        cfg = AgentLoopConfig(
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            tick_seconds=float(os.getenv("AGENT_LOOP_TICK_SECONDS", "2.0")),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "500")),
            think_timeout_seconds=float(os.getenv("AGENT_LOOP_THINK_TIMEOUT_SECONDS", "30")),
            planning_enabled=_truthy(os.getenv("AGENT_ENABLE_PLANNING", "false")),
            planning_model=os.getenv("AGENT_PLANNING_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
            planning_max_tokens=int(os.getenv("AGENT_PLANNING_MAX_TOKENS", "800")),
            planning_min_description_chars=int(os.getenv("AGENT_PLANNING_MIN_DESCRIPTION_CHARS", "120")),
            reflection_use_openai=_truthy(os.getenv("AGENT_REFLECTION_USE_OPENAI", "false")),
            reflection_openai_on_failure_only=_truthy(os.getenv("AGENT_REFLECTION_OPENAI_ON_FAILURE_ONLY", "true")),
            reflection_openai_every_n=int(os.getenv("AGENT_REFLECTION_OPENAI_EVERY_N", "0")),
            reflection_max_tokens=int(os.getenv("AGENT_REFLECTION_MAX_TOKENS", "120")),
            reflection_auto_subgoal_on_failure=_truthy(os.getenv("AGENT_REFLECTION_AUTO_SUBGOAL_ON_FAILURE", "false")),
            reflection_subgoal_priority_boost=int(os.getenv("AGENT_REFLECTION_SUBGOAL_PRIORITY_BOOST", "1")),
            safety_enabled=_truthy(os.getenv("AGENT_SAFETY_ENABLED", "true")),
            loop_max_iterations=int(os.getenv("AGENT_LOOP_MAX_ITERATIONS", "0")),
            health_ttl_seconds=int(os.getenv("AGENT_HEALTH_TTL_SECONDS", "60")),
            max_consecutive_failures=int(os.getenv("AGENT_MAX_CONSECUTIVE_FAILURES", "5")),
            max_consecutive_no_progress=int(os.getenv("AGENT_MAX_CONSECUTIVE_NO_PROGRESS", "12")),
            failure_backoff_base_seconds=float(os.getenv("AGENT_FAILURE_BACKOFF_BASE_SECONDS", "1.0")),
            failure_backoff_max_seconds=float(os.getenv("AGENT_FAILURE_BACKOFF_MAX_SECONDS", "30.0")),
            failure_backoff_jitter_seconds=float(os.getenv("AGENT_FAILURE_BACKOFF_JITTER_SECONDS", "0.25")),
            escalation_cooldown_seconds=float(os.getenv("AGENT_ESCALATION_COOLDOWN_SECONDS", "30.0")),
            escalate_broadcast=_truthy(os.getenv("AGENT_ESCALATE_BROADCAST", "true")),
            escalate_delegate=_truthy(os.getenv("AGENT_ESCALATE_DELEGATE", "true")),
        )
        return AgentLoop(agent_id=agent_id, agent_name=agent_name, agent_role=agent_role, config=cfg)

    def run_forever(self):
        print(
            f"[agent_loop] starting: id={self.state.agent_id} name={self.state.agent_name} role={self.state.agent_role} run_id={self.state.run_id}"
        )

        while True:
            # Kill switch / iteration limit (should never block normal execution unless enabled)
            if self._should_stop_now():
                break

            started = time.time()

            # Update health at loop start
            self._update_health(phase="start", extra={"iteration": int(self.state.iteration)})

            observation: JsonDict = {}
            decision: JsonDict = {"thought": "", "action": {"type": "sleep", "payload": {"seconds": self.config.tick_seconds}}}
            action_result: JsonDict = {"status": "error", "error": "uninitialized"}

            try:
                observation = self.observe()
                decision = self.think(observation)
                action_result = self.act(decision)
            except Exception as e:
                # Safety: keep loop alive
                action_result = {"status": "error", "type": "exception", "error": repr(e)}

            # Reflection + memory
            reflection = self.reflect(observation, decision, action_result)
            self._safety_after_step(observation, decision, action_result, reflection)
            self.store_memory(observation, decision, action_result, reflection)

            # state update + persist
            self.state.iteration += 1
            self.state.last_observation = observation
            self.state.last_decision = decision
            self.state.last_action_result = action_result
            self._save_state()

            # Update health at loop end
            self._update_health(
                phase="end",
                extra={
                    "iteration": int(self.state.iteration),
                    "action_status": action_result.get("status"),
                    "consecutive_failures": int(self.state.consecutive_failures),
                    "consecutive_no_progress": int(self.state.consecutive_no_progress),
                },
            )

            # Scheduling the next tick (agent triggers its own next action)
            sleep_s = float(decision.get("sleep_seconds") or 0)
            if sleep_s <= 0:
                elapsed = time.time() - started
                sleep_s = max(self.config.tick_seconds - elapsed, self.config.min_sleep_seconds)

            # Apply retry/backoff on failures
            sleep_s = self._apply_failure_backoff(sleep_s)

            time.sleep(sleep_s)

    # ---------------------------
    # Observe
    # ---------------------------
    def observe(self) -> JsonDict:
        """Pull any pending messages for this agent from Redis.

        Inbound messages are expected (best-effort) as JSON strings in a Redis list:
        - key: agent:inbox:<agent_id>

        This module doesn't define a sender; other components/agents can LPUSH to that key.
        """

        msgs: List[JsonDict] = []
        try:
            raw = self.r.lrange(self.inbox_key, 0, -1)
            if raw:
                self.r.delete(self.inbox_key)
            for item in raw:
                if isinstance(item, str):
                    parsed = _safe_json_loads(item)
                    msgs.append(parsed or {"raw": item})
                else:
                    msgs.append({"raw": item})
        except Exception as e:
            msgs.append({"type": "error", "where": "observe", "error": repr(e)})

        # Broadcast messages (non-blocking)
        try:
            bmsgs = self.bus.poll_broadcast(max_messages=10)
            for b in bmsgs:
                if isinstance(b, dict):
                    msgs.append(b)
        except Exception:
            pass

        # Create goals from any inbound goal messages (agent owns goal state after ingest)
        try:
            self.goals.ingest_messages(msgs)
        except Exception:
            pass

        active_goal = None
        goals_snapshot = None
        try:
            active_goal = self.goals.select_goal_to_work_on()
            goals_snapshot = self.goals.snapshot(limit=25)
        except Exception:
            active_goal = None
            goals_snapshot = {"active_goal_id": None, "goals": []}

        plan = None
        current_step = None

        # Optional planning: create or load a plan for complex goals.
        if active_goal:
            plan = self._load_plan(active_goal.id)

            if plan is None and self.config.planning_enabled and self._goal_seems_complex(active_goal):
                plan = self._create_plan_for_goal(active_goal, context={"goals": goals_snapshot})

            if plan is not None:
                plan, current_step = self._ensure_current_step(plan)
                self._save_plan(active_goal.id, plan)

        # Cognitive memory: read before deciding
        memory_context = {
            "working": {},
            "relevant": [],
        }

        # Relevance query derived from the agent's active goal + current plan step
        query_parts = []
        try:
            if active_goal and getattr(active_goal, "description", None):
                query_parts.append(str(active_goal.description))
            if isinstance(current_step, dict) and current_step.get("description"):
                query_parts.append(str(current_step.get("description")))
        except Exception:
            pass
        query = "\n".join([p for p in query_parts if p]).strip()

        try:
            from app.services.memory_manager import MemoryManager

            mm = MemoryManager()
            memory_context["working"] = mm.get_working_memory(self.state.agent_id)
            if query:
                raw_relevant = mm.retrieve_relevant(
                    self.state.agent_id,
                    query=query,
                    types=[mm.SEMANTIC, mm.EPISODIC, mm.LEGACY_EPISODIC],
                    limit=8,
                    candidate_limit=200,
                )

                # Make sure what we embed into the observation is JSON-serializable
                safe_relevant = []
                for rec in raw_relevant or []:
                    if not isinstance(rec, dict):
                        continue
                    safe = {}
                    for k, v in rec.items():
                        if isinstance(v, (str, int, float, bool)) or v is None:
                            safe[k] = v
                        elif isinstance(v, (list, dict)):
                            safe[k] = v
                        else:
                            safe[k] = str(v)
                    safe_relevant.append(safe)

                memory_context["relevant"] = safe_relevant
        except Exception:
            # Redis-only fallback (best-effort)
            try:
                raw_wm = self.r.get(f"agent:working_memory:{self.state.agent_id}")
                if raw_wm:
                    obj = _safe_json_loads(raw_wm)
                    if isinstance(obj, dict):
                        memory_context["working"] = obj
            except Exception:
                pass
            try:
                # Use the rolling list written by celery_worker fallback
                raw = self.r.lrange(self.memory_key, 0, 25)
                parsed = []
                for item in raw:
                    if isinstance(item, str):
                        o = _safe_json_loads(item)
                        if o is not None:
                            parsed.append(o)
                memory_context["relevant"] = parsed
            except Exception:
                pass

        return {
            "ts": time.time(),
            "messages": msgs,
            "active_goal": (active_goal.to_dict() if active_goal else None),
            "goals": goals_snapshot,
            "plan": plan,
            "current_plan_step": current_step,
            "planning_enabled": bool(self.config.planning_enabled),
            "memory": memory_context,
            "safety": self._safety_snapshot(),
        }

    # ---------------------------
    # Think
    # ---------------------------
    def think(self, observation: JsonDict) -> JsonDict:
        """Compute the next action.

        Strategy:
        - If OPENAI_API_KEY is available inside this agent container, call OpenAI locally.
        - Otherwise, offload to Celery task app.celery_worker.agent_think_step.

        The decision is expected to be a JSON dict with at least:
        - thought: str
        - action: {type: str, payload: dict}
        - sleep_seconds: number (optional)
        """

        # Role heuristic (optional) to reduce OpenAI usage and enforce specialization.
        try:
            role_decision = getattr(self, "role_agent", None).pre_decide(observation)
            if isinstance(role_decision, dict):
                return self._normalize_decision(role_decision)
        except Exception:
            pass

        if os.getenv("OPENAI_API_KEY"):
            d, err = self._think_via_openai_local(observation)
            if d is not None:
                return d

            # Fallback to Celery if local OpenAI failed
            d2, err2 = self._think_via_celery(observation)
            if d2 is not None:
                return d2

            return {
                "thought": "think failed (local OpenAI + celery)",
                "action": {"type": "sleep", "payload": {"seconds": self.config.tick_seconds}},
                "sleep_seconds": self.config.tick_seconds,
                "error": {"local": err, "celery": err2},
            }

        d, err = self._think_via_celery(observation)
        if d is not None:
            return d

        return {
            "thought": "think failed; defaulting to sleep",
            "action": {"type": "sleep", "payload": {"seconds": self.config.tick_seconds}},
            "sleep_seconds": self.config.tick_seconds,
            "error": err,
        }

    def _think_via_openai_local(self, observation: JsonDict) -> Tuple[Optional[JsonDict], Optional[str]]:
        try:
            from app.services.openai_service import OpenAIService

            prompt = self._build_decision_prompt(observation)
            openai = OpenAIService()
            resp = openai.completion(prompt, model=self.config.model, max_tokens=self.config.max_tokens)
            content = (
                resp.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            decision = _safe_json_loads(content)
            if decision is None:
                return None, f"OpenAI returned non-JSON content: {content[:200]}"

            return self._normalize_decision(decision), None
        except Exception as e:
            return None, repr(e)

    def _think_via_celery(self, observation: JsonDict) -> Tuple[Optional[JsonDict], Optional[str]]:
        try:
            # Late import to keep agent containers usable even if Celery modules aren't present.
            from app.celery_worker import agent_think_step

            async_result = agent_think_step.delay(
                self.state.agent_id,
                self.state.agent_name,
                self.state.agent_role,
                self.state.to_dict(),
                observation,
            )
            decision = async_result.get(timeout=self.config.think_timeout_seconds)
            if not isinstance(decision, dict):
                return None, f"Celery think returned non-dict: {type(decision)}"

            return self._normalize_decision(decision), None
        except Exception as e:
            return None, repr(e)

    def _build_decision_prompt(self, observation: JsonDict) -> str:
        allowed_actions = [
            {
                "type": "sleep",
                "payload": {"seconds": "number"},
            },
            {
                "type": "publish",
                "payload": {"channel": "string", "message": "json"},
            },
            {
                "type": "spawn_agent",
                "payload": {"name": "string", "role": "string", "metadata": "object"},
            },
            {
                "type": "run_coordinator_task",
                "payload": {"goal": "string", "requirements": "list", "constraints": "object"},
            },
            {
                "type": "add_goal",
                "payload": {"description": "string", "priority": "number", "parent_goal_id": "string|null"},
            },
            {
                "type": "create_subgoal",
                "payload": {"parent_goal_id": "string", "description": "string", "priority": "number"},
            },
            {
                "type": "complete_goal",
                "payload": {"goal_id": "string"},
            },
            {
                "type": "fail_goal",
                "payload": {"goal_id": "string"},
            },
            {
                "type": "plan_goal",
                "payload": {"goal_id": "string (optional; default active_goal.id)"},
            },
            {
                "type": "complete_plan_step",
                "payload": {"goal_id": "string (optional)", "step_id": "string (optional; default current step)"},
            },
            {
                "type": "fail_plan_step",
                "payload": {"goal_id": "string (optional)", "step_id": "string (optional; default current step)", "reason": "string (optional)"},
            },
            {
                "type": "send_message",
                "payload": {"recipient_agent_id": "string", "content": "string", "metadata": "object"},
            },
            {
                "type": "broadcast_message",
                "payload": {"content": "string", "metadata": "object"},
            },
            {
                "type": "delegate_task",
                "payload": {"recipient_agent_id": "string", "task": "object"},
            },
            {
                "type": "status_update",
                "payload": {"status": "string", "details": "object", "broadcast": "bool", "recipient_agent_id": "string|null"},
            },
            {
                "type": "noop",
                "payload": {},
            },
        ]

        role_instructions = ""
        try:
            role_instructions = getattr(self, "role_agent", None).role_instructions() or ""
        except Exception:
            role_instructions = ""

        return (
            "You are an autonomous agent running in a multi-agent system. "
            "You must choose ONE next action from the allowed actions and return STRICT JSON.\n\n"
            f"Agent identity: id={self.state.agent_id} name={self.state.agent_name} role={self.state.agent_role}\n\n"
            f"Current state (json): {json.dumps(self.state.to_dict())}\n\n"
            f"Observation (json): {json.dumps(observation)}\n\n"
            "IMPORTANT: Goals are owned and managed by you (the agent), not by the orchestrator. "
            "When deciding what to do, prefer working on the active_goal if present. "
            "If a plan/current_plan_step exists, prioritize progressing the current_plan_step and mark it complete when done.\n\n"
            + (role_instructions + "\n\n" if role_instructions else "")
            + f"Allowed actions (json schema-like): {json.dumps(allowed_actions)}\n\n"
            "Return JSON with keys: thought (string), action (object with type,payload), sleep_seconds (number, optional)."
        )

    def _normalize_decision(self, decision: JsonDict) -> JsonDict:
        # Ensure minimal shape
        action = decision.get("action")
        if not isinstance(action, dict):
            action = {"type": "sleep", "payload": {"seconds": self.config.tick_seconds}}

        action_type = action.get("type")
        if not isinstance(action_type, str):
            action_type = "sleep"

        payload = action.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        out: JsonDict = {
            "thought": str(decision.get("thought") or ""),
            "action": {"type": action_type, "payload": payload},
        }

        if "sleep_seconds" in decision:
            try:
                out["sleep_seconds"] = float(decision.get("sleep_seconds"))
            except Exception:
                pass

        # If action is sleep and sleep_seconds missing, derive it
        if out["action"]["type"] == "sleep" and "sleep_seconds" not in out:
            try:
                out["sleep_seconds"] = float(payload.get("seconds", self.config.tick_seconds))
            except Exception:
                out["sleep_seconds"] = self.config.tick_seconds

        return out

    # ---------------------------
    # Act
    # ---------------------------
    def act(self, decision: JsonDict) -> JsonDict:
        action = decision.get("action") or {}
        action_type = action.get("type")
        payload = action.get("payload") or {}

        if action_type == "sleep":
            # Sleep is handled by scheduling logic in run_forever
            return {"status": "scheduled", "type": "sleep", "payload": payload}

        if action_type == "publish":
            try:
                channel = str(payload.get("channel") or "")
                msg = payload.get("message")
                if not channel:
                    return {"status": "error", "error": "publish.channel missing"}
                self.r.publish(channel, json.dumps(msg))
                return {"status": "ok", "type": "publish", "channel": channel}
            except Exception as e:
                return {"status": "error", "type": "publish", "error": repr(e)}

        if action_type == "spawn_agent":
            try:
                name = str(payload.get("name") or f"agent-{int(time.time())}")
                role = str(payload.get("role") or "")
                metadata = payload.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                req = {"name": name, "role": role, "metadata": metadata}
                self.r.publish("agent.spawn.request", json.dumps(req))
                return {"status": "ok", "type": "spawn_agent", "requested": req}
            except Exception as e:
                return {"status": "error", "type": "spawn_agent", "error": repr(e)}

        if action_type == "run_coordinator_task":
            try:
                from app.celery_worker import run_coordinator_task

                goal = str(payload.get("goal") or "")
                requirements = payload.get("requirements") or []
                constraints = payload.get("constraints") or {}

                # Best-effort normalize
                if not isinstance(requirements, list):
                    requirements = [str(requirements)]
                if not isinstance(constraints, dict):
                    constraints = {"value": constraints}

                task_id = str(uuid.uuid4())
                # Use the same UUID as the Celery task id for consistency with the HTTP layer.
                run_coordinator_task.apply_async(args=(task_id, goal, requirements, constraints), task_id=task_id)
                return {"status": "ok", "type": "run_coordinator_task", "task_id": task_id}
            except Exception as e:
                return {"status": "error", "type": "run_coordinator_task", "error": repr(e)}

        if action_type == "add_goal":
            try:
                desc = str(payload.get("description") or "").strip()
                if not desc:
                    return {"status": "error", "type": "add_goal", "error": "description missing"}
                pr = int(payload.get("priority") or 0)
                parent = payload.get("parent_goal_id")
                parent_id = str(parent) if parent else None
                g = self.goals.create_goal(desc, priority=pr, parent_goal_id=parent_id)
                return {"status": "ok", "type": "add_goal", "goal_id": g.id}
            except Exception as e:
                return {"status": "error", "type": "add_goal", "error": repr(e)}

        if action_type == "create_subgoal":
            try:
                parent_goal_id = str(payload.get("parent_goal_id") or "").strip()
                desc = str(payload.get("description") or "").strip()
                if not parent_goal_id or not desc:
                    return {"status": "error", "type": "create_subgoal", "error": "parent_goal_id/description missing"}
                pr = int(payload.get("priority") or 0)
                g = self.goals.create_subgoal(parent_goal_id, desc, priority=pr)
                return {"status": "ok", "type": "create_subgoal", "goal_id": g.id, "parent_goal_id": parent_goal_id}
            except Exception as e:
                return {"status": "error", "type": "create_subgoal", "error": repr(e)}

        if action_type == "complete_goal":
            try:
                goal_id = str(payload.get("goal_id") or "").strip()
                if not goal_id:
                    return {"status": "error", "type": "complete_goal", "error": "goal_id missing"}
                self.goals.set_status(goal_id, "completed")
                return {"status": "ok", "type": "complete_goal", "goal_id": goal_id}
            except Exception as e:
                return {"status": "error", "type": "complete_goal", "error": repr(e)}

        if action_type == "fail_goal":
            try:
                goal_id = str(payload.get("goal_id") or "").strip()
                if not goal_id:
                    return {"status": "error", "type": "fail_goal", "error": "goal_id missing"}
                self.goals.set_status(goal_id, "failed")
                return {"status": "ok", "type": "fail_goal", "goal_id": goal_id}
            except Exception as e:
                return {"status": "error", "type": "fail_goal", "error": repr(e)}

        if action_type == "plan_goal":
            try:
                goal_id = str(payload.get("goal_id") or "").strip()
                if not goal_id:
                    g = self.goals.get_active_goal()
                    goal_id = g.id if g else ""
                if not goal_id:
                    return {"status": "error", "type": "plan_goal", "error": "no active goal"}

                g = self.goals.get_goal(goal_id) or self.goals.get_active_goal()
                if not g:
                    return {"status": "error", "type": "plan_goal", "error": f"goal not found: {goal_id}"}

                plan = self._create_plan_for_goal(g, context={"trigger": "explicit"})
                return {"status": "ok", "type": "plan_goal", "goal_id": goal_id, "plan": plan}
            except Exception as e:
                return {"status": "error", "type": "plan_goal", "error": repr(e)}

        if action_type in ("complete_plan_step", "fail_plan_step"):
            try:
                goal_id = str(payload.get("goal_id") or "").strip()
                if not goal_id:
                    g = self.goals.get_active_goal()
                    goal_id = g.id if g else ""
                if not goal_id:
                    return {"status": "error", "type": action_type, "error": "no active goal"}

                plan = self._load_plan(goal_id)
                if not plan:
                    return {"status": "error", "type": action_type, "error": "no plan for goal"}

                plan, current_step = self._ensure_current_step(plan)
                step_id = str(payload.get("step_id") or "").strip()
                if not step_id and current_step:
                    step_id = str(current_step.get("id") or "")
                if not step_id:
                    return {"status": "error", "type": action_type, "error": "no step_id"}

                # Update status
                new_status = "completed" if action_type == "complete_plan_step" else "failed"
                reason = str(payload.get("reason") or "").strip() if action_type == "fail_plan_step" else ""

                steps = plan.get("steps") or []
                updated = False
                for st in steps:
                    if isinstance(st, dict) and str(st.get("id") or "") == step_id:
                        st["status"] = new_status
                        if reason:
                            st["failure_reason"] = reason
                        updated = True
                        break

                if not updated:
                    return {"status": "error", "type": action_type, "error": f"step not found: {step_id}"}

                # Advance to next runnable step
                plan["steps"] = steps
                plan, next_step = self._ensure_current_step(plan)
                self._save_plan(goal_id, plan)

                # Record memory event (best-effort)
                try:
                    from app.celery_worker import agent_store_memory

                    agent_store_memory.delay(
                        self.state.agent_id,
                        f"plan.step.{new_status}",
                        {
                            "goal_id": goal_id,
                            "step_id": step_id,
                            "status": new_status,
                            "reason": reason,
                            "plan": plan,
                        },
                    )
                except Exception:
                    pass

                return {
                    "status": "ok",
                    "type": action_type,
                    "goal_id": goal_id,
                    "step_id": step_id,
                    "new_status": new_status,
                    "next_step": next_step,
                }
            except Exception as e:
                return {"status": "error", "type": action_type, "error": repr(e)}

        if action_type == "send_message":
            try:
                rid = str(payload.get("recipient_agent_id") or "").strip()
                content = str(payload.get("content") or "").strip()
                meta = payload.get("metadata")
                if not isinstance(meta, dict):
                    meta = {}
                if not rid or not content:
                    return {"status": "error", "type": "send_message", "error": "recipient_agent_id/content required"}

                msg = make_direct_message(
                    sender_agent_id=self.state.agent_id,
                    sender_agent_name=self.state.agent_name,
                    sender_role=self.state.agent_role,
                    recipient_agent_id=rid,
                    content=content,
                    metadata=meta,
                )
                ok = self.bus.send_direct(rid, msg)
                return {"status": "ok" if ok else "error", "type": "send_message", "recipient_agent_id": rid}
            except Exception as e:
                return {"status": "error", "type": "send_message", "error": repr(e)}

        if action_type == "broadcast_message":
            try:
                content = str(payload.get("content") or "").strip()
                meta = payload.get("metadata")
                if not isinstance(meta, dict):
                    meta = {}
                if not content:
                    return {"status": "error", "type": "broadcast_message", "error": "content required"}

                msg = make_broadcast_message(
                    sender_agent_id=self.state.agent_id,
                    sender_agent_name=self.state.agent_name,
                    sender_role=self.state.agent_role,
                    content=content,
                    metadata=meta,
                )
                ok = self.bus.broadcast(msg)
                return {"status": "ok" if ok else "error", "type": "broadcast_message"}
            except Exception as e:
                return {"status": "error", "type": "broadcast_message", "error": repr(e)}

        if action_type == "delegate_task":
            try:
                rid = str(payload.get("recipient_agent_id") or "").strip()
                task = payload.get("task")
                if not isinstance(task, dict):
                    return {"status": "error", "type": "delegate_task", "error": "task must be object"}
                if not rid:
                    return {"status": "error", "type": "delegate_task", "error": "recipient_agent_id required"}

                msg = make_task_delegation(
                    sender_agent_id=self.state.agent_id,
                    sender_agent_name=self.state.agent_name,
                    sender_role=self.state.agent_role,
                    recipient_agent_id=rid,
                    task=task,
                )
                ok = self.bus.send_direct(rid, msg)
                return {"status": "ok" if ok else "error", "type": "delegate_task", "recipient_agent_id": rid}
            except Exception as e:
                return {"status": "error", "type": "delegate_task", "error": repr(e)}

        if action_type == "status_update":
            try:
                status = str(payload.get("status") or "").strip()
                details = payload.get("details")
                if not isinstance(details, dict):
                    details = {}
                broadcast = bool(payload.get("broadcast", True))
                rid = payload.get("recipient_agent_id")
                rid = str(rid).strip() if rid else None
                if not status:
                    return {"status": "error", "type": "status_update", "error": "status required"}

                msg = make_status_update(
                    sender_agent_id=self.state.agent_id,
                    sender_agent_name=self.state.agent_name,
                    sender_role=self.state.agent_role,
                    status=status,
                    details=details,
                    broadcast=broadcast,
                    recipient_agent_id=rid,
                )
                ok = self.bus.send_status(msg)
                return {"status": "ok" if ok else "error", "type": "status_update", "broadcast": broadcast, "recipient_agent_id": rid}
            except Exception as e:
                return {"status": "error", "type": "status_update", "error": repr(e)}

        if action_type == "noop":
            return {"status": "ok", "type": "noop"}

        return {"status": "error", "error": f"unknown action type: {action_type}"}

    # ---------------------------
    # Reflect
    # ---------------------------
    def reflect(self, observation: JsonDict, decision: JsonDict, action_result: JsonDict) -> JsonDict:
        """Lightweight reflection.

        Requirements:
        - Compare outcome vs intended goal
        - Identify what worked/failed
        - Generate a short self-critique
        - Store reflection in episodic memory (done by store_memory)

        This reflection is designed to be cheap by default (heuristic only).
        Optional OpenAI refinement can be enabled via env config.
        """

        ts = time.time()
        action = (decision.get("action") or {}) if isinstance(decision, dict) else {}
        action_type = action.get("type")

        status = action_result.get("status")
        ok = status in ("ok", "scheduled")
        failed = status == "error"

        active_goal = observation.get("active_goal") if isinstance(observation, dict) else None
        goal_id = None
        goal_desc = None
        goal_priority = None
        if isinstance(active_goal, dict):
            goal_id = active_goal.get("id")
            goal_desc = active_goal.get("description")
            goal_priority = active_goal.get("priority")

        current_step = observation.get("current_plan_step") if isinstance(observation, dict) else None
        step_id = None
        step_desc = None
        if isinstance(current_step, dict):
            step_id = current_step.get("id")
            step_desc = current_step.get("description")

        intended = {
            "goal_id": goal_id,
            "goal_description": goal_desc,
            "plan_step_id": step_id,
            "plan_step_description": step_desc,
            "action": action,
        }

        what_worked: List[str] = []
        what_failed: List[str] = []

        if ok:
            what_worked.append(f"action {action_type} executed successfully")
        if failed:
            what_failed.append(f"action {action_type} failed")
            if action_result.get("error"):
                what_failed.append(f"error: {action_result.get('error')}")

        # Compare outcome vs intended goal (coarse)
        alignment = "unknown"
        if action_type in ("complete_goal", "complete_plan_step") and ok:
            alignment = "progress"
        elif action_type in ("fail_goal", "fail_plan_step"):
            alignment = "handled_failure"
        elif action_type in ("plan_goal", "create_subgoal", "add_goal"):
            alignment = "improve_structure"
        elif failed:
            alignment = "regression"
        else:
            alignment = "neutral"

        critique = ""
        if failed:
            critique = "I attempted an action that failed; I should reduce ambiguity and choose a smaller next step or replan."
        elif ok and alignment in ("progress", "improve_structure"):
            critique = "My action aligned with the goal; I should continue incrementally and verify outcomes."
        elif ok:
            critique = "The action completed, but I should ensure it advances the active goal and avoid busywork."
        else:
            critique = "I need to confirm whether my action meaningfully advances the goal."

        # Suggestions to influence future decisions / planning / goal handling
        suggestion: Optional[JsonDict] = None

        plan_present = bool(observation.get("plan")) if isinstance(observation, dict) else False
        planning_enabled = bool(observation.get("planning_enabled")) if isinstance(observation, dict) else False

        if failed:
            if plan_present and step_id:
                suggestion = {
                    "type": "fail_plan_step",
                    "payload": {"goal_id": goal_id, "step_id": step_id, "reason": "action_failed"},
                }
            elif planning_enabled and goal_id:
                suggestion = {"type": "plan_goal", "payload": {"goal_id": goal_id}}
            elif goal_id and goal_desc:
                suggestion = {
                    "type": "create_subgoal",
                    "payload": {
                        "parent_goal_id": goal_id,
                        "description": "Diagnose failure and unblock progress",
                        "priority": int(goal_priority or 0) + int(self.config.reflection_subgoal_priority_boost),
                    },
                }

                # Optional: auto-create the subgoal (off by default)
                if (
                    self.config.reflection_auto_subgoal_on_failure
                    and suggestion
                    and suggestion.get("type") == "create_subgoal"
                    and isinstance(suggestion.get("payload"), dict)
                ):
                    try:
                        p = suggestion["payload"]
                        self.goals.create_subgoal(
                            parent_goal_id=str(p.get("parent_goal_id")),
                            description=str(p.get("description")),
                            priority=int(p.get("priority") or 0),
                        )
                        what_worked.append("created a subgoal to address the failure")
                    except Exception:
                        pass

        # Optional OpenAI refinement (very small) to make critique more useful.
        if self._should_use_openai_reflection(failed=failed):
            try:
                refined = self._reflect_via_openai_light(intended=intended, outcome=action_result)
                if refined:
                    critique = str(refined.get("critique") or critique)
                    ww = refined.get("what_worked")
                    wf = refined.get("what_failed")
                    if isinstance(ww, list) and ww:
                        what_worked = [str(x) for x in ww][:5]
                    if isinstance(wf, list) and wf:
                        what_failed = [str(x) for x in wf][:5]
                    # Allow model to suggest a follow-up action (still optional)
                    if isinstance(refined.get("suggestion"), dict) and not suggestion:
                        suggestion = refined.get("suggestion")
            except Exception:
                pass

        return {
            "ts": ts,
            "intended": intended,
            "outcome": action_result,
            "alignment": alignment,
            "what_worked": what_worked[:5],
            "what_failed": what_failed[:5],
            "critique": critique[:350],
            "suggestion": suggestion,
        }

    def _should_use_openai_reflection(self, failed: bool) -> bool:
        if not self.config.reflection_use_openai:
            return False

        if self.config.reflection_openai_on_failure_only and not failed:
            return False

        try:
            every_n = int(self.config.reflection_openai_every_n or 0)
            if every_n > 0:
                # state.iteration is incremented after store_memory; treat next tick as iteration+1
                return ((int(self.state.iteration) + 1) % every_n) == 0
        except Exception:
            pass

        return True

    def _reflect_via_openai_light(self, intended: JsonDict, outcome: JsonDict) -> Optional[JsonDict]:
        """Very small OpenAI call to refine critique.

        This is intentionally minimal and only used when explicitly enabled.
        """
        if not os.getenv("OPENAI_API_KEY"):
            return None

        from app.services.openai_service import OpenAIService

        prompt = (
            "You are a concise self-critique module for an autonomous agent. "
            "Return STRICT JSON only. Keep it short.\n\n"
            f"Intended (json): {json.dumps(intended)}\n\n"
            f"Outcome (json): {json.dumps(outcome)}\n\n"
            "Return JSON shape:\n"
            "{\n"
            "  \"critique\": \"...\",\n"
            "  \"what_worked\": [\"...\"],\n"
            "  \"what_failed\": [\"...\"],\n"
            "  \"suggestion\": {\"type\": \"...\", \"payload\": {...}}\n"
            "}\n"
        )

        openai = OpenAIService()
        resp = openai.completion(prompt, model=self.config.model, max_tokens=int(self.config.reflection_max_tokens))
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        obj = _safe_json_loads(content)
        if not isinstance(obj, dict):
            return None
        return obj

    # ---------------------------
    # Store Memory
    # ---------------------------
    def store_memory(
        self,
        observation: JsonDict,
        decision: JsonDict,
        action_result: JsonDict,
        reflection: JsonDict,
    ):
        record = {
            "ts": time.time(),
            "iteration": self.state.iteration,
            "observation": observation,
            "decision": decision,
            "action_result": action_result,
            "reflection": reflection,
        }

        # Prefer Celery for persistence if available
        if _truthy(os.getenv("AGENT_LOOP_USE_CELERY_MEMORY", "true")):
            try:
                from app.celery_worker import agent_store_memory

                # Legacy episodic record (kept for backward compatibility)
                agent_store_memory.delay(self.state.agent_id, "agent_loop_tick", record)

                # Explicit cognitive memory categories (additive)
                agent_store_memory.delay(self.state.agent_id, "episodic", {
                    "ts": record.get("ts"),
                    "iteration": record.get("iteration"),
                    "action": record.get("decision") or {},
                    "outcome": record.get("action_result") or {},
                    "reflection": record.get("reflection") or {},
                    "context": (record.get("observation") or {}),
                })

                # Working memory is current context (best-effort)
                obs = record.get("observation") or {}
                agent_store_memory.delay(self.state.agent_id, "working", {
                    "ts": record.get("ts"),
                    "iteration": record.get("iteration"),
                    "active_goal": obs.get("active_goal"),
                    "current_plan_step": obs.get("current_plan_step"),
                    "planning_enabled": obs.get("planning_enabled"),
                    "last_thought": (record.get("decision") or {}).get("thought"),
                    "last_reflection": record.get("reflection") or {},
                    "last_critique": (record.get("reflection") or {}).get("critique"),
                    "last_suggestion": (record.get("reflection") or {}).get("suggestion"),
                })

                return
            except Exception:
                # fall through to local/redis
                pass

        # Try local MemoryManager (may or may not be available in slim agent images)
        try:
            from app.services.memory_manager import MemoryManager

            MemoryManager().save(self.state.agent_id, "agent_loop_tick", record)
            return
        except Exception:
            pass

        # Redis fallback: keep a rolling list
        try:
            self.r.lpush(self.memory_key, json.dumps(record))
            self.r.ltrim(self.memory_key, 0, 199)
        except Exception:
            pass

    # ---------------------------
    # State persistence
    # ---------------------------
    def _load_state(self) -> Optional[AgentState]:
        try:
            raw = self.r.get(self.state_key)
            if not raw:
                return None
            d = _safe_json_loads(raw)
            if d is None:
                return None
            return AgentState.from_dict(d)
        except Exception:
            return None

    def _save_state(self):
        try:
            self.r.set(self.state_key, json.dumps(self.state.to_dict()))
        except Exception:
            pass

    # ---------------------------
    # Safety / environment awareness
    # ---------------------------
    def _safety_snapshot(self) -> JsonDict:
        return {
            "enabled": bool(self.config.safety_enabled),
            "iteration": int(self.state.iteration),
            "max_iterations": int(self.config.loop_max_iterations or 0),
            "consecutive_failures": int(self.state.consecutive_failures),
            "max_consecutive_failures": int(self.config.max_consecutive_failures),
            "consecutive_no_progress": int(self.state.consecutive_no_progress),
            "max_consecutive_no_progress": int(self.config.max_consecutive_no_progress),
            "kill_switch_env": self.config.kill_switch_env,
            "health_ttl_seconds": int(self.config.health_ttl_seconds),
        }

    def _should_stop_now(self) -> bool:
        # safety disabled => never stop via safety (still allow env hard kill switch)
        if self._kill_switch_enabled():
            self._best_effort_status("kill_switch", {"reason": "kill switch enabled"})
            return True

        if not self.config.safety_enabled:
            return False

        try:
            if int(self.config.loop_max_iterations or 0) > 0 and int(self.state.iteration) >= int(self.config.loop_max_iterations):
                self._best_effort_status(
                    "loop_stopped",
                    {"reason": "max iterations reached", "iteration": int(self.state.iteration), "max": int(self.config.loop_max_iterations)},
                )
                return True
        except Exception:
            pass

        return False

    def _kill_switch_enabled(self) -> bool:
        # Env kill switch
        try:
            if _truthy(os.getenv(self.config.kill_switch_env, "false")):
                return True
        except Exception:
            pass

        # Redis kill key(s)
        try:
            v = self.r.get(f"{self.config.kill_key_prefix}{self.state.agent_id}")
            if v and _truthy(str(v)):
                return True
        except Exception:
            pass

        try:
            if self.state.agent_name:
                v = self.r.get(f"{self.config.kill_key_prefix}{self.state.agent_name}")
                if v and _truthy(str(v)):
                    return True
        except Exception:
            pass

        return False

    def _update_health(self, phase: str, extra: Optional[JsonDict] = None):
        # Health should never block execution.
        try:
            ttl = int(self.config.health_ttl_seconds or 0)
            if ttl <= 0:
                return

            key = f"{self.config.health_key_prefix}{self.state.agent_id}"
            payload: JsonDict = {
                "ts": time.time(),
                "phase": phase,
                "agent_id": self.state.agent_id,
                "agent_name": self.state.agent_name,
                "agent_role": self.state.agent_role,
                "run_id": self.state.run_id,
                "iteration": int(self.state.iteration),
                "consecutive_failures": int(self.state.consecutive_failures),
                "consecutive_no_progress": int(self.state.consecutive_no_progress),
            }
            if extra and isinstance(extra, dict):
                payload.update(extra)

            self.r.setex(key, ttl, json.dumps(payload))
        except Exception:
            pass

    def _is_progress(self, reflection: JsonDict) -> bool:
        try:
            alignment = str(reflection.get("alignment") or "").strip().lower()
            return alignment in {"progress", "improve_structure", "handled_failure"}
        except Exception:
            return False

    def _safety_after_step(self, observation: JsonDict, decision: JsonDict, action_result: JsonDict, reflection: JsonDict):
        if not self.config.safety_enabled:
            return

        status = str(action_result.get("status") or "")
        failed = status == "error"

        # Failure counters
        if failed:
            self.state.consecutive_failures = int(self.state.consecutive_failures) + 1
        else:
            self.state.consecutive_failures = 0

        # Progress counters
        if self._is_progress(reflection):
            self.state.consecutive_no_progress = 0
            self.state.last_progress_at = time.time()
        else:
            self.state.consecutive_no_progress = int(self.state.consecutive_no_progress) + 1

        # Escalation/delegation (cooldown-protected)
        try:
            now = time.time()
            cooldown = float(self.config.escalation_cooldown_seconds or 0)
            if cooldown < 0:
                cooldown = 0
            if (now - float(self.state.last_escalation_at or 0.0)) < cooldown:
                return

            too_many_failures = int(self.state.consecutive_failures) >= int(self.config.max_consecutive_failures)
            stuck = int(self.state.consecutive_no_progress) >= int(self.config.max_consecutive_no_progress)

            if not (too_many_failures or stuck):
                return

            self.state.last_escalation_at = now

            details = {
                "reason": "consecutive_failures" if too_many_failures else "stuck_no_progress",
                "consecutive_failures": int(self.state.consecutive_failures),
                "consecutive_no_progress": int(self.state.consecutive_no_progress),
                "last_action": (decision.get("action") or {}),
                "last_reflection": reflection,
                "active_goal": (observation.get("active_goal") if isinstance(observation, dict) else None),
                "current_plan_step": (observation.get("current_plan_step") if isinstance(observation, dict) else None),
            }

            # Broadcast a status update
            if self.config.escalate_broadcast:
                self._best_effort_status("agent_escalation", details)

            # Directly notify a planner/critic if available
            try:
                planner = getattr(self, "role_agent", None).find_first_agent_by_role("planner")
            except Exception:
                planner = None
            try:
                critic = getattr(self, "role_agent", None).find_first_agent_by_role("critic")
            except Exception:
                critic = None

            if isinstance(planner, dict) and planner.get("agent_id"):
                rid = str(planner.get("agent_id"))
                try:
                    self.bus.send_direct(rid, make_direct_message(
                        sender_agent_id=self.state.agent_id,
                        sender_agent_name=self.state.agent_name,
                        sender_role=self.state.agent_role,
                        recipient_agent_id=rid,
                        content=f"Escalation: {details['reason']}",
                        metadata=details,
                    ))
                except Exception:
                    pass

                # Optional delegation: ask planner to unblock/replan
                if self.config.escalate_delegate:
                    try:
                        task = {
                            "description": "Unblock progress (replan / delegate / propose subgoals)",
                            "context": details,
                            "priority": 1,
                        }
                        self.bus.send_direct(rid, make_task_delegation(
                            sender_agent_id=self.state.agent_id,
                            sender_agent_name=self.state.agent_name,
                            sender_role=self.state.agent_role,
                            recipient_agent_id=rid,
                            task=task,
                        ))
                    except Exception:
                        pass

            if isinstance(critic, dict) and critic.get("agent_id"):
                rid = str(critic.get("agent_id"))
                try:
                    self.bus.send_direct(rid, make_direct_message(
                        sender_agent_id=self.state.agent_id,
                        sender_agent_name=self.state.agent_name,
                        sender_role=self.state.agent_role,
                        recipient_agent_id=rid,
                        content=f"Escalation: {details['reason']} (please critique)",
                        metadata=details,
                    ))
                except Exception:
                    pass

        except Exception:
            # Safety should never crash the loop.
            pass

    def _compute_backoff_seconds(self) -> float:
        try:
            n = int(self.state.consecutive_failures)
            if n <= 0:
                return 0.0
            base = float(self.config.failure_backoff_base_seconds)
            mx = float(self.config.failure_backoff_max_seconds)
            jitter = float(self.config.failure_backoff_jitter_seconds)

            if base < 0:
                base = 0.0
            if mx < 0:
                mx = 0.0
            if jitter < 0:
                jitter = 0.0

            # exponential backoff
            backoff = base * (2 ** max(n - 1, 0))
            if mx > 0:
                backoff = min(backoff, mx)

            # deterministic jitter (based on run_id + iteration) to avoid heavy RNG
            if jitter > 0:
                try:
                    h = abs(hash(f"{self.state.run_id}:{self.state.iteration}")) % 1000
                    j = (h / 1000.0) * jitter
                    backoff += j
                except Exception:
                    pass

            return float(backoff)
        except Exception:
            return 0.0

    def _apply_failure_backoff(self, sleep_s: float) -> float:
        if not self.config.safety_enabled:
            return sleep_s
        try:
            backoff = self._compute_backoff_seconds()
            if backoff <= 0:
                return sleep_s
            return max(float(sleep_s), float(backoff))
        except Exception:
            return sleep_s

    def _best_effort_status(self, status: str, details: Optional[JsonDict] = None):
        try:
            msg = make_status_update(
                sender_agent_id=self.state.agent_id,
                sender_agent_name=self.state.agent_name,
                sender_role=self.state.agent_role,
                status=status,
                details=details or {},
                broadcast=True,
                recipient_agent_id=None,
            )
            self.bus.send_status(msg)
        except Exception:
            pass

    # ---------------------------
    # Planning + plan persistence
    # ---------------------------
    def _plan_key(self, goal_id: str) -> str:
        return f"{self.config.plan_key_prefix}{self.state.agent_id}:{goal_id}"

    def _load_plan(self, goal_id: str) -> Optional[JsonDict]:
        try:
            raw = self.r.get(self._plan_key(goal_id))
            if not raw:
                return None
            d = _safe_json_loads(raw)
            if d is None or not isinstance(d, dict):
                return None
            return self._normalize_plan(d)
        except Exception:
            return None

    def _save_plan(self, goal_id: str, plan: JsonDict):
        try:
            self.r.set(self._plan_key(goal_id), json.dumps(plan))
        except Exception:
            pass

    def _normalize_plan(self, plan: JsonDict) -> JsonDict:
        plan = dict(plan or {})
        plan.setdefault("steps", [])
        plan.setdefault("current_step_index", 0)
        if not isinstance(plan.get("steps"), list):
            plan["steps"] = []
        try:
            plan["current_step_index"] = int(plan.get("current_step_index") or 0)
        except Exception:
            plan["current_step_index"] = 0

        # Normalize steps
        out_steps = []
        for i, s in enumerate(plan["steps"]):
            if not isinstance(s, dict):
                continue
            sd = dict(s)
            sd.setdefault("id", sd.get("step_id") or str(uuid.uuid4()))
            sd.setdefault("order", int(sd.get("order") or (i + 1)))
            sd.setdefault("description", "")
            sd.setdefault("status", "pending")
            out_steps.append(sd)
        out_steps.sort(key=lambda st: int(st.get("order") or 0))
        plan["steps"] = out_steps

        # Keep index in bounds
        if plan["current_step_index"] < 0:
            plan["current_step_index"] = 0
        if plan["current_step_index"] >= len(plan["steps"]):
            plan["current_step_index"] = 0 if plan["steps"] else 0

        return plan

    def _ensure_current_step(self, plan: JsonDict) -> Tuple[JsonDict, Optional[JsonDict]]:
        plan = self._normalize_plan(plan)
        steps: List[JsonDict] = plan.get("steps") or []
        if not steps:
            return plan, None

        # Prefer current index if it's runnable
        idx = int(plan.get("current_step_index") or 0)
        if 0 <= idx < len(steps) and steps[idx].get("status") in ("pending", "active"):
            if steps[idx].get("status") == "pending":
                steps[idx]["status"] = "active"
            plan["steps"] = steps
            return plan, steps[idx]

        # Otherwise find first runnable
        for i, st in enumerate(steps):
            if st.get("status") in ("pending", "active"):
                plan["current_step_index"] = i
                if st.get("status") == "pending":
                    st["status"] = "active"
                plan["steps"] = steps
                return plan, st

        # No runnable steps
        return plan, None

    def _goal_seems_complex(self, goal) -> bool:
        # goal is a goals.goal.Goal
        desc = getattr(goal, "description", "") or ""
        return len(desc.strip()) >= int(self.config.planning_min_description_chars)

    def _create_plan_for_goal(self, goal, context: Optional[JsonDict] = None) -> Optional[JsonDict]:
        goal_id = getattr(goal, "id", "")
        goal_desc = getattr(goal, "description", "")
        if not goal_id:
            return None

        plan_dict: Optional[JsonDict] = None
        err: Optional[str] = None

        # Prefer local OpenAI planning if key is present inside the agent container.
        if os.getenv("OPENAI_API_KEY"):
            try:
                planner = Planner(model=self.config.planning_model, max_tokens=self.config.planning_max_tokens)
                plan_obj, err = planner.plan_with_error(goal_id=goal_id, goal_description=goal_desc, context=context or {})
                plan_dict = plan_obj.to_dict()
            except Exception as e:
                err = repr(e)

        # Fallback: ask celery-worker to plan
        if plan_dict is None:
            try:
                from app.celery_worker import agent_plan_goal

                async_result = agent_plan_goal.delay(goal_id, goal_desc, context or {})
                plan_dict = async_result.get(timeout=self.config.think_timeout_seconds)
                if not isinstance(plan_dict, dict):
                    plan_dict = None
            except Exception as e:
                err = err or repr(e)

        if plan_dict is None:
            # Last-resort minimal plan
            plan_dict = {
                "goal_id": goal_id,
                "goal_description": goal_desc,
                "steps": [{"id": str(uuid.uuid4()), "order": 1, "description": f"Work on goal: {goal_desc}", "status": "pending"}],
                "current_step_index": 0,
                "error": err,
            }

        plan_dict = self._normalize_plan(plan_dict)
        self._save_plan(goal_id, plan_dict)

        # Store the plan in memory (best-effort)
        try:
            from app.celery_worker import agent_store_memory

            agent_store_memory.delay(self.state.agent_id, "plan.created", {"goal_id": goal_id, "plan": plan_dict})
        except Exception:
            pass

        return plan_dict


def main():
    AgentLoop.from_env().run_forever()


if __name__ == "__main__":
    main()
