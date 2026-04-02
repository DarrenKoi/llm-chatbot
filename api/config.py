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
CUBE_API_ID = os.environ.get("CUBE_API_ID", "")
CUBE_API_TOKEN = os.environ.get("CUBE_API_TOKEN", "")
CUBE_API_URL = os.environ.get("CUBE_API_URL", "http://cube.skhynix.com:8888")
CUBE_MULTIMESSAGE_URL = os.environ.get("CUBE_MULTIMESSAGE_URL", f"{CUBE_API_URL}/api/multiMessage")
CUBE_RICHNOTIFICATION_URL = os.environ.get("CUBE_RICHNOTIFICATION_URL", f"{CUBE_API_URL}/legacy/richnotification")
CUBE_BOT_ID = os.environ.get("CUBE_BOT_ID", CUBE_API_ID)
CUBE_BOT_TOKEN = os.environ.get("CUBE_BOT_TOKEN", CUBE_API_TOKEN)
CUBE_BOT_NAME = os.environ.get("CUBE_BOT_NAME", "ITC OSS")
CUBE_BOT_USERNAMES = tuple(
    name.strip()
    for name in os.environ.get("CUBE_BOT_USERNAMES", CUBE_BOT_NAME).split(",")
    if name.strip()
)
CUBE_TIMEOUT_SECONDS = int(os.environ.get("CUBE_TIMEOUT_SECONDS", 10))

# LLM
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_SYSTEM_PROMPT_OVERRIDE = os.environ.get("LLM_SYSTEM_PROMPT_OVERRIDE", "")
LLM_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT_SECONDS", 30))
LLM_THINKING_MESSAGE = os.environ.get("LLM_THINKING_MESSAGE", "잠시만요, 답변을 준비하고 있어요... 🤔")

# Flask
APP_NAME = os.environ.get("APP_NAME", "llm_chatbot")
APP_ENV = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development"))
APP_START_SCHEDULER = os.environ.get("APP_START_SCHEDULER", "").strip().lower() in {"1", "true", "yes", "on"}

# MongoDB (conversation storage; empty = in-memory fallback)
AFM_MONGO_URI = os.environ.get("AFM_MONGO_URI", "")
AFM_DB_NAME = os.environ.get("AFM_DB_NAME", "itc-afm-data-platform-mongodb")

# Redis (empty = in-memory fallback)
REDIS_URL = os.environ.get("REDIS_URL", "")
REDIS_FALLBACK_URL = os.environ.get("REDIS_FALLBACK_URL", "")

# Cube queue (Redis-backed async worker)
CUBE_QUEUE_REDIS_URL = os.environ.get("CUBE_QUEUE_REDIS_URL", REDIS_FALLBACK_URL or REDIS_URL)
CUBE_QUEUE_NAME = os.environ.get("CUBE_QUEUE_NAME", "cube:incoming")
CUBE_QUEUE_PROCESSING_NAME = os.environ.get("CUBE_QUEUE_PROCESSING_NAME", f"{CUBE_QUEUE_NAME}:processing")
CUBE_MESSAGE_DEDUP_TTL_SECONDS = int(os.environ.get("CUBE_MESSAGE_DEDUP_TTL_SECONDS", 3600))
CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS = int(os.environ.get("CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS", 5))
CUBE_QUEUE_MAX_RETRIES = int(os.environ.get("CUBE_QUEUE_MAX_RETRIES", 3))
CUBE_WORKER_RETRY_DELAY_SECONDS = int(os.environ.get("CUBE_WORKER_RETRY_DELAY_SECONDS", 5))

# Scheduler (Redis-based distributed lock)
SCHEDULER_REDIS_URL = os.environ.get("SCHEDULER_REDIS_URL", REDIS_FALLBACK_URL or REDIS_URL)
SCHEDULER_LOCK_PREFIX = os.environ.get("SCHEDULER_LOCK_PREFIX", "scheduler:sknn_v3")
SCHEDULER_LOCK_TTL_SECONDS = int(os.environ.get("SCHEDULER_LOCK_TTL_SECONDS", 3600))
SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS = int(os.environ.get("SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS", 30))
SCHEDULER_JOB_MISFIRE_GRACE_SECONDS = int(os.environ.get("SCHEDULER_JOB_MISFIRE_GRACE_SECONDS", 60))
SCHEDULER_WORKER_IDLE_SECONDS = int(os.environ.get("SCHEDULER_WORKER_IDLE_SECONDS", 60))

