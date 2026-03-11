# AMAS Backend (Autonomous Multi-Agent System)

This repository is a production-ready scaffold for an Autonomous Multi-Agent System (AMAS).
It provides:
- FastAPI backend with endpoints for agent management and task orchestration
- AgentSpawner and Docker Orchestrator using the Docker SDK
- Pre-defined agent templates that run as separate Docker containers
- PostgreSQL persistence and Redis for pub/sub & Celery
- OpenAI and Search service integrations (config-driven)
- Celery pipelines for async execution

**Important:** Fill `.env` with real credentials (OpenAI key, search API keys) before running.

See `/run_instructions.md` for quick start and examples.

Postman exports are in `/postman/`:
- `postman/amas.postman_collection.json`
- `postman/amas.postman_environment.json`
