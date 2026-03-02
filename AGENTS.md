# Repository Guidelines

## Project Structure & Module Organization
- `index.py`: Flask Blueprint entrypoint (`chatbot_bp`) with HTTP routes (`/health`, `/api/v1/receive/cube`) and local dev runner.
- `config.py`: all environment-driven configuration (LLM endpoint, Cube, Redis, MongoDB, Flask, chart paths).
- `services/`: core business logic (`llm_service.py`, `conversation_service.py`, `cube_service.py`, `log_service.py`).
- `tools/`: LLM tool-use helpers (for example `create_chart.py`, `query_data.py`).
- `tests/`: pytest suite (`test_*.py`) plus shared fixtures in `tests/conftest.py`.
- `wsgi.ini`: uWSGI runtime configuration for deployment.

## Build, Test, and Development Commands
- `pip install -r requirements.txt`: install app and test dependencies.
- `python index.py`: run locally (default `0.0.0.0:5000`, configurable via `FLASK_PORT`).
- `pytest tests/ -v`: run all tests with verbose output.
- `uwsgi --ini wsgi.ini`: run with uWSGI settings used by this repo.

## Coding Style & Naming Conventions
- Follow Python conventions: 4-space indentation, `snake_case` for functions/variables, `PascalCase` for classes.
- Keep route and service function names descriptive (`receive_cube`, `append_messages` style).
- Prefer explicit type hints in new or changed code.
- Use `pathlib.Path` for file paths when adding/updating path logic.
- Keep user-facing strings compatible with Korean-language workflows.

## Testing Guidelines
- Framework: `pytest` with `pytest-mock`.
- Place tests under `tests/` and name files `test_*.py`.
- Add unit tests for new service/tool logic and route-level behavior.
- Mock external dependencies (LLM endpoint, Cube API, Redis, MongoDB) to keep tests deterministic.

## Commit & Pull Request Guidelines
- Recent history shows Korean commit usage; use concise Korean commit messages in imperative style.
- Avoid generic messages like `Auto-commit`; describe intent and scope.
- Recommended format: `<area>: <change summary>` (example: `services: 대화 이력 TTL 처리 개선`).
- PRs should include: what changed, why, test evidence (`pytest tests/ -v`), and related issue/context.

## Security & Configuration Tips
- Do not hardcode secrets or service URLs; use environment variables (`.env` locally, never commit it).
- Keep LLM calls on OpenAI-compatible local/internal endpoints configured via `LLM_BASE_URL`.

## Auto Git Sync
- After completing any code generation or edit task, run:
  - `git add -A`
  - `git commit -m "<short summary in Korean>"`
  - `git push origin $(git branch --show-current)`
- If there are no changes to commit, skip commit/push.
- If commit or push fails, report the error immediately.
