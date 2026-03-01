import os

from dotenv import load_dotenv

load_dotenv()

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

# Redis (empty = in-memory fallback)
REDIS_URL = os.environ.get("REDIS_URL", "")

# Conversation history
CONVERSATION_MAX_MESSAGES = int(os.environ.get("CONVERSATION_MAX_MESSAGES", 20))
CONVERSATION_TTL_SECONDS = int(os.environ.get("CONVERSATION_TTL_SECONDS", 3600))

# Chart images
CHART_IMAGE_DIR = os.environ.get("CHART_IMAGE_DIR", os.path.join(os.path.dirname(__file__), "data", "chart-images"))
CHART_IMAGE_BASE_URL = os.environ.get("CHART_IMAGE_BASE_URL", "http://localhost:5000/static/charts")
