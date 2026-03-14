from __future__ import annotations

import hashlib
import logging
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from database import DatabaseManager

logger = logging.getLogger(__name__)

DEFAULT_AVATAR_PATH = Path("ui/assets/default_avatar.png")


def _versioned_avatar_path(user_id: int, payload: bytes, directory: Path) -> Path:
    digest = hashlib.sha1(payload).hexdigest()[:12]
    return directory / f"{user_id}_{digest}.jpg"


def invalidate_avatar_cache(user_id: int, directory: Path) -> None:
    if not directory.exists():
        return
    removed = 0
    for old in directory.glob(f"{user_id}_*.jpg"):
        try:
            old.unlink()
            removed += 1
        except OSError:
            logger.warning("avatar cache remove failed user_id=%s path=%s", user_id, old)
    logger.info("avatar cache invalidated user_id=%s removed=%s", user_id, removed)


def save_custom_avatar(user_id: int, payload: bytes, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    out = _versioned_avatar_path(user_id, payload, directory)
    invalidate_avatar_cache(user_id, directory)
    with Image.open(BytesIO(payload)) as src:
        img = ImageOps.exif_transpose(src).convert("RGB")
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        square = img.crop((left, top, left + side, top + side)).resize((512, 512), Image.Resampling.LANCZOS)
        square.save(out, format="JPEG", quality=90, optimize=True)
    DatabaseManager.set_custom_avatar(user_id, str(out))
    logger.info("avatar saved user_id=%s path=%s", user_id, out)
    return out


def get_avatar_source(user_id: int) -> str:
    settings = DatabaseManager.get_avatar_settings(user_id)
    source = settings.get("avatar_source", "telegram")
    custom = Path(settings.get("custom_avatar_path", "")) if settings.get("custom_avatar_path") else None
    tg = Path(settings.get("telegram_avatar_path", "")) if settings.get("telegram_avatar_path") else None

    if source == "custom" and custom and custom.exists():
        logger.info("avatar source selected user_id=%s source=custom", user_id)
        return "custom"
    if tg and tg.exists():
        logger.info("avatar source selected user_id=%s source=telegram", user_id)
        return "telegram"
    logger.info("avatar source selected user_id=%s source=default", user_id)
    return "default"


def get_effective_avatar(user_id: int) -> str:
    settings = DatabaseManager.get_avatar_settings(user_id)
    source = settings.get("avatar_source", "telegram")
    custom = Path(settings.get("custom_avatar_path", "")) if settings.get("custom_avatar_path") else None
    tg = Path(settings.get("telegram_avatar_path", "")) if settings.get("telegram_avatar_path") else None
    if source == "custom":
        if custom and custom.exists():
            logger.info("effective avatar user_id=%s source=custom path=%s", user_id, custom)
            return str(custom)
        logger.warning("custom avatar missing, fallback to telegram/default user_id=%s", user_id)
    if tg and tg.exists():
        logger.info("effective avatar user_id=%s source=telegram path=%s", user_id, tg)
        return str(tg)
    if DEFAULT_AVATAR_PATH.exists():
        logger.info("effective avatar user_id=%s source=default path=%s", user_id, DEFAULT_AVATAR_PATH)
        return str(DEFAULT_AVATAR_PATH)
    logger.info("effective avatar user_id=%s source=default-empty", user_id)
    return ""


def reset_avatar(user_id: int, directory: Path | None = None) -> str:
    settings = DatabaseManager.get_avatar_settings(user_id)
    custom = Path(settings.get("custom_avatar_path", "")) if settings.get("custom_avatar_path") else None
    if custom and custom.exists():
        try:
            custom.unlink()
        except OSError:
            logger.warning("custom avatar delete failed user_id=%s path=%s", user_id, custom)
    if directory is not None:
        invalidate_avatar_cache(user_id, directory)
    DatabaseManager.reset_avatar_source(user_id)
    source = get_avatar_source(user_id)
    logger.info("avatar reset user_id=%s effective_source=%s", user_id, source)
    return source


def build_avatar_preview(path: str) -> bytes | None:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    return p.read_bytes()
