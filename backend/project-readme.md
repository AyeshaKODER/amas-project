AMAS Backend (amas-final-backend-v3)

1\. Project Overview

This repository is a backend scaffold for an Autonomous Multi‑Agent
System (AMAS) built around:

• A FastAPI service providing HTTP endpoints to: ◦ register agents, ◦
spawn agent containers, ◦ start an asynchronous coordinator workflow. •
A Celery worker that executes background tasks (workflow execution +
agent cognition/memory tasks). • Redis used as: ◦ Celery broker/result
backend (via CELERY_BROKER_URL / CELERY_RESULT_BACKEND, defaulting to
REDIS_URL), ◦ pub/sub backplane for orchestrator↔agents, ◦
state/health/inbox storage for autonomous agent loops. • A long-running
orchestrator process that listens to Redis pub/sub and spawns agent
containers using the Docker daemon socket. • An agent template image
(agents/template) used as the default runtime for spawned agents; it can
optionally run an internal autonomous loop.

Level of autonomy (no exaggeration): • The system supports an opt-in
autonomous agent loop (observe → think → act → reflect → store memory)
inside agent containers. • It is not fully autonomous end-to-end by
default: agent spawning and workflow execution are triggered externally
(via FastAPI or via Redis pub/sub messages). There is no built-in "run
everything until done" external API with status/result retrieval.

2\. Architecture Overview

2.1 Docker Compose services (from docker-compose.yml)

