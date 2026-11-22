# -*- coding: utf-8 -*-
"""Minimal OpenAI-compatible chat client used by the agent loop."""
from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from .config import Settings


class LLMError(RuntimeError):
    pass


ChatFn = Callable[[list[dict]], str]


def thinking_kwargs(settings: Settings) -> dict:
    if not settings.disable_thinking:
        return {}
    # Different vendors use different names; unknown fields are ignored.
    return {
        "enable_thinking": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "reasoning_effort": "none",
    }


class LLMClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        if not settings.llm_api_key:
            raise LLMError("LLM_API_KEY is empty; set it in .env or the environment")
        self.settings = settings
        self._client = client or httpx.Client(timeout=settings.request_timeout_s)

    @property
    def url(self) -> str:
        return f"{self.settings.llm_base_url}/chat/completions"

    def chat(self, messages: list[dict], temperature: float = 0.0,
             retries: int = 3) -> str:
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature,
        }
        payload.update(thinking_kwargs(self.settings))
        last: Exception | None = None
        for attempt in range(retries):
            try:
                resp = self._client.post(
                    self.url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.settings.llm_api_key}",
                    },
                    json=payload,
                )
                if resp.status_code >= 400:
                    raise LLMError(
                        f"chat HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                body = resp.json()
                choices = body.get("choices") or []
                if not choices:
                    raise LLMError(f"chat response has no choices: {body}")
                content = choices[0].get("message", {}).get("content")
                if not isinstance(content, str):
                    raise LLMError("chat response content is not a string")
                return content
            except Exception as exc:  # noqa: BLE001
                last = exc
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        raise LLMError(f"chat failed after {retries} attempts: {last}")

    def close(self) -> None:
        self._client.close()
