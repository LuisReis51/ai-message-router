# AI Message Router

An **AI boardroom** service that fans out tasks to multiple LLM providers simultaneously and aggregates their responses. Results stream in real-time via WebSocket and can be pushed directly into Windsurf IDE.

## Supported Providers

| Provider  | API               | Streaming |
|-----------|-------------------|-----------|
| ChatGPT   | OpenAI API        | Yes       |
| Claude    | Anthropic API     | Yes       |
| Gemini    | Google GenAI      | No        |
| Grok      | xAI (OpenAI-compat) | Yes     |
| DeepSeek  | OpenAI-compatible | Yes       |
| Ollama    | Local HTTP API    | Yes       |

## Architecture

```
Client (REST / WebSocket)
    │
    ▼
┌─────────────────────────┐
│    FastAPI Application   │
│  ┌───────────────────┐  │
│  │    AI Router       │  │  ← Fan-out + concurrency control
│  │  ┌─────┐ ┌─────┐  │  │
│  │  │ GPT │ │Claude│  │  │
│  │  └─────┘ └─────┘  │  │
│  │  ┌─────┐ ┌─────┐  │  │
│  │  │Gemini│ │ Grok│  │  │
│  │  └─────┘ └─────┘  │  │
│  │  ┌─────┐ ┌──────┐ │  │
│  │  │Deep  │ │Ollama│ │  │
│  │  │Seek  │ │(local)││  │
│  │  └─────┘ └──────┘ │  │
│  └───────────────────┘  │
│          │               │
│  ┌───────┴────────┐     │
│  │  Redis Cache    │     │  ← Task persistence + pub/sub
│  └────────────────┘     │
│          │               │
│  ┌───────┴────────┐     │
│  │ Windsurf Push   │     │  ← HTTP POST or file-based injection
│  └────────────────┘     │
└─────────────────────────┘
```

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/LuisReis51/ai-message-router.git
cd ai-message-router
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Run

```bash
# Option A: Direct
uvicorn app.main:app --reload

# Option B: Docker Compose (includes Redis)
docker compose up --build
```

The server starts at `http://localhost:8000`.

- **API docs**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health

## API Reference

### REST Endpoints

| Method | Path                            | Description                           |
|--------|---------------------------------|---------------------------------------|
| POST   | `/api/tasks`                    | Submit a task to the AI boardroom     |
| GET    | `/api/tasks`                    | List recent tasks                     |
| GET    | `/api/tasks/{task_id}`          | Get a specific task result            |
| GET    | `/api/providers`                | List all providers and their status   |
| GET    | `/api/providers/enabled`        | List enabled provider names           |
| POST   | `/api/tasks/{task_id}/push-windsurf` | Push results to Windsurf IDE    |

### Submit a Task

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain quantum computing in 3 sentences",
    "providers": ["openai", "claude", "gemini"],
    "temperature": 0.7,
    "push_to_windsurf": false
  }'
```

### WebSocket

Connect to `ws://localhost:8000/ws` and send JSON messages:

```json
{
  "event": "submit_task",
  "data": {
    "prompt": "What is the meaning of life?",
    "providers": ["openai", "claude"],
    "push_to_windsurf": true
  }
}
```

Server streams back:
1. `task_started` - Task has been queued
2. `provider_response` - One per provider as they complete
3. `task_completed` - Final aggregated result

### Windsurf Integration

Results are pushed to Windsurf via:
1. **HTTP POST** to the Windsurf extension's local API (`http://localhost:3000/api/ai-router/results`)
2. **File fallback** - writes JSON to `~/.ai-router/windsurf/{task_id}.json` for extension pickup

Set `push_to_windsurf: true` in your task request, or call `POST /api/tasks/{task_id}/push-windsurf` after.

Only the HTTP push reaches the IDE. `delivered` is true for that case alone — a
successful file fallback leaves it false, since the payload is merely persisted
for the extension to pick up later. The outcome is reported on the task as
`metadata.windsurf` (and `metadata.windsurf_pushed`, an alias for `delivered`):

```json
{
  "delivered": false,
  "channel": "file",
  "endpoint": "http://localhost:3000/api/ai-router/results",
  "filepath": "/home/you/.ai-router/windsurf/d6e901c535a9.json",
  "http_error": "ConnectError: All connection attempts failed",
  "file_error": null
}
```

If the HTTP push and the file write both fail, `channel` is `null` and both
error fields are populated.

## Configuration

All configuration is via environment variables (or `.env` file):

| Variable            | Default                      | Description                    |
|---------------------|------------------------------|--------------------------------|
| `OPENAI_API_KEY`    | -                            | OpenAI API key                 |
| `ANTHROPIC_API_KEY` | -                            | Anthropic API key              |
| `GEMINI_API_KEY`    | -                            | Google Gemini API key          |
| `GROK_API_KEY`      | -                            | xAI Grok API key               |
| `DEEPSEEK_API_KEY`  | -                            | DeepSeek API key               |
| `OLLAMA_BASE_URL`   | `http://localhost:11434`     | Ollama server URL              |
| `REDIS_URL`         | `redis://localhost:6379/0`   | Redis connection URL           |
| `PROVIDER_TIMEOUT`  | `60`                         | Timeout per provider (seconds) |
| `MAX_CONCURRENCY`   | `6`                          | Max simultaneous API calls     |

Providers are auto-enabled when their API key is set.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Lint
ruff check app/

# Format
ruff format app/

# Test
pytest
```
