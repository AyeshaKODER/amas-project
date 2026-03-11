from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


JsonDict = Dict[str, Any]


class MessageTypes:
    # Human/agent chat
    DIRECT = "direct"
    BROADCAST = "broadcast"

    # Coordination
    DELEGATE_TASK = "delegate_task"
    STATUS = "status"


@dataclass
class AgentMessage:
    """JSON-first message envelope.

    Designed for Redis transport (lists or pubsub). Keep payload JSON-serializable.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = MessageTypes.DIRECT

    sender_agent_id: str = ""
    sender_agent_name: str = ""
    sender_role: str = ""

    recipient_agent_id: Optional[str] = None
    broadcast: bool = False

    # Optional correlation for workflows/tasks
    conversation_id: Optional[str] = None
    correlation_id: Optional[str] = None

    created_at: float = field(default_factory=lambda: time.time())

    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "id": self.id,
            "type": self.type,
            "sender_agent_id": self.sender_agent_id,
            "sender_agent_name": self.sender_agent_name,
            "sender_role": self.sender_role,
            "recipient_agent_id": self.recipient_agent_id,
            "broadcast": bool(self.broadcast),
            "conversation_id": self.conversation_id,
            "correlation_id": self.correlation_id,
            "created_at": float(self.created_at),
            "payload": self.payload or {},
        }

    @staticmethod
    def from_dict(d: JsonDict) -> "AgentMessage":
        return AgentMessage(
            id=str(d.get("id") or str(uuid.uuid4())),
            type=str(d.get("type") or MessageTypes.DIRECT),
            sender_agent_id=str(d.get("sender_agent_id") or ""),
            sender_agent_name=str(d.get("sender_agent_name") or ""),
            sender_role=str(d.get("sender_role") or ""),
            recipient_agent_id=(str(d.get("recipient_agent_id")) if d.get("recipient_agent_id") else None),
            broadcast=bool(d.get("broadcast") or False),
            conversation_id=(str(d.get("conversation_id")) if d.get("conversation_id") else None),
            correlation_id=(str(d.get("correlation_id")) if d.get("correlation_id") else None),
            created_at=float(d.get("created_at") or time.time()),
            payload=dict(d.get("payload") or {}),
        )


def make_direct_message(
    sender_agent_id: str,
    sender_agent_name: str,
    sender_role: str,
    recipient_agent_id: str,
    content: str,
    metadata: Optional[JsonDict] = None,
) -> AgentMessage:
    return AgentMessage(
        type=MessageTypes.DIRECT,
        sender_agent_id=sender_agent_id,
        sender_agent_name=sender_agent_name,
        sender_role=sender_role,
        recipient_agent_id=recipient_agent_id,
        broadcast=False,
        payload={"content": content, "metadata": metadata or {}},
    )


def make_broadcast_message(
    sender_agent_id: str,
    sender_agent_name: str,
    sender_role: str,
    content: str,
    metadata: Optional[JsonDict] = None,
) -> AgentMessage:
    return AgentMessage(
        type=MessageTypes.BROADCAST,
        sender_agent_id=sender_agent_id,
        sender_agent_name=sender_agent_name,
        sender_role=sender_role,
        recipient_agent_id=None,
        broadcast=True,
        payload={"content": content, "metadata": metadata or {}},
    )


def make_task_delegation(
    sender_agent_id: str,
    sender_agent_name: str,
    sender_role: str,
    recipient_agent_id: str,
    task: JsonDict,
) -> AgentMessage:
    return AgentMessage(
        type=MessageTypes.DELEGATE_TASK,
        sender_agent_id=sender_agent_id,
        sender_agent_name=sender_agent_name,
        sender_role=sender_role,
        recipient_agent_id=recipient_agent_id,
        broadcast=False,
        payload={"task": task},
    )


def make_status_update(
    sender_agent_id: str,
    sender_agent_name: str,
    sender_role: str,
    status: str,
    details: Optional[JsonDict] = None,
    broadcast: bool = True,
    recipient_agent_id: Optional[str] = None,
) -> AgentMessage:
    return AgentMessage(
        type=MessageTypes.STATUS,
        sender_agent_id=sender_agent_id,
        sender_agent_name=sender_agent_name,
        sender_role=sender_role,
        recipient_agent_id=recipient_agent_id,
        broadcast=bool(broadcast),
        payload={"status": status, "details": details or {}},
    )
