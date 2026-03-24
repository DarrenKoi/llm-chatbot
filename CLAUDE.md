# LLM Chatbot

Flask-based Cube integration server with conversation persistence and CDN support.

## Rules

- **Environment-based config** — all secrets and service URLs come from env vars (see `api/config.py`). Never hardcode credentials or URLs.
- **Korean language support** — user messages arrive in Korean. Keep UI-facing strings and error messages compatible.
- **Use `pathlib`** — always use `pathlib.Path` for file paths instead of `os.path`. All OS compatibility matters.
- **Korean commit messages** — write git commit messages in Korean.

## Architecture

- `index.py` — simple entry point, imports `create_application` from `api`
- `wsgi.ini` — uWSGI configuration
- `api/__init__.py` — Flask app factory (`create_application`)
- `api/blueprint_loader.py` — automatic router discovery
- `api/config.py` — all env-based configuration
- `api/cdn/`, `api/cube/` — API domain packages
- `api/conversation_service.py` — conversation history storage
- `api/scheduled_tasks/` — scheduler infrastructure (lock, registry) and task packages
- `api/scheduled_tasks/tasks/` — auto-discovered simple tasks (cleanup, etc.)
- `api/scheduled_tasks/scan_member_info/` — hynix member info batch scan (service + task)

## Dev Environment

- Code at home (no Cube access), test at office
- Use `.env` file for local overrides; never commit it
- `pip install -r requirements.txt` to set up

## Testing

- `pytest tests/ -v` — run all tests (works at home, no external services needed)
- Tests use mocks for Redis, image/file processing, and Cube-related inputs
- Test files: `tests/test_*.py`, shared fixtures in `tests/conftest.py`
