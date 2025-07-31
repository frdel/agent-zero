import base64
from io import BytesIO
import mimetypes
import os

from flask import Response
from python.helpers.api import ApiHandler, Input, Output, Request
from python.helpers import files, runtime
from python.api import file_info


def stream_file_download(file_source, download_name, chunk_size=8192):
    """
    Create a streaming response for file downloads that shows progress in browser.

    Args:
        file_source: Either a file path (str) or BytesIO object
        download_name: Name for the downloaded file
        chunk_size: Size of chunks to stream (default 8192 bytes)

    Returns:
        Flask Response object with streaming content
    """
    # Calculate file size for Content-Length header
    if isinstance(file_source, str):
        # File path - get size from filesystem
        file_size = os.path.getsize(file_source)
    elif isinstance(file_source, BytesIO):
        # BytesIO object - get size from buffer
        current_pos = file_source.tell()
        file_source.seek(0, 2)  # Seek to end
        file_size = file_source.tell()
        file_source.seek(current_pos)  # Restore original position
    else:
        raise ValueError(f"Unsupported file source type: {type(file_source)}")

    def generate():
        if isinstance(file_source, str):
            # File path - open and stream from disk
            with open(file_source, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        elif isinstance(file_source, BytesIO):
            # BytesIO object - stream from memory
            file_source.seek(0)  # Ensure we're at the beginning
            while True:
                chunk = file_source.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    # Detect content type based on file extension
    content_type, _ = mimetypes.guess_type(download_name)
    if not content_type:
        content_type = 'application/octet-stream'

    # Create streaming response with proper headers for immediate streaming
    response = Response(
        generate(),
        content_type=content_type,
        direct_passthrough=True,  # Prevent Flask from buffering the response
        headers={
            'Content-Disposition': f'attachment; filename="{download_name}"',
            'Content-Length': str(file_size),  # Critical for browser progress bars
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Accept-Ranges': 'bytes'  # Allow browser to resume downloads
        }
    )

    return response


class DownloadFile(ApiHandler):

    @classmethod
    def get_methods(cls):
        return ["GET"]

    async def process(self, input: Input, request: Request) -> Output:
        file_path = request.args.get("path", input.get("path", ""))
        if not file_path:
            raise ValueError("No file path provided")
        if not file_path.startswith("/"):
            file_path = f"/{file_path}"

        file = await runtime.call_development_function(
            file_info.get_file_info, file_path
        )

        if not file["exists"]:
            raise Exception(f"File {file_path} not found")

        if file["is_dir"]:
            zip_file = await runtime.call_development_function(files.zip_dir, file["abs_path"])
            if runtime.is_development():
                b64 = await runtime.call_development_function(fetch_file, zip_file)
                file_data = BytesIO(base64.b64decode(b64))
                return stream_file_download(
                    file_data,
                    download_name=os.path.basename(zip_file)
                )
            else:
                return stream_file_download(
                    zip_file,
                    download_name=f"{os.path.basename(file_path)}.zip"
                )
        elif file["is_file"]:
            if runtime.is_development():
                b64 = await runtime.call_development_function(fetch_file, file["abs_path"])
                file_data = BytesIO(base64.b64decode(b64))
                return stream_file_download(
                    file_data,
                    download_name=os.path.basename(file_path)
                )
            else:
                return stream_file_download(
                    file["abs_path"],
                    download_name=os.path.basename(file["file_name"])
                )
        raise Exception(f"File {file_path} not found")


async def fetch_file(path):
    with open(path, "rb") as file:
        file_content = file.read()
        return base64.b64encode(file_content).decode("utf-8")
