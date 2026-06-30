import os
from pathlib import Path
from platform import system

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
# 기본적으로 .env를 환경변수보다 우선시킨다(override=True) — 프로덕션(uWSGI)에서는
# 셸/배포 설정이 LLM_* 같은 변수를 이미 export해 두는 경우가 많아, override 없이는
# .env 수정이 무시된다(기존 환경변수가 우선). .env가 항상 최종 권위를 갖도록 보장한다.
# 테스트는 DOTENV_OVERRIDE=false로 끄고 monkeypatch한 환경변수를 사용한다.
_DOTENV_OVERRIDE = os.environ.get("DOTENV_OVERRIDE", "true").lower() in ("true", "1", "yes")
if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=_DOTENV_OVERRIDE)
else:
    load_dotenv(BASE_DIR / ".env.example", override=_DOTENV_OVERRIDE)

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
    name.strip() for name in os.environ.get("CUBE_BOT_USERNAMES", CUBE_BOT_NAME).split(",") if name.strip()
)
CUBE_TIMEOUT_SECONDS = int(os.environ.get("CUBE_TIMEOUT_SECONDS", 10))
CUBE_MESSAGE_MAX_LINES = int(os.environ.get("CUBE_MESSAGE_MAX_LINES", 40))
CUBE_RICH_ROUTING_ENABLED = os.environ.get("CUBE_RICH_ROUTING_ENABLED", "false").lower() in ("true", "1", "yes")
CUBE_DELIVERY_DELAY_SECONDS = float(os.environ.get("CUBE_DELIVERY_DELAY_SECONDS", "1"))

# LLM
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_SYSTEM_PROMPT_OVERRIDE = os.environ.get("LLM_SYSTEM_PROMPT_OVERRIDE", "")
LLM_TIMEZONE = os.environ.get("LLM_TIMEZONE", "Asia/Seoul")
LLM_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT_SECONDS", 30))
LLM_HEALTHCHECK_TIMEOUT_SECONDS = int(os.environ.get("LLM_HEALTHCHECK_TIMEOUT_SECONDS", 10))
LLM_HEALTHCHECK_ON_STARTUP = os.environ.get("LLM_HEALTHCHECK_ON_STARTUP", "true").lower() in ("true", "1", "yes")
LLM_THINKING_MESSAGE = os.environ.get("LLM_THINKING_MESSAGE", "잠시만요, 답변을 준비하고 있어요... 🤔")
LLM_THINKING_MESSAGE_DELAY_SECONDS = float(os.environ.get("LLM_THINKING_MESSAGE_DELAY_SECONDS", "5"))

# Flask
APP_NAME = os.environ.get("APP_NAME", "llm_chatbot")
APP_ENV = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development"))

# Web chat dev fallback — only honored when the request comes from localhost.
# Leave empty in production. When set, the LASTUSER cookie may be omitted on local requests.
WEB_CHAT_DEV_USER = os.environ.get("WEB_CHAT_DEV_USER", "").strip()
WEB_CHAT_DEV_USER_NAME = os.environ.get("WEB_CHAT_DEV_USER_NAME", "").strip()
# MongoDB (conversation storage; empty = in-memory fallback)
AFM_MONGO_URI = os.environ.get("AFM_MONGO_URI", "")
AFM_DB_NAME = os.environ.get("AFM_DB_NAME", "itc-afm-data-platform-mongodb")
CONVERSATION_COLLECTION_NAME = os.environ.get("CONVERSATION_COLLECTION_NAME", "cube_conversation_history")
LANGGRAPH_CHECKPOINT_COLLECTION_NAME = os.environ.get("LANGGRAPH_CHECKPOINT_COLLECTION_NAME", "cube_checkpoints")
LANGGRAPH_CHECKPOINT_WRITES_COLLECTION_NAME = os.environ.get(
    "LANGGRAPH_CHECKPOINT_WRITES_COLLECTION_NAME",
    "cube_checkpoint_writes",
)
CHECKPOINT_TTL_SECONDS = int(os.environ.get("CHECKPOINT_TTL_SECONDS", 3 * 24 * 60 * 60))

# Redis (empty = in-memory fallback)
REDIS_URL = os.environ.get("REDIS_URL", "")

