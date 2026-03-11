# How to extend the AMAS backend

- Add new agent images in `agents/<your_agent>/` with a Dockerfile and runtime.
- Use AgentSpawner.spawn_agent_container(name, role, image) to programmatically create agents.
- Agents can publish requests to Redis on `agent.spawn.request` with payload:
  {'name': 'MyAgent', 'role':'Specialized', 'metadata': {...}}
- Orchestrator listens and will spawn containers, then register them into Postgres.
- Use MemoryManager to persist and query agent memories.
- CoordinatorWorkflow.offload() dispatches heavy orchestration to Celery.
