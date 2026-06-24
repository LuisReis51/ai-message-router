from __future__ import annotations

import abc
import time
from typing import AsyncIterator

from app.models import ProviderName, ProviderResponse


class BaseProvider(abc.ABC):
    """Abstract base class for all AI provider connectors."""

    name: ProviderName
    model: str

    @abc.abstractmethod
    def is_enabled(self) -> bool:
        """Return True if the provider has valid credentials / is reachable."""

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        """Send a prompt and return the full response."""

    async def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Yield response tokens as they arrive. Default falls back to generate()."""
        resp = await self.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        yield resp.content

    def _make_response(
        self,
        content: str,
        start_time: float,
        *,
        token_usage: dict[str, int] | None = None,
        error: str | None = None,
    ) -> ProviderResponse:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        return ProviderResponse(
            provider=self.name,
            model=self.model,
            content=content,
            latency_ms=latency_ms,
            token_usage=token_usage,
            error=error,
        )
