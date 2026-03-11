from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import redis

from communication.protocols import AgentMessage, MessageTypes


JsonDict = Dict[str, Any]


class MessageBus:
    """Redis-backed, JSON message bus.

    Transport:
    - Direct messages: Redis list per agent inbox (agent:inbox:<agent_id>)
    - Broadcast: Redis pubsub channel (agent:broadcast)

    This avoids orchestrator relaying messages and works across containers.
    """

    BROADCAST_CHANNEL = "agent:broadcast"

    def __init__(self, redis_url: str, agent_id: str, agent_name: str = "", agent_role: str = ""):
        self.redis_url = redis_url
        self.r = redis.from_url(redis_url, decode_responses=True)

        self.agent_id = agent_id
        self.agent_name = agent_name
        self.agent_role = agent_role

        self._pubsub = None

    def inbox_key(self, agent_id: str) -> str:
        return f"agent:inbox:{agent_id}"

    # -----------------
    # subscribe / poll
    # -----------------
    def ensure_subscriptions(self):
        if self._pubsub is not None:
            return
        p = self.r.pubsub(ignore_subscribe_messages=True)
        p.subscribe(self.BROADCAST_CHANNEL)
        self._pubsub = p

    def poll_broadcast(self, max_messages: int = 10) -> List[JsonDict]:
        """Non-blocking poll for broadcast messages."""
        self.ensure_subscriptions()
        msgs: List[JsonDict] = []
        if not self._pubsub:
            return msgs

        for _ in range(max_messages):
            m = self._pubsub.get_message(timeout=0.0)
            if not m:
                break
            if m.get("type") != "message":
                continue
            data = m.get("data")
            if not isinstance(data, str):
                continue
            obj = self._safe_json_loads(data)
            if obj is not None:
                msgs.append(obj)
        return msgs

    # -----------------
    # send
    # -----------------
    def send_direct(self, recipient_agent_id: str, message: AgentMessage) -> bool:
        try:
            message.type = message.type or MessageTypes.DIRECT
            message.recipient_agent_id = recipient_agent_id
            message.broadcast = False
            self.r.lpush(self.inbox_key(recipient_agent_id), json.dumps(message.to_dict()))
            return True
        except Exception:
            return False

    def broadcast(self, message: AgentMessage) -> bool:
        try:
            message.type = message.type or MessageTypes.BROADCAST
            message.recipient_agent_id = None
            message.broadcast = True
            self.r.publish(self.BROADCAST_CHANNEL, json.dumps(message.to_dict()))
            return True
        except Exception:
            return False

    def send_status(self, message: AgentMessage) -> bool:
        # status can be direct or broadcast depending on message.broadcast
        if message.broadcast:
            return self.broadcast(message)
        if message.recipient_agent_id:
            return self.send_direct(message.recipient_agent_id, message)
        # default: broadcast
        message.broadcast = True
        return self.broadcast(message)

    # -----------------
    # internals
    # -----------------
    def _safe_json_loads(self, s: str) -> Optional[JsonDict]:
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                return obj
            return {"value": obj}
        except Exception:
            return None
