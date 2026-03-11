# app/services/registry.py
"""
AgentRegistry that prefers a Postgres/SQLAlchemy-backed implementation if available
but falls back to a safe in-memory registry when DB / modules / engine are not ready.
This keeps the orchestrator from crashing at import/startup time.
"""

from typing import Optional, List, Dict, Any
import time
import traceback

# Try to import DB-backed modules. If any import fails, we'll use an in-memory fallback.
_USE_DB = False
try:
    from app.db.session import get_session, engine, Base  # type: ignore
    from app.db import models  # type: ignore
    from sqlalchemy import select
    _USE_DB = True
except Exception:
    # Log the failure for debugging but continue with a fallback
    _USE_DB = False
    _IMPORT_ERROR = traceback.format_exc()

# In-memory fallback implementation
class _InMemoryRegistry:
    def __init__(self):
        self._agents: Dict[str, Dict[str, Any]] = {}

    def register(self, agent_id: str, name: str, role: str, metadata: dict, container_id: Optional[str] = None):
        self._agents[agent_id] = {
            "agent_id": agent_id,
            "name": name,
            "role": role,
            "metadata": metadata or {},
            "container_id": container_id,
            "created_at": time.time(),
        }
        return agent_id

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return self._agents.get(agent_id)

    def get_or_create(self, name: str, role: str = None, metadata: dict = None):
        for rec in self._agents.values():
            if rec.get("name") == name:
                return rec
        import uuid
        agent_id = str(uuid.uuid4())
        self.register(agent_id, name, role or "", metadata or {}, container_id="")
        return self._agents[agent_id]

    def unregister(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def list_agents(self) -> List[Dict[str, Any]]:
        return list(self._agents.values())

# DB-backed class wrapper (keeps same method names)
class _DBRegistry:
    def __init__(self):
        # Ensure tables exist (best-effort)
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            raise

    def register(self, agent_id: str, name: str, role: str, metadata: dict, container_id: str):
        session = get_session()
        with session.begin():
            obj = models.Agent(id=agent_id, name=name, role=role, metadata_json=metadata or {}, container_id=container_id)
            session.add(obj)
        return agent_id

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        session = get_session()
        stmt = select(models.Agent).where(models.Agent.id == agent_id)
        res = session.execute(stmt).scalar_one_or_none()
        if res is None:
            return None
        return {
            "agent_id": res.id,
            "name": res.name,
            "role": res.role,
            "metadata": getattr(res, "metadata_json", {}) or {},
            "container_id": res.container_id,
            "created_at": getattr(res, "created_at", None),
        }

    def get_or_create(self, name: str, role: str = None, metadata: dict = None):
        session = get_session()
        stmt = select(models.Agent).where(models.Agent.name == name)
        res = session.execute(stmt).scalar_one_or_none()
        if res:
            return {
                "agent_id": res.id,
                "name": res.name,
                "role": res.role,
                "metadata": getattr(res, "metadata_json", {}) or {},
                "container_id": res.container_id,
                "created_at": getattr(res, "created_at", None),
            }
        import uuid
        agent_id = str(uuid.uuid4())
        self.register(agent_id, name, role or "", metadata or {}, container_id="")
        return {"agent_id": agent_id, "name": name, "role": role, "metadata": metadata or {}, "container_id": ""}

    def unregister(self, agent_id: str):
        session = get_session()
        with session.begin():
            session.query(models.Agent).filter(models.Agent.id == agent_id).delete()

    def list_agents(self) -> List[Dict[str, Any]]:
        session = get_session()
        rows = session.query(models.Agent).all()
        results = []
        for r in rows:
            results.append({
                "agent_id": r.id,
                "name": r.name,
                "role": r.role,
                "metadata": getattr(r, "metadata_json", {}) or {},
                "container_id": r.container_id,
                "created_at": getattr(r, "created_at", None),
            })
        return results

# Public AgentRegistry using DB when possible, otherwise in-memory fallback
class AgentRegistry:
    def __init__(self):
        if _USE_DB:
            try:
                self._impl = _DBRegistry()
                print("AgentRegistry: using Postgres-backed registry")
                return
            except Exception as e:
                print("AgentRegistry: failed DB init; falling back to in-memory", repr(e))
        else:
            if '_IMPORT_ERROR' in globals():
                print("AgentRegistry: DB import error (truncated):")
                print(str(_IMPORT_ERROR).splitlines()[:10])
            print("AgentRegistry: using in-memory registry")

        self._impl = _InMemoryRegistry()

    def register(self, agent_id: str, name: str, role: str, metadata: dict, container_id: str):
        return self._impl.register(agent_id, name, role, metadata, container_id)

    def get(self, agent_id: str):
        return self._impl.get(agent_id)

    def get_or_create(self, name: str, role: str = None, metadata: dict = None):
        return self._impl.get_or_create(name, role, metadata)

    def unregister(self, agent_id: str):
        return self._impl.unregister(agent_id)

    def list_agents(self) -> List[Dict[str, Any]]:
        return self._impl.list_agents()


