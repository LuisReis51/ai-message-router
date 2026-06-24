from __future__ import annotations

import logging
import time

from anthropic import AsyncAnthropic

from app.config import settings
from app.models import ProviderName, ProviderResponse
from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseProvider):
    name = ProviderName.CLAUDE

    def __init__(self) -> None:
        self.model = settings.anthropic_model
        self._client: AsyncAnthropic | None = None

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    def is_enabled(self) -> bool:
        return bool(settings.anthropic_api_key)

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            client = self._get_client()
            kwargs: dict = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            resp = await client.messages.create(**kwargs)
            content = resp.content[0].text if resp.content else ""
            usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            }
            return self._make_response(content, start, token_usage=usage)
        except Exception as exc:
            logger.exception("Claude provider error")
            return self._make_response("", start, error=str(exc))
