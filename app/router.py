from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.models import (
    ProviderName,
    ProviderResponse,
    ProviderStatus,
    TaskRequest,
    TaskResult,
    TaskStatus,
)
from app.providers.base import BaseProvider
from app.providers.claude_provider import ClaudeProvider
from app.providers.deepseek_provider import DeepSeekProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.grok_provider import GrokProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class AIRouter:
    """Core router that fans out tasks to multiple AI providers concurrently."""

    def __init__(self) -> None:
        self._providers: dict[ProviderName, BaseProvider] = {
            ProviderName.OPENAI: OpenAIProvider(),
            ProviderName.CLAUDE: ClaudeProvider(),
            ProviderName.GEMINI: GeminiProvider(),
            ProviderName.GROK: GrokProvider(),
            ProviderName.DEEPSEEK: DeepSeekProvider(),
            ProviderName.OLLAMA: OllamaProvider(),
        }
        self._tasks: dict[str, TaskResult] = {}

    def get_enabled_providers(self) -> list[ProviderName]:
        return [name for name, p in self._providers.items() if p.is_enabled()]

    def get_provider_statuses(self) -> list[ProviderStatus]:
        statuses = []
        for name, provider in self._providers.items():
            statuses.append(
                ProviderStatus(
                    name=name,
                    enabled=provider.is_enabled(),
                    model=provider.model,
                )
            )
        return statuses

    def get_task(self, task_id: str) -> TaskResult | None:
        return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 50) -> list[TaskResult]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    async def route(
        self,
        request: TaskRequest,
        on_response: asyncio.Queue[ProviderResponse] | None = None,
    ) -> TaskResult:
        """Fan out a task to selected providers and collect all responses."""
        result = TaskResult(prompt=request.prompt, status=TaskStatus.IN_PROGRESS)
        self._tasks[result.task_id] = result

        target_providers = request.providers or self.get_enabled_providers()
        if not target_providers:
            result.status = TaskStatus.FAILED
            result.metadata["error"] = "No providers available"
            return result

        sem = asyncio.Semaphore(settings.max_concurrency)

        async def _call_provider(name: ProviderName) -> ProviderResponse:
            async with sem:
                provider = self._providers[name]
                if not provider.is_enabled():
                    return ProviderResponse(
                        provider=name,
                        model=provider.model,
                        content="",
                        latency_ms=0,
                        error="Provider not enabled (missing API key)",
                    )
                try:
                    resp = await asyncio.wait_for(
                        provider.generate(
                            request.prompt,
                            system_prompt=request.system_prompt,
                            temperature=request.temperature,
                            max_tokens=request.max_tokens,
                        ),
                        timeout=settings.provider_timeout,
                    )
                except asyncio.TimeoutError:
                    resp = ProviderResponse(
                        provider=name,
                        model=provider.model,
                        content="",
                        latency_ms=settings.provider_timeout * 1000,
                        error=f"Timeout after {settings.provider_timeout}s",
                    )
                if on_response:
                    await on_response.put(resp)
                return resp

        tasks = [_call_provider(name) for name in target_providers]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for resp in responses:
            if isinstance(resp, Exception):
                logger.error("Unexpected provider exception: %s", resp)
                continue
            result.responses.append(resp)

        has_success = any(r.error is None for r in result.responses)
        has_failure = any(r.error is not None for r in result.responses)

        if has_success and not has_failure:
            result.status = TaskStatus.COMPLETED
        elif has_success and has_failure:
            result.status = TaskStatus.PARTIAL
        else:
            result.status = TaskStatus.FAILED

        result.completed_at = datetime.now(timezone.utc)
        return result
