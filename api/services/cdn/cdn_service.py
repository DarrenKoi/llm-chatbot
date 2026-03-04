import json
import logging
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
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
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _metadata_key(file_id: str) -> str:
    return f"cdn:file:{file_id}"


def _metadata_index_key() -> str:
    return "cdn:file:index"


def _build_file_url(file_id: str) -> str:
    return f"{config.CDN_BASE_URL.rstrip('/')}/{file_id}"


def _original_dir() -> Path:
    return Path(config.CDN_STORAGE_DIR) / "original"


def _variant_root_dir() -> Path:
    return Path(config.CDN_STORAGE_DIR) / "variant"


def _extract_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower().strip()
    if not suffix:
        raise ValueError("File extension is required")
    return suffix.lstrip(".")


def _validate_file_id(file_id: str) -> bool:
    return bool(file_id) and len(file_id) == 32 and all(c in "0123456789abcdef" for c in file_id)


def _parse_positive_int(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _normalize_resize_options(
    width: int | None,
    height: int | None,
    thumbnail: bool,
) -> tuple[int | None, int | None, str]:
    width = _parse_positive_int(width, "w")
    height = _parse_positive_int(height, "h")

    if thumbnail:
        if width is not None or height is not None:
            raise ValueError("thumbnail cannot be combined with w/h options")
        width = config.CDN_THUMBNAIL_WIDTH
        height = config.CDN_THUMBNAIL_HEIGHT
        mode = "thumbnail"
    elif width is not None or height is not None:
        mode = "resize"
    else:
        mode = "original"

    if width is not None and width > config.CDN_MAX_RESIZE_WIDTH:
        raise ValueError(f"w must be <= {config.CDN_MAX_RESIZE_WIDTH}")
    if height is not None and height > config.CDN_MAX_RESIZE_HEIGHT:
        raise ValueError(f"h must be <= {config.CDN_MAX_RESIZE_HEIGHT}")

    return width, height, mode


def _storage_usage_bytes() -> int:
    root = Path(config.CDN_STORAGE_DIR)
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _assert_storage_limit(extra_bytes: int = 0) -> None:
    limit = config.CDN_STORAGE_LIMIT_BYTES
    if limit <= 0:
        return
    current = _storage_usage_bytes()
    if current + extra_bytes > limit:
        raise ValueError("CDN storage limit exceeded")


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


def _save_metadata(file_id: str, metadata: dict) -> None:
    _get_metadata_backend().set(file_id, metadata)


def _load_metadata(file_id: str) -> dict | None:
    return _get_metadata_backend().get(file_id)


def save_uploaded_file(file: FileStorage) -> dict:
    if file is None or not file.filename:
        raise ValueError("No file provided")

    extension = _extract_extension(file.filename)
    if extension not in config.CDN_ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {extension}")

    content_type = (file.mimetype or "").lower()

    data = file.read()
    if not data:
        raise ValueError("Uploaded file is empty")
    if len(data) > config.CDN_MAX_UPLOAD_BYTES:
        raise ValueError(f"File is too large (max {config.CDN_MAX_UPLOAD_BYTES} bytes)")

    return save_file_bytes(
        data=data,
        extension=extension,
        content_type=content_type or _CONTENT_TYPE_BY_EXT.get(extension, "application/octet-stream"),
        original_filename=file.filename,
    )


def save_file_bytes(data: bytes, extension: str, content_type: str, original_filename: str = "") -> dict:
    if extension not in config.CDN_ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {extension}")
    if not data:
        raise ValueError("File data is empty")
    if len(data) > config.CDN_MAX_UPLOAD_BYTES:
        raise ValueError(f"File is too large (max {config.CDN_MAX_UPLOAD_BYTES} bytes)")
    _assert_storage_limit(len(data))

    storage_dir = _original_dir()
    storage_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex
    filename = f"{file_id}.{extension}"
    file_path = storage_dir / filename
    file_path.write_bytes(data)

    metadata = {
        "file_id": file_id,
        "filename": filename,
        "file_path": str(file_path),
        "content_type": content_type or _CONTENT_TYPE_BY_EXT.get(extension, "application/octet-stream"),
        "size_bytes": len(data),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "original_filename": original_filename,
    }
    _save_metadata(file_id, metadata)
    metadata["file_url"] = _build_file_url(file_id)
    return metadata


def get_file(file_id: str) -> tuple[Path, str] | None:
    return get_file_variant(file_id=file_id, width=None, height=None, thumbnail=False)


def get_file_variant(
    file_id: str,
    width: int | None = None,
    height: int | None = None,
    thumbnail: bool = False,
) -> tuple[Path, str] | None:
    if not _validate_file_id(file_id):
        return None

    metadata = _load_metadata(file_id)
    if not metadata:
        return None

    file_path = Path(metadata["file_path"])
    if not file_path.exists():
        return None

    extension = _extract_extension(metadata["filename"])
    content_type = metadata.get("content_type", "application/octet-stream")

    # 비이미지 파일은 variant(resize/thumbnail) 미지원 — 원본 반환
    if extension not in _IMAGE_EXTENSIONS:
        return file_path, content_type

    width, height, mode = _normalize_resize_options(width=width, height=height, thumbnail=thumbnail)
    if mode == "original":
        return file_path, content_type

    variant_dir = _variant_root_dir() / file_id
    variant_dir.mkdir(parents=True, exist_ok=True)

    variant_key = f"{mode}-{width or 0}x{height or 0}"
    variant_file = variant_dir / f"{variant_key}.{extension}"

    if variant_file.exists():
        return variant_file, content_type

    variant_bytes = _create_variant_bytes(
        source_file=file_path,
        extension=extension,
        target_width=width,
        target_height=height,
    )
    _assert_storage_limit(len(variant_bytes))
    variant_file.write_bytes(variant_bytes)

    return variant_file, content_type


def _pil_resample_filter():
    from PIL import Image

    if hasattr(Image, "Resampling"):
        return Image.Resampling.LANCZOS
    return Image.LANCZOS


def _image_format_by_extension(extension: str) -> str:
    mapping = {
        "jpg": "JPEG",
        "jpeg": "JPEG",
        "png": "PNG",
        "gif": "GIF",
        "webp": "WEBP",
    }
    return mapping.get(extension, "PNG")


def _create_variant_bytes(source_file: Path, extension: str, target_width: int | None, target_height: int | None) -> bytes:
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("Pillow is required for resize/thumbnail") from e

    with Image.open(source_file) as img:
        result = img.copy()
        src_width, src_height = result.size

        box = (target_width or src_width, target_height or src_height)
        result.thumbnail(box, _pil_resample_filter())

        image_format = _image_format_by_extension(extension)
        save_kwargs = {"format": image_format}
        if image_format in {"JPEG", "WEBP"}:
            save_kwargs["quality"] = 85
        if image_format == "JPEG" and result.mode not in {"RGB", "L"}:
            result = result.convert("RGB")

        buffer = BytesIO()
        result.save(buffer, **save_kwargs)
        return buffer.getvalue()


def get_expired_file_ids(reference_time: datetime | None = None) -> list[str]:
    retention_days = config.CDN_RETENTION_DAYS
    if retention_days <= 0:
        return []

    now = reference_time or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)
    expired: list[str] = []

    for file_id in _get_metadata_backend().list_ids():
        metadata = _load_metadata(file_id)
        if not metadata:
            continue
        created_at = metadata.get("created_at")
        if not created_at:
            continue
        try:
            created_dt = datetime.fromisoformat(created_at)
        except ValueError:
            continue
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        if created_dt < cutoff:
            expired.append(file_id)

    return expired