# Scan member info batch scheduler
SCAN_MEMBER_INFO_ENABLED = os.environ.get("SCAN_MEMBER_INFO_ENABLED", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SCAN_MEMBER_INFO_REDIS_URL = os.environ.get(
    "SCAN_MEMBER_INFO_REDIS_URL",
    SCHEDULER_REDIS_URL or REDIS_FALLBACK_URL or REDIS_URL,
)
SCAN_MEMBER_INFO_STATE_KEY = os.environ.get("SCAN_MEMBER_INFO_STATE_KEY", "scan_member_info:state")
SCAN_MEMBER_INFO_BATCH_SIZE = int(os.environ.get("SCAN_MEMBER_INFO_BATCH_SIZE", 500))
SCAN_MEMBER_INFO_INTERVAL_MINUTES = int(os.environ.get("SCAN_MEMBER_INFO_INTERVAL_MINUTES", 432))
SCAN_MEMBER_INFO_DUMMY_TOTAL_COUNT = int(os.environ.get("SCAN_MEMBER_INFO_DUMMY_TOTAL_COUNT", 50000))

# Logging
LOG_DIR = Path(os.environ.get("LOG_DIR", str(BASE_DIR / "logs"))).expanduser()
LOG_TIMEZONE = os.environ.get("LOG_TIMEZONE", "Asia/Seoul")
ACTIVITY_LOG_THEME = os.environ.get("ACTIVITY_LOG_THEME", "activity")
# Backward-compatible alias for legacy callers; the logger now uses LOG_DIR/theme layout.
ACTIVITY_LOG_DIR = Path(os.environ.get("ACTIVITY_LOG_DIR", str(LOG_DIR / ACTIVITY_LOG_THEME))).expanduser()
LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", 7))
ACTIVITY_LOG_MAX_BYTES = int(os.environ.get("ACTIVITY_LOG_MAX_BYTES", 20 * 1024 * 1024))
ACTIVITY_LOG_BACKUP_COUNT = int(os.environ.get("ACTIVITY_LOG_BACKUP_COUNT", 30))
TOPIC_LOG_MAX_BYTES = int(os.environ.get("TOPIC_LOG_MAX_BYTES", 10 * 1024 * 1024))
TOPIC_LOG_BACKUP_COUNT = int(os.environ.get("TOPIC_LOG_BACKUP_COUNT", 14))

# Workflow state
WORKFLOW_STATE_DIR = Path(os.environ.get("WORKFLOW_STATE_DIR", str(BASE_DIR / "var" / "workflow_state"))).expanduser()

# MCP cache
MCP_CACHE_DIR = Path(os.environ.get("MCP_CACHE_DIR", str(BASE_DIR / "var" / "mcp_cache"))).expanduser()

# Conversation history
CONVERSATION_MAX_MESSAGES = int(os.environ.get("CONVERSATION_MAX_MESSAGES", 20))
CONVERSATION_TTL_SECONDS = int(os.environ.get("CONVERSATION_TTL_SECONDS", 3600))

# Workspace (cross-platform)
_linux_workspace_root = Path("/project/workSpace")
if system() == "Linux" and _linux_workspace_root.exists():
    _default_workspace_root = _linux_workspace_root
else:
    _default_workspace_root = BASE_DIR

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(_default_workspace_root))).expanduser()

# File delivery
FILE_DELIVERY_STORAGE_DIR = Path(
    os.environ.get(
        "FILE_DELIVERY_STORAGE_DIR",
        "/project/workSpace/itc-1stop-solution-pjt-shared/file_delivery",
    )
).expanduser()
FILE_DELIVERY_BASE_URL = os.environ.get(
    "FILE_DELIVERY_BASE_URL",
    "http://itc-1stop-solution-llm-webapp.aipp02.skhynix.com/file-delivery/files",
)
FILE_DELIVERY_MAX_UPLOAD_BYTES = int(os.environ.get("FILE_DELIVERY_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
FILE_DELIVERY_STORAGE_LIMIT_BYTES = int(
    os.environ.get("FILE_DELIVERY_STORAGE_LIMIT_BYTES", 8 * 1024 * 1024 * 1024)
)
FILE_DELIVERY_ALLOWED_EXTENSIONS = tuple(
    ext.strip().lower()
    for ext in os.environ.get(
        "FILE_DELIVERY_ALLOWED_EXTENSIONS",
        "png,jpg,jpeg,gif,webp,xlsx,pptx,docx",
    ).split(",")
    if ext.strip()
)
FILE_DELIVERY_IMAGE_TTL_SECONDS = int(
    os.environ.get("FILE_DELIVERY_IMAGE_TTL_SECONDS", 0)
)
FILE_DELIVERY_REDIS_URL = os.environ.get("FILE_DELIVERY_REDIS_URL", REDIS_FALLBACK_URL or REDIS_URL)
FILE_DELIVERY_RETENTION_DAYS = int(os.environ.get("FILE_DELIVERY_RETENTION_DAYS", 30))
FILE_DELIVERY_MAX_RESIZE_WIDTH = int(
    os.environ.get("FILE_DELIVERY_MAX_RESIZE_WIDTH", 2048)
)
FILE_DELIVERY_MAX_RESIZE_HEIGHT = int(
    os.environ.get("FILE_DELIVERY_MAX_RESIZE_HEIGHT", 2048)
)
FILE_DELIVERY_THUMBNAIL_WIDTH = int(
    os.environ.get("FILE_DELIVERY_THUMBNAIL_WIDTH", 320)
)
FILE_DELIVERY_THUMBNAIL_HEIGHT = int(
    os.environ.get("FILE_DELIVERY_THUMBNAIL_HEIGHT", 320)
)
