# Repository Guidelines

## Project Structure & Module Organization
- `index.py`: local dev runner that boots the Flask app from `api.create_application()`.
- `api/config.py`: all environment-driven configuration (Cube, Redis, Flask app metadata, logging, CDN paths).
- `api/cdn/`, `api/cube/`: API-domain packages and related routers/services.
- `api/conversation_service.py`: conversation history backend and retention logic.
- `tests/`: pytest suite (`test_*.py`) plus shared fixtures in `tests/conftest.py`.
- `wsgi.ini`: uWSGI runtime configuration for deployment.

## Build, Test, and Development Commands
- `pip install -r requirements.txt`: install app and test dependencies.
- `python index.py`: run locally on fixed `0.0.0.0:5000`.
- `pytest tests/ -v`: run all tests with verbose output.
- `uwsgi --ini wsgi.ini`: run with uWSGI settings used by this repo.

## Coding Style & Naming Conventions
- Keep route and service function names descriptive (`receive_cube`, `append_messages` style).
- Prefer explicit type hints in new or changed code.
- Do not use `from __future__ import annotations`; write annotations directly without that import.
- Use `pathlib.Path` for file paths when adding/updating path logic.
- Keep user-facing strings compatible with Korean-language workflows.

## Testing Guidelines
- Framework: `pytest` with `pytest-mock`.
- Place tests under `tests/` and name files `test_*.py`.
- Add unit tests for new service logic and route-level behavior.
- Mock external dependencies (Cube API, Redis, filesystem/image libraries) to keep tests deterministic.

## Commit & Pull Request Guidelines
- Recent history shows Korean commit usage; use concise Korean commit messages in imperative style.
- Avoid generic messages like `Auto-commit`; describe intent and scope.
- Recommended format: `<area>: <change summary>` (example: `api: 대화 이력 TTL 처리 개선`).
- PRs should include: what changed, why, test evidence (`pytest tests/ -v`), and related issue/context.

## Security & Configuration Tips
- Do not hardcode secrets or service URLs; use environment variables (`.env` locally, never commit it).
- Keep integration points and storage paths environment-driven.

## Auto Git Sync
- After completing any code generation or edit task, run:
  - `git add -A`
  - `git commit -m "<short summary in Korean>"`
  - `git push origin $(git branch --show-current)`
- If there are no changes to commit, skip commit/push.
- If commit or push fails, report the error immediately.
