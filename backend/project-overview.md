AMAS Backend (amas-final-backend-v3)

1\. Project Overview

This repository implements a backend scaffold for an Autonomous
Multi‑Agent System (AMAS) using:

• A FastAPI HTTP API to create/register agents, spawn agent containers,
and start an asynchronous "coordinator workflow". • A Celery worker for
background execution (workflow execution + agent cognition/memory
tasks). • A Redis broker/backplane used for: ◦ Celery broker/result
backend (by default) ◦ pub/sub channels that connect the orchestrator
and agents ◦ agent runtime inbox/state/health keys • A long-running
orchestrator service that listens on Redis pub/sub and spawns agent
containers via the Docker API. • Agent containers built from
agents/template/ which can optionally run an internal autonomous loop
(observe → think → act → reflect → store memory).

This is not a fully automatic system end-to-end by default: agents are
spawned explicitly (API or Redis message), and "autonomy" is opt-in via
environment variables/metadata.

2\. Architecture Overview

Docker Compose services (as defined in docker-compose.yml)

• api ◦ Runs FastAPI via Uvicorn (uvicorn app.main:app \--host 0.0.0.0
\--port 8000) ◦ Exposes port 8000 on the host. ◦ Depends on postgres and
redis. ◦ Mounts /var/run/docker.sock to allow the API to spawn
containers directly (via Docker SDK). • celery-worker ◦ Runs Celery
worker: ▪ celery -A app.celery_worker.celery worker \--loglevel=info -Q
coordinator -n worker.%h ◦ Consumes the coordinator queue. ◦ Depends on
redis and postgres. • orchestrator ◦ Runs a Python process:
/app/app/services/orchestrator_service.py ◦ Subscribes to Redis channel
agent.spawn.request. ◦ On spawn requests, it uses the Docker SDK to
start an agent container and then registers it using AgentRegistry. ◦
Mounts /var/run/docker.sock. • agent_template ◦ Builds the agent
template image from agents/template/Dockerfile. ◦ Image name defaults to
amas_agent_template:latest unless AGENT_DEFAULT_IMAGE overrides it. ◦
Runs once and exits (restart is \"no\"). • postgres ◦ Postgres 15 ◦
Exposes port 5432 on the host. ◦ Uses a named volume pgdata. • redis ◦
Redis 7 ◦ Exposes port 6379 on the host. ◦ Uses a named volume
redisdata.

How the system starts from zero

1\. docker compose up \--build builds images (API, Celery worker,
orchestrator, agent template). 2. postgres and redis start and become
healthy. 3. api starts FastAPI on port 8000. 4. celery-worker starts and
listens on queue coordinator. 5. orchestrator starts and listens on
Redis pub/sub channel agent.spawn.request. 6. Agents can then be: ◦
spawned via the API (POST /agents/spawn) directly by the API container,
or ◦ spawned by the orchestrator when something publishes to
agent.spawn.request.

Agent container lifecycle

• Agent containers are created by
AgentSpawner.spawn_agent_container(\...). • Each spawn generates a UUID
agent_id and starts a container named agent\_\<first8(agent_id)\>. • By
default, spawned agents use the image AGENT_DEFAULT_IMAGE (default
amas_agent_template:latest). • The spawner attempts to attach agents to
the same Docker network as the spawner container (auto-detected), unless
overridden by: ◦ DOCKER_AGENT_NETWORK or AGENT_NETWORK

Agent runtime behavior (inside agents/template)

The template agent runtime (agents/template/agent_runtime.py) always: •
publishes a heartbeat message to Redis channel agent.heartbeat every 10
seconds • starts a minimal HTTP server in the agent container on port
8080 with: ◦ GET /health → returns JSON with {agent_id, name} • idles
indefinitely

If AGENT_AUTONOMOUS_LOOP=true is set inside the agent container
environment, it additionally runs the autonomous loop implemented in
agent_runtime/agent_loop.py.

Celery task flow

• POST /run triggers CoordinatorWorkflow.start(\...), which enqueues: ◦
app.celery_worker.run_coordinator_task (routed to queue coordinator)

The coordinator task: 1. reads/creates core agents (spawns a hard-coded
list if none exist) 2. calls the search integration
(SearchService.search) 3. calls OpenAI (OpenAIService.completion) and
stores the result 4. stores memory (MemoryManager.save) 5. publishes
completion event to Redis channel workflow.completed

Autonomous agents can also enqueue: • app.celery_worker.agent_think_step
(decision step) • app.celery_worker.agent_store_memory (persistence +
working/episodic/semantic memory behaviors) •
app.celery_worker.agent_plan_goal (LLM planning)

How OpenAI is used

• OpenAI calls go through app/services/openai_service.py
(OpenAIService). • It reads OPENAI_API_KEY and uses the OpenAI Python
SDK. • The autonomous agent loop uses OpenAI in multiple optional
places: ◦ decision-making ("think") if available in the agent container
◦ planning ("plan") via planning/Planner ◦ reflection (only if enabled)

Memory, planning, autonomy (what is actually implemented)

• Memory persistence ◦ Implemented in app/services/memory_manager.py. ◦
Stores records in a memories table via SQLAlchemy Core. ◦ Maintains
"working memory" in Redis key agent:working_memory:\<agent_id\>
(best-effort). ◦ Includes basic relevance retrieval (lexical overlap
scoring). ◦ Includes optional episodic summarization into semantic
memory (best-effort; uses OpenAI). • Planning ◦ Implemented in
planning/planner.py and integrated into agent_runtime/agent_loop.py. ◦
Planning is optional and enabled via env (AGENT_ENABLE_PLANNING=true). ◦
Plans are stored in Redis under key agent:plan:\<agent_id\>:\<goal_id\>.
• Autonomy ◦ Implemented as an opt-in autonomous loop in
agent_runtime/agent_loop.py. ◦ Agents can: ▪ request spawning new agents
by publishing to agent.spawn.request ▪ publish/broadcast/direct-message
other agents via Redis ▪ create goals/subgoals and mark
completion/failure ▪ plan goals and advance plan steps ◦ There is no
external API to "observe agent decisions" directly; observability is via
logs and Redis keys/channels.

3\. Tech Stack

• Python 3.11 (Docker base images) • FastAPI + Uvicorn (HTTP API) •
Celery 5.3.1 (async background execution) • Redis 7 (Celery
broker/result backend + pubsub + agent state) • PostgreSQL 15
(persistence; registry uses SQLAlchemy create_all at runtime) •
SQLAlchemy 2.x + Alembic (DB models and migrations tooling; migrations
are not automatically executed by services) • docker (docker-py) 6.1.3
(spawn/stop agent containers) • openai 1.5.0 (LLM calls) • httpx (search
integration HTTP calls)

4\. Folder Structure

• app/ ◦ main.py --- FastAPI app entrypoint ◦ api.py --- HTTP routes ◦
celery_worker.py --- Celery app + tasks (run_coordinator_task,
agent_think_step, agent_store_memory, agent_plan_goal) ◦ db/ ---
SQLAlchemy session + models ◦ services/ ▪ agent_spawner.py --- spawns
agent containers via Docker SDK ▪ orchestrator_service.py --- Redis
listener that spawns agents from agent.spawn.request ▪ registry.py ---
agent registry (Postgres-backed with in-memory fallback) ▪
memory_manager.py --- Postgres/Redis memory persistence and retrieval ▪
openai_service.py --- OpenAI wrapper ▪ search_service.py --- SerpAPI (or
fallback provider) search integration ▪ workflow.py --- coordinator
workflow that enqueues Celery work ◦ utils/docker_client.py --- hardened
Docker client creation • agents/ ◦ template/ --- Dockerfile + runtime
used for spawned agents ◦ research_agent/ --- example agent container
(not used by the main spawner flow unless you explicitly build/run it) •
agent_runtime/ ◦ agent_loop.py --- autonomous agent loop implementation
◦ roles/ --- role specializations: planner/executor/critic (heuristics +
prompt instructions) • communication/ ◦ Redis-based messaging primitives
(direct inbox + broadcast pubsub) • goals/ ◦ goal data model and
Redis-backed goal manager used by the agent loop • planning/ ◦ LLM-based
planner and plan types • alembic/, alembic.ini ◦ Alembic configuration
and migration files (not run automatically by containers) •
docker-compose.yml, Dockerfile.\* ◦ container definitions

5\. Environment Variables

This section lists only env vars that the code references (Python code
and/or Docker plumbing), with where they are used.

Core infrastructure • DATABASE_URL ◦ Purpose: SQLAlchemy database
connection string. ◦ Used in: app/db/session.py, alembic/env.py, env.py,
session_check.py. • REDIS_URL ◦ Purpose: Redis connection string. ◦ Used
in: app/celery_worker.py (fallback broker),
app/services/orchestrator_service.py, app/services/agent_spawner.py
(passed into agents), agent_runtime/agent_loop.py, agent runtimes. •
CELERY_BROKER_URL ◦ Purpose: Celery broker connection string. ◦ Used in:
app/celery_worker.py. • CELERY_RESULT_BACKEND ◦ Purpose: Celery result
backend connection string. ◦ Used in: app/celery_worker.py.

OpenAI • OPENAI_API_KEY ◦ Purpose: enables OpenAI API calls. ◦ Used in:
app/services/openai_service.py, app/celery_worker.py,
agent_runtime/agent_loop.py, planning/planner.py. • OPENAI_MODEL ◦
Purpose: default OpenAI model name used by some tasks/agent loop. ◦ Used
in: app/celery_worker.py, agent_runtime/agent_loop.py. •
OPENAI_MAX_TOKENS ◦ Purpose: token limit for some OpenAI calls. ◦ Used
in: app/celery_worker.py, agent_runtime/agent_loop.py.

Search • SEARCH_API_PROVIDER ◦ Purpose: selects search provider logic. ◦
Used in: app/services/search_service.py. • SERPAPI_API_KEY ◦ Purpose:
API key for SerpAPI when SEARCH_API_PROVIDER=serpapi. ◦ Used in:
app/services/search_service.py.

Docker / agent spawning • AGENT_DEFAULT_IMAGE ◦ Purpose: default Docker
image used when spawning agents. ◦ Used in:
app/services/agent_spawner.py, app/celery_worker.py (when spawning "core
agents"). • DOCKER_BASE_IMAGE ◦ Purpose: default base image string
(declared in code; not used for actual build logic in the spawner). ◦
Used in: app/services/agent_spawner.py. • DOCKER_AGENT_NETWORK /
AGENT_NETWORK ◦ Purpose: overrides auto-detected Docker network for
agent containers. ◦ Used in: app/services/agent_spawner.py. • HOSTNAME ◦
Purpose: used to inspect the current container for network
auto-detection. ◦ Used in: app/services/agent_spawner.py. • DOCKER_HOST,
DOCKER_CONTEXT, DOCKER_TLS_VERIFY, DOCKER_CERT_PATH, DOCKER_API_VERSION
◦ Purpose: these can affect docker-py; the code explicitly clears them
before creating a Docker client. ◦ Used in: app/utils/docker_client.py
(clears/unsets them). • DOCKER_CONFIG ◦ Purpose: docker client config
dir isolation. ◦ Used in: app/utils/docker_client.py (forces
DOCKER_CONFIG=/tmp).

Agent container identity/runtime • AGENT_ID ◦ Purpose: agent UUID
identity inside the agent container. ◦ Used in:
agents/template/agent_runtime.py, agents/research_agent/run.py,
agent_runtime/agent_loop.py. • AGENT_NAME ◦ Purpose: agent display name
inside the agent container. ◦ Used in: agents/template/agent_runtime.py,
agents/research_agent/run.py, agent_runtime/agent_loop.py. • AGENT_ROLE
◦ Purpose: agent role string (used for role specialization). ◦ Used in:
agent_runtime/agent_loop.py. • AGENT_AUTONOMOUS_LOOP ◦ Purpose: enables
autonomous loop inside the template runtime. ◦ Used in:
agents/template/agent_runtime.py. • AGENT_AUTONOMOUS_LOOP_DEFAULT ◦
Purpose: default toggle applied by the spawner (can also be enabled via
spawn metadata). ◦ Used in: app/services/agent_spawner.py. •
AGENT_LOOP_TICK_SECONDS ◦ Purpose: agent loop tick interval. ◦ Used in:
agent_runtime/agent_loop.py. • AGENT_LOOP_THINK_TIMEOUT_SECONDS ◦
Purpose: timeout waiting for Celery "think" result. ◦ Used in:
agent_runtime/agent_loop.py. • AGENT_LOOP_MAX_ITERATIONS ◦ Purpose: stop
after N iterations (0 = unlimited). ◦ Used in:
agent_runtime/agent_loop.py. • AGENT_HEALTH_TTL_SECONDS ◦ Purpose: TTL
for agent health key updates in Redis. ◦ Used in:
agent_runtime/agent_loop.py. • AGENT_KILL_SWITCH ◦ Purpose: kill switch
env var that stops the loop if truthy. ◦ Used in:
agent_runtime/agent_loop.py (via configurable kill_switch_env default).

Agent planning configuration • AGENT_ENABLE_PLANNING ◦ Purpose: enables
planning for complex goals. ◦ Used in: agent_runtime/agent_loop.py. •
AGENT_PLANNING_MODEL ◦ Purpose: OpenAI model used for planning. ◦ Used
in: agent_runtime/agent_loop.py. • AGENT_PLANNING_MAX_TOKENS ◦ Purpose:
planning token limit. ◦ Used in: agent_runtime/agent_loop.py. •
AGENT_PLANNING_MIN_DESCRIPTION_CHARS ◦ Purpose: minimum goal description
length before auto-planning triggers. ◦ Used in:
agent_runtime/agent_loop.py.

Agent reflection configuration • AGENT_REFLECTION_USE_OPENAI •
AGENT_REFLECTION_OPENAI_ON_FAILURE_ONLY •
AGENT_REFLECTION_OPENAI_EVERY_N • AGENT_REFLECTION_MAX_TOKENS •
AGENT_REFLECTION_AUTO_SUBGOAL_ON_FAILURE •
AGENT_REFLECTION_SUBGOAL_PRIORITY_BOOST ◦ Purpose: optional reflection
behavior tuning. ◦ Used in: agent_runtime/agent_loop.py.

Agent safety/backoff configuration • AGENT_SAFETY_ENABLED •
AGENT_MAX_CONSECUTIVE_FAILURES • AGENT_MAX_CONSECUTIVE_NO_PROGRESS •
AGENT_FAILURE_BACKOFF_BASE_SECONDS • AGENT_FAILURE_BACKOFF_MAX_SECONDS •
AGENT_FAILURE_BACKOFF_JITTER_SECONDS • AGENT_ESCALATION_COOLDOWN_SECONDS
• AGENT_ESCALATE_BROADCAST • AGENT_ESCALATE_DELEGATE ◦ Purpose: safety
counters, escalation, and backoff configuration. ◦ Used in:
agent_runtime/agent_loop.py.

Role loading (agent specialization) • AGENT_ROLE_CLASS ◦ Purpose: import
path override for a role class. ◦ Used in:
agent_runtime/roles/factory.py. • AGENT_ROLE_IMPL ◦ Purpose: selects
built-in role: planner \| executor \| critic. ◦ Used in:
agent_runtime/roles/factory.py.

Memory tuning (Celery memory task) • WORKING_MEMORY_TTL_SECONDS ◦
Purpose: TTL for working memory key in Redis. ◦ Used in:
app/celery_worker.py (agent_store_memory). • MEMORY_SUMMARIZE_EVERY_N •
MEMORY_SUMMARY_EPISODE_WINDOW ◦ Purpose: episodic summarization
cadence/window (best-effort). ◦ Used in: app/celery_worker.py.

Example agent only • AUTO_SPAWN ◦ Purpose: causes
agents/research_agent/run.py to publish spawn requests periodically. ◦
Used in: agents/research_agent/run.py.

6\. Running the Project From Scratch (Step-by-step)

6.1 Prerequisites

• Docker Engine + Docker Compose plugin (supports docker compose) •
Ability for containers to access the Docker daemon socket: ◦
docker-compose.yml mounts /var/run/docker.sock into api and
orchestrator.

6.2 Get the code

Clone the repository (example; use your actual remote):

• Git: ◦ git clone \<repo-url\> ◦ cd amas-final-backend-v3 (or your
local directory name)

6.3 Create .env

1\. Copy .env.example to .env. 2. Edit .env and set at minimum: ◦
POSTGRES\_\* and DATABASE_URL (already present in .env.example) ◦
OPENAI_API_KEY (recommended for real LLM behavior) ◦ search
configuration (see below)

Important search note: • SearchService defaults to
SEARCH_API_PROVIDER=serpapi. • If you keep serpapi, you must set
SERPAPI_API_KEY. • If you do not have a SerpAPI key, set
SEARCH_API_PROVIDER to any value other than serpapi to use the
DuckDuckGo fallback.

6.4 Build and start all services

From the repo root:

• Build + run: ◦ docker compose up \--build

This starts: • api on host port 8000 • postgres on host port 5432 •
redis on host port 6379 • celery-worker (no port) • orchestrator (no
port) • agent_template (builds image once and exits)

6.5 Verify containers are running

• Check status: ◦ docker compose ps

Expected: • api, postgres, redis, celery-worker, orchestrator should be
running. • agent_template may show as "exited" after successfully
building the image.

6.6 Check logs for successful startup

• API: ◦ docker compose logs -f api • Celery worker: ◦ docker compose
logs -f celery-worker • Orchestrator: ◦ docker compose logs -f
orchestrator • Postgres + Redis: ◦ docker compose logs -f postgres ◦
docker compose logs -f redis

7\. Testing the Project End-to-End (VERY IMPORTANT)

7.1 API Testing Using Postman

Base URL (when running compose locally): • http://localhost:8000

No authentication is implemented in the API code.

7.1.1 GET / (root)

• Method: GET • URL: http://localhost:8000/ • Headers: none required

Example success response:

{ \"status\": \"ok\", \"service\": \"AMAS Backend\" }

What it does: • Simple service indicator defined in app/main.py.

7.1.2 POST /agents/create (register agent in registry)

• Method: POST • URL: http://localhost:8000/agents/create • Headers: ◦
Content-Type: application/json

Example request body:

{ \"name\": \"Planner1\", \"role\": \"planner\", \"metadata\": {} }

Example success response (shape):

{ \"agent\": { \"agent_id\": \"\<uuid\>\", \"name\": \"Planner1\",
\"role\": \"planner\", \"metadata\": {}, \"container_id\": \"\",
\"created_at\": \"\<timestamp or datetime\>\" } }

What it triggers: • Calls AgentRegistry.get_or_create(\...). • This does
not start a Docker container; it only registers the agent in the
registry backend (DB if available; otherwise in-memory).

7.1.3 POST /agents/spawn (spawn an agent Docker container)

• Method: POST • URL: http://localhost:8000/agents/spawn • Headers: ◦
Content-Type: application/json

Example request body (use default template image):

{ \"name\": \"AgentA\", \"role\": \"planner\", \"image\":
\"amas_agent_template:latest\", \"metadata\": {} }

Example success response (shape):

{ \"spawned\": { \"agent_id\": \"\<uuid\>\", \"container_id\":
\"\<docker-container-id\>\", \"status\": \"started\" } }

What it triggers: • AgentSpawner.spawn_agent_container(\...) is called
directly by the API service. • On success, the API registers the agent
in the registry using registry.register(\...).

Notes: • Autonomy is not enabled unless explicitly configured. See
"Verifying Autonomous Behavior".

7.1.4 GET /agents (list registered agents)

• Method: GET • URL: http://localhost:8000/agents • Headers: none
required

Example success response (shape):

{ \"agents\": \[ { \"agent_id\": \"\<uuid\>\", \"name\": \"AgentA\",
\"role\": \"planner\", \"metadata\": {}, \"container_id\":
\"\<docker-container-id\>\", \"created_at\": \"\<timestamp or
datetime\>\" } \] }

What it triggers: • AgentRegistry.list_agents().

7.1.5 POST /run (start coordinator workflow via Celery)

• Method: POST • URL: http://localhost:8000/run • Headers: ◦
Content-Type: application/json

Example request body:

{ \"goal\": \"Summarize the latest company news for ACME\",
\"requirements\": \[\"Return a short summary\"\], \"constraints\":
{\"tone\": \"neutral\"} }

Example success response:

{ \"task_id\": \"\<uuid\>\" }

What it triggers: • Enqueues app.celery_worker.run_coordinator_task via
Celery (run_coordinator_task.delay(\...)). • There is no API endpoint
implemented to fetch task status/result by task_id.

How to observe completion: • Subscribe to Redis channel
workflow.completed (see section 7.4 and 8).

7.1.6 POST /shutdown/{agent_id} (stop and remove agent container)

• Method: POST • URL: http://localhost:8000/shutdown/\<agent_id\> •
Headers: none required

Example success response:

{ \"status\": \"shutdown\", \"agent_id\": \"\<agent_id\>\" }

What it triggers: • Stops and removes the Docker container matching name
agent\_\<first8(agent_id)\>. • Unregisters the agent from the registry.

7.2 Postman Collection Setup

Create a Postman environment with: • base_url = http://localhost:8000

Then use requests like: • {{base_url}}/agents • {{base_url}}/run

No auth headers are required by the current API implementation.

7.3 Agent Execution Testing via Postman

There are two different "execution" concepts implemented:

1\) Coordinator workflow execution (Celery) • Trigger via: ◦ POST
{{base_url}}/run • Confirmation: ◦ Celery worker logs show task
execution ◦ Redis pubsub channel workflow.completed receives an event

2\) Agent container execution (runtime process) • Trigger via: ◦ POST
{{base_url}}/agents/spawn • Confirmation: ◦ docker ps shows a new
container named like agent\_\<8chars\> ◦ agent container logs show
startup message: ▪ Agent \<AGENT_NAME\> running with id \<AGENT_ID\>

If you want the spawned agent to run the autonomous loop, you must
enable it (next section).

7.4 Verifying Autonomous Behavior

Autonomous behavior is implemented, but opt-in.

7.4.1 Enable autonomy when spawning (via metadata)

The spawner supports enabling autonomy using metadata:

• Example POST /agents/spawn request body enabling autonomous loop:

{ \"name\": \"AutonomousPlanner\", \"role\": \"planner\", \"image\":
\"amas_agent_template:latest\", \"metadata\": { \"autonomous_loop\":
true } }

This causes the spawner to set AGENT_AUTONOMOUS_LOOP=true inside the
agent container.

7.4.2 Watch agent logs for autonomous loop startup

Once autonomous loop is enabled, the agent loop prints a line beginning
with:

• \[agent_loop\] starting: id=\... name=\... role=\... run_id=\...

View agent logs:

• List containers: ◦ docker ps • Tail the agent container logs: ◦ docker
logs -f \<agent_container_name_or_id\>

7.4.3 Observe orchestration and messaging via Redis

Use Redis CLI inside the Redis container:

• Subscribe to key channels: ◦ docker compose exec redis redis-cli
SUBSCRIBE agent.spawn.request agent.spawn.response agent.heartbeat
workflow.completed agent:broadcast

What to look for: • agent.heartbeat messages from agents (template
runtime emits these every 10 seconds) • agent.spawn.request /
agent.spawn.response when agents or external actors request spawning via
orchestrator • workflow.completed when the coordinator workflow finishes

7.4.4 Inspect agent state/health in Redis

The autonomous loop uses Redis keys such as: • agent:state:\<agent_id\>
(serialized loop state) • agent:health:\<agent_id\> (health record with
TTL) • agent:plan:\<agent_id\>:\<goal_id\> (plan state if planning is
used) • agent:inbox:\<agent_id\> (inbox list for direct messages)

You can inspect keys:

• List keys (example patterns): ◦ docker compose exec redis redis-cli
KEYS \"agent:state:\*\" ◦ docker compose exec redis redis-cli KEYS
\"agent:health:\*\" ◦ docker compose exec redis redis-cli KEYS
\"agent:plan:\*\" ◦ docker compose exec redis redis-cli KEYS
\"agent:inbox:\*\" • Fetch a state value: ◦ docker compose exec redis
redis-cli GET agent:state:\<agent_id\>

7.4.5 Inject a goal message into an agent inbox (optional)

The goal manager supports goal creation from inbox messages.

Example (LPUSH a goal instruction):

• docker compose exec redis redis-cli LPUSH agent:inbox:\<agent_id\>
\"{\\\"type\\\":\\\"goal\\\",\\\"description\\\":\\\"Write a short plan
for improving observability\\\",\\\"priority\\\":5}\"

Then watch the agent logs for subsequent loop activity.

8\. Observability & Debugging

8.1 Container status

• docker compose ps • docker ps

8.2 Service logs (recommended first line of debugging)

• API: ◦ docker compose logs -f api • Celery worker: ◦ docker compose
logs -f celery-worker • Orchestrator: ◦ docker compose logs -f
orchestrator • Redis / Postgres: ◦ docker compose logs -f redis ◦ docker
compose logs -f postgres

8.3 Debugging OpenAI issues

Symptoms: • In Celery tasks, OpenAI errors are caught and included in
the generated analysis text (e.g., OpenAI error: \...). • In agent
cognition (agent_think_step), OpenAI failures cause the agent decision
to default to sleeping.

Checks: • Ensure OPENAI_API_KEY is set in .env. • Check celery-worker
logs for exceptions in tasks: ◦ run_coordinator_task ◦ agent_think_step
◦ agent_plan_goal ◦ agent_store_memory

8.4 Debugging Celery not consuming tasks

Checks: • Confirm worker is running: ◦ docker compose ps • Confirm
worker command consumes queue coordinator (it does, by command line). •
Look for incoming task logs: ◦ docker compose logs -f celery-worker •
Confirm broker URL: ◦ CELERY_BROKER_URL (falls back to REDIS_URL)

8.5 Debugging agent spawning failures

Symptoms: • API returns 500 on /agents/spawn ("Failed to spawn agent").
• Orchestrator prints errors handling spawn requests.

Checks: • Confirm Docker socket mount exists for api and orchestrator in
compose. • Check logs: ◦ docker compose logs -f api ◦ docker compose
logs -f orchestrator

Note: • app/utils/docker_client.py clears Docker context env vars to
avoid docker-py "http+docker" scheme issues, then attempts unix socket
URLs.

8.6 Debugging agents exiting early

The template agent runtime is designed to run indefinitely. If it exits:
• Check the agent container logs: ◦ docker logs \<agent_container_id\> •
Confirm it can connect to Redis using REDIS_URL (agents rely on it
immediately for heartbeat). • If autonomy is enabled, confirm Celery and
Redis are reachable (autonomous loop can offload cognition/memory to
Celery).

9\. Limitations (Honest & Required)

• No task status/result API ◦ POST /run returns a task_id, but there is
no endpoint to query status or retrieve the final result. Observability
is via logs and Redis pub/sub (workflow.completed). • Orchestrator is
not HTTP-exposed ◦ It only listens to Redis channel agent.spawn.request.
• Agent container HTTP API is internal only ◦ The template agent runs an
HTTP server on port 8080, but spawned agents do not publish ports to the
host by default. • Autonomy is opt-in and not "fully automatic" ◦
Spawning and enabling autonomous loop require explicit configuration. ◦
Many behaviors are best-effort (especially memory operations when
dependencies are unavailable). • Search provider defaults may fail
without configuration ◦ SEARCH_API_PROVIDER=serpapi requires
SERPAPI_API_KEY. Without it, the coordinator task will fail at the
search step. • Database migrations are not run automatically ◦ Services
use create_all best-effort behaviors. Alembic is present, but migrations
are not invoked as part of container startup. • Some DB models are
present but not wired into the API ◦ Task, TaskStep, Message, Tool,
AgentTool tables exist in models, but the HTTP API currently only uses
agent registry endpoints and does not expose task/message CRUD. •
Logging is primarily print(\...) ◦ There is no structured logging
configuration in the running services.

10\. Future Improvements

• Add API endpoints to: ◦ fetch workflow status/result by task_id ◦
expose agent health/status from Redis (agent:health:\*) via HTTP ◦ list
agent containers and their runtime state coherently • Add a durable
event stream: ◦ persist workflow events (instead of only Redis pub/sub)
• Introduce structured logging: ◦ consistent JSON logs across API,
Celery, orchestrator, and agents • Add automated tests: ◦ unit tests for
API and services ◦ integration tests that start compose and validate
/run and /agents/spawn • Improve agent observability: ◦ explicit tracing
of decisions/actions (persisted and queryable) ◦ dashboards for Redis
keys, agent health, and memory summaries • Make migrations first-class:
◦ run Alembic migrations automatically at startup (or provide a
dedicated migration job container) • Harden agent spawning: ◦ explicit
network configuration ◦ configurable port publishing for agent /health
endpoint when desired
