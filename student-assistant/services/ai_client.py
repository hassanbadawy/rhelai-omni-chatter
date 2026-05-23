"""Generic OpenAI-compatible LLM client.

Works with LlamaStack, vLLM, Ollama, LMStudio, OpenRouter, MaaS — anything
that exposes the OpenAI Chat Completions API at /v1/chat/completions.

The caller is responsible for reading base_url/model/api_key from
SettingsService so that runtime changes take effect without a restart.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=60.0, pool=300.0)


class AIClientError(RuntimeError):
    """Raised on non-2xx responses or malformed payloads."""


class AIClient:
    """Thin async wrapper around the OpenAI chat completions endpoint."""

    def __init__(self, base_url: str, model: str, api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    def _url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _body(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int,
        stream: bool,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if response_format:
            body["response_format"] = response_format
        return body

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Non-streaming chat completion. Returns the assistant message text."""
        async with httpx.AsyncClient(headers=self._headers, timeout=_TIMEOUT) as http:
            try:
                resp = await http.post(
                    self._url(),
                    content=json.dumps(
                        self._body(
                            messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            stream=False,
                            response_format=response_format,
                        )
                    ),
                )
            except httpx.HTTPError as e:
                raise AIClientError(f"LLM request failed: {type(e).__name__}: {e}") from e

        if resp.status_code >= 400:
            raise AIClientError(
                f"LLM returned HTTP {resp.status_code}: {resp.text[:500]}"
            )

        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise AIClientError(f"LLM response was not JSON: {e}") from e

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise AIClientError(f"Unexpected LLM response shape: {e}\n{data}") from e

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Server-sent events streaming. Yields text deltas as they arrive."""
        body = json.dumps(
            self._body(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
        )
        async with httpx.AsyncClient(headers=self._headers, timeout=_TIMEOUT) as http:
            async with http.stream("POST", self._url(), content=body) as resp:
                if resp.status_code >= 400:
                    text = await resp.aread()
                    raise AIClientError(
                        f"LLM stream returned HTTP {resp.status_code}: {text[:500]}"
                    )
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
