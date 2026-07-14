"""Shared implementation for OpenAI-compatible chat providers.

Groq, GitHub Models, OpenRouter and Ollama all expose an OpenAI-style
``/chat/completions`` endpoint, so their providers subclass this and only
declare their name, base URL, auth header and default model. This keeps the
provider files tiny and the transport logic in one place (DRY).
"""
from __future__ import annotations

import json
import time
from typing import AsyncIterator

import httpx

from .base import (
    BaseProvider,
    InvalidRequest,
    LLMResponse,
    Message,
    ProviderConnectionError,
    ProviderServerError,
    ProviderTimeout,
    QuotaExceeded,
    RateLimitError,
    Usage,
)

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class OpenAICompatProvider(BaseProvider):
    """Base for providers speaking the OpenAI chat-completions protocol."""

    #: Full URL of the chat-completions endpoint.
    chat_url: str = ""
    #: Extra headers merged into every request (e.g. OpenRouter attribution).
    extra_headers: dict[str, str] = {}

    def _api_key(self) -> str | None:
        """Return the credential for this provider, or None if unset."""
        raise NotImplementedError

    def is_available(self) -> bool:
        return bool(self._api_key()) and bool(self.chat_url)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        key = self._api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _payload(
        self,
        messages: list[Message],
        temperature: float,
        max_tokens: int | None,
        stream: bool,
    ) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return payload

    def _raise_for_status(self, resp: httpx.Response) -> None:
        code = resp.status_code
        if code == 200:
            return
        text = resp.text[:500]
        low = text.lower()
        if code == 429:
            if "quota" in low or "exhaust" in low or "insufficient" in low:
                raise QuotaExceeded(f"{self.name} quota exceeded: {text}", provider=self.name)
            raise RateLimitError(f"{self.name} rate limited (429): {text}", provider=self.name)
        if code >= 500:
            raise ProviderServerError(f"{self.name} server error ({code}): {text}", provider=self.name)
        if code in (401, 403):
            raise InvalidRequest(f"{self.name} auth failed ({code}): {text}", provider=self.name)
        raise InvalidRequest(f"{self.name} request error ({code}): {text}", provider=self.name)

    async def chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        payload = self._payload(messages, temperature, max_tokens, stream=False)
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.post(self.chat_url, headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"{self.name} timed out: {exc}", provider=self.name) from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError(f"{self.name} connection failed: {exc}", provider=self.name) from exc

        self._raise_for_status(resp)
        latency_ms = (time.perf_counter() - started) * 1000
        data = resp.json()
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
            finish = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderServerError(
                f"{self.name} returned an unexpected payload", provider=self.name
            ) from exc

        usage_raw = data.get("usage") or {}
        usage = Usage(
            prompt_tokens=usage_raw.get("prompt_tokens", 0),
            completion_tokens=usage_raw.get("completion_tokens", 0),
            total_tokens=usage_raw.get("total_tokens", 0),
        )
        return LLMResponse(
            text=text.strip(),
            provider=self.name,
            model=self.model,
            usage=usage,
            latency_ms=latency_ms,
            finish_reason=finish,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        payload = self._payload(messages, temperature, max_tokens, stream=True)
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                async with client.stream(
                    "POST", self.chat_url, headers=self._headers(), json=payload
                ) as resp:
                    if resp.status_code != 200:
                        await resp.aread()
                        self._raise_for_status(resp)
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line[len("data:"):].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            obj = json.loads(chunk)
                            delta = obj["choices"][0]["delta"].get("content")
                            if delta:
                                yield delta
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"{self.name} timed out: {exc}", provider=self.name) from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError(f"{self.name} connection failed: {exc}", provider=self.name) from exc

    async def health_check(self) -> bool:
        if not self.is_available():
            return False
        try:
            await self.chat(
                [Message(role="user", content="ping")],
                temperature=0.0,
                max_tokens=1,
            )
            return True
        except Exception:  # noqa: BLE001
            return False
