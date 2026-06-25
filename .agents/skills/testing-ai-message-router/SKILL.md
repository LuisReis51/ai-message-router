---
name: testing-ai-message-router
description: Test the AI Message Router FastAPI service end-to-end. Use when verifying REST API, WebSocket, Redis persistence, provider error handling, 3D frontend UI, or Windsurf push changes.
---

# Testing the AI Message Router

## Prerequisites

- Python 3.11+ with dependencies installed (`pip install -r requirements.txt`)
- Redis server running locally (`redis-server` or via Docker)
- `websockets` Python package installed (for WebSocket tests)
- `playwright` Python package with Chromium installed (for frontend DOM inspection)

## Devin Secrets Needed

None required for baseline testing. Provider API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, XAI_API_KEY, DEEPSEEK_API_KEY) are only needed to test actual LLM responses.

## Quick Start

```bash
cd /home/ubuntu/repos/ai-message-router

# Ensure Redis is running
redis-cli ping  # should return PONG
# If not: sudo apt-get install -y redis-server && sudo systemctl start redis-server

# Load API keys if available
source .env 2>/dev/null || true

# Start the server (user prefers port 5100)
python -m uvicorn app.main:app --host 0.0.0.0 --port 5100
```

## Key Test Areas

### 1. 3D Frontend UI (Browser-based, requires recording)

The app serves a 3D interactive frontend at `GET /`. Test via browser at `http://localhost:5100`:

**Initial load:**
- Title "AI Boardroom" with gradient text
- 3D Three.js particle background with wireframe icosahedron and orbital rings
- 6 provider chips: ChatGPT, Claude, Gemini, Grok, DeepSeek, Ollama
- Textarea with placeholder, blue send button, empty state message

**Provider chip toggle:**
- Click enabled chip to deselect (removes `.selected` class)
- Click again to re-select (adds `.selected` class back)
- Use Playwright CDP (`http://localhost:29229`) to verify DOM class states:
  ```python
  # Connect via CDP and check chip states
  result = await page.evaluate("""() => {
      const chips = document.querySelectorAll('[class*="provider-chip"]');
      return Array.from(chips).map(c => ({text: c.textContent.trim(), classes: c.className}));
  }""")
  ```

**Submitting prompts:**
- Select providers, type question, click send
- Response cards appear with "Thinking..." spinner initially
- Status bar progresses: "Sending to N AI providers..." → "Received X of N responses..." → "Done!"
- Cards show: provider name, model name, response text, latency, token count

**DOM structure verification:**
- Both `#emptyState` and `#responsesGrid` must be children of `#responsesArea`
- Verify programmatically after submission:
  ```python
  result = await page.evaluate('''() => {
      const area = document.getElementById("responsesArea");
      const grid = document.getElementById("responsesGrid");
      const empty = document.getElementById("emptyState");
      return {
          gridParentId: grid.parentElement.id,
          emptyParentId: empty.parentElement.id,
          gridInsideArea: area.contains(grid),
          emptyInsideArea: area.contains(empty),
          gridDisplay: grid.style.display,
          emptyDisplay: empty.style.display
      };
  }''')
  # After submit: gridDisplay should be "grid", emptyDisplay should be "none"
  # Both parentIds should be "responsesArea"
  ```

**Validation:**
- Empty textarea + send → toast "Please type a question first"
- No providers selected + send → toast "Please select at least one AI provider"

**Error messages (human-friendly):**
- Quota issues → "Quota exceeded - enable billing on this API"
- No credits → "No credits - purchase credits for this provider"
- Insufficient balance → "Insufficient balance - add funds to account"
- Model not found → "Model not available - update model in .env"
- Connection error → "Cannot connect - is the service running?"

### 2. REST API (curl-based, no recording needed)

- `GET /health` — check `status`, `redis`, `providers_enabled`, `websocket_clients`
- `GET /api/providers` — 6 provider objects with correct enabled/disabled states
- `POST /api/tasks` — submit tasks targeting specific providers
- `GET /api/tasks/{id}` — retrieve by ID; verify Redis persistence with `redis-cli GET ai_router:task:{id}`
- `GET /api/tasks` — verify reverse chronological ordering
- `POST /api/tasks/{id}/push-windsurf` — manual Windsurf push

### 3. Input Validation

All should return HTTP 422:
- Empty prompt: `{"prompt": ""}`
- Temperature out of range: `{"prompt": "x", "temperature": 5.0}`
- Invalid provider: `{"prompt": "x", "providers": ["nonexistent"]}`

### 4. WebSocket Protocol (Python script)

Connect to `ws://localhost:5100/ws` and test:
- `{"event": "ping"}` → `{"event": "pong", "data": {}}`
- `{"event": "list_providers"}` → `{"event": "providers", "data": {...}}`
- `{"event": "submit_task", "data": {...}}` → sequence of `task_started`, `provider_response`(s), `task_completed`
- Invalid JSON → `{"event": "error", "data": {"message": "Invalid JSON"}}`
- Unknown event → `{"event": "error", "data": {"message": "Unknown event: ..."}}`