• api ◦ Built from Dockerfile.api ◦ Command: uvicorn app.main:app
\--host 0.0.0.0 \--port 8000 \--loop asyncio ◦ Exposes: host port 8000 →
container port 8000 ◦ Mounts Docker socket:
/var/run/docker.sock:/var/run/docker.sock:ro (override file may mount
without :ro) ◦ Depends on: postgres, redis • celery-worker ◦ Built from
Dockerfile.celery ◦ Command: celery -A app.celery_worker.celery worker
\--loglevel=info -Q coordinator -n worker.%h ◦ Consumes queue:
coordinator ◦ Depends on: redis, postgres • orchestrator ◦ Built from
Dockerfile.orchestrator ◦ Command: python -u
/app/app/services/orchestrator_service.py ◦ Mounts Docker socket:
/var/run/docker.sock:/var/run/docker.sock:ro (override file may mount
without :ro) ◦ Depends on: redis, postgres • agent_template ◦ Built from
agents/template/Dockerfile ◦ Image:
\${AGENT_DEFAULT_IMAGE:-amas_agent_template:latest} ◦ Runs once and
exits (restart: \"no\") ◦ Purpose: ensures the default agent image
exists so the spawner can create agent containers • postgres ◦ Image:
postgres:15 ◦ Exposes: host port 5432 → container port 5432 ◦ Persists
data in volume: pgdata • redis ◦ Image: redis:7 ◦ Exposes: host port
6379 → container port 6379 ◦ Persists data in volume: redisdata

2.2 How the system starts (from zero)

1\. docker compose up \--build builds: ◦ API image ◦ Celery worker image
◦ Orchestrator image ◦ Agent template image 2. postgres and redis start
and pass health checks. 3. api starts FastAPI (Uvicorn) and serves HTTP
on port 8000. 4. celery-worker starts and consumes tasks from the
coordinator queue. 5. orchestrator starts and subscribes to Redis
channel agent.spawn.request.

2.3 Orchestrator responsibilities (from
app/services/orchestrator_service.py)

• Subscribes to Redis pub/sub channel: agent.spawn.request • For each
message: ◦ parses JSON payload {name, role, metadata} ◦ spawns an agent
container via AgentSpawner.spawn_agent_container(\...) ◦ registers the
agent using AgentRegistry.register(\...) ◦ publishes a response on Redis
channel: agent.spawn.response with agent_id and container_id • Logs via
print(\...), including: ◦ Orchestrator started, listening for
agent.spawn.request ◦ Spawn request received \<name\> ◦ Error handling
spawn request \<error\>

2.4 Agent containers and lifecycle

Spawning implementation: app/services/agent_spawner.py

• Each spawn creates: ◦ agent_id = UUID ◦ Docker container name:
agent\_\<first8(agent_id)\> • Default image used if not specified: ◦
AGENT_DEFAULT_IMAGE (default: amas_agent_template:latest) • Environment
passed into agent containers includes: ◦ AGENT_ID, AGENT_NAME,
AGENT_ROLE, REDIS_URL ◦ pass-through keys when present: OPENAI_API_KEY,
OPENAI_MODEL, OPENAI_MAX_TOKENS, SEARCH_API_PROVIDER, SERPAPI_API_KEY,
CELERY_BROKER_URL, CELERY_RESULT_BACKEND, DATABASE_URL • Network
behavior: ◦ attempts to detect the current container's Docker network
(prefers \<compose\>\_default) ◦ can be overridden by
DOCKER_AGENT_NETWORK or AGENT_NETWORK

Autonomy toggle at spawn time: • If AGENT_AUTONOMOUS_LOOP_DEFAULT=true
(env) or spawn metadata includes autonomous_loop / autonomous truthy: ◦
spawner sets AGENT_AUTONOMOUS_LOOP=true inside the agent container • If
spawn metadata includes loop_tick_seconds: ◦ spawner sets
AGENT_LOOP_TICK_SECONDS=\<value\> inside agent container • Spawn
metadata can also inject additional environment variables via
metadata.env (validated keys only)

Shutdown implementation: AgentSpawner.shutdown_agent(agent_id) •
Searches containers by name filter: agent\_\<first8(agent_id)\> • Stops
and removes the container(s)

2.5 Agent runtime behavior (default template)

Agent template image: agents/template/Dockerfile Agent template runtime:
agents/template/agent_runtime.py

On startup, the template runtime: • publishes a heartbeat to Redis
channel agent.heartbeat every 10 seconds • starts an HTTP server in the
container on 0.0.0.0:8080 with: ◦ GET /health → returns JSON {agent_id,
name} • prints: Agent \<AGENT_NAME\> running with id \<AGENT_ID\> • runs
indefinitely

If AGENT_AUTONOMOUS_LOOP=true, it additionally runs the autonomous loop
implemented in agent_runtime/agent_loop.py.

2.6 Celery worker, tasks, and queue routing

Celery app: app/celery_worker.py

Broker/backends: • Broker: CELERY_BROKER_URL (fallback to REDIS_URL,
default redis://redis:6379/0) • Result backend: CELERY_RESULT_BACKEND
(fallback to broker)

Task routing (explicit): • app.celery_worker.run_coordinator_task →
queue coordinator • app.celery_worker.agent_think_step → queue
coordinator • app.celery_worker.agent_store_memory → queue coordinator •
app.celery_worker.agent_plan_goal → queue coordinator

Coordinator workflow trigger path: • FastAPI POST /run →
CoordinatorWorkflow.start(\...) → enqueues
run_coordinator_task.delay(\...)

Coordinator task behavior (run_coordinator_task): 1. Loads agent
registry (AgentRegistry) 2. If no agents exist, spawns a hard-coded list
of "core" agents via AgentSpawner and registers them: ◦ ResearchAgent,
WriterAgent, ReviewerAgent, CoordinatorAgent, MemoryAgent, SearchAgent,
AnalyzerAgent 3. Runs SearchService.search(goal, num=5) 4. Calls OpenAI
via OpenAIService.completion(\...) 5. Writes memory via
MemoryManager.save(\...) 6. Publishes a completion event (best-effort)
to Redis pub/sub: ◦ channel: workflow.completed

2.7 How OpenAI fits into execution

OpenAI wrapper: app/services/openai_service.py

• Reads OPENAI_API_KEY • Uses OpenAI SDK: ◦ prefers new client
(OpenAI(\...).chat.completions.create) when available ◦ falls back to
legacy openai.ChatCompletion.create • Used by: ◦ coordinator task
(run_coordinator_task) ◦ agent cognition task (agent_think_step) ◦
planning task (agent_plan_goal) ◦ agent runtime loop (when OpenAI is
available inside the agent container)

3\. Tech Stack

From requirements.txt and runtime usage:

• Python 3.11 (Docker images) • FastAPI + Uvicorn (HTTP API) • Celery
(background tasks) • Redis (broker/result backend + pubsub + agent
state) • PostgreSQL (persistence) • SQLAlchemy + Alembic (ORM/models +
migrations tooling) • docker (docker-py) (spawning agent containers) •
openai (LLM calls) • httpx (search integration) • requests / urllib3
(pinned for docker-py compatibility)

4\. Folder Structure

• app/ ◦ main.py --- FastAPI app initialization ◦ api.py --- FastAPI
routes ◦ celery_worker.py --- Celery app + task definitions ◦ db/ ▪
session.py --- SQLAlchemy engine/session (reads DATABASE_URL) ▪
models.py --- SQLAlchemy models
(Agent/Task/TaskStep/Message/Tool/AgentTool) ◦ services/ ▪
agent_spawner.py --- Docker-based agent container creation/shutdown ▪
orchestrator_service.py --- Redis listener that spawns agents on
agent.spawn.request ▪ registry.py --- AgentRegistry (DB-backed when
possible, else in-memory fallback) ▪ memory_manager.py --- memory
persistence + retrieval helpers (DB + Redis best-effort) ▪
openai_service.py --- OpenAI wrapper ▪ search_service.py --- search
integration ▪ workflow.py --- coordinator workflow wrapper that enqueues
Celery ◦ utils/ ▪ docker_client.py --- hardened Docker client creator
(clears docker context env vars) • agents/ ◦ template/ --- default agent
image/runtime used for spawned agents ◦ research_agent/ --- example
agent image/runtime (not used by default spawns unless explicitly
built/used) • agent_runtime/ ◦ agent_loop.py --- autonomous agent loop
implementation ◦ roles/ --- role specializations (planner, executor,
critic) + role loader • communication/ ◦ Redis-backed message bus and
message protocol definitions (direct inbox + broadcast channel) • goals/
◦ Redis-backed goal manager used by the autonomous agent loop •
planning/ ◦ LLM-based planner (Planner) and plan structures •
services_from_image/ ◦ Legacy copies of service modules (not the
canonical implementation path for the running services) • alembic/,
alembic.ini ◦ Alembic migration scripts/config (not automatically
applied during container startup)

5\. Environment Variables

Only environment variables actually read by the Python code and/or
interpolated by docker-compose.yml are listed below.

5.1 Infrastructure

• DATABASE_URL ◦ Used in: app/db/session.py, alembic/env.py, env.py,
session_check.py ◦ Purpose: DB connection string for SQLAlchemy/Alembic
• REDIS_URL ◦ Used in: app/celery_worker.py,
app/services/orchestrator_service.py, app/services/agent_spawner.py,
agent_runtime/agent_loop.py, agent runtimes ◦ Purpose: Redis connection
string for broker/pubsub/state • CELERY_BROKER_URL ◦ Used in:
app/celery_worker.py ◦ Purpose: Celery broker URL (defaults to
REDIS_URL) • CELERY_RESULT_BACKEND ◦ Used in: app/celery_worker.py ◦
Purpose: Celery result backend URL (defaults to broker)

5.2 OpenAI

• OPENAI_API_KEY ◦ Used in: app/services/openai_service.py,
app/celery_worker.py, agent_runtime/agent_loop.py, planning/planner.py ◦
Purpose: enables OpenAI API calls • OPENAI_MODEL ◦ Used in:
app/celery_worker.py, agent_runtime/agent_loop.py ◦ Purpose: model
override for some OpenAI calls • OPENAI_MAX_TOKENS ◦ Used in:
app/celery_worker.py, agent_runtime/agent_loop.py ◦ Purpose: token limit
override for some OpenAI calls

5.3 Search

• SEARCH_API_PROVIDER ◦ Used in: app/services/search_service.py ◦
Purpose: search backend selection (serpapi or fallback) •
SERPAPI_API_KEY ◦ Used in: app/services/search_service.py ◦ Purpose:
SerpAPI key when provider is serpapi

5.4 Docker / agent spawning

• AGENT_DEFAULT_IMAGE ◦ Used in: app/services/agent_spawner.py,
app/celery_worker.py ◦ Purpose: default image used when spawning agents
• DOCKER_BASE_IMAGE ◦ Used in: app/services/agent_spawner.py ◦ Purpose:
defined default base image string (declared; not used for building
images in code) • DOCKER_AGENT_NETWORK / AGENT_NETWORK ◦ Used in:
app/services/agent_spawner.py ◦ Purpose: override docker network for
agent containers • HOSTNAME ◦ Used in: app/services/agent_spawner.py ◦
Purpose: container ID used for auto-detecting compose network via Docker
API • DOCKER_CONFIG ◦ Used in: app/utils/docker_client.py ◦ Purpose:
forced to /tmp to avoid host docker context/config interference •
DOCKER_HOST, DOCKER_CONTEXT, DOCKER_TLS_VERIFY, DOCKER_CERT_PATH,
DOCKER_API_VERSION ◦ Used in: app/utils/docker_client.py ◦ Purpose:
cleared/unset before importing docker SDK to avoid unsupported
schemes/context issues

5.5 Agent identity/runtime toggles

• AGENT_ID ◦ Used in: agents/template/agent_runtime.py,
agents/research_agent/run.py, agent_runtime/agent_loop.py • AGENT_NAME ◦
Used in: agents/template/agent_runtime.py, agents/research_agent/run.py,
agent_runtime/agent_loop.py • AGENT_ROLE ◦ Used in:
agent_runtime/agent_loop.py • AGENT_AUTONOMOUS_LOOP ◦ Used in:
agents/template/agent_runtime.py ◦ Purpose: enables the autonomous agent
loop inside the agent container • AGENT_AUTONOMOUS_LOOP_DEFAULT ◦ Used
in: app/services/agent_spawner.py ◦ Purpose: default spawner-side toggle
that sets AGENT_AUTONOMOUS_LOOP=true in spawned agents •
AGENT_LOOP_TICK_SECONDS ◦ Used in: agent_runtime/agent_loop.py •
AGENT_LOOP_THINK_TIMEOUT_SECONDS ◦ Used in: agent_runtime/agent_loop.py
• AGENT_LOOP_MAX_ITERATIONS ◦ Used in: agent_runtime/agent_loop.py •
AGENT_HEALTH_TTL_SECONDS ◦ Used in: agent_runtime/agent_loop.py •
AGENT_LOOP_USE_CELERY_MEMORY ◦ Used in: agent_runtime/agent_loop.py ◦
Purpose: controls whether the agent loop uses the Celery task
agent_store_memory (defaults to truthy) • AGENT_KILL_SWITCH ◦ Used in:
agent_runtime/agent_loop.py ◦ Purpose: env kill switch that stops the
autonomous loop if truthy

5.6 Agent planning / reflection / safety tuning (agent loop)

Used in: agent_runtime/agent_loop.py

• Planning: ◦ AGENT_ENABLE_PLANNING ◦ AGENT_PLANNING_MODEL ◦
AGENT_PLANNING_MAX_TOKENS ◦ AGENT_PLANNING_MIN_DESCRIPTION_CHARS •
Reflection: ◦ AGENT_REFLECTION_USE_OPENAI ◦
AGENT_REFLECTION_OPENAI_ON_FAILURE_ONLY ◦
AGENT_REFLECTION_OPENAI_EVERY_N ◦ AGENT_REFLECTION_MAX_TOKENS ◦
AGENT_REFLECTION_AUTO_SUBGOAL_ON_FAILURE ◦
AGENT_REFLECTION_SUBGOAL_PRIORITY_BOOST • Safety/backoff/escalation: ◦
AGENT_SAFETY_ENABLED ◦ AGENT_MAX_CONSECUTIVE_FAILURES ◦
AGENT_MAX_CONSECUTIVE_NO_PROGRESS ◦ AGENT_FAILURE_BACKOFF_BASE_SECONDS ◦
AGENT_FAILURE_BACKOFF_MAX_SECONDS ◦ AGENT_FAILURE_BACKOFF_JITTER_SECONDS
◦ AGENT_ESCALATION_COOLDOWN_SECONDS ◦ AGENT_ESCALATE_BROADCAST ◦
AGENT_ESCALATE_DELEGATE

5.7 Role selection

Used in: agent_runtime/roles/factory.py

• AGENT_ROLE_CLASS --- fully qualified Python class path override •
AGENT_ROLE_IMPL --- selects built-in role (planner, executor, critic)

5.8 Memory tuning (Celery-side)

Used in: app/celery_worker.py

• WORKING_MEMORY_TTL_SECONDS • MEMORY_SUMMARIZE_EVERY_N •
MEMORY_SUMMARY_EPISODE_WINDOW

5.9 Example agent only

Used in: agents/research_agent/run.py

• AUTO_SPAWN

6\. Running the Project From Scratch

6.1 Prerequisites

• Docker Engine • Docker Compose (supports docker compose) • Docker
socket access inside containers (compose mounts /var/run/docker.sock
into api and orchestrator)

6.2 Clone the repository

Use your actual repo URL:

git clone \<repo-url\> cd \<repo-directory\>

6.3 Create .env

1\. Copy the example file:

cp .env.example .env

2\. Edit .env and set at least: • OPENAI_API_KEY (required for real
OpenAI behavior) • DATABASE_URL and Postgres credentials (defaults are
provided in .env.example) • Search configuration: ◦ default is
SEARCH_API_PROVIDER=serpapi, which requires SERPAPI_API_KEY ◦ to avoid
SerpAPI requirement, set SEARCH_API_PROVIDER to a non-serpapi value to
use the DuckDuckGo fallback path in code

6.4 Build and start services

From the repository root:

docker compose up \--build

6.5 Verify services are running

docker compose ps

Expected behavior: • api, celery-worker, orchestrator, postgres, redis
are running • agent_template may exit after building the image (it is
configured to not restart)

6.6 Verify the API is responding

The FastAPI root endpoint is:

• GET http://localhost:8000/ (put this URL in Postman or curl)

Expected JSON response shape:

{\"status\":\"ok\",\"service\":\"AMAS Backend\"}

6.7 Inspect logs

API:

docker compose logs -f api

Celery worker:

docker compose logs -f celery-worker

Orchestrator:

docker compose logs -f orchestrator

Redis / Postgres:

docker compose logs -f redis docker compose logs -f postgres

7\. Testing the Project End-to-End

7.1 API testing (FastAPI)

Base URL:

• http://localhost:8000 (no auth is implemented in the API code)

Endpoints (from app/api.py and app/main.py):

1\) GET / • Purpose: basic health/status response

2\) POST /agents/create • Purpose: create/register an agent entry in the
registry (does not spawn a container)

Example request body:

{ \"name\": \"Planner1\", \"role\": \"planner\", \"metadata\": {} }

3\) POST /agents/spawn • Purpose: spawn an agent Docker container using
Docker SDK from the API container and register it

Example request body:

{ \"name\": \"AgentA\", \"role\": \"planner\", \"image\":
\"amas_agent_template:latest\", \"metadata\": {} }

4\) GET /agents • Purpose: list agents from the registry backend (DB if
available, else in-memory)

5\) POST /shutdown/{agent_id} • Purpose: stop + remove the agent
container agent\_\<first8(agent_id)\> and unregister it

