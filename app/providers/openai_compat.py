from __future__ import annotations

import logging
import time

from openai import AsyncOpenAI

from app.models import ProviderResponse
from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseProvider):
    """Base for providers that expose an OpenAI-compatible chat completions API.

    Subclasses only need to set ``name`` and call ``super().__init__(...)``
    with the appropriate credentials/model.
    """

    def __init__(
        self, *, api_key: str, model: str, base_url: str | None = None
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            kwargs: dict = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    def is_enabled(self) -> bool:
        return bool(self._api_key)

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
            messages: list[dict[str, str]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            client = self._get_client()
            resp = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content or ""
            usage = None
            if resp.usage:
                usage = {
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens,
                    "total_tokens": resp.usage.total_tokens,
                }
            return self._make_response(content, start, token_usage=usage)
        except Exception as exc:
            logger.exception("%s provider error", self.name.value)
            return self._make_response("", start, error=str(exc))
