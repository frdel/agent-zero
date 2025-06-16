import asyncio
import subprocess
import shlex
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle

class CodeExecution(Tool):

    async def execute(self, **kwargs):
        """
        This method executes a command directly on the host using a non-interactive
        subprocess, bypassing all SSH and RFC logic.
        """
        await self.agent.handle_intervention()

        runtime = self.args.get("runtime", "terminal").lower().strip()
        code_to_run = self.args.get("code", "")

        command_to_execute = ""

        if runtime == "python":
            command_to_execute = f"python -c {shlex.quote(code_to_run)}"
        elif runtime == "nodejs":
            command_to_execute = f"node -e {shlex.quote(code_to_run)}"
        elif runtime == "terminal":
            command_to_execute = code_to_run
        else:
            return Response(message=f"Error: Runtime '{runtime}' is not supported.", break_loop=False)

        if not command_to_execute:
             return Response(message="Error: No code or command provided to execute.", break_loop=False)

        PrintStyle.info(f"Executing command directly on host: {command_to_execute}")

        try:
            # Run the blocking subprocess call in a separate thread
            proc = await asyncio.to_thread(
                subprocess.run,
                command_to_execute,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300 # 5-minute timeout for longer operations
            )

            # Combine stdout and stderr for a complete picture, clearly labeled
            full_output = ""
            if proc.stdout:
                full_output += f"STDOUT:\n{proc.stdout.strip()}"
            if proc.stderr:
                if full_output: full_output += "\n\n"
                full_output += f"STDERR:\n{proc.stderr.strip()}"

            if not full_output:
                full_output = f"Command executed with return code {proc.returncode} and no output."

            self.agent.hist_add_tool_result(self.name, full_output)
            return Response(message=full_output, break_loop=False)

        except subprocess.TimeoutExpired:
            error_message = "Error: Command timed out after 300 seconds."
            self.agent.hist_add_tool_result(self.name, error_message)
            return Response(message=error_message, break_loop=False)
        except Exception as e:
            error_message = f"An unexpected error occurred during command execution: {str(e)}"
            self.agent.hist_add_tool_result(self.name, error_message)
            return Response(message=error_message, break_loop=False)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="code_exe",
            heading=f"{self.agent.agent_name}: Using DIRECT tool '{self.name}'",
            content="",
            kvps=self.args,
        )

    async def after_execution(self, response, **kwargs):
        pass
