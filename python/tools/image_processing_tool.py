from agent import Agent
from python.helpers.tool import Tool, Response
from python.helpers import files
from python.helpers.process_image import process_image
from python.helpers.print_style import PrintStyle
import base64
import os

class ImageProcessingTool(Tool):

    def encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def execute(self, query: str, **kwargs):

        image_paths = self.args["image_paths"]

        if not image_paths or not isinstance(image_paths, list):
            raise ValueError("The image_paths is either empty, None, or not a valid list of strings.")

        processed_image_paths = []

        for image_path in image_paths:
            if not image_path.startswith("http"):
                if not os.path.exists(image_path):
                    raise FileNotFoundError(f"The local file '{image_path}' not found.")
                with open(image_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                    image_path = f"data:image/jpeg;base64,{base64_image}"
            processed_image_paths.append(image_path)

        content = process_image(query, processed_image_paths)

        # if self.agent.handle_intervention(content): 
        #     return Response(message="", break_loop=False)  # wait for intervention and handle it, if paused

        # Return the response
        return Response(message=content, break_loop=False)