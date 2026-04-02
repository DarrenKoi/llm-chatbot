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

## Dedicated Scheduler Worker

Run APScheduler as a separate process instead of inside the Flask web workers:

```bash
python scheduler_worker.py
```

When `wsgi.ini` uses `attach-daemon = python scheduler_worker.py`, keep `APP_START_SCHEDULER=false` so only the dedicated scheduler daemon owns APScheduler. This avoids starting extra schedulers inside each Flask web worker.
