"""Google Gemini provider via the Generative Language REST API.

Uses httpx (async) directly rather than the SDK so all providers share the same
transport and error-handling style. Maps the shared ``Message`` list onto
Gemini's ``contents`` / ``systemInstruction`` shape.
"""
from __future__ import annotations

import json
import os
import time
from typing import AsyncIterator

import httpx

from ._openai_compat import DEFAULT_TIMEOUT
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

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self) -> None:
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.embed_model = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")

    def _api_key(self) -> str | None:
        return os.getenv("GEMINI_API_KEY")

    def is_available(self) -> bool:
        return bool(self._api_key())

    # ---- payload helpers ------------------------------------------------- #
    @staticmethod
    def _to_contents(messages: list[Message]) -> tuple[list[dict], dict | None]:
        contents: list[dict] = []
        system_parts: list[str] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
                continue
            role = "model" if m.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m.content}]})
        system = (
            {"parts": [{"text": "\n".join(system_parts)}]} if system_parts else None
        )
        return contents, system

    def _body(self, messages: list[Message], temperature: float, max_tokens: int | None) -> dict:
        contents, system = self._to_contents(messages)
        body: dict = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        if system:
            body["systemInstruction"] = system
        if max_tokens is not None:
            body["generationConfig"]["maxOutputTokens"] = max_tokens
        return body

    def _raise_for_status(self, resp: httpx.Response) -> None:
        code = resp.status_code
        if code == 200:
            return
        text = resp.text[:500]
        low = text.lower()
        if code == 429 or "resource_exhausted" in low or "quota" in low:
            raise QuotaExceeded(f"gemini quota/resource exhausted: {text}", provider=self.name)
        if code >= 500:
            raise ProviderServerError(f"gemini server error ({code}): {text}", provider=self.name)
        if code in (401, 403):
            raise InvalidRequest(f"gemini auth failed ({code}): {text}", provider=self.name)
        raise InvalidRequest(f"gemini request error ({code}): {text}", provider=self.name)

    @staticmethod
    def _extract_text(data: dict) -> tuple[str, str | None]:
        candidates = data.get("candidates") or []
        if not candidates:
            return "", None
        cand = candidates[0]
        parts = cand.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        return text, cand.get("finishReason")

    # ---- interface ------------------------------------------------------- #
    async def chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        key = self._api_key()
        url = f"{_API_ROOT}/models/{self.model}:generateContent?key={key}"
        body = self._body(messages, temperature, max_tokens)
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.post(url, json=body)
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"gemini timed out: {exc}", provider=self.name) from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError(f"gemini connection failed: {exc}", provider=self.name) from exc

        self._raise_for_status(resp)
        latency_ms = (time.perf_counter() - started) * 1000
        data = resp.json()
        text, finish = self._extract_text(data)
        um = data.get("usageMetadata", {})
        usage = Usage(
            prompt_tokens=um.get("promptTokenCount", 0),
            completion_tokens=um.get("candidatesTokenCount", 0),
            total_tokens=um.get("totalTokenCount", 0),
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
        key = self._api_key()
        url = f"{_API_ROOT}/models/{self.model}:streamGenerateContent?alt=sse&key={key}"
        body = self._body(messages, temperature, max_tokens)
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                async with client.stream("POST", url, json=body) as resp:
                    if resp.status_code != 200:
                        await resp.aread()
                        self._raise_for_status(resp)
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line[len("data:"):].strip()
                        try:
                            obj = json.loads(chunk)
                            text, _ = self._extract_text(obj)
                            if text:
                                yield text
                        except json.JSONDecodeError:
                            continue
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"gemini timed out: {exc}", provider=self.name) from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError(f"gemini connection failed: {exc}", provider=self.name) from exc

    async def embeddings(self, text: str | list[str]) -> list[list[float]]:
        key = self._api_key()
        items = [text] if isinstance(text, str) else text
        url = f"{_API_ROOT}/models/{self.embed_model}:embedContent?key={key}"
        vectors: list[list[float]] = []
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                for item in items:
                    resp = await client.post(
                        url,
                        json={
                            "model": f"models/{self.embed_model}",
                            "content": {"parts": [{"text": item}]},
                        },
                    )
                    self._raise_for_status(resp)
                    vectors.append(resp.json()["embedding"]["values"])
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"gemini embeddings timed out: {exc}", provider=self.name) from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError(f"gemini embeddings failed: {exc}", provider=self.name) from exc
        return vectors

    async def health_check(self) -> bool:
        if not self.is_available():
            return False
        try:
            await self.chat(
                [Message(role="user", content="ping")], temperature=0.0, max_tokens=1
            )
            return True
        except Exception:  # noqa: BLE001
            return False
