import base64
from python.helpers.print_style import PrintStyle
from python.helpers.tool import Tool, Response
from python.helpers import files, images
from mimetypes import guess_type
from python.helpers import history
import os # <<< ADDED for os.path.exists

# image optimization and token estimation for context window
MAX_PIXELS = 768_000
QUALITY = 75
TOKENS_ESTIMATE = 1500


class VisionLoad(Tool):
    async def execute(self, paths: list[str] = [], **kwargs) -> Response:

        self.images_dict = {}
        template: list[dict[str, str]] = []  # type: ignore

        for path in paths:
            # --- MODIFICATION: Replace RFC call with direct local file check ---
            # The 'files.get_abs_path' ensures it resolves paths correctly within the project.
            absolute_path = files.get_abs_path(path)
            if not os.path.exists(absolute_path):
                PrintStyle().error(f"File not found locally: {absolute_path}")
                continue
            # --- END MODIFICATION ---

            if path not in self.images_dict:
                mime_type, _ = guess_type(str(absolute_path))
                if mime_type and mime_type.startswith("image/"):
                    try:
                        # --- MODIFICATION: Replace RFC call with direct local file read ---
                        with open(absolute_path, "rb") as f:
                            file_content = f.read()
                        # --- END MODIFICATION ---

                        # Compress and convert to JPEG
                        compressed = images.compress_image(
                            file_content, max_pixels=MAX_PIXELS, quality=QUALITY
                        )
                        # Encode as base64
                        file_content_b64 = base64.b64encode(compressed).decode("utf-8")

                        # Construct the data URL (always JPEG after compression)
                        self.images_dict[path] = file_content_b64
                    except Exception as e:
                        self.images_dict[path] = None
                        PrintStyle().error(f"Error processing image {path}: {e}")
                        self.agent.context.log.log("warning", f"Error processing image {path}: {e}")

        # The 'dummy' message is not shown; after_execution handles the real output.
        return Response(message="dummy", break_loop=False)

    async def after_execution(self, response: Response, **kwargs):

        # build image data messages for LLMs, or error message
        content = []
        if self.images_dict:
            for path, image in self.images_dict.items():
                if image:
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                        }
                    )
                else:
                    content.append(
                        {
                            "type": "text",
                            "text": "Error processing image " + path,
                        }
                    )
            # append as raw message content for LLMs with vision tokens estimate
            msg = history.RawMessage(raw_content=content, preview="<Image data loaded>")
            self.agent.hist_add_message(
                False, content=msg, tokens=TOKENS_ESTIMATE * len(content)
            )
        else:
            self.agent.hist_add_tool_result(self.name, "No images processed")

        # print and log short version
        message = (
            "No images processed"
            if not self.images_dict
            else f"{len(self.images_dict)} images processed"
        )
        PrintStyle(
            font_color="#1B4F72", background_color="white", padding=True, bold=True
        ).print(f"{self.agent.agent_name}: Response from tool '{self.name}'")
        PrintStyle(font_color="#85C1E9").print(message)
        self.log.update(result=message)
