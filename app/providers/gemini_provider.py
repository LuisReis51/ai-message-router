from __future__ import annotations

import logging
import time

from google import genai
from google.genai import types

from app.config import settings
from app.models import ProviderName, ProviderResponse
from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseProvider):
    name = ProviderName.GEMINI

    def __init__(self) -> None:
        self.model = settings.gemini_model
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    def is_enabled(self) -> bool:
        return bool(settings.gemini_api_key)

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
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_prompt if system_prompt else None,
            )
            resp = await client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            content = resp.text or ""
            usage = None
            if resp.usage_metadata:
                usage = {
                    "prompt_tokens": resp.usage_metadata.prompt_token_count or 0,
                    "completion_tokens": resp.usage_metadata.candidates_token_count or 0,
                    "total_tokens": resp.usage_metadata.total_token_count or 0,
                }
            return self._make_response(content, start, token_usage=usage)
        except Exception as exc:
            logger.exception("Gemini provider error")
            return self._make_response("", start, error=str(exc))
