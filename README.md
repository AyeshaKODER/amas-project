# 🤖 AMAS — Autonomous Multi-Agent System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?style=for-the-badge&logo=fastapi)
![Next.js](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js)
![Redis](https://img.shields.io/badge/Redis-7-red?style=for-the-badge&logo=redis)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?style=for-the-badge&logo=postgresql)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker)

**A production-grade platform for running, monitoring, and coordinating autonomous AI agents.**

</div>

---

## 🧠 What is AMAS?

AMAS (Autonomous Multi-Agent System) is a platform that lets you define a **goal**, and have a fleet of AI agents autonomously **plan, collaborate, and execute** to achieve it — while you watch in real time.

Each agent runs in its own Docker container, has its own memory, goals, and plans, and communicates with other agents through a Redis pub/sub bus. A central coordinator workflow ties everything together using search + LLM analysis.

> **Think of it as:** giving AI agents a real operating environment — not just a chat window.

---

## ✨ Key Features

- 🎯 **Goal-Driven Agents** — Submit a goal; agents plan and execute autonomously
- 🐳 **Containerized Execution** — Each agent runs in an isolated Docker container
- 🔄 **Real-Time Visibility** — Live event stream via Server-Sent Events (SSE)
- 🧩 **Multi-Agent Coordination** — Agents delegate, collaborate, and broadcast via Redis
- 🧠 **Memory System** — Episodic, semantic, and working memory backed by PostgreSQL + Redis
- 📊 **Full Observability** — Health, state, goals, plans, and reputation per agent
- ⚡ **Async Workflows** — Celery-powered background task queue
- 🔍 **Search + LLM Pipeline** — SerpAPI/DuckDuckGo + OpenAI for intelligent analysis

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Next.js Frontend                   │
│         (React 19 · TanStack Query · Tailwind)       │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / SSE
┌────────────────────▼────────────────────────────────┐
│                 FastAPI Backend                      │
│              (REST API + SSE Stream)                 │
└──────┬──────────┬──────────────┬───────────────────┘
       │          │              │
  ┌────▼───┐ ┌───▼────┐  ┌──────▼──────┐
  │Celery  │ │ Redis  │  │ PostgreSQL  │
  │Worker  │ │Pub/Sub │  │  Registry   │
  └────┬───┘ └───┬────┘  └─────────────┘
       │         │
┌──────▼─────────▼──────────────────────┐
│         Agent Containers (Docker)      │
│  [Planner] [Executor] [Critic] [...]   │
└────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| Frontend | Next.js 16, React 19, TanStack Query |
| Task Queue | Celery + Redis broker |
| Messaging | Redis Pub/Sub |
| Persistence | PostgreSQL 15 |
| Orchestration | Docker SDK |
| AI Services | OpenAI + SerpAPI/DuckDuckGo |

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API key
- (Optional) SerpAPI key for web search

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/amas.git
cd amas
```

### 2. Set up environment variables

```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 3. Start everything

```bash
docker compose up --build
```

### 4. Open the dashboard

```
Frontend:  http://localhost:3000
Backend:   http://localhost:8000
API Docs:  http://localhost:8000/docs
```

---

## 📁 Project Structure

```
amas/
├── app/                        # FastAPI backend
│   ├── main.py                 # App entry point + CORS
│   ├── api.py                  # Route definitions
│   ├── celery_worker.py        # Celery task definitions
│   ├── services/
│   │   ├── registry.py         # Agent registry (DB + in-memory)
│   │   ├── agent_spawner.py    # Docker container management
│   │   ├── workflow.py         # Coordinator workflow
│   │   ├── memory_manager.py   # Episodic/semantic/working memory
│   │   ├── openai_service.py   # LLM integration
│   │   └── search_service.py   # Web search integration
│   ├── visibility_api.py       # Read-only agent observability
│   └── stream_events.py        # SSE Redis pub/sub bridge
├── frontend/                   # Next.js frontend
│   ├── app/                    # App router pages
│   └── components/             # UI components
├── agent_runtime/              # Agent container code
│   └── agent_runtime.py        # Autonomous loop
├── docker-compose.yml
└── .env.example
```

---

## 🔌 API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/system/health` | GET | Full system health (Redis, DB, Celery) |
| `/agents` | GET | List all agents |
| `/agents/create` | POST | Register an agent |
| `/agents/spawn` | POST | Spawn agent Docker container |
| `/shutdown/{agent_id}` | POST | Stop and remove agent |
| `/run` | POST | Start workflow (async) |
| `/ask` | POST | Start workflow (blocking) |
| `/tasks/{task_id}` | GET | Get task status + result |
| `/stream/events` | GET | SSE real-time event stream |
| `/agents/{id}/health` | GET | Agent health from Redis |
| `/agents/{id}/goals` | GET | Agent current goals |
| `/agents/{id}/plan` | GET | Agent execution plan |

Full API docs available at `/docs` when running locally.

---

## 🎬 How It Works

1. **Submit a goal** via the frontend workflow screen
2. **Backend enqueues** a Celery task with your goal
3. **Coordinator runs**: searches the web, calls OpenAI, spawns agents if needed
4. **Agents work autonomously**: each runs observe → think → act → reflect loop
5. **Real-time updates** stream to your dashboard via SSE
6. **Results appear** when workflow completes — full analysis + sources

---

## 👥 Team

Built with ❤️ for the IIT competition.

| Role | Contribution |
|------|-------------|
| Backend & AI | FastAPI, Celery, Agent Runtime, Redis architecture |
| Frontend & Integration | Next.js dashboard, API integration, UI/UX |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
