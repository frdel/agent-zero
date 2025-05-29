from python.helpers.tool import Tool, Response
from python.helpers.aider import create_streaming_aider_coder
from python.helpers.print_style import PrintStyle
from python.helpers.settings import Settings
from python.helpers import settings


class CodingAgentTool(Tool):

    async def execute(self, **kwargs):
        files = kwargs.get("files", [])
        if not isinstance(files, list):
            if files:
                files = [files]
            else:
                files = []

        read_only_files = kwargs.get("read_only_files", [])
        if not isinstance(read_only_files, list):
            if read_only_files:
                read_only_files = [read_only_files]
            else:
                read_only_files = []

        dry_run = kwargs.get("dry_run", False)
        max_reflections = kwargs.get("max_reflections", 10)  # Default to 10 reflection attempts

        root_path = kwargs.get("root_path", None)
        if not root_path:
            return Response(message="No root path provided", break_loop=False)

        task = kwargs.get("task", None)
        if not task:
            return Response(message="No task provided", break_loop=False)

        def log_callback(response_type: str, content: str):
            # log only last 2000 characters from response capture
            self.log.update(content=response_capture.get_full_response()[-2000:])

        conf: Settings = settings.get_settings()
        MODEL_NAME = conf["chat_model_name"]
        MODEL_PROVIDER = conf["chat_model_provider"]

        response = None
        try:
            streaming_wrapper, response_capture = create_streaming_aider_coder(
                model_name=MODEL_PROVIDER.lower() + "/" + MODEL_NAME,
                files=files,
                git_repo_path=root_path,
                dry_run=bool(dry_run),
                verbose=False,
                read_only_files=read_only_files,
                auto_commits=True,
                stream=True,  # Enable native streaming
                max_reflections=max_reflections,
            )

            # Use the improved async method with native streaming
            result = await streaming_wrapper.run_with_streaming_async(
                message=task,
                response_callback=log_callback
            )

            if result.get("success"):
                response = "=" * 10 + "\nTask completed successfully" + "\n" + "=" * 10 + "\n# Details:\n\n" + response_capture.get_full_response()
            else:
                response = "Error: " + result.get("error", "No response provided by agent")
        except Exception as e:
            PrintStyle().error(f"Error: {e}")
            response = f"Error: {e}"

        return Response(message=response, break_loop=False)
