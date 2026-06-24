from __future__ import annotations

from app.config import settings
from app.models import ProviderName
from app.providers.openai_compat import OpenAICompatibleProvider


class GrokProvider(OpenAICompatibleProvider):
    """Grok uses an OpenAI-compatible API via xAI."""

    name = ProviderName.GROK

    def __init__(self) -> None:
        super().__init__(
            api_key=settings.grok_api_key,
            model=settings.grok_model,
            base_url=settings.grok_base_url,
        )
