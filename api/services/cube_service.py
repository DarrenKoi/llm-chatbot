import logging

from api import config

logger = logging.getLogger(__name__)


def send_text_message(channel_id: str, text: str):
    """Stub: Send a text message to a Cube channel."""
    logger.info(f"[CUBE STUB] Text to {channel_id}: {text[:100]}...")
    # TODO: implement with Cube API docs


def send_rich_notification(channel_id: str, text: str, image_url: str = None):
    """Stub: Send a rich notification (text + optional image) to a Cube channel."""
    logger.info(f"[CUBE STUB] Rich notification to {channel_id}: text={text[:100]}..., image={image_url}")
    # TODO: implement with Cube API docs
