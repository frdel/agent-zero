import base64
import io
import math
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from PIL import Image


def prepare_content(content: Any) -> Any:
    if isinstance(content, list):
        return [prepare_content(item) for item in content]
    if not isinstance(content, dict):
        return content

    if content.get("type") == "image_url":
        image_url = content.get("image_url")
        if isinstance(image_url, dict):
            url = str(image_url.get("url", "") or "").strip()
            if is_local_ref(url):
                return {**content, "image_url": {**image_url, "url": to_data_url(url)}}
        elif isinstance(image_url, str):
            url = image_url.strip()
            if is_local_ref(url):
                return {**content, "image_url": {"url": to_data_url(url)}}

    return {key: prepare_content(value) for key, value in content.items()}


def is_local_ref(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if lowered.startswith(("http://", "https://", "data:")):
        return False
    return lowered.startswith("file://") or url.startswith(("/", "./", "../", "~", "§§secret("))


def to_data_url(url: str) -> str:
    path = resolve_ref(url)
    mime_type = mimetypes.guess_type(path.name)[0]
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"Image attachment must have an image MIME type: {path}")
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def resolve_ref(url: str) -> Path:
    raw_path = unquote(urlparse(url).path) if url.lower().startswith("file://") else url
    resolution_path = raw_path
    if "§§secret(" in resolution_path:
        from helpers.secrets import get_secrets_manager

        try:
            resolution_path = get_secrets_manager().replace_placeholders(raw_path)
        except Exception:
            # Keep unresolved placeholders on the normal missing-path error path.
            pass
    path = Path(resolution_path).expanduser()
    candidates = [path]
    if resolution_path.startswith("/a0/"):
        from helpers import files

        candidates.append(Path(files.fix_dev_path(resolution_path)))
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
