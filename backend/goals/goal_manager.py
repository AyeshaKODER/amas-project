from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import redis

from goals.goal import Goal


JsonDict = Dict[str, Any]


class GoalManager:
    """Agent-owned goal manager.

    Persistence strategy:
    - Stores all goals + active goal id in Redis so goals survive across loop iterations.
    - Key is namespaced by agent_id so each agent owns its own goal set.

    The orchestrator does not manage goals; it only spawns/stops containers.
    """

    def __init__(self, redis_client: "redis.Redis", agent_id: str, key_prefix: str = "agent:goals:"):
        self.r = redis_client
        self.agent_id = agent_id
        self.key = f"{key_prefix}{agent_id}"

        self._cache: Optional[JsonDict] = None

    # -----------------
    # persistence
    # -----------------
    def _load(self) -> JsonDict:
        if self._cache is not None:
            return self._cache
        raw = None
        try:
            raw = self.r.get(self.key)
        except Exception:
            raw = None

        if not raw:
            self._cache = {"active_goal_id": None, "goals": {}}
            return self._cache

        try:
            d = json.loads(raw)
            if not isinstance(d, dict):
                d = {"active_goal_id": None, "goals": {}}
        except Exception:
            d = {"active_goal_id": None, "goals": {}}

        # normalize
        d.setdefault("active_goal_id", None)
        d.setdefault("goals", {})
        if not isinstance(d["goals"], dict):
            d["goals"] = {}

        self._cache = d
        return d

    def _save(self, d: JsonDict):
        self._cache = d
        try:
            self.r.set(self.key, json.dumps(d))
        except Exception:
            pass

    # -----------------
    # CRUD
    # -----------------
    def list_goals(self) -> List[Goal]:
        d = self._load()
        goals = []
        for g in (d.get("goals") or {}).values():
            if isinstance(g, dict):
                goals.append(Goal.from_dict(g))
        return goals

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        d = self._load()
        g = (d.get("goals") or {}).get(goal_id)
        if isinstance(g, dict):
            return Goal.from_dict(g)
        return None

    def create_goal(self, description: str, priority: int = 0, parent_goal_id: Optional[str] = None) -> Goal:
        d = self._load()
        goal = Goal(description=description, priority=int(priority), parent_goal_id=parent_goal_id)
        (d["goals"])[goal.id] = goal.to_dict()
        self._save(d)
        return goal

    def create_subgoal(self, parent_goal_id: str, description: str, priority: int = 0) -> Goal:
        return self.create_goal(description=description, priority=priority, parent_goal_id=parent_goal_id)

    def set_status(self, goal_id: str, status: str):
        d = self._load()
        g = (d.get("goals") or {}).get(goal_id)
        if not isinstance(g, dict):
            return
        goal = Goal.from_dict(g)
        goal.status = status
        goal.touch()
        d["goals"][goal_id] = goal.to_dict()

        # If marking completed/failed and it was active, clear active
        if status in ("completed", "failed") and d.get("active_goal_id") == goal_id:
            d["active_goal_id"] = None

        self._save(d)

    # -----------------
    # selection
    # -----------------
    def get_active_goal(self) -> Optional[Goal]:
        d = self._load()
        active_id = d.get("active_goal_id")
        if not active_id:
            return None
        return self.get_goal(str(active_id))

    def select_goal_to_work_on(self) -> Optional[Goal]:
        """Select an active goal or promote a pending goal.

        Policy:
        - If there's an active goal, keep it.
        - Else pick the highest priority pending goal.
        - If none pending, return None.
        """
        d = self._load()

        active = self.get_active_goal()
        if active and active.status == "active":
            return active

        # Pick best pending
        best: Optional[Goal] = None
        for g in self.list_goals():
            if g.status != "pending":
                continue
            if best is None:
                best = g
                continue
            if g.priority > best.priority:
                best = g
            elif g.priority == best.priority and g.created_at < best.created_at:
                best = g

        if best is None:
            d["active_goal_id"] = None
            self._save(d)
            return None

        best.status = "active"
        best.touch()
        d["goals"][best.id] = best.to_dict()
        d["active_goal_id"] = best.id
        self._save(d)
        return best

    # -----------------
    # message ingestion (optional)
    # -----------------
    def ingest_messages(self, messages: List[JsonDict]) -> int:
        """Create goals from inbox messages if they contain goal instructions.

        Supported shapes (best-effort):
        - {"type":"goal", "description":"...", "priority": 3}
        - {"type":"goal.create", "description":"..."}
        - {"goal": {"description":"...", "priority": 1, "parent_goal_id": "..."}}
        - {"type":"delegate_task", "payload": {"task": {"description": "...", ...}}}
        - {"type":"delegate_task", "payload": {"task": {"goal": "...", ...}}}

        Returns number of goals created.
        """
        created = 0
        for m in messages or []:
            if not isinstance(m, dict):
                continue

            if isinstance(m.get("goal"), dict):
                g = m["goal"]
                desc = str(g.get("description") or "").strip()
                if not desc:
                    continue
                pr = int(g.get("priority") or 0)
                parent = g.get("parent_goal_id")
                parent_id = str(parent) if parent else None
                self.create_goal(desc, pr, parent_goal_id=parent_id)
                created += 1
                continue

            t = str(m.get("type") or "").strip().lower()
            if t in ("goal", "goal.create"):
                desc = str(m.get("description") or "").strip()
                if not desc:
                    continue
                pr = int(m.get("priority") or 0)
                parent = m.get("parent_goal_id")
                parent_id = str(parent) if parent else None
                self.create_goal(desc, pr, parent_goal_id=parent_id)
                created += 1
                continue

            # Delegated task -> goal (agent-owned)
            if t == "delegate_task":
                payload = m.get("payload")
                if isinstance(payload, dict):
                    task = payload.get("task")
                else:
                    task = None
                if isinstance(task, dict):
                    desc = str(task.get("description") or task.get("goal") or "").strip()
                    if not desc:
                        continue
                    pr = int(task.get("priority") or 0)
                    parent = task.get("parent_goal_id")
                    parent_id = str(parent) if parent else None
                    self.create_goal(f"Delegated: {desc}", pr, parent_goal_id=parent_id)
                    created += 1

        return created

    def snapshot(self, limit: int = 50) -> JsonDict:
        """Return a small JSON snapshot suitable for embedding into prompts."""
        goals = self.list_goals()
        # sort active first, then priority desc
        goals.sort(key=lambda g: (0 if g.status == "active" else 1, -g.priority, g.created_at))
        goals = goals[:limit]
        return {
            "active_goal_id": (self._load().get("active_goal_id")),
            "goals": [g.to_dict() for g in goals],
        }
