# LLM Chatbot

Cube webhook/CDN server. Tool calling and model orchestration are handled in a separate repository.

## Python Version

This project is based on Python 3.11.

- Local version file: `.python-version` (`3.11`)
- Runtime hint file: `runtime.txt` (`python-3.11.11`)

## Quick Start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python index.py
```

The local dev server listens on fixed port `5000`.

## Code Style

This repository uses `ruff` for Python linting and formatting.

```bash
ruff check .
ruff format .
```

If you want `ruff` to rewrite simple lint issues automatically as well:

```bash
ruff check . --fix
```

## Docs

- Workflow onboarding guide: `doc/guideline/workflow_추가_가이드.md`
- Router auto-registration guide: `doc/guideline/router_가이드.md`

## Dedicated Scheduler Worker

`wsgi.ini` attaches `scheduler_worker.py` as a dedicated daemon (`attach-daemon`). The web app never starts a scheduler — only the daemon process owns APScheduler.

```bash
python scheduler_worker.py
```
