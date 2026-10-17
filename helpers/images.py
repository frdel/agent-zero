import base64
import hashlib
import io
import math
import mimetypes
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from PIL import Image


# Keep request bodies below the A0 gateway limit (about 4 MB) with a safety margin.
IMAGE_INLINE_MAX_BYTES = 600_000          # raw bytes allowed per inlined image
IMAGE_REQUEST_BUDGET_BYTES = 1_800_000    # raw bytes allowed for all inlined images in one request
IMAGE_BUDGET_FLOOR_BYTES = 120_000        # never shrink a single image below this
IMAGE_COMPRESSION_STEPS: tuple[tuple[int, int], ...] = (
    (1_000_000, 80),
    (800_000, 72),
    (640_000, 65),
    (450_000, 55),
    (300_000, 45),
    (200_000, 35),
    (120_000, 30),
)


def prepare_content(content: Any, image_budget: int | None = None) -> Any:
    if isinstance(content, list):
        return [prepare_content(item, image_budget=image_budget) for item in content]
    if not isinstance(content, dict):
        return content

    if content.get("type") == "image_url":
        image_url = content.get("image_url")
        if isinstance(image_url, dict):
            url = str(image_url.get("url", "") or "").strip()
            if is_local_ref(url):
                return {**content, "image_url": {**image_url, "url": to_data_url(url, max_bytes=image_budget)}}
        elif isinstance(image_url, str):
            url = image_url.strip()
            if is_local_ref(url):
                return {**content, "image_url": {"url": to_data_url(url, max_bytes=image_budget)}}

    return {key: prepare_content(value, image_budget=image_budget) for key, value in content.items()}


def is_local_ref(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if lowered.startswith(("http://", "https://", "data:")):
        return False
    return lowered.startswith("file://") or url.startswith(("/", "./", "../", "~"))


def count_local_refs(content: Any) -> int:
    """Count local image references inside message content."""
    if isinstance(content, list):
        return sum(count_local_refs(item) for item in content)
    if not isinstance(content, dict):
        return 0
    if content.get("type") == "image_url":
        image_url = content.get("image_url")
        url = image_url.get("url") if isinstance(image_url, dict) else image_url
        if isinstance(url, str) and is_local_ref(url.strip()):
            return 1
    return sum(count_local_refs(value) for value in content.values())


def image_budget_for(contents: list[Any]) -> int | None:
    """Adaptive per-image byte budget so a whole request stays small."""
    refs = sum(count_local_refs(content) for content in contents)
    if refs <= 0:
        return None
    return max(
        IMAGE_BUDGET_FLOOR_BYTES,
        min(IMAGE_INLINE_MAX_BYTES, IMAGE_REQUEST_BUDGET_BYTES // refs),
    )


def to_data_url(url: str, max_bytes: int | None = None) -> str:
    path = resolve_ref(url)
    mime_type = mimetypes.guess_type(path.name)[0]
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"Image attachment must have an image MIME type: {path}")
    limit = (
        IMAGE_INLINE_MAX_BYTES
        if max_bytes is None
        else max(IMAGE_BUDGET_FLOOR_BYTES, min(int(max_bytes), IMAGE_INLINE_MAX_BYTES))
    )
    data = path.read_bytes()
    if len(data) > limit:
        compressed = _compressed_bytes(path, data, limit)
        if compressed:
            data = compressed
            mime_type = "image/jpeg"
    encoded = base64.b64encode(data).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _compressed_bytes(path: Path, data: bytes, limit: int) -> bytes | None:
    """Compress image bytes to the byte limit, caching the result in a temp cache."""
    cache_path = _cache_path(path, limit)
    if cache_path is not None and cache_path.is_file():
        try:
            cached = cache_path.read_bytes()
            if cached:
                return cached
        except OSError:
            pass

    best: bytes | None = None
    for max_pixels, quality in IMAGE_COMPRESSION_STEPS:
        try:
            candidate = compress_image(data, max_pixels=max_pixels, quality=quality)
        except Exception:
            continue
        if best is None or len(candidate) < len(best):
            best = candidate
        if len(candidate) <= limit:
            break

    if best is None:
        return None
    if cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(best)
        except OSError:
            pass
    return best


def _cache_path(path: Path, limit: int) -> Path | None:
    """Return a temp cache path for a compressed image, outside chat artifact folders."""
    try:
        stamp = path.stat()
        key = f"{path}:{stamp.st_mtime_ns}:{stamp.st_size}:{limit}".encode("utf-8")
    except OSError:
        return None
    digest = hashlib.sha256(key).hexdigest()[:32]
    return Path(tempfile.gettempdir()) / "a0_image_cache" / f"{digest}.jpg"


def resolve_ref(url: str) -> Path:
    raw_path = unquote(urlparse(url).path) if url.lower().startswith("file://") else url
    path = Path(raw_path).expanduser()
    candidates = [path]
    if raw_path.startswith("/a0/"):
        from helpers import files

        candidates.append(Path(files.fix_dev_path(raw_path)))
    elif not path.is_absolute():
        from helpers import files

        candidates.append(Path(files.get_abs_path(raw_path)))

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists() and candidate.is_file():
            return candidate

    raise FileNotFoundError(f"Image attachment path does not exist: {raw_path}")


def compress_image(image_data: bytes, *, max_pixels: int = 256_000, quality: int = 50) -> bytes:
    """Compress an image by scaling it down and converting to JPEG with quality settings.
    
    Args:
        image_data: Raw image bytes
        max_pixels: Maximum number of pixels in the output image (width * height)
        quality: JPEG quality setting (1-100)
    
    Returns:
        Compressed image as bytes
    """
    # load image from bytes
    img = Image.open(io.BytesIO(image_data))
    
    # calculate scaling factor to get to max_pixels
    current_pixels = img.width * img.height
    if current_pixels > max_pixels:
        scale = math.sqrt(max_pixels / current_pixels)
        new_width = int(img.width * scale)
        new_height = int(img.height * scale)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # convert to RGB if needed (for JPEG)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # save as JPEG with compression
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)
    return output.getvalue()
