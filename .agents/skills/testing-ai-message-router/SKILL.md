---
name: testing-ai-message-router
description: How to run and end-to-end test the ai-message-router FastAPI app locally, including the Windsurf push paths (HTTP delivery vs file fallback) and the WebSocket task flow.
---

# Testing ai-message-router locally

## Devin Secrets Needed
None. The app runs with no API keys and no Redis.

## Starting the app
```bash
cd <repo>
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # blueprint already does this
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- Redis absent → warning logged, persistence skipped; the app still works and `GET /api/tasks`
  returns in-memory tasks (handy for viewing task metadata in a browser).
- With no keys, only `ollama` is enabled and Ollama isn't running, so tasks return
  `status: "failed"` with `error: "All connection attempts failed"`. This is expected —
  routing/Windsurf/WebSocket plumbing is still fully exercisable. Always pass
  `"providers": ["ollama"]`.
- The repo may have NO `main` branch; check `git branch -a` for the real base branch before
  diffing or standing up a base-branch comparison.

## Windsurf push testing
The router POSTs to `http://{WINDSURF_HOST}:{WINDSURF_PORT}/api/ai-router/results`
(default `localhost:3000`). Nothing serves it by default, so pushes fall back to
`~/.ai-router/windsurf/{task_id}.json`.

To test the HTTP path, stand up a mock listener on port 3000 that accepts
`POST /api/ai-router/results` and `GET /health`. Make the mock **log every payload it
actually receives** (file + an HTML index page) so you can prove real delivery instead of
trusting the API response, and make its behavior mode-switchable via an env var
(`ok` / `500` / `404` / `redirect` / `hang`) so you can cover non-2xx, redirect and the
10s client-timeout cases from one script. A working copy lives at `/tmp/mock_windsurf.py`
during a session; re-create it if missing.

Useful scenario levers:
- File fallback: just stop the listener on 3000.
- Both transports failing: start uvicorn with `HOME=/proc` so `~/.ai-router` can't be created.
- Redirects are NOT followed by httpx by default → surfaces as `HTTP 307`.
- Timeout case: mock sleeps > 10s; the request returns in ~10s with a `ReadTimeout`.

## Triggering flows
- REST: `POST /api/tasks` with `{"prompt":..., "providers":["ollama"], "push_to_windsurf":true}`.
- Manual push: `POST /api/tasks/{task_id}/push-windsurf` (404 for unknown ids).
- WebSocket: connect `ws://127.0.0.1:8000/ws`, send
  `{"event":"submit_task","data":{"prompt":"...","providers":["ollama"],"push_to_windsurf":true}}`;
  read until `task_completed`. The `websockets` package is already in requirements.
- The frontend (`app/static/index.html`, served at `/`) never sends `push_to_windsurf`, so the
  Windsurf feature is **not reachable from the UI** — test it over HTTP/WS and use
  `GET /api/tasks?limit=1` in the browser when you need visual evidence of task metadata.

## Gotchas
- Do NOT use `pkill -f mock_windsurf.py` — the pattern matches the exec tool's own shell
  command line and kills your shell. Kill by PID from `ss -ltnp | grep :3000` instead, and
  start background helpers with `setsid nohup ... < /dev/null &` so they survive.
- Base-branch comparisons: `git worktree add /tmp/base-wt <base-branch>`, copy `.env` in,
  and run it on a second port (8001) with the same venv; remove the worktree afterwards.
