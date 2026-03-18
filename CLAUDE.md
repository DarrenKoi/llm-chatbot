# LLM Chatbot

Flask-based chatbot on the internal "Cube" platform, powered by local LLMs.

## Rules

- **No external LLM services** — never use OpenAI, Anthropic, or any cloud AI APIs. All LLM calls go through local endpoints using OpenAI-compatible format (`/v1/chat/completions`).
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
- `api/cdn/`, `api/cube/`, `api/llm/` — API domain packages
- `api/conversation_service.py` — conversation history storage
- `api/llm/tools/` — tool-use functions callable by the LLM (chart creation, data queries)

## Dev Environment

- Code at home (no Cube/LLM access), test at office
- Use `.env` file for local overrides; never commit it
- `pip install -r requirements.txt` to set up

## Testing

- `pytest tests/ -v` — run all tests (works at home, no external services needed)
- Tests use mocks for LLM, Redis, MongoDB, and Cube APIs
- Test files: `tests/test_*.py`, shared fixtures in `tests/conftest.py`
