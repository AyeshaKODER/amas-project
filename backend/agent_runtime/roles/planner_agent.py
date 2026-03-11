from __future__ import annotations

from typing import Any, Dict, Optional

from agent_runtime.roles.base_agent import BaseAgent


JsonDict = Dict[str, Any]


class PlannerAgent(BaseAgent):
    role_name = "planner"

    def role_instructions(self) -> str:
        return (
            "ROLE: PlannerAgent\n"
            "You specialize in planning and task decomposition.\n"
            "You should:\n"
            "- Create or refine plans for complex goals\n"
            "- Delegate executable tasks to ExecutorAgents\n"
            "- Ask CriticAgents for review/feedback\n"
            "You should avoid claiming to have executed work; instead coordinate and delegate.\n"
        )

    def pre_decide(self, observation: JsonDict) -> Optional[JsonDict]:
        # Heuristic: if there's an active goal and planning is enabled and no plan exists -> plan it.
        active_goal = observation.get("active_goal")
        planning_enabled = bool(observation.get("planning_enabled"))
        plan = observation.get("plan")

        if isinstance(active_goal, dict) and planning_enabled and not plan:
            gid = str(active_goal.get("id") or "")
            if gid:
                return {
                    "thought": "Active goal has no plan; generating a plan.",
                    "action": {"type": "plan_goal", "payload": {"goal_id": gid}},
                    "sleep_seconds": 0,
                }

        # Heuristic: if we have a current plan step, delegate it to an executor once.
        current_step = observation.get("current_plan_step")
        if isinstance(active_goal, dict) and isinstance(current_step, dict):
            gid = str(active_goal.get("id") or "")
            sid = str(current_step.get("id") or "")
            sdesc = str(current_step.get("description") or "").strip()
            if gid and sid and sdesc:
                # Use Redis set to avoid re-delegating the same step every tick
                try:
                    key = f"agent:delegations:{self.identity.agent_id}:{gid}"
                    if self.bus.r.sismember(key, sid):
                        return None
                    self.bus.r.sadd(key, sid)
                except Exception:
                    pass

                target = self.find_first_agent_by_role("executor")
                if target and target.get("agent_id"):
                    rid = str(target.get("agent_id"))
                    task = {
                        "description": sdesc,
                        "goal_id": gid,
                        "plan_step_id": sid,
                        "priority": int(active_goal.get("priority") or 0),
                    }
                    return {
                        "thought": f"Delegating step to executor {rid}.",
                        "action": {"type": "delegate_task", "payload": {"recipient_agent_id": rid, "task": task}},
                        "sleep_seconds": 2,
                    }

        return None
