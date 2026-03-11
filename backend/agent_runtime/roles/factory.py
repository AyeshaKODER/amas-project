from __future__ import annotations

import importlib
import os
from typing import Optional

from agent_runtime.roles.base_agent import AgentIdentity, BaseAgent
from agent_runtime.roles.critic_agent import CriticAgent
from agent_runtime.roles.executor_agent import ExecutorAgent
from agent_runtime.roles.planner_agent import PlannerAgent
from communication.message_bus import MessageBus


def _truthy(v: str) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "y", "on")


def load_role_agent(identity: AgentIdentity, bus: MessageBus) -> BaseAgent:
    """Load a role agent.

    Configuration precedence:
    1) AGENT_ROLE_CLASS: python import path, e.g. "agent_runtime.roles.planner_agent.PlannerAgent"
    2) AGENT_ROLE_IMPL: one of: planner | executor | critic | default
    3) identity.agent_role: if it exactly matches one of planner|executor|critic

    Returns BaseAgent (default is BaseAgent behavior via Planner/Executor/Critic fallback to BaseAgent).
    """

    # 1) Explicit class path
    class_path = os.getenv("AGENT_ROLE_CLASS")
    if class_path:
        try:
            mod_name, cls_name = class_path.rsplit(".", 1)
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, cls_name)
            obj = cls(identity, bus)
            if isinstance(obj, BaseAgent):
                return obj
        except Exception:
            pass

    # 2) Short impl name
    impl = (os.getenv("AGENT_ROLE_IMPL") or "").strip().lower()
    if not impl:
        impl = (identity.agent_role or "").strip().lower()

    if impl == "planner":
        return PlannerAgent(identity, bus)
    if impl == "executor":
        return ExecutorAgent(identity, bus)
    if impl == "critic":
        return CriticAgent(identity, bus)

    # default: use a minimal base agent
    return BaseAgent(identity, bus)
