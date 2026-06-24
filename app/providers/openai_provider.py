from __future__ import annotations

from app.config import settings
from app.models import ProviderName
from app.providers.openai_compat import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    name = ProviderName.OPENAI

    def __init__(self) -> None:
        super().__init__(api_key=settings.openai_api_key, model=settings.openai_model)
