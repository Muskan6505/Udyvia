"""Provider wrapper for the advisor LLM. The model only extracts fields and phrases explanations;
it never sets prices or eligibility. Any failure raises LLMUnavailable so callers fall back offline."""
from __future__ import annotations

import json
import time

import httpx

from .. import config


class LLMUnavailable(Exception):
    pass


class GeminiClient:
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str, *, timeout: float = 8.0, transport: httpx.BaseTransport | None = None):
        self._key, self._model, self._timeout, self._transport = api_key, model, timeout, transport

    def generate_json(self, system: str, user: str) -> dict:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as c:
                r = c.post(self.URL.format(model=self._model), json=body, headers={"x-goog-api-key": self._key})
            if r.status_code != 200:
                raise LLMUnavailable(f"gemini http {r.status_code}")      # never include the key or body in errors
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            out = json.loads(text)
        except LLMUnavailable:
            raise
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as e:
            raise LLMUnavailable(type(e).__name__) from None
        if not isinstance(out, dict):
            raise LLMUnavailable("not an object")
        return out


_down_until = 0.0     # circuit breaker: after a failure, skip the LLM briefly instead of waiting on every message


def get_llm() -> GeminiClient | None:
    if config.ADVISOR_LLM == "off" or not config.GEMINI_API_KEY or time.time() < _down_until:
        return None
    return GeminiClient(config.GEMINI_API_KEY, config.GEMINI_MODEL, timeout=config.LLM_TIMEOUT_SECONDS)


def mark_down(seconds: float = 60.0) -> None:
    global _down_until
    _down_until = time.time() + seconds
