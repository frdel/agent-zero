from typing import Any
from python.helpers.tool import Tool, Response
from python.helpers.aider import create_streaming_aider_coder
from python.helpers.print_style import PrintStyle
from python.helpers.settings import Settings
from python.helpers import settings
from python.helpers import runtime


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

        response = None
        aider_kwargs = {
            "files": files,
            "git_repo_path": root_path,
            "dry_run": bool(dry_run),
            "verbose": False,
            "read_only_files": read_only_files,
            "auto_commits": True,
            "stream": True,
            "max_reflections": max_reflections,
        }
        try:
            if runtime.is_development():
                aider_kwargs["task"] = task

                result: dict[str, Any] = await runtime.call_development_function(call_aider_via_rfc, **aider_kwargs)  # type: ignore

                if result.get("success"):
                    response = "=" * 10 + "\nTask completed successfully" + "\n" + "=" * 10 + "\n# Details:\n\n" + result.get("response", "")
                else:
                    response = "Error: " + result.get("error", "No response provided by agent")

                return Response(message=response, break_loop=False)
            else:
                streaming_wrapper, response_capture = create_streaming_aider_coder(**aider_kwargs)

                # Use the improved async method with native streaming
                result: dict[str, Any] = await streaming_wrapper.run_with_streaming_async(
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


async def call_aider_via_rfc(
    task: str,
    files: list[str],
    git_repo_path: str,
    dry_run: bool,
    verbose: bool,
    read_only_files: list[str],
    auto_commits: bool,
    stream: bool,
    max_reflections: int
) -> dict[str, Any]:
    try:
        streaming_wrapper, _ = create_streaming_aider_coder(
            files=files,
            git_repo_path=git_repo_path,
            dry_run=dry_run,
            verbose=verbose,
            read_only_files=read_only_files,
            auto_commits=auto_commits,
            stream=stream,
            max_reflections=max_reflections,
        )

        # Use the improved async method with native streaming
        return await streaming_wrapper.run_with_streaming_async(
            message=task,
            response_callback=None
        )
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
