from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models import ProviderResponse, TaskRequest, WSMessage

logger = logging.getLogger(__name__)

ws_router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(self._connections))

    async def broadcast(self, message: WSMessage) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(message.model_dump(mode="json"))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """WebSocket endpoint for real-time task submission and streaming responses.

    Protocol:
    - Client sends: {"event": "submit_task", "data": {TaskRequest fields}}
    - Server sends: {"event": "task_started", "task_id": "...", "data": {}}
    - Server sends: {"event": "provider_response", "task_id": "...", "data": {ProviderResponse}}
      (one per provider, as they complete)
    - Server sends: {"event": "task_completed", "task_id": "...", "data": {TaskResult}}
    """
    await manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"event": "error", "data": {"message": "Invalid JSON"}})
                continue

            event = msg.get("event")
            if event == "submit_task":
                await _handle_submit(ws, msg.get("data", {}))
            elif event == "ping":
                await ws.send_json({"event": "pong", "data": {}})
            elif event == "list_providers":
                await _handle_list_providers(ws)
            else:
                await ws.send_json(
                    {"event": "error", "data": {"message": f"Unknown event: {event}"}}
                )
    except WebSocketDisconnect:
        manager.disconnect(ws)


async def _handle_submit(ws: WebSocket, data: dict) -> None:
    """Handle a task submission via WebSocket."""
    from app.main import ai_router, redis_service, windsurf_service

    try:
        request = TaskRequest(**data)
    except Exception as exc:
        await ws.send_json({"event": "error", "data": {"message": f"Invalid task request: {exc}"}})
        return

    response_queue: asyncio.Queue[ProviderResponse] = asyncio.Queue()

    # Start routing in background
    route_task = asyncio.create_task(ai_router.route(request, on_response=response_queue))

    # Notify client
    # We need the task_id, which is generated inside route(). Send a pending message.
    await ws.send_json(
        WSMessage(event="task_started", data={"prompt": request.prompt}).model_dump(mode="json")
    )

    # Stream individual provider responses as they arrive
    done = False
    while not done:
        try:
            resp = await asyncio.wait_for(response_queue.get(), timeout=1.0)
            await ws.send_json(
                WSMessage(
                    event="provider_response",
                    data=resp.model_dump(mode="json"),
                ).model_dump(mode="json")
            )
        except asyncio.TimeoutError:
            if route_task.done():
                # Drain any remaining items
                while not response_queue.empty():
                    resp = response_queue.get_nowait()
                    await ws.send_json(
                        WSMessage(
                            event="provider_response",
                            data=resp.model_dump(mode="json"),
                        ).model_dump(mode="json")
                    )
                done = True

    result = await route_task
    await redis_service.store_task(result)

    if request.push_to_windsurf:
        pushed = await windsurf_service.push_results(result)
        result.metadata["windsurf_pushed"] = pushed

    await ws.send_json(
        WSMessage(
            event="task_completed",
            task_id=result.task_id,
            data=result.model_dump(mode="json"),
        ).model_dump(mode="json")
    )


async def _handle_list_providers(ws: WebSocket) -> None:
    from app.main import ai_router

    statuses = ai_router.get_provider_statuses()
    await ws.send_json(
        WSMessage(
            event="providers",
            data={"providers": [s.model_dump(mode="json") for s in statuses]},
        ).model_dump(mode="json")
    )
