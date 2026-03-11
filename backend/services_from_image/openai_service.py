import os
from typing import Any, Dict, Optional

import openai


def _truthy(v: Optional[str]) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "y", "on")


class OpenAIService:
    """Compatibility wrapper around the OpenAI python SDK.

    See app/services/openai_service.py for the canonical implementation.
    This copy is kept for legacy image builds.
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self._client = None

        if not self.api_key:
            print("Warning: OPENAI_API_KEY not set. OpenAI calls will fail until configured.")
            return

        try:
            from openai import OpenAI  # type: ignore

            self._client = OpenAI(api_key=self.api_key)
        except Exception:
            try:
                openai.api_key = self.api_key
            except Exception:
                pass

    def completion(self, prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 1024) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": "You are an agent."},
            {"role": "user", "content": prompt},
        ]

        if self._client is not None:
            resp = self._client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
            try:
                return resp.model_dump()
            except Exception:
                return {
                    "choices": [
                        {"message": {"content": getattr(resp.choices[0].message, "content", "")}}
                    ]
                }

        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return resp
