from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes import router as api_router
from app.api.websocket import manager, ws_router
from app.config import settings
from app.router import AIRouter
from app.services.redis_service import RedisService
from app.services.windsurf import WindsurfService

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Singleton services
ai_router = AIRouter()
redis_service = RedisService()
windsurf_service = WindsurfService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AI Message Router")
    await redis_service.connect()

    enabled = ai_router.get_enabled_providers()
    if enabled:
        logger.info("Enabled providers: %s", ", ".join(p.value for p in enabled))
    else:
        logger.warning("No AI providers enabled. Set API keys in .env to enable providers.")

    windsurf_ok = await windsurf_service.check_health()
    logger.info("Windsurf IDE: %s", "connected" if windsurf_ok else "not available")

    yield

    # Shutdown
    logger.info("Shutting down AI Message Router")
    await redis_service.disconnect()


app = FastAPI(
    title="AI Message Router",
    description=(
        "An AI boardroom service that fans out tasks to multiple LLM providers "
        "(ChatGPT, Claude, Gemini, Grok, DeepSeek, Ollama) and aggregates responses. "
        "Results can be streamed via WebSocket and pushed to Windsurf IDE."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)


_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def root():
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "redis": redis_service.is_connected,
        "providers_enabled": len(ai_router.get_enabled_providers()),
        "websocket_clients": manager.active_count,
    }
