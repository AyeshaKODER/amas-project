# Run instructions (local development)

1. Copy `.env.example` to `.env` and fill in secrets (OpenAI key, database URL, etc.).
2. Build and start all services:
   ```bash
   docker compose up --build
   ```
3. The API will be available at `http://localhost:8000` (FastAPI + Uvicorn).
4. Use the endpoints:
   - `GET /`
   - `POST /agents/create`
   - `POST /agents/spawn`
   - `GET /agents`
   - `POST /shutdown/{agent_id}`
   - `POST /run` (enqueue workflow)
   - `GET /tasks/{task_id}` (poll workflow status/result)
   - `POST /ask` (enqueue + wait for result; supports `constraints.use_openai`)
5. Logs: `docker compose logs -f api` and `docker compose logs -f celery-worker`

Notes:
- Agent containers use the agent template at `/agents/template`.
- To test OpenAI & Search, provide keys in `.env`.
