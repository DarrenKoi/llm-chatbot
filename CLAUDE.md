# LLM Chatbot

Flask-based chatbot on the internal "Cube" platform, powered by local LLMs.

## Rules

- **No external LLM services** — never use OpenAI, Anthropic, or any cloud AI APIs. All LLM calls go through local endpoints using OpenAI-compatible format (`/v1/chat/completions`).
- **Environment-based config** — all secrets and service URLs come from env vars (see `config.py`). Never hardcode credentials or URLs.
- **Korean language support** — user messages arrive in Korean. Keep UI-facing strings and error messages compatible.

## Architecture

- `config.py` — all env-based configuration
- `index.py` — Flask routes and request handling (Blueprint: `chatbot_bp`)
- `services/` — business logic (LLM, Cube, conversation history, logging)
- `tools/` — tool-use functions callable by the LLM (chart creation, data queries)

## Dev Environment

- Code at home (no Cube/LLM access), test at office
- Use `.env` file for local overrides; never commit it
- `pip install -r requirements.txt` to set up