# User profile
USER_PROFILE_PROVIDER_CALLABLE = os.environ.get("USER_PROFILE_PROVIDER_CALLABLE", "")
USER_PROFILE_API_URL = os.environ.get("USER_PROFILE_API_URL", "")
USER_PROFILE_API_TIMEOUT_SECONDS = float(os.environ.get("USER_PROFILE_API_TIMEOUT_SECONDS", "1.5"))
USER_PROFILE_REDIS_URL = os.environ.get("USER_PROFILE_REDIS_URL", REDIS_URL)
USER_PROFILE_REDIS_KEY_PREFIX = os.environ.get("USER_PROFILE_REDIS_KEY_PREFIX", "user:profile")

# member_info (사내 구성원 디렉터리 REST — oss-mcp-fastapi)
# 빈 BASE_URL이거나 ENABLED=false면 모든 member_info 기능은 무동작(집/테스트 안전).
MEMBER_INFO_ENABLED = os.environ.get("MEMBER_INFO_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
MEMBER_INFO_BASE_URL = os.environ.get("MEMBER_INFO_BASE_URL", "").strip().rstrip("/")
MEMBER_INFO_TIMEOUT_SECONDS = float(os.environ.get("MEMBER_INFO_TIMEOUT_SECONDS", "2.0"))
MEMBER_INFO_RESULT_LIMIT = int(os.environ.get("MEMBER_INFO_RESULT_LIMIT", "5"))
MEMBER_INFO_INCLUDE_CONTACT = os.environ.get("MEMBER_INFO_INCLUDE_CONTACT", "true").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# Cube queue (shares the primary Redis URL)
CUBE_QUEUE_REDIS_URL = REDIS_URL
CUBE_QUEUE_NAME = os.environ.get("CUBE_QUEUE_NAME", "cube:incoming")
CUBE_QUEUE_PROCESSING_NAME = os.environ.get("CUBE_QUEUE_PROCESSING_NAME", f"{CUBE_QUEUE_NAME}:processing")
CUBE_MESSAGE_DEDUP_TTL_SECONDS = int(os.environ.get("CUBE_MESSAGE_DEDUP_TTL_SECONDS", 3600))
# 처리 완료한 메시지의 멱등성 마커 보존 시간(초). 워커 재시작 복구(recover) 시 이미 응답을
# 보낸 메시지를 다시 처리해 중복 답변이 나가는 것을 막는다. message_id 기준으로 기록한다.
CUBE_MESSAGE_PROCESSED_TTL_SECONDS = int(os.environ.get("CUBE_MESSAGE_PROCESSED_TTL_SECONDS", 3600))
# 큐에 쌓인 메시지가 이 시간(초)보다 오래되면 워커가 응답하지 않고 폐기한다.
# LLM/워커 다운 후 재기동 시 오래된 질문에 뒤늦게 답하는 문제를 방지한다. 0(또는 음수)이면 비활성화.
CUBE_QUEUE_MESSAGE_TTL_SECONDS = int(os.environ.get("CUBE_QUEUE_MESSAGE_TTL_SECONDS", 300))
CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS = int(os.environ.get("CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS", 5))
CUBE_QUEUE_MAX_RETRIES = int(os.environ.get("CUBE_QUEUE_MAX_RETRIES", 3))
CUBE_WORKER_RETRY_DELAY_SECONDS = int(os.environ.get("CUBE_WORKER_RETRY_DELAY_SECONDS", 5))

# Scheduler (Redis-based distributed lock)
SCHEDULER_REDIS_URL = os.environ.get("SCHEDULER_REDIS_URL", REDIS_URL)
SCHEDULER_LOCK_PREFIX = os.environ.get("SCHEDULER_LOCK_PREFIX", "scheduler:sknn_v3")
SCHEDULER_LOCK_TTL_SECONDS = int(os.environ.get("SCHEDULER_LOCK_TTL_SECONDS", 3600))
SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS = int(os.environ.get("SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS", 30))
SCHEDULER_JOB_MISFIRE_GRACE_SECONDS = int(os.environ.get("SCHEDULER_JOB_MISFIRE_GRACE_SECONDS", 60))
SCHEDULER_WORKER_IDLE_SECONDS = int(os.environ.get("SCHEDULER_WORKER_IDLE_SECONDS", 60))

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

# Conversation history storage
CONVERSATION_BACKEND = os.environ.get("CONVERSATION_BACKEND", "auto").strip().lower()
CONVERSATION_LOCAL_DIR = Path(
    os.environ.get("CONVERSATION_LOCAL_DIR", str(BASE_DIR / "var" / "conversation_history"))
).expanduser()

# MCP cache
MCP_CACHE_DIR = Path(os.environ.get("MCP_CACHE_DIR", str(BASE_DIR / "var" / "mcp_cache"))).expanduser()

# Conversation history
CONVERSATION_MAX_MESSAGES = int(os.environ.get("CONVERSATION_MAX_MESSAGES", 5))
CONVERSATION_TTL_SECONDS = int(os.environ.get("CONVERSATION_TTL_SECONDS", 0))

# Workspace (cross-platform)
_linux_workspace_root = Path("/project/workSpace")
if system() == "Linux" and _linux_workspace_root.exists():
    _default_workspace_root = _linux_workspace_root
else:
    _default_workspace_root = BASE_DIR

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(_default_workspace_root))).expanduser()
WEB_APP_URL = os.environ.get(
    "WEB_APP_URL",
    "http://itc-1stop-solution-llm-webapp.aipp02.skhynix.com",
).rstrip("/")
CUBE_RICHNOTIFICATION_CALLBACK_URL = os.environ.get(
    "CUBE_RICHNOTIFICATION_CALLBACK_URL",
    f"{WEB_APP_URL}/api/v1/cube/richnotification/callback",
).rstrip("/")

