from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


JsonDict = Dict[str, Any]


def _safe_json_loads(s: str) -> Optional[JsonDict]:
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
        return {"value": obj}
    except Exception:
        return None


@dataclass
class PlanStep:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order: int = 0
    description: str = ""
    status: str = "pending"  # pending | active | completed | failed

    def to_dict(self) -> JsonDict:
        return {
            "id": self.id,
            "order": int(self.order),
            "description": self.description,
            "status": self.status,
        }


@dataclass
class ExecutionPlan:
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str = ""
    goal_description: str = ""
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    steps: List[PlanStep] = field(default_factory=list)
    current_step_index: int = 0

    def to_dict(self) -> JsonDict:
        return {
            "plan_id": self.plan_id,
            "goal_id": self.goal_id,
            "goal_description": self.goal_description,
            "created_at": float(self.created_at),
            "updated_at": float(self.updated_at),
            "current_step_index": int(self.current_step_index),
            "steps": [s.to_dict() for s in self.steps],
        }


class Planner:
    """LLM-based planner.

    - Accepts a high-level Goal (goal_id + description)
    - Uses OpenAI via the existing OpenAIService wrapper
    - Returns a structured execution plan with ordered steps

    This module is intentionally decoupled from the orchestrator. Agents decide when to plan.
    """

    def __init__(self, model: str = "gpt-4o-mini", max_tokens: int = 800):
        self.model = model
        self.max_tokens = max_tokens

    def build_prompt(self, goal_id: str, goal_description: str, context: Optional[JsonDict] = None) -> str:
        context = context or {}
        return (
            "You are a planning module for an autonomous agent. "
            "Given a high-level goal, produce an ordered list of concrete sub-tasks. "
            "Return STRICT JSON only.\n\n"
            f"Goal id: {goal_id}\n"
            f"Goal description: {goal_description}\n\n"
            f"Context (json): {json.dumps(context)}\n\n"
            "Return JSON with shape:\n"
            "{\n"
            "  \"steps\": [\n"
            "    {\"order\": 1, \"description\": \"...\"}\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Use 3 to 10 steps.\n"
            "- Steps must be actionable and ordered.\n"
            "- Do not include markdown.\n"
        )

    def plan(self, goal_id: str, goal_description: str, context: Optional[JsonDict] = None) -> ExecutionPlan:
        plan, _ = self.plan_with_error(goal_id, goal_description, context=context)
        return plan

    def plan_with_error(
        self, goal_id: str, goal_description: str, context: Optional[JsonDict] = None
    ) -> Tuple[ExecutionPlan, Optional[str]]:
        plan = ExecutionPlan(goal_id=goal_id, goal_description=goal_description)

        try:
            from app.services.openai_service import OpenAIService

            prompt = self.build_prompt(goal_id, goal_description, context=context)
            openai = OpenAIService()
            resp = openai.completion(prompt, model=self.model, max_tokens=self.max_tokens)
            content = (
                resp.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            obj = _safe_json_loads(content)
            if obj is None:
                return self._fallback_plan(plan, reason="non_json"), f"non-json content: {content[:200]}"

            steps_raw = obj.get("steps")
            if not isinstance(steps_raw, list) or not steps_raw:
                return self._fallback_plan(plan, reason="no_steps"), "missing/invalid steps"

            steps: List[PlanStep] = []
            for i, s in enumerate(steps_raw[:10]):
                if isinstance(s, str):
                    desc = s
                    order = i + 1
                elif isinstance(s, dict):
                    desc = str(s.get("description") or "").strip()
                    order = int(s.get("order") or (i + 1))
                else:
                    continue

                if not desc:
                    continue

                steps.append(PlanStep(order=order, description=desc, status="pending"))

            if not steps:
                return self._fallback_plan(plan, reason="empty_steps"), "empty steps after normalization"

            # Normalize ordering by order then original
            steps.sort(key=lambda st: st.order)
            for idx, st in enumerate(steps):
                st.order = idx + 1

            plan.steps = steps
            plan.current_step_index = 0
            plan.updated_at = time.time()
            return plan, None

        except Exception as e:
            return self._fallback_plan(plan, reason="exception"), repr(e)

    def _fallback_plan(self, plan: ExecutionPlan, reason: str) -> ExecutionPlan:
        # Minimal plan: a single actionable step
        plan.steps = [
            PlanStep(order=1, description=f"Work on goal: {plan.goal_description}", status="pending")
        ]
        plan.current_step_index = 0
        plan.updated_at = time.time()
        return plan
