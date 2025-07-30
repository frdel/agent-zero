import base64
import os
from python.helpers.api import ApiHandler, Request, Response
from python.helpers import files
from python.helpers.print_style import PrintStyle
import json


class ApiFilesGet(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return False

    @classmethod
    def requires_csrf(cls) -> bool:
        return False

    @classmethod
    def requires_api_key(cls) -> bool:
        return True

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            # Get paths from input
            paths = input.get("paths", [])

            if not paths:
                return Response(
                    '{"error": "paths array is required"}',
                    status=400,
                    mimetype="application/json"
                )

            if not isinstance(paths, list):
                return Response(
                    '{"error": "paths must be an array"}',
                    status=400,
                    mimetype="application/json"
                )

            result = {}

            for path in paths:
                try:
                    # Convert internal paths to external paths
                    if path.startswith("/a0/tmp/uploads/"):
                        # Internal path - convert to external
                        filename = path.replace("/a0/tmp/uploads/", "")
                        external_path = files.get_abs_path("tmp/uploads", filename)
                        filename = os.path.basename(external_path)
                    elif path.startswith("/a0/"):
                        # Other internal Agent Zero paths
                        relative_path = path.replace("/a0/", "")
                        external_path = files.get_abs_path(relative_path)
                        filename = os.path.basename(external_path)
                    else:
                        # Assume it's already an external/absolute path
                        external_path = path
                        filename = os.path.basename(path)

                    # Check if file exists
                    if not os.path.exists(external_path):
                        PrintStyle.warning(f"File not found: {path}")
                        continue

                    # Read and encode file
                    with open(external_path, "rb") as f:
                        file_content = f.read()
                        base64_content = base64.b64encode(file_content).decode('utf-8')
                        result[filename] = base64_content

                    PrintStyle().print(f"Retrieved file: {filename} ({len(file_content)} bytes)")

                except Exception as e:
                    PrintStyle.error(f"Failed to read file {path}: {str(e)}")
                    continue

            # Log the retrieval
            PrintStyle(
                background_color="#2ECC71", font_color="white", bold=True, padding=True
            ).print(f"API Files retrieved: {len(result)} files")

            return result

        except Exception as e:
            PrintStyle.error(f"API files get error: {str(e)}")
            return Response(
                json.dumps({"error": f"Internal server error: {str(e)}"}),
                status=500,
                mimetype="application/json"
            )
