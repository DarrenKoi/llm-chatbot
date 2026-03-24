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

Recommended environment flags:

```bash
APP_START_SCHEDULER=false
MEMBER_REFRESH_ENABLED=true
MEMBER_REFRESH_BATCH_SIZE=500
MEMBER_REFRESH_INTERVAL_MINUTES=432
```

`432` minutes is a 30-day cycle target for `50,000 / 500 = 100` runs.
