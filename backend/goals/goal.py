from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


GoalStatus = str  # pending | active | completed | failed


@dataclass
class Goal:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    priority: int = 0
    status: GoalStatus = "pending"
    parent_goal_id: Optional[str] = None

    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "priority": int(self.priority),
            "status": self.status,
            "parent_goal_id": self.parent_goal_id,
            "created_at": float(self.created_at),
            "updated_at": float(self.updated_at),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Goal":
        return Goal(
            id=str(d.get("id") or str(uuid.uuid4())),
            description=str(d.get("description") or ""),
            priority=int(d.get("priority") or 0),
            status=str(d.get("status") or "pending"),
            parent_goal_id=(str(d.get("parent_goal_id")) if d.get("parent_goal_id") else None),
            created_at=float(d.get("created_at") or time.time()),
            updated_at=float(d.get("updated_at") or time.time()),
        )

    def touch(self):
        self.updated_at = time.time()
