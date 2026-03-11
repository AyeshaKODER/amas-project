from __future__ import annotations

from typing import Any, Dict, Optional

from agent_runtime.roles.base_agent import BaseAgent


JsonDict = Dict[str, Any]


class ExecutorAgent(BaseAgent):
    role_name = "executor"

    def role_instructions(self) -> str:
        return (
            "ROLE: ExecutorAgent\n"
            "You specialize in execution.\n"
            "You should:\n"
            "- Take delegated tasks or the current plan step and perform concrete progress\n"
            "- Prefer completing the current_plan_step and marking it complete when done\n"
            "- Provide status updates to the team\n"
            "You should avoid doing broad replanning unless blocked.\n"
        )

    def pre_decide(self, observation: JsonDict) -> Optional[JsonDict]:
        # Lightweight heuristic: if we have an active plan step and last action succeeded,
        # consider marking it complete to move forward.
        current_step = observation.get("current_plan_step")
        if isinstance(current_step, dict) and current_step.get("id"):
            # If the last reflection suggests progress, we can complete step.
            mem = observation.get("memory")
            if isinstance(mem, dict):
                working = mem.get("working")
            else:
                working = None

            last_reflection = None
            if isinstance(working, dict):
                last_reflection = working.get("last_reflection")

            if isinstance(last_reflection, dict) and last_reflection.get("alignment") == "progress":
                return {
                    "thought": "Last action made progress; advancing plan by completing current step.",
                    "action": {"type": "complete_plan_step", "payload": {"step_id": str(current_step.get("id"))}},
                    "sleep_seconds": 1,
                }

        return None
