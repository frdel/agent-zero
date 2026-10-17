from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from helpers import files, media_artifacts


DEFAULT_MAX_IMAGE_BYTES = media_artifacts.DEFAULT_MAX_ARTIFACT_SIZE_BYTES
ImageCategory = Literal["images", "screenshots"]


@dataclass(frozen=True)
class ChatImage:
    path: str
    a0_path: str
    mime: str
    size: int


def screenshot_dir(context_id: str, source: str) -> Path:
    return artifact_dir(context_id, category="screenshots", source=source)


def artifact_dir(
    context_id: str,
    *,
    category: ImageCategory = "images",
    source: str = "vision-load",
) -> Path:
    context_segment = files.safe_file_name(str(context_id or "default")).strip("._") or "default"
    safe_category = files.safe_file_name(category).strip("._") or "images"
    safe_source = files.safe_file_name(source).strip("._") or "vision-load"

    return Path(files.get_abs_path("usr/chats", context_segment)) / safe_category / safe_source


def save_image_bytes(
    *,
    context_id: str,
    payload: bytes,
    mime_type: str = "image/png",
    category: ImageCategory = "images",
    source: str = "vision-load",
    preferred_name: str = "",
    max_bytes: int | None = DEFAULT_MAX_IMAGE_BYTES,
) -> ChatImage:
    data = bytes(payload or b"")
    if not data:
        raise media_artifacts.EmptyBase64Data("image payload is empty")
    if max_bytes is not None and len(data) > max_bytes:
        raise media_artifacts.ArtifactTooLarge(len(data), max_bytes)

    safe_mime = media_artifacts.normalize_mime(
        mime_type,
        default="image/png",
        required_prefix="image/",
    )
    default_extension = media_artifacts.guess_extension(safe_mime, ".png")
    default_filename = f"{source or 'image'}{default_extension}"
    filename = media_artifacts.safe_filename(
        preferred_name,
        default=default_filename,
        default_extension=default_extension,
    )
    filename_path = Path(filename)
    stem = filename_path.stem or Path(default_filename).stem or "image"
    suffix = filename_path.suffix or default_extension
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = artifact_dir(context_id, category=category, source=source) / (
        f"{stem}-{timestamp}-{uuid.uuid4().hex[:8]}{suffix}"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return ChatImage(
        path=str(path),
        a0_path=files.normalize_a0_path(str(path)),
        mime=safe_mime,
        size=len(data),
    )


def save_image_base64(
    *,
    context_id: str,
    data: str,
    mime_type: str = "image/png",
    category: ImageCategory = "images",
    source: str = "vision-load",
    preferred_name: str = "",
    max_bytes: int | None = DEFAULT_MAX_IMAGE_BYTES,
) -> ChatImage:
    payload = media_artifacts.decode_base64_payload(data, max_bytes=max_bytes)
    return save_image_bytes(
        context_id=context_id,
        payload=payload.payload,
        mime_type=mime_type,
        category=category,
        source=source,
        preferred_name=preferred_name,
        max_bytes=max_bytes,
    )


def save_image_file(
    *,
    context_id: str,
    path: str | Path,
    category: ImageCategory = "images",
    source: str = "vision-load",
    preferred_name: str = "",
    max_bytes: int | None = DEFAULT_MAX_IMAGE_BYTES,
) -> ChatImage:
    image_path = Path(path)
    payload = image_path.read_bytes()
    mime = media_artifacts.normalize_mime(
        _guess_image_mime(image_path),
        default="image/png",
        required_prefix="image/",
    )
    return save_image_bytes(
        context_id=context_id,
        payload=payload,
        mime_type=mime,
        category=category,
        source=source,
        preferred_name=preferred_name or image_path.name,
        max_bytes=max_bytes,
    )


def save_image_data_url(
    *,
    context_id: str,
    data_url: str,
    category: ImageCategory = "images",
    source: str = "vision-load",
    preferred_name: str = "",
    max_bytes: int | None = DEFAULT_MAX_IMAGE_BYTES,
) -> ChatImage:
    header, encoded = _split_image_data_url(data_url)
    mime = header.removeprefix("data:").split(";", 1)[0] or "image/png"
    return save_image_base64(
        context_id=context_id,
        data=encoded,
        mime_type=mime,
        category=category,
        source=source,
        preferred_name=preferred_name,
        max_bytes=max_bytes,
    )


def materialize_image_ref(
    *,
    context_id: str,
    url: str,
    source: str = "",
    preferred_name: str = "",
    max_bytes: int | None = DEFAULT_MAX_IMAGE_BYTES,
) -> str:
    value = str(url or "").strip()
    if not value or not str(context_id or "").strip():
        return value

    resolved_source = source or infer_source(value, preferred_name)
    category = category_for_source(resolved_source)
    if _is_data_image_url(value):
        saved = save_image_data_url(
            context_id=context_id,
            data_url=value,
            category=category,
            source=resolved_source,
            preferred_name=preferred_name,
            max_bytes=max_bytes,
        )
        return saved.a0_path

    from helpers import images

    source_path = images.resolve_ref(value)
    if is_chat_scoped_path(context_id=context_id, path=source_path):
        return files.normalize_a0_path(str(source_path))
    saved = save_image_file(
        context_id=context_id,
        path=source_path,
        category=category,
        source=resolved_source,
        preferred_name=preferred_name or source_path.name,
        max_bytes=max_bytes,
    )
    return saved.a0_path


def is_chat_scoped_path(*, context_id: str, path: str | Path) -> bool:
    if not str(context_id or "").strip():
        return False
    try:
        target = Path(path).resolve(strict=False)
        root = artifact_dir(context_id, category="images", source="vision-load").parents[1].resolve(strict=False)
        return target == root or root in target.parents
    except OSError:
        return False


def infer_source(value: str = "", preferred_name: str = "") -> str:
    raw = f"{value or ''} {preferred_name or ''}".lower()
    if "computer-use" in raw or "computer_use" in raw or "_a0_connector/computer_use" in raw:
        return "computer-use"
    if "/desktop/screenshots/" in raw or "\\desktop\\screenshots\\" in raw or "desktop-" in raw:
        return "desktop"
    if (
        "/browser/screenshots/" in raw
        or "\\browser\\screenshots\\" in raw
        or "host-browser" in raw
        or "browser-" in raw
    ):
        return "browser"
    return "vision-load"


def category_for_source(source: str) -> ImageCategory:
    return "screenshots" if source in {"desktop", "browser", "computer-use"} else "images"


def _guess_image_mime(path: Path) -> str:
    import mimetypes

    return mimetypes.guess_type(path.name)[0] or "image/png"


def _is_data_image_url(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized.startswith("data:image/") and ";base64," in normalized


def _split_image_data_url(data_url: str) -> tuple[str, str]:
    value = str(data_url or "").strip()
    if not _is_data_image_url(value) or "," not in value:
        raise ValueError("image data URL must be data:image/*;base64,...")
    return value.split(",", 1)


_IMAGE_REF_RE = re.compile(
    r"(?:img://+|/api/image_get\?path=)(?P<path>[^)\s\"'<>]+)",
    re.IGNORECASE,
)
_IMAGE_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".svgz",
    ".webp",
}


def snapshot_image_refs(
    text: str,
    *,
    context_id: str,
    source: str = "response",
) -> str:
    """Copy live image files referenced in chat text onto unique chat artifacts.

    Chat markdown historically points at live workdir paths such as
    `img:///a0/usr/workdir/logo.png`. Reusing that filename later overwrites the
    file, so older chat bubbles show the newest image. This rewrites each
    non-chat-scoped local image onto a unique snapshot under the chat folder.
    """
    value = str(text or "")
    if not value or not str(context_id or "").strip():
        return value

    replacements: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        original = match.group(0)
        if original in replacements:
            return replacements[original]
        rewritten = _snapshot_matched_image_ref(
            original,
            context_id=context_id,
            source=source,
        )
        replacements[original] = rewritten
        return rewritten

    return _IMAGE_REF_RE.sub(_replace, value)


def _snapshot_matched_image_ref(
    original: str,
    *,
    context_id: str,
    source: str,
) -> str:
    path_value = _image_ref_path(original)
    if not path_value:
        return original
    if not _looks_like_image_path(path_value):
        return original
    try:
        from helpers import images

        source_path = images.resolve_ref(path_value)
        if is_chat_scoped_path(context_id=context_id, path=source_path):
            snapshotted = files.normalize_a0_path(str(source_path))
        else:
            saved = save_image_file(
                context_id=context_id,
                path=source_path,
                category="images",
                source=source,
                preferred_name=source_path.name,
            )
            snapshotted = saved.a0_path
    except (FileNotFoundError, OSError, ValueError):
        return original
    return _rewrite_image_ref(original, snapshotted)


def _image_ref_path(value: str) -> str:
    raw = str(value or "").strip()
    lowered = raw.lower()
    if lowered.startswith("img:"):
        rest = raw.split(":", 1)[1]
        if rest.startswith("//"):
            rest = rest[2:]
        if rest.lower().startswith("a0/"):
            rest = "/" + rest
        raw = rest
    elif "path=" in lowered:
        raw = raw.split("path=", 1)[1]
    return raw.split("&", 1)[0].strip()


def _looks_like_image_path(path_value: str) -> bool:
    suffix = Path(path_value.split("?", 1)[0]).suffix.lower()
    return suffix in _IMAGE_EXTENSIONS


def _rewrite_image_ref(original: str, snapshotted: str) -> str:
    if original.lower().startswith("img:"):
        return f"img://{snapshotted}"
    if original.lower().startswith("/api/image_get?path="):
        return f"/api/image_get?path={snapshotted}"
    return snapshotted