# File delivery
FILE_DELIVERY_STORAGE_DIR = Path(
    os.environ.get(
        "FILE_DELIVERY_STORAGE_DIR",
        "/project/workSpace/itc-1stop-solution-pjt-shared/file_delivery",
    )
).expanduser()
FILE_DELIVERY_BASE_URL = os.environ.get(
    "FILE_DELIVERY_BASE_URL",
    f"{WEB_APP_URL}/file-delivery/files",
).rstrip("/")
FILE_DELIVERY_MAX_UPLOAD_BYTES = int(os.environ.get("FILE_DELIVERY_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
FILE_DELIVERY_STORAGE_LIMIT_BYTES = int(os.environ.get("FILE_DELIVERY_STORAGE_LIMIT_BYTES", 8 * 1024 * 1024 * 1024))
FILE_DELIVERY_ALLOWED_EXTENSIONS = tuple(
    ext.strip().lower()
    for ext in os.environ.get(
        "FILE_DELIVERY_ALLOWED_EXTENSIONS",
        "png,jpg,jpeg,gif,webp,xlsx,pptx,docx,txt,pdf",
    ).split(",")
    if ext.strip()
)
FILE_DELIVERY_IMAGE_TTL_SECONDS = int(os.environ.get("FILE_DELIVERY_IMAGE_TTL_SECONDS", 0))
FILE_DELIVERY_REDIS_URL = os.environ.get("FILE_DELIVERY_REDIS_URL", REDIS_URL)
FILE_DELIVERY_RETENTION_DAYS = int(os.environ.get("FILE_DELIVERY_RETENTION_DAYS", 21))
FILE_DELIVERY_CLEANUP_HOUR = int(os.environ.get("FILE_DELIVERY_CLEANUP_HOUR", 1))
FILE_DELIVERY_CLEANUP_MINUTE = int(os.environ.get("FILE_DELIVERY_CLEANUP_MINUTE", 0))
FILE_DELIVERY_MAX_RESIZE_WIDTH = int(os.environ.get("FILE_DELIVERY_MAX_RESIZE_WIDTH", 2048))
FILE_DELIVERY_MAX_RESIZE_HEIGHT = int(os.environ.get("FILE_DELIVERY_MAX_RESIZE_HEIGHT", 2048))
FILE_DELIVERY_THUMBNAIL_WIDTH = int(os.environ.get("FILE_DELIVERY_THUMBNAIL_WIDTH", 320))
FILE_DELIVERY_THUMBNAIL_HEIGHT = int(os.environ.get("FILE_DELIVERY_THUMBNAIL_HEIGHT", 320))
