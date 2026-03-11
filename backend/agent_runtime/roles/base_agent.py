from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from communication.message_bus import MessageBus
from communication.protocols import (
    AgentMessage,
    make_broadcast_message,
    make_direct_message,
    make_status_update,
    make_task_delegation,
)


JsonDict = Dict[str, Any]


@dataclass
class AgentIdentity:
    agent_id: str
    agent_name: str
    agent_role: str


def _normalize_role(role: str) -> str:
    r = (role or "").strip().lower()
    r = r.replace("_", "").replace("-", "")
    if r.endswith("agent"):
        r = r[: -len("agent")]
    return r


class BaseAgent:
    """Base class for role implementations.

    This is intentionally small:
    - role-specific prompting / heuristics live in subclasses
    - orchestrator is not involved
    - roles are swappable via configuration
    """

    role_name: str = "base"

    def __init__(self, identity: AgentIdentity, bus: MessageBus):
        self.identity = identity
        self.bus = bus

    # ----------
    # Strategy hooks
    # ----------
    def role_instructions(self) -> str:
        """Appended to the decision prompt to bias the model."""
        return ""

    def pre_decide(self, observation: JsonDict) -> Optional[JsonDict]:
        """Optional heuristic decision to avoid OpenAI usage.

        Return a decision dict shaped like AgentLoop expects:
        {"thought": "...", "action": {"type": "...", "payload": {...}}, "sleep_seconds": n}

        Return None to fall back to the normal think path.
        """
        return None

    # ----------
    # Discovery helpers
    # ----------
    def list_agents(self) -> List[JsonDict]:
        """List agents from the shared registry (DB-backed when available)."""
        try:
            from app.services.registry import AgentRegistry

            return AgentRegistry().list_agents() or []
        except Exception:
            return []

    def find_agents_by_role(self, role: str) -> List[JsonDict]:
        role_norm = _normalize_role(role)
        out = []
        for a in self.list_agents():
            if not isinstance(a, dict):
                continue
            r = _normalize_role(str(a.get("role") or ""))
            if r == role_norm:
                out.append(a)
        return out

    def find_first_agent_by_role(self, role: str) -> Optional[JsonDict]:
        for a in self.find_agents_by_role(role):
            if str(a.get("agent_id") or "") != self.identity.agent_id:
                return a
        return None

    # ----------
    # Messaging helpers
    # ----------
    def send_direct_text(self, recipient_agent_id: str, content: str, metadata: Optional[JsonDict] = None) -> bool:
        msg = make_direct_message(
            sender_agent_id=self.identity.agent_id,
            sender_agent_name=self.identity.agent_name,
            sender_role=self.identity.agent_role,
            recipient_agent_id=recipient_agent_id,
            content=content,
            metadata=metadata or {},
        )
        return self.bus.send_direct(recipient_agent_id, msg)

    def broadcast_text(self, content: str, metadata: Optional[JsonDict] = None) -> bool:
        msg = make_broadcast_message(
            sender_agent_id=self.identity.agent_id,
            sender_agent_name=self.identity.agent_name,
            sender_role=self.identity.agent_role,
            content=content,
            metadata=metadata or {},
        )
        return self.bus.broadcast(msg)

    def delegate_task(self, recipient_agent_id: str, task: JsonDict) -> bool:
        msg = make_task_delegation(
            sender_agent_id=self.identity.agent_id,
            sender_agent_name=self.identity.agent_name,
            sender_role=self.identity.agent_role,
            recipient_agent_id=recipient_agent_id,
            task=task,
        )
        return self.bus.send_direct(recipient_agent_id, msg)

    def status_update(self, status: str, details: Optional[JsonDict] = None, broadcast: bool = True, recipient_agent_id: Optional[str] = None) -> bool:
        msg = make_status_update(
            sender_agent_id=self.identity.agent_id,
            sender_agent_name=self.identity.agent_name,
            sender_role=self.identity.agent_role,
            status=status,
            details=details or {},
            broadcast=broadcast,
            recipient_agent_id=recipient_agent_id,
        )
        return self.bus.send_status(msg)
