from __future__ import annotations

import json
import logging
import os

import httpx

from app.config import settings
from app.models import TaskResult, WindsurfChannel, WindsurfPushResult

logger = logging.getLogger(__name__)


class WindsurfService:
    """Push aggregated AI responses into Windsurf IDE.

    Windsurf exposes a local HTTP endpoint (via its extension) that accepts
    structured messages. This service formats the router's TaskResult and
    POSTs it to the Windsurf listener.

    Supports two modes:
    1. HTTP POST to Windsurf's local API (default)
    2. File-based injection (writes a .windsurf.json for the extension to pick up)
    """

    def __init__(self) -> None:
        self.base_url = f"http://{settings.windsurf_host}:{settings.windsurf_port}"
        self.results_endpoint = f"{self.base_url}/api/ai-router/results"

    async def push_results(self, result: TaskResult) -> WindsurfPushResult:
        """Push a TaskResult to Windsurf.

        Attempts the HTTP push first; only that counts as delivered to the IDE.
        On failure the payload is written to disk for extension pickup, which is
        reported as the ``file`` channel with ``delivered`` still False.
        """
        payload = self._format_payload(result)

        http_error = await self._push_http(payload)
        if http_error is None:
            return WindsurfPushResult(
                delivered=True,
                channel=WindsurfChannel.HTTP,
                endpoint=self.results_endpoint,
            )

        filepath, file_error = self._push_file(payload, result.task_id)
        return WindsurfPushResult(
            delivered=False,
            channel=WindsurfChannel.FILE if filepath else None,
            endpoint=self.results_endpoint,
            filepath=filepath,
            http_error=http_error,
            file_error=file_error,
        )

    async def _push_http(self, payload: dict) -> str | None:
        """POST the payload to Windsurf. Returns None on success, else the error."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    self.results_endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code in (200, 201, 204):
                    logger.info("Results pushed to Windsurf via HTTP")
                    return None
                logger.warning("Windsurf HTTP push returned %d", resp.status_code)
                return f"HTTP {resp.status_code} from {self.results_endpoint}"
        except Exception as exc:
            logger.debug("Windsurf HTTP push failed: %s", exc)
            # Some httpx exceptions (e.g. ReadTimeout) carry an empty message.
            return f"{type(exc).__name__}: {str(exc) or 'no detail'}"

    def _push_file(self, payload: dict, task_id: str) -> tuple[str | None, str | None]:
        """Write the payload for extension pickup. Returns (filepath, error)."""
        try:
            output_dir = os.path.expanduser("~/.ai-router/windsurf")
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, f"{task_id}.json")
            with open(filepath, "w") as f:
                json.dump(payload, f, indent=2, default=str)
            logger.info("Windsurf IDE unreachable; results written to %s for pickup", filepath)
            return filepath, None
        except Exception as exc:
            logger.error("Windsurf file push failed: %s", exc)
            return None, f"{type(exc).__name__}: {exc}"

    def _format_payload(self, result: TaskResult) -> dict:
        """Format a TaskResult into a Windsurf-friendly payload."""
        responses = []
        for r in result.responses:
            responses.append(
                {
                    "provider": r.provider.value,
                    "model": r.model,
                    "content": r.content,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                    "tokens": r.token_usage,
                }
            )

        best_response = None
        successful = [r for r in result.responses if r.error is None]
        if successful:
            best_response = min(successful, key=lambda r: r.latency_ms)

        return {
            "task_id": result.task_id,
            "prompt": result.prompt,
            "status": result.status.value,
            "response_count": len(result.responses),
            "responses": responses,
            "best_response": {
                "provider": best_response.provider.value,
                "content": best_response.content,
            }
            if best_response
            else None,
            "created_at": result.created_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        }

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
