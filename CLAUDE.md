# LLM Chatbot

Flask-based Cube integration server with conversation persistence and CDN support.

## Rules

- **Environment-based config** — all secrets and service URLs come from env vars (see `api/config.py`). Never hardcode credentials or URLs.
- **Korean language support** — user messages arrive in Korean. Keep UI-facing strings and error messages compatible.
- **Use `pathlib`** — always use `pathlib.Path` for file paths instead of `os.path`. All OS compatibility matters.
- **No `from __future__ import annotations`** — write type hints directly without this import (project convention in `AGENTS.md`).
- **Korean commit messages** — write git commit messages in Korean.

## Architecture

- `index.py` — simple entry point, imports `create_application` from `api`
- `cube_worker.py`, `scheduler_worker.py` — top-level daemon entry points (attached via `wsgi.ini` `attach-daemon`)
- `wsgi.ini` — uWSGI configuration
- `api/__init__.py` — Flask app factory (`create_application`)
- `api/blueprint_loader.py` — automatic router discovery
- `api/config.py` — all env-based configuration
- `api/cube/` — Cube webhook, queue worker, rich-notification blocks
- `api/llm/` — LLM service and prompt assembly (OpenAI-compatible client)
- `api/workflows/` — LangGraph orchestrator, registered graphs (`start_chat`, `translator`)
- `api/mcp/` — MCP client, tool selector, executor
- `api/file_delivery/` — uploaded-file serving and cleanup
- `api/profile/`, `api/monitoring_service.py`, `api/mongo.py`
- `api/html_templates/` — server-rendered pages (landing, monitor, conversation, etc.)
- `api/conversation_service.py` — conversation history storage
- `api/scheduled_tasks/` — scheduler infrastructure (lock, registry) and task packages
- `api/scheduled_tasks/tasks/` — auto-discovered simple tasks (cleanup, etc.)
- `devtools/` — local dev scripts, Cube message generators, workflow dev harnesses (not shipped)

## Dev Environment

- Code at home (no Cube access), test at office
- Use `.env` file for local overrides; never commit it
- Empty `REDIS_URL` or `AFM_MONGO_URI` falls back to in-memory storage — useful for home dev, not for production.
- `pip install -r requirements.txt` to set up
- `python index.py` — run Flask dev server on `0.0.0.0:5000`
- `python cube_worker.py` / `python scheduler_worker.py` — run the daemons standalone (normally attached by uWSGI)
- `ruff check .` / `ruff format .` — lint and format (add `--fix` to auto-repair)

## Testing

- `pytest tests/ -v` — run all tests (works at home, no external services needed)
- Tests use mocks for Redis, image/file processing, and Cube-related inputs
- Test files: `tests/test_*.py`, shared fixtures in `tests/conftest.py`
