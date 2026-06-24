from __future__ import annotations

import logging
import time

import httpx

from app.config import settings
from app.models import ProviderName, ProviderResponse
from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """Connector for locally-running Ollama LLMs."""

    name = ProviderName.OLLAMA

    def __init__(self) -> None:
        self.model = settings.ollama_model
        self.base_url = settings.ollama_base_url.rstrip("/")

    def is_enabled(self) -> bool:
        return bool(self.base_url)

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
            payload: dict = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }
            if system_prompt:
                payload["system"] = system_prompt

            async with httpx.AsyncClient(timeout=settings.provider_timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()

            content = data.get("response", "")
            usage = None
            if "eval_count" in data:
                usage = {
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                }
            return self._make_response(content, start, token_usage=usage)
        except Exception as exc:
            logger.exception("Ollama provider error")
            return self._make_response("", start, error=str(exc))