6\) POST /run • Purpose: enqueue coordinator workflow execution via
Celery; returns task_id

Example request body:

{ \"goal\": \"Summarize findings about X\", \"requirements\": \[\"Return
a short summary\"\], \"constraints\": {} }

Important note (from code): there is no FastAPI endpoint to query
workflow result/status by task_id.

7.2 Agent spawning testing

1\. Call POST /agents/spawn 2. Confirm a new Docker container exists:

docker ps

3\. Confirm agent logs:

docker logs -f \<agent_container_id_or_name\>

Template agent startup log includes:

• Agent \<AGENT_NAME\> running with id \<AGENT_ID\>

7.3 Coordinator workflow testing (Celery)

1\. Call POST /run 2. Watch Celery worker logs:

docker compose logs -f celery-worker

3\. Observe Redis pub/sub completion event (the coordinator publishes to
workflow.completed best-effort):

docker compose exec redis redis-cli SUBSCRIBE workflow.completed

7.4 Autonomous agent behavior testing (opt-in)

Autonomy is enabled when the spawned agent container has
AGENT_AUTONOMOUS_LOOP=true.

7.4.1 Enable autonomy at spawn time (via request metadata)

app/services/agent_spawner.py enables AGENT_AUTONOMOUS_LOOP when: •
AGENT_AUTONOMOUS_LOOP_DEFAULT=true (env), or • spawn metadata contains
autonomous_loop / autonomous truthy

Example POST /agents/spawn body:

{ \"name\": \"AutonomousPlanner\", \"role\": \"planner\", \"image\":
\"amas_agent_template:latest\", \"metadata\": { \"autonomous_loop\":
true } }

