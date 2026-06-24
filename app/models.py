from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProviderName(str, Enum):
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    GROK = "grok"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class TaskRequest(BaseModel):
    """Incoming task to be routed to AI providers."""

    prompt: str = Field(..., min_length=1, description="The task/prompt to send to AI providers")
    providers: list[ProviderName] | None = Field(
        default=None,
        description="Specific providers to target. None = all enabled providers.",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Optional system prompt prepended to all provider calls",
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    push_to_windsurf: bool = Field(
        default=False,
        description="Whether to push aggregated results to Windsurf IDE",
    )


class ProviderResponse(BaseModel):
    """Response from a single AI provider."""

    provider: ProviderName
    model: str
    content: str
    latency_ms: int
    token_usage: dict[str, int] | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskResult(BaseModel):
    """Aggregated result for a routed task."""

    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    prompt: str
    status: TaskStatus = TaskStatus.PENDING
    responses: list[ProviderResponse] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderStatus(BaseModel):
    """Health/availability status for a provider."""

    name: ProviderName
    enabled: bool
    model: str
    healthy: bool = True
    last_error: str | None = None


class WSMessage(BaseModel):
    """WebSocket message envelope."""

    event: str
    task_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
