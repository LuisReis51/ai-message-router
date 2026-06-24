from __future__ import annotations

from app.config import settings
from app.models import ProviderName
from app.providers.openai_compat import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek uses an OpenAI-compatible API."""

    name = ProviderName.DEEPSEEK

    def __init__(self) -> None:
        super().__init__(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
        )
