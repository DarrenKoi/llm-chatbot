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

# Cube
CUBE_API_TOKEN = os.environ.get("CUBE_API_TOKEN", "")
CUBE_API_URL = os.environ.get("CUBE_API_URL", "")

# Flask
APP_NAME = os.environ.get("APP_NAME", "llm_chatbot")
APP_ENV = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development"))

# Redis (empty = in-memory fallback)
REDIS_URL = os.environ.get("REDIS_URL", "")
REDIS_FALLBACK_URL = os.environ.get("REDIS_FALLBACK_URL", "")

# Scheduler (Redis-based distributed lock)
SCHEDULER_REDIS_URL = os.environ.get("SCHEDULER_REDIS_URL", REDIS_FALLBACK_URL or REDIS_URL)
SCHEDULER_LOCK_PREFIX = os.environ.get("SCHEDULER_LOCK_PREFIX", "scheduler:sknn_v3")
SCHEDULER_LOCK_TTL_SECONDS = int(os.environ.get("SCHEDULER_LOCK_TTL_SECONDS", 3600))
SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS = int(os.environ.get("SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS", 30))
SCHEDULER_JOB_MISFIRE_GRACE_SECONDS = int(os.environ.get("SCHEDULER_JOB_MISFIRE_GRACE_SECONDS", 60))

# Logging
LOG_DIR = Path(os.environ.get("LOG_DIR", str(BASE_DIR / "logs"))).expanduser()
ACTIVITY_LOG_THEME = os.environ.get("ACTIVITY_LOG_THEME", "activity")
# Backward-compatible alias for legacy callers; the logger now uses LOG_DIR/theme layout.
ACTIVITY_LOG_DIR = Path(os.environ.get("ACTIVITY_LOG_DIR", str(LOG_DIR / ACTIVITY_LOG_THEME))).expanduser()
LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", 7))
ACTIVITY_LOG_MAX_BYTES = int(os.environ.get("ACTIVITY_LOG_MAX_BYTES", 20 * 1024 * 1024))
ACTIVITY_LOG_BACKUP_COUNT = int(os.environ.get("ACTIVITY_LOG_BACKUP_COUNT", 30))
TOPIC_LOG_MAX_BYTES = int(os.environ.get("TOPIC_LOG_MAX_BYTES", 10 * 1024 * 1024))
TOPIC_LOG_BACKUP_COUNT = int(os.environ.get("TOPIC_LOG_BACKUP_COUNT", 14))

# Conversation history
CONVERSATION_MAX_MESSAGES = int(os.environ.get("CONVERSATION_MAX_MESSAGES", 20))
CONVERSATION_TTL_SECONDS = int(os.environ.get("CONVERSATION_TTL_SECONDS", 3600))

# Workspace / PVC (cross-platform)
_linux_workspace_root = Path("/project/workSpace")
if system() == "Linux" and _linux_workspace_root.exists():
    _default_workspace_root = _linux_workspace_root
else:
    _default_workspace_root = BASE_DIR

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(_default_workspace_root))).expanduser()
PVC_ROOT = Path(os.environ.get("PVC_ROOT", str(WORKSPACE_ROOT / "pvc" / "download"))).expanduser()

# CDN
CDN_STORAGE_DIR = Path(os.environ.get("CDN_STORAGE_DIR", str(PVC_ROOT / "cdn" / "files"))).expanduser()
CDN_BASE_URL = os.environ.get("CDN_BASE_URL", "http://localhost:5000/cdn/files")
CDN_MAX_UPLOAD_BYTES = int(os.environ.get("CDN_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
CDN_STORAGE_LIMIT_BYTES = int(os.environ.get("CDN_STORAGE_LIMIT_BYTES", 8 * 1024 * 1024 * 1024))
CDN_ALLOWED_EXTENSIONS = tuple(
    ext.strip().lower()
    for ext in os.environ.get("CDN_ALLOWED_EXTENSIONS", "png,jpg,jpeg,gif,webp,xlsx,pptx,docx").split(",")
    if ext.strip()
)
CDN_IMAGE_TTL_SECONDS = int(os.environ.get("CDN_IMAGE_TTL_SECONDS", 0))
CDN_REDIS_URL = os.environ.get("CDN_REDIS_URL", REDIS_FALLBACK_URL or REDIS_URL)
CDN_RETENTION_DAYS = int(os.environ.get("CDN_RETENTION_DAYS", 30))
CDN_MAX_RESIZE_WIDTH = int(os.environ.get("CDN_MAX_RESIZE_WIDTH", 2048))
CDN_MAX_RESIZE_HEIGHT = int(os.environ.get("CDN_MAX_RESIZE_HEIGHT", 2048))
CDN_THUMBNAIL_WIDTH = int(os.environ.get("CDN_THUMBNAIL_WIDTH", 320))
CDN_THUMBNAIL_HEIGHT = int(os.environ.get("CDN_THUMBNAIL_HEIGHT", 320))