7.4.2 Confirm autonomous loop is running (logs)

The autonomous loop prints:

• \[agent_loop\] starting: id=\... name=\... role=\... run_id=\...

7.4.3 Confirm agent backplane behavior via Redis

Subscribe to key channels used in code:

docker compose exec redis redis-cli SUBSCRIBE agent.spawn.request
agent.spawn.response agent.heartbeat workflow.completed agent:broadcast

What these indicate (by code): • agent.heartbeat: template agents
publish heartbeat JSON periodically • agent.spawn.request: orchestrator
listens here to spawn new containers • agent.spawn.response:
orchestrator publishes spawn results here • agent:broadcast: MessageBus
broadcast channel for agent-to-agent messages • workflow.completed:
coordinator completion notification

7.4.4 Inspect agent state/health/inbox keys

The autonomous loop uses Redis keys including (from
agent_runtime/agent_loop.py and communication/message_bus.py):

• agent:state:\<agent_id\> • agent:health:\<agent_id\> •
agent:kill:\<agent_id\> (kill key) • agent:inbox:\<agent_id\> (direct
message inbox) • agent:plan:\<agent_id\>:\<goal_id\> (stored plans) •
agent:goals:\<agent_id\> (goal manager store) •
agent:working_memory:\<agent_id\> (working memory)

