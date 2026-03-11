import os
from typing import Any, Dict, Optional

import openai


def _truthy(v: Optional[str]) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "y", "on")


class OpenAIService:
    """Small compatibility wrapper around the OpenAI python SDK.

    Contract preserved:
    - completion(prompt, model, max_tokens) returns a dict shaped like ChatCompletion responses:
      {"choices": [{"message": {"content": "..."}}], ...}

    Implementation:
    - If openai>=1.0 is installed, use the new client (`OpenAI().chat.completions.create`).
    - Else fall back to legacy `openai.ChatCompletion.create`.
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self._client = None

        if not self.api_key:
            print("Warning: OPENAI_API_KEY not set. OpenAI calls will fail until configured.")
            return

        # Prefer the v1 client when available.
        try:
            from openai import OpenAI  # type: ignore

            self._client = OpenAI(api_key=self.api_key)
        except Exception:
            # Legacy path: set global api_key
            try:
                openai.api_key = self.api_key
            except Exception:
                pass

    def completion(self, prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 1024) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": "You are an agent."},
            {"role": "user", "content": prompt},
        ]

        # v1 client
        if self._client is not None:
            resp = self._client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
            # openai>=1 returns pydantic models
            try:
                return resp.model_dump()
            except Exception:
                # best-effort fallback
                return {
                    "choices": [
                        {"message": {"content": getattr(resp.choices[0].message, "content", "")}}
                    ]
                }

        # Legacy client
        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
        # legacy already returns dict-like
        return resp
