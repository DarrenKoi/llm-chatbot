import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.datastructures import FileStorage

from api import config

logger = logging.getLogger(__name__)

_metadata_backend = None

_CONTENT_TYPE_BY_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def _metadata_key(image_id: str) -> str:
    return f"cdn:image:{image_id}"


def _build_image_url(image_id: str) -> str:
    return f"{config.CDN_BASE_URL.rstrip('/')}/{image_id}"


def _extract_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower().strip()
    if not suffix:
        raise ValueError("File extension is required")
    return suffix.lstrip(".")


def _validate_image_id(image_id: str) -> bool:
    return bool(image_id) and len(image_id) == 32 and all(c in "0123456789abcdef" for c in image_id)


def _get_metadata_backend():
    global _metadata_backend
    if _metadata_backend is not None:
        return _metadata_backend

    if config.CDN_REDIS_URL:
        try:
            import redis

            client = redis.from_url(config.CDN_REDIS_URL)
            client.ping()
            _metadata_backend = _RedisMetadataBackend(client)
            return _metadata_backend
        except Exception:
            logger.exception("CDN Redis is unavailable. Falling back to in-memory metadata backend.")

    _metadata_backend = _InMemoryMetadataBackend()
    return _metadata_backend


def _save_metadata(image_id: str, metadata: dict) -> None:
    _get_metadata_backend().set(image_id, metadata)


def _load_metadata(image_id: str) -> dict | None:
    return _get_metadata_backend().get(image_id)


def save_uploaded_image(file: FileStorage) -> dict:
    if file is None or not file.filename:
        raise ValueError("No file provided")

    extension = _extract_extension(file.filename)
    if extension not in config.CDN_ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported image extension: {extension}")

    content_type = (file.mimetype or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise ValueError("Only image uploads are allowed")

    data = file.read()
    if not data:
        raise ValueError("Uploaded file is empty")
    if len(data) > config.CDN_MAX_UPLOAD_BYTES:
        raise ValueError(f"File is too large (max {config.CDN_MAX_UPLOAD_BYTES} bytes)")

    return save_image_bytes(
        data=data,
        extension=extension,
        content_type=content_type or _CONTENT_TYPE_BY_EXT.get(extension, "application/octet-stream"),
        original_filename=file.filename,
    )


def save_image_bytes(data: bytes, extension: str, content_type: str, original_filename: str = "") -> dict:
    if extension not in config.CDN_ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported image extension: {extension}")
    if not data:
        raise ValueError("Image data is empty")
    if len(data) > config.CDN_MAX_UPLOAD_BYTES:
        raise ValueError(f"File is too large (max {config.CDN_MAX_UPLOAD_BYTES} bytes)")

    storage_dir = Path(config.CDN_STORAGE_DIR)
    storage_dir.mkdir(parents=True, exist_ok=True)

    image_id = uuid.uuid4().hex
    filename = f"{image_id}.{extension}"
    file_path = storage_dir / filename
    file_path.write_bytes(data)

    metadata = {
        "image_id": image_id,
        "filename": filename,
        "file_path": str(file_path),
        "content_type": content_type or _CONTENT_TYPE_BY_EXT.get(extension, "application/octet-stream"),
        "size_bytes": len(data),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "original_filename": original_filename,
    }
    _save_metadata(image_id, metadata)
    metadata["image_url"] = _build_image_url(image_id)
    return metadata


def get_image_file(image_id: str) -> tuple[Path, str] | None:
    if not _validate_image_id(image_id):
        return None

    metadata = _load_metadata(image_id)
    if not metadata:
        return None

    file_path = Path(metadata["file_path"])
    if not file_path.exists():
        return None

    return file_path, metadata.get("content_type", "application/octet-stream")


class _RedisMetadataBackend:
    def __init__(self, client):
        self._r = client

    def set(self, image_id: str, metadata: dict):
        payload = json.dumps(metadata, ensure_ascii=False)
        key = _metadata_key(image_id)
        if config.CDN_IMAGE_TTL_SECONDS > 0:
            self._r.set(key, payload, ex=config.CDN_IMAGE_TTL_SECONDS)
        else:
            self._r.set(key, payload)

    def get(self, image_id: str) -> dict | None:
        data = self._r.get(_metadata_key(image_id))
        if not data:
            return None
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data)


class _InMemoryMetadataBackend:
    def __init__(self):
        self._store: dict[str, dict] = {}

    def set(self, image_id: str, metadata: dict):
        self._store[image_id] = metadata

    def get(self, image_id: str) -> dict | None:
        return self._store.get(image_id)
