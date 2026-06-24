---
name: testing-ai-message-router
description: Test the AI Message Router FastAPI service end-to-end. Use when verifying REST API, WebSocket, Redis persistence, provider error handling, or Windsurf push changes.
---

# Testing the AI Message Router

## Prerequisites

- Python 3.11+ with venv at `ai-message-router/.venv`
- Redis server running locally (`redis-server` or via Docker)
- `websockets` Python package installed in venv (for WebSocket tests)

## Devin Secrets Needed

None required for baseline testing. Provider API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.) are only needed to test actual LLM responses.

## Quick Start

```bash
cd /home/ubuntu/repos/ai-message-router
source .venv/bin/activate

# Ensure Redis is running
redis-cli ping  # should return PONG
# If not: sudo apt-get install -y redis-server && sudo systemctl start redis-server

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Key Test Areas

### 1. REST API (curl-based)

- `GET /health` — check `status`, `redis`, `providers_enabled`, `websocket_clients`
- `GET /` — check `service`, `version`, `providers_enabled` list
- `GET /api/providers` — 6 provider objects with correct enabled/disabled states
- `POST /api/tasks` — submit tasks targeting specific providers
- `GET /api/tasks/{id}` — retrieve by ID; verify Redis persistence with `redis-cli GET ai_router:task:{id}`
- `GET /api/tasks` — verify reverse chronological ordering
- `POST /api/tasks/{id}/push-windsurf` — manual Windsurf push

### 2. Input Validation

All should return HTTP 422:
- Empty prompt: `{"prompt": ""}`
- Temperature out of range: `{"prompt": "x", "temperature": 5.0}`
- Invalid provider: `{"prompt": "x", "providers": ["nonexistent"]}`

### 3. WebSocket Protocol (Python script)

Connect to `ws://localhost:8000/ws` and test:
- `{"event": "ping"}` → `{"event": "pong", "data": {}}`
- `{"event": "list_providers"}` → `{"event": "providers", "data": {...}}`
- `{"event": "submit_task", "data": {...}}` → sequence of `task_started`, `provider_response`(s), `task_completed`
- Invalid JSON → `{"event": "error", "data": {"message": "Invalid JSON"}}`
- Unknown event → `{"event": "error", "data": {"message": "Unknown event: ..."}}`

### 4. Windsurf File Fallback

Set `push_to_windsurf: true` in task request. Since no Windsurf IDE is running, the service falls back to writing `~/.ai-router/windsurf/{task_id}.json`. Verify the file exists and contains valid JSON with expected keys.

### 5. Provider Error Paths

Without API keys, all providers except Ollama are disabled. This is useful for testing:
- Disabled providers: return `"Provider not enabled (missing API key)"` with `content=""`
- Ollama (enabled via default base_url but not running): returns connection error with `latency_ms > 0`

## Known Issues

- **WebSocket streaming for disabled providers**: `_call_provider()` in `router.py` might return early for disabled providers without putting the response on the `on_response` queue. This means WebSocket clients may miss individual `provider_response` events for disabled providers. Verify this is fixed by checking that WS clients receive `provider_response` events for ALL providers, not just enabled ones.

## Tips

- All testing is shell-based (curl + Python scripts). No GUI recording needed.
- The `websockets` package is needed for WS tests: `pip install websockets`
- Redis keys use prefix `ai_router:task:` with 1-hour TTL
- Provider models: openai→gpt-4o, claude→claude-sonnet-4-20250514, gemini→gemini-1.5-pro, grok→grok-2, deepseek→deepseek-chat, ollama→llama3