Example inspection commands:

docker compose exec redis redis-cli KEYS \"agent:state:\*\" docker
compose exec redis redis-cli GET agent:state:\<agent_id\>

8\. Observability & Debugging

8.1 Containers and logs

List containers:

docker compose ps docker ps

Tail logs:

docker compose logs -f api docker compose logs -f celery-worker docker
compose logs -f orchestrator

8.2 Redis inspection (pub/sub, keys)

Subscribe to channels:

docker compose exec redis redis-cli SUBSCRIBE agent.spawn.request
agent.spawn.response agent.heartbeat workflow.completed agent:broadcast

Inspect keys used by agents:

docker compose exec redis redis-cli KEYS \"agent:\*\"

8.3 Celery debugging

• Confirm worker is running and consuming coordinator queue:

docker compose ps docker compose logs -f celery-worker

• Broker/backend configuration comes from: ◦ CELERY_BROKER_URL /
CELERY_RESULT_BACKEND (fall back to REDIS_URL)

8.4 OpenAI debugging

OpenAI calls fail if OPENAI_API_KEY is missing: • OpenAIService prints:
Warning: OPENAI_API_KEY not set. OpenAI calls will fail until
configured.

Check: • docker compose logs -f celery-worker (task failures/errors) •
agent container logs (autonomous loop think/plan/reflection paths)

