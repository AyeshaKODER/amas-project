import uuid
from typing import List, Dict, Any
from app.services.agent_spawner import AgentSpawner
from app.services.registry import AgentRegistry
from app.services.openai_service import OpenAIService
from app.services.search_service import SearchService
from app.services.memory_manager import MemoryManager
from app.celery_worker import run_coordinator_task

class CoordinatorWorkflow:
    def __init__(self, spawner: AgentSpawner, registry: AgentRegistry):
        self.spawner = spawner
        self.registry = registry
        self.openai = OpenAIService()
        self.search = SearchService()
        self.memory = MemoryManager()
    def start(self, goal: str, requirements: List[str], constraints: Dict[str,Any]):
        task_id = str(uuid.uuid4())
        # Offload to Celery using the same UUID as the Celery task id so callers
        # can later query AsyncResult(task_id).
        run_coordinator_task.apply_async(args=(task_id, goal, requirements, constraints), task_id=task_id)
        return task_id


