import os
from pathlib import Path
from platform import system

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv(BASE_DIR / ".env.example")

# LLM
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "no-key")
LLM_MODEL = os.environ.get("LLM_MODEL", "kimi-k2.5")
LLM_SYSTEM_PROMPT = os.environ.get("LLM_SYSTEM_PROMPT", "You are a helpful assistant.")

# Cube
CUBE_API_TOKEN = os.environ.get("CUBE_API_TOKEN", "")
CUBE_API_URL = os.environ.get("CUBE_API_URL", "")

# Flask
FLASK_PORT = int(os.environ.get("FLASK_PORT", 5000))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", 4))

# MongoDB
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "llm_chatbot")

# Redis (empty = in-memory fallback)
REDIS_URL = os.environ.get("REDIS_URL", "")
REDIS_FALLBACK_URL = os.environ.get("REDIS_FALLBACK_URL", "")

# Logging
LOG_DIR = os.environ.get("LOG_DIR", str(BASE_DIR / "logs"))

# Conversation history
CONVERSATION_MAX_MESSAGES = int(os.environ.get("CONVERSATION_MAX_MESSAGES", 20))
CONVERSATION_TTL_SECONDS = int(os.environ.get("CONVERSATION_TTL_SECONDS", 3600))

# Chart images
CHART_IMAGE_DIR = os.environ.get("CHART_IMAGE_DIR", str(BASE_DIR / "data" / "chart-images"))
CHART_IMAGE_BASE_URL = os.environ.get("CHART_IMAGE_BASE_URL", "http://localhost:5000/static/charts")

# Workspace / PVC (cross-platform)
_linux_workspace_root = Path("/project/workSpace")
if system() == "Linux" and _linux_workspace_root.exists():
    _default_workspace_root = _linux_workspace_root
else:
    _default_workspace_root = BASE_DIR

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(_default_workspace_root))).expanduser()
PVC_ROOT = Path(os.environ.get("PVC_ROOT", str(WORKSPACE_ROOT / "pvc" / "download"))).expanduser()

# CDN
CDN_STORAGE_DIR = Path(os.environ.get("CDN_STORAGE_DIR", str(PVC_ROOT / "cdn" / "images"))).expanduser()
CDN_BASE_URL = os.environ.get("CDN_BASE_URL", "http://localhost:5000/cdn/images")
CDN_MAX_UPLOAD_BYTES = int(os.environ.get("CDN_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
CDN_ALLOWED_EXTENSIONS = tuple(
    ext.strip().lower()
    for ext in os.environ.get("CDN_ALLOWED_EXTENSIONS", "png,jpg,jpeg,gif,webp").split(",")
    if ext.strip()
)
CDN_IMAGE_TTL_SECONDS = int(os.environ.get("CDN_IMAGE_TTL_SECONDS", 0))
CDN_REDIS_URL = os.environ.get("CDN_REDIS_URL", REDIS_FALLBACK_URL or REDIS_URL)
