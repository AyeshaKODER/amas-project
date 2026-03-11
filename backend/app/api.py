from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from app.services.agent_spawner import AgentSpawner
from app.services.registry import AgentRegistry
from app.services.workflow import CoordinatorWorkflow
from app.celery_worker import celery as celery_app
from celery.exceptions import TimeoutError as CeleryTimeoutError

router = APIRouter()

class AgentCreateRequest(BaseModel):
    name: str
    role: Optional[str] = None
    metadata: Optional[dict] = Field(default_factory=dict)

class SpawnRequest(BaseModel):
    name: str
    role: Optional[str] = None
    image: Optional[str] = None
    metadata: Optional[dict] = Field(default_factory=dict)

class RunRequest(BaseModel):
    goal: str
    requirements: List[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)

spawner = AgentSpawner()
registry = AgentRegistry()
workflow = CoordinatorWorkflow(spawner=spawner, registry=registry)

def _serialize_agent(agent):
    """
    Convert agent to a JSON-serializable dict whether agent is:
    - an object with to_dict()
    - a pydantic model with dict()
    - already a dict
    - otherwise try vars() / __dict__ / str()
    """  
    if hasattr(agent, "to_dict") and callable(getattr(agent, "to_dict")):
        return agent.to_dict()
    if hasattr(agent, "dict") and callable(getattr(agent, "dict")):
        return agent.dict()
    if isinstance(agent, dict):
        return agent
    try:
        return vars(agent)
    except Exception:
        return getattr(agent, "__dict__", str(agent))
    
 

@router.post('/agents/create')
async def create_agent(req: AgentCreateRequest):
    agent = registry.get_or_create(req.name, role=req.role, metadata=req.metadata)
    agent_data = _serialize_agent(agent)
    return {'agent': agent_data}

@router.post('/agents/spawn')
async def spawn_agent(req: SpawnRequest):
    container_info = spawner.spawn_agent_container(name=req.name, role=req.role, image=req.image, metadata=req.metadata)
    if not container_info:
        raise HTTPException(status_code=500, detail='Failed to spawn agent')
    # register
    registry.register(container_info.get('agent_id'), name=req.name, role=req.role, metadata=req.metadata, container_id=container_info.get('container_id'))
    return {'spawned': container_info}

@router.post('/run')
async def run_workflow(req: RunRequest, background: BackgroundTasks):
    # Enqueue and return immediately.
    task_id = workflow.start(req.goal, req.requirements, req.constraints)
    return {'task_id': task_id}


@router.post('/ask')
async def ask(req: RunRequest, timeout_seconds: int = Query(180, ge=1, le=600)):
    """Run the coordinator workflow and wait (blocking) for a result.

    Behavior:
    - Enqueues the coordinator workflow (Celery) and then long-polls for completion.
    - Returns 200 with the task result if it completes within timeout_seconds.
    - Returns 202 if still pending.

    Notes:
    - The coordinator task can be configured to skip OpenAI by setting constraints.use_openai=false
      in the request body (handled inside app/celery_worker.py).
    """
    import time as _time

    task_id = workflow.start(req.goal, req.requirements, req.constraints)
    async_result = celery_app.AsyncResult(task_id)

    deadline = _time.time() + float(timeout_seconds)

    # Long-poll in short intervals so we don't block on a single long .get() call.
    while _time.time() < deadline:
        try:
            if async_result.ready():
                result = async_result.get(timeout=1)
                return {'task_id': task_id, 'result': result}
        except CeleryTimeoutError:
            # not ready yet
            pass
        except Exception as e:
            raise HTTPException(status_code=500, detail={'task_id': task_id, 'status': 'error', 'error': repr(e)})

        _time.sleep(0.5)

    # Still running
    raise HTTPException(status_code=202, detail={'task_id': task_id, 'status': 'pending'})


@router.get('/tasks/{task_id}')
async def get_task(task_id: str):
    """Fetch Celery task status/result for a previously enqueued workflow."""
    res = celery_app.AsyncResult(task_id)

    payload: Dict[str, Any] = {
        'task_id': task_id,
        'state': res.state,
        'ready': bool(res.ready()),
    }

    if res.ready():
        try:
            payload['successful'] = bool(res.successful())
        except Exception:
            payload['successful'] = None

        if payload.get('successful'):
            payload['result'] = res.result
        else:
            payload['error'] = str(res.result)

    return payload

@router.get('/agents')
async def list_agents():
    # If registry.list_agents returns non-serializable objects, let registry handle serialization,
    # otherwise ensure we return JSON-serializable structures.
    agents = registry.list_agents()
    # If list contains objects, serialize each defensively:
    if isinstance(agents, list) and agents and not isinstance(agents[0], dict):
        agents = [_serialize_agent(a) for a in agents]
    return {'agents': agents}

@router.post('/shutdown/{agent_id}')
async def shutdown_agent(agent_id: str):
    ok = spawner.shutdown_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail='Agent not found or failed to shutdown')
    registry.unregister(agent_id)
    return {'status': 'shutdown', 'agent_id': agent_id}


