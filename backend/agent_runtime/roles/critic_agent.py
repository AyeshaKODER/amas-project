from __future__ import annotations

from typing import Any, Dict, Optional

from agent_runtime.roles.base_agent import BaseAgent


JsonDict = Dict[str, Any]


class CriticAgent(BaseAgent):
    role_name = "critic"

    def role_instructions(self) -> str:
        return (
            "ROLE: CriticAgent\n"
            "You specialize in critique and quality control.\n"
            "You should:\n"
            "- Inspect reflection and outcomes for misalignment or failures\n"
            "- Suggest smaller steps, replanning, or subgoal creation\n"
            "- Communicate feedback to PlannerAgents and ExecutorAgents\n"
            "You should avoid performing the execution yourself.\n"
        )

    def pre_decide(self, observation: JsonDict) -> Optional[JsonDict]:
        mem = observation.get("memory")
        working = mem.get("working") if isinstance(mem, dict) else None
        last_reflection = working.get("last_reflection") if isinstance(working, dict) else None

        if not isinstance(last_reflection, dict):
            return None

        critique = str(last_reflection.get("critique") or "").strip()
        suggestion = last_reflection.get("suggestion")

        # If we have a critique and a suggestion, message the planner.
        if critique:
            planner = self.find_first_agent_by_role("planner")
            if planner and planner.get("agent_id"):
                rid = str(planner.get("agent_id"))
                content = f"Critique: {critique}"
                meta = {"suggestion": suggestion, "reflection": last_reflection}
                return {
                    "thought": f"Sending critique to planner {rid}.",
                    "action": {"type": "send_message", "payload": {"recipient_agent_id": rid, "content": content, "metadata": meta}},
                    "sleep_seconds": 2,
                }

        return None