9\. Limitations (Honest)

• No workflow result/status API: ◦ POST /run returns a task_id, but
there is no FastAPI endpoint to query status/result by task_id. •
Orchestrator is internal-only: ◦ it listens to Redis agent.spawn.request
and is not exposed via HTTP. • Agent HTTP server is not exposed to the
host by default: ◦ template agent runs 0.0.0.0:8080 with GET /health
inside the agent container, but compose does not publish that port. •
Autonomy is opt-in: ◦ autonomous loop requires
AGENT_AUTONOMOUS_LOOP=true (directly or via spawner defaults/metadata).
• Search defaults require configuration: ◦ default
SEARCH_API_PROVIDER=serpapi requires SERPAPI_API_KEY or searches will
error. • Migrations are not automatically applied: ◦ Alembic exists, but
services do not run migrations during startup. • Several DB models are
defined but not exposed via API: ◦ Task, TaskStep, Message, Tool,
AgentTool are present in app/db/models.py, but the FastAPI API does not
provide CRUD for them. • Logging/observability is primarily via
print(\...) and container logs (no structured logging pipeline in code).

10\. Future Improvements

• Add HTTP endpoints for: ◦ workflow status/result retrieval by task_id
◦ agent runtime health/state inspection (proxying Redis keys like
agent:health:\* and agent:state:\*) ◦ a first-class "send message to
agent" endpoint (writing to agent:inbox:\<agent_id\> or broadcast
channel) • Improve observability: ◦ structured logging across api,
celery-worker, orchestrator, and agent containers ◦ persist workflow
lifecycle events (not only pub/sub) • Make migrations operational: ◦ add
a dedicated migration job/container or run migrations on startup •
Harden agent runtime execution: ◦ clearer separation between "template
runtime idle" and "autonomous loop" ◦ explicit port publishing option
for agent /health if desired • Add tests: ◦ unit tests for FastAPI
routes/services ◦ integration tests that run compose and validate /run
and /agents/spawn behaviors
