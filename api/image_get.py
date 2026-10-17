import base64
import os
from pathlib import Path
from urllib.parse import quote
from helpers.api import ApiHandler, Request, Response, send_file
from helpers import files, runtime
import io
from mimetypes import guess_type


IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".svg",
    ".ico",
    ".svgz",
)
SVG_EXTENSIONS = (".svg", ".svgz")
SVG_CONTENT_SECURITY_POLICY = (
    "sandbox; default-src 'none'; script-src 'none'; "
    "img-src 'self' data:; style-src 'unsafe-inline'"
)


class ImageGet(ApiHandler):

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        # input data
        path = input.get("path", request.args.get("path", ""))

        if not path:
            raise ValueError("No path provided")

        # get file extension and info
        file_ext = os.path.splitext(path)[1].lower()
        filename = os.path.basename(path)

        if file_ext in IMAGE_EXTENSIONS:
            try:
                local_path = _resolve_allowed_image_path(path)
            except ValueError as exc:
                return Response(str(exc), status=403, mimetype="text/plain")

            served_path = local_path
            served_existing_file = False

            # in development environment, try to serve the image from local file system if exists, otherwise from docker
            if runtime.is_development():
                if files.exists(local_path):
                    response = send_file(local_path)
                    served_existing_file = True
                else:
                    # Try fetching from Docker via RFC as fallback
                    try:
                        remote_path = await runtime.call_development_function(
                            _resolve_allowed_image_path, path
                        )
                        if await runtime.call_development_function(
                            files.exists, remote_path
                        ):
                            b64_content = await runtime.call_development_function(
                                files.read_file_base64, remote_path
                            )
                            file_content = base64.b64decode(b64_content)
                            mime_type, _ = guess_type(filename)
                            if not mime_type:
                                mime_type = "application/octet-stream"
                            response = send_file(
                                io.BytesIO(file_content),
                                mimetype=mime_type,
                                as_attachment=False,
                                download_name=filename,
                            )
                            served_path = str(remote_path)
                            served_existing_file = True
                        else:
                            response = _send_fallback_icon("image")
                    except Exception:
                        response = _send_fallback_icon("image")
            else:
                if files.exists(local_path):
                    response = send_file(local_path)
                    served_existing_file = True
                else:
                    response = _send_fallback_icon("image")

            _set_image_headers(
                response,
                filename,
                file_ext,
                cache_control=_cache_control_for_image(
                    served_path, exists=served_existing_file
                ),
            )
            return response
        else:
            # Handle non-image files with fallback icons
            return _send_file_type_icon(file_ext, filename)


def _resolve_allowed_image_path(path: str) -> str:
    """Resolve a requested image path and keep it inside Agent Zero's base dir."""

    if runtime.is_development():
        candidate = Path(files.fix_dev_path(path))
    else:
        candidate = Path(files.get_abs_path(path))

    if not candidate.is_absolute():
        candidate = Path(files.get_base_dir()) / candidate

    base_dir = Path(files.get_base_dir()).resolve()
    resolved = candidate.resolve(strict=False)

    try:
        resolved.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError("Path is outside of allowed directory") from exc

    return str(resolved)


def _cache_control_for_image(path: str, *, exists: bool) -> str:
    """Choose cache policy for a served image URL.

    Chat markdown historically points at live workdir files. Caching a missing-file
    fallback icon under that same URL hides later writes for an hour. Unique chat
    artifacts are immutable and can be cached; mutable workdir files must revalidate.
    """
    if not exists:
        return "no-store"
    normalized = str(path or "").replace("\\", "/").lower()
    if "/usr/chats/" in normalized:
        return "public, max-age=3600"
    return "no-cache"


def _set_image_headers(
    response: Response,
    filename: str,
    file_ext: str,
    *,
    cache_control: str = "no-cache",
) -> None:
    # Add cache headers for better device sync performance.
    response.headers["Cache-Control"] = cache_control
    response.headers["X-File-Type"] = "image"
    response.headers["X-File-Name"] = quote(filename)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if file_ext in SVG_EXTENSIONS:
        response.headers["Content-Security-Policy"] = SVG_CONTENT_SECURITY_POLICY


def _send_file_type_icon(file_ext, filename=None):
    """Return appropriate icon for file type"""

    # Map file extensions to icon names
    icon_mapping = {
        # Archive files
        ".zip": "archive",
        ".rar": "archive",
        ".7z": "archive",
        ".tar": "archive",
        ".gz": "archive",
        # Document files
        ".pdf": "document",
        ".doc": "document",
        ".docx": "document",
        ".txt": "document",
        ".rtf": "document",
        ".odt": "document",
        # Code files
        ".py": "code",
        ".js": "code",
        ".html": "code",
        ".css": "code",
        ".json": "code",
        ".xml": "code",
        ".md": "code",
        ".yml": "code",
        ".yaml": "code",
        ".sql": "code",
        ".sh": "code",
        ".bat": "code",
        # Spreadsheet files
        ".xls": "document",
        ".xlsx": "document",
        ".csv": "document",
        # Presentation files
        ".ppt": "document",
        ".pptx": "document",
        ".odp": "document",
    }

    # Get icon name, default to 'file' if not found
    icon_name = icon_mapping.get(file_ext, "file")

    response = _send_fallback_icon(icon_name)

    # Add headers for device sync
    if hasattr(response, "headers"):
        response.headers["Cache-Control"] = (
            "public, max-age=86400"  # Cache icons for 24 hours
        )
        response.headers["X-File-Type"] = "icon"
        response.headers["X-Icon-Type"] = icon_name
        if filename:
            response.headers["X-File-Name"] = quote(filename)

    return response


def _send_fallback_icon(icon_name):
    """Return fallback icon from public directory"""

    # Path to public icons
    icon_path = files.get_abs_path(f"webui/public/{icon_name}.svg")

    # Check if specific icon exists, fallback to generic file icon
    if not os.path.exists(icon_path):
        icon_path = files.get_abs_path("webui/public/file.svg")

    # Final fallback if file.svg doesn't exist
    if not os.path.exists(icon_path):
        raise ValueError(f"Fallback icon not found: {icon_path}")

    return send_file(icon_path, mimetype="image/svg+xml")
