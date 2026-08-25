from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import ProviderStatus, TaskRequest, TaskResult

router = APIRouter(prefix="/api", tags=["router"])


def _get_services():
    """Lazy import to avoid circular deps; returns (ai_router, redis_svc, windsurf_svc)."""
    from app.main import ai_router, redis_service, windsurf_service

    return ai_router, redis_service, windsurf_service


@router.post("/tasks", response_model=TaskResult)
async def submit_task(request: TaskRequest) -> TaskResult:
    """Submit a task to the AI boardroom. Fans out to all selected providers."""
    ai_router, redis_svc, windsurf_svc = _get_services()

    result = await ai_router.route(request)

    # Persist to Redis
    await redis_svc.store_task(result)

    # Push to Windsurf if requested
    if request.push_to_windsurf:
        push = await windsurf_svc.push_results(result)
        result.metadata["windsurf_pushed"] = push.delivered
        result.metadata["windsurf"] = push.model_dump(mode="json")

    return result


@router.get("/tasks", response_model=list[TaskResult])
async def list_tasks(limit: int = 50) -> list[TaskResult]:
    """List recent tasks."""
    ai_router, _, _ = _get_services()
    return ai_router.list_tasks(limit=limit)


@router.get("/tasks/{task_id}", response_model=TaskResult)
async def get_task(task_id: str) -> TaskResult:
    """Get a specific task result by ID."""
    ai_router, redis_svc, _ = _get_services()

    # Try in-memory first, then Redis
    result = ai_router.get_task(task_id)
    if result is None:
        result = await redis_svc.get_task(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return result


@router.get("/providers", response_model=list[ProviderStatus])
async def list_providers() -> list[ProviderStatus]:
    """List all providers and their status."""
    ai_router, _, _ = _get_services()
    return ai_router.get_provider_statuses()


@router.get("/providers/enabled", response_model=list[str])
async def list_enabled_providers() -> list[str]:
    """List only the enabled provider names."""
    ai_router, _, _ = _get_services()
    return [p.value for p in ai_router.get_enabled_providers()]


@router.post("/tasks/{task_id}/push-windsurf")
async def push_to_windsurf(task_id: str) -> dict:
    """Manually push a task's results to Windsurf."""
    ai_router, redis_svc, windsurf_svc = _get_services()

    result = ai_router.get_task(task_id)
    if result is None:
        result = await redis_svc.get_task(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    push = await windsurf_svc.push_results(result)
    return {"task_id": task_id, "pushed": push.delivered, **push.model_dump(mode="json")}
