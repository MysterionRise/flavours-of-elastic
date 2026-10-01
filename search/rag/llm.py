"""A minimal OpenRouter chat client with readable errors.

OpenRouter (https://openrouter.ai) serves many models behind one
OpenAI-compatible API. The key comes from OPENROUTER_API_KEY and the model
from OPENROUTER_MODEL (or --model); the model id is checked against the
public model list before the first question, so a typo fails fast.
"""

from __future__ import annotations

import os

API = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-3.5-flash-lite"


class LlmError(RuntimeError):
    """The LLM call failed; the message says what to do about it."""


ERRORS = {
    401: "OpenRouter rejected the API key: check OPENROUTER_API_KEY",
    402: "the OpenRouter account has no credits left",
    403: "OpenRouter refused the request (moderation or account restriction)",
    404: "OpenRouter does not know model '{model}': see {api}/models",
    408: "OpenRouter timed out: try again",
    429: "OpenRouter rate limit reached: wait a moment and try again",
}


class OpenRouter:
    def __init__(
        self, api_key: str | None = None, model: str | None = None, session=None
    ):
        self.api_key = (
            api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        )
        self.model = model or os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL
        self._session = session

    @property
    def session(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def check(self) -> None:
        """Fail fast without a key or with a model OpenRouter doesn't list."""
        if not self.api_key:
            raise LlmError(
                "OPENROUTER_API_KEY is not set: export it (https://openrouter.ai/keys),"
                " or run with --retrieve-only"
            )
        response = self.session.get(f"{API}/models", timeout=30)
        if response.ok:
            known = {model.get("id") for model in response.json().get("data", [])}
            if self.model not in known:
                raise LlmError(
                    f"OpenRouter does not list model '{self.model}': pick one from {API}/models"
                    " and set OPENROUTER_MODEL"
                )

    def chat(
        self, messages: list[dict], max_tokens: int = 500, temperature: float = 0.2
    ) -> str:
        import requests

        try:
            response = self.session.post(
                f"{API}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=60,
            )
        except requests.RequestException as exc:
            raise LlmError(f"cannot reach OpenRouter: {exc}") from exc
        if response.status_code in ERRORS:
            raise LlmError(
                ERRORS[response.status_code].format(model=self.model, api=API)
            )
        if not response.ok:
            raise LlmError(
                f"OpenRouter answered HTTP {response.status_code}: {response.text[:300]}"
            )
        payload = response.json()
        if payload.get("error"):
            raise LlmError(
                f"OpenRouter error: {payload['error'].get('message', payload['error'])}"
            )
        return payload["choices"][0]["message"]["content"] or ""