def delete_file(file_id: str) -> bool:
    metadata = _load_metadata(file_id)
    if not metadata:
        return False

    file_path = Path(metadata.get("file_path", ""))
    if file_path.exists():
        file_path.unlink()

    variant_dir = _variant_root_dir() / file_id
    if variant_dir.exists():
        shutil.rmtree(variant_dir, ignore_errors=True)

    _get_metadata_backend().delete(file_id)
    return True


class _RedisMetadataBackend:
    def __init__(self, client):
        self._r = client

    def set(self, file_id: str, metadata: dict):
        payload = json.dumps(metadata, ensure_ascii=False)
        key = _metadata_key(file_id)
        if config.CDN_IMAGE_TTL_SECONDS > 0:
            self._r.set(key, payload, ex=config.CDN_IMAGE_TTL_SECONDS)
        else:
            self._r.set(key, payload)
        self._r.sadd(_metadata_index_key(), file_id)

    def get(self, file_id: str) -> dict | None:
        data = self._r.get(_metadata_key(file_id))
        if not data:
            return None
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data)

    def delete(self, file_id: str):
        self._r.delete(_metadata_key(file_id))
        self._r.srem(_metadata_index_key(), file_id)

    def list_ids(self) -> list[str]:
        raw_ids = self._r.smembers(_metadata_index_key())
        file_ids: list[str] = []
        for value in raw_ids:
            if isinstance(value, bytes):
                file_ids.append(value.decode("utf-8"))
            else:
                file_ids.append(str(value))
        return file_ids


class _InMemoryMetadataBackend:
    def __init__(self):
        self._store: dict[str, dict] = {}

    def set(self, file_id: str, metadata: dict):
        self._store[file_id] = metadata

    def get(self, file_id: str) -> dict | None:
        return self._store.get(file_id)

    def delete(self, file_id: str):
        self._store.pop(file_id, None)

    def list_ids(self) -> list[str]:
        return list(self._store.keys())