Both `list_providers` and `submit_task` handlers use a shared `_get_services()` helper for lazy imports. If either handler fails with an import error, check `app/api/websocket.py` — the helper function should import `ai_router`, `redis_service`, and `windsurf_service` from `app.main`.

### 5. Windsurf File Fallback

Set `push_to_windsurf: true` in task request. Since no Windsurf IDE is running, the service falls back to writing `~/.ai-router/windsurf/{task_id}.json`. Verify the file exists and contains valid JSON with expected keys.

### 6. Provider Error Paths

Without API keys, all providers except Ollama are disabled. This is useful for testing:
- Disabled providers: return `"Provider not enabled (missing API key)"` with `content=""`
- Ollama (enabled via default base_url but not running): returns connection error with `latency_ms > 0`

### 7. Swagger Docs

- `GET /docs` should still load the Swagger UI (not the 3D frontend)
- Title shows "AI Message Router" with version and all endpoints listed

### 8. Deployment Config (shell-based, no recording needed)

When testing deployment-related changes (render.yaml, Dockerfile, docker-compose.yml):

**PORT env var override:**
- Start server with a non-default port: `PORT=9999 python -m uvicorn app.main:app --host 0.0.0.0 --port 9999`
- Verify it responds on 9999: `curl localhost:9999/health`
- Verify default port 8000 is NOT listening: `curl localhost:8000/health` should fail
- This proves the PORT injection (used by Render, Railway, etc.) works correctly

**REDIS_URL="" graceful degradation (simulates Render free tier):**
- Start server with `REDIS_URL="" python -m uvicorn app.main:app --host 0.0.0.0 --port 8111`
- Server should log: `WARNING | Redis unavailable (...) - running without persistence/cache`
- `/health` should return `"redis": false`
- Task submission should still work (in-memory only, no persistence)
- This proves the app won't crash on platforms without Redis

**render.yaml env var name validation:**
- Verify programmatically that render.yaml env var keys (UPPER_SNAKE) map to config.py fields (lower_snake) via pydantic-settings convention
- Key mappings: OPENAI_API_KEY→openai_api_key, ANTHROPIC_API_KEY→anthropic_api_key, GEMINI_API_KEY→gemini_api_key, GROK_API_KEY→grok_api_key, DEEPSEEK_API_KEY→deepseek_api_key, REDIS_URL→redis_url, PORT→port

**Dockerfile with custom PORT:**
- `docker build -t ai-router-test .`
- `docker run -d -p 7777:7777 -e PORT=7777 -e REDIS_URL="" --name ai-router-test ai-router-test`
- Verify logs show `Uvicorn running on http://0.0.0.0:7777`
- `curl localhost:7777/health` should succeed
- The Dockerfile uses shell-form CMD (not exec-form) intentionally for `${PORT:-8000}` expansion — the Docker build warning about JSON args is expected

**Port conflicts:** Kill previous servers before starting new ones: `pkill -f "uvicorn app.main" 2>/dev/null; sleep 2`. Check ports with `ss -tlnp | grep PORT_NUMBER`. Some ports may be held by system processes — use a different port if so.

## Known Issues

- **Provider model names may change**: Models like `gemini-2.0-flash`, `claude-sonnet-4-5-20250929`, `grok-3` may be deprecated over time. If providers return 404/model-not-found errors, check `app/config.py` and `.env` for model name settings.
- **Account-level issues**: Gemini free tier quota might be 0 (needs billing), Grok/DeepSeek may need credits/funds added. These are not code bugs.
- **uvicorn PATH issue on Windows**: Users may need `python -m uvicorn` instead of `uvicorn` directly.
- **Provider consolidation**: OpenAI, Grok, and DeepSeek share `OpenAICompatibleProvider` base class. If one breaks, all three likely break — test at least one of them to verify the base class works.

## Tips

- For frontend testing, use browser GUI with screen recording. For API/WebSocket testing, use shell (curl + Python scripts) without recording.
- Use Playwright CDP at `http://localhost:29229` to inspect DOM state programmatically during frontend tests.
- The `websockets` package is needed for WS tests: `pip install websockets`
- Redis keys use prefix `ai_router:task:` with 1-hour TTL
- Provider models are configured in `app/config.py` (defaults) and overridable via `.env`
- The frontend auto-selects all enabled providers on load. Deselect unwanted ones by clicking their chips.
- No CI is configured on this repo, so there are no CI checks to wait for.
- When testing refactors that consolidate code (e.g. provider base classes), test at least one provider from the consolidated group AND one independent provider (e.g. Claude) to verify both paths.
- Save test evidence (curl output, WS logs) to /tmp files during testing — VM restarts can wipe these, so capture them promptly for your report.
