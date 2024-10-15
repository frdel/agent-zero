import asyncio
from dataclasses import dataclass
import shlex
import time
from python.helpers.tool import Tool, Response
from python.helpers import files
from python.helpers.print_style import PrintStyle
from python.helpers.shell_local import LocalInteractiveSession
from python.helpers.shell_ssh import SSHInteractiveSession
from python.helpers.docker import DockerContainerManager


@dataclass
class State:
    shell: LocalInteractiveSession | SSHInteractiveSession
    docker: DockerContainerManager | None


class CodeExecution(Tool):

    async def execute(self, **kwargs):

        await self.agent.handle_intervention()  # wait for intervention and handle it, if paused

        await self.prepare_state()

        # os.chdir(files.get_abs_path("./work_dir")) #change CWD to work_dir

        runtime = self.args.get("runtime", "").lower().strip()

        if runtime == "python":
            response = await self.execute_python_code(self.args["code"])
        elif runtime == "nodejs":
            response = await self.execute_nodejs_code(self.args["code"])
        elif runtime == "terminal":
            response = await self.execute_terminal_command(self.args["code"])
        elif runtime == "output":
            response = await self.get_terminal_output(
                wait_with_output=5, wait_without_output=60
            )
        elif runtime == "reset":
            response = await self.reset_terminal()
        else:
            response = self.agent.read_prompt(
                "fw.code_runtime_wrong.md", runtime=runtime
            )

        if not response:
            response = self.agent.read_prompt("fw.code_no_output.md")
        return Response(message=response, break_loop=False)

    async def before_execution(self, **kwargs):
        await self.agent.handle_intervention()  # wait for intervention and handle it, if paused
        PrintStyle(
            font_color="#1B4F72", padding=True, background_color="white", bold=True
        ).print(f"{self.agent.agent_name}: Using tool '{self.name}'")
        self.log = self.agent.context.log.log(
            type="code_exe",
            heading=f"{self.agent.agent_name}: Using tool '{self.name}'",
            content="",
            kvps=self.args,
        )
        if self.args and isinstance(self.args, dict):
            for key, value in self.args.items():
                PrintStyle(font_color="#85C1E9", bold=True).stream(
                    self.nice_key(key) + ": "
                )
                PrintStyle(
                    font_color="#85C1E9",
                    padding=isinstance(value, str) and "\n" in value,
                ).stream(value)
                PrintStyle().print()

    async def after_execution(self, response, **kwargs):
        msg_response = self.agent.read_prompt(
            "fw.tool_response.md", tool_name=self.name, tool_response=response.message
        )
        await self.agent.append_message(msg_response, human=True)

    async def prepare_state(self, reset=False):
        self.state = self.agent.get_data("cot_state")
        if not self.state or reset:

            # initialize docker container if execution in docker is configured
            if self.agent.config.code_exec_docker_enabled:
                docker = DockerContainerManager(
                    logger=self.agent.context.log,
                    name=self.agent.config.code_exec_docker_name,
                    image=self.agent.config.code_exec_docker_image,
                    ports=self.agent.config.code_exec_docker_ports,
                    volumes=self.agent.config.code_exec_docker_volumes,
                )
                docker.start_container()
            else:
                docker = None

            # initialize local or remote interactive shell insterface
            if self.agent.config.code_exec_ssh_enabled:
                shell = SSHInteractiveSession(
                    self.agent.context.log,
                    self.agent.config.code_exec_ssh_addr,
                    self.agent.config.code_exec_ssh_port,
                    self.agent.config.code_exec_ssh_user,
                    self.agent.config.code_exec_ssh_pass,
                )
            else:
                shell = LocalInteractiveSession()

            self.state = State(shell=shell, docker=docker)
            await shell.connect()
        self.agent.set_data("cot_state", self.state)

    async def execute_python_code(self, code: str, reset: bool = False):
        escaped_code = shlex.quote(code)
        command = f"ipython -c {escaped_code}"
        return await self.terminal_session(command, reset)

    async def execute_nodejs_code(self, code: str, reset: bool = False):
        escaped_code = shlex.quote(code)
        command = f"node /exe/node_eval.js {escaped_code}"
        return await self.terminal_session(command, reset)

    async def execute_terminal_command(self, command: str, reset: bool = False):
        return await self.terminal_session(command, reset)

    async def terminal_session(self, command: str, reset: bool = False):

        await self.agent.handle_intervention()  # wait for intervention and handle it, if paused
        if reset:
            await self.reset_terminal()

        self.state.shell.send_command(command)

        PrintStyle(background_color="white", font_color="#1B4F72", bold=True).print(
            f"{self.agent.agent_name} code execution output"
        )
        return await self.get_terminal_output()

    async def get_terminal_output(
        self,
        reset_full_output=True,
        wait_with_output=3,
        wait_without_output=10,
        max_exec_time=60,
    ):
        idle = 0
        SLEEP_TIME = 0.1
        start_time = time.time()
        full_output = ""

        while max_exec_time <= 0 or time.time() - start_time < max_exec_time:
            await asyncio.sleep(SLEEP_TIME)  # Wait for some output to be generated
            full_output, partial_output = await self.state.shell.read_output(
                timeout=max_exec_time, reset_full_output=reset_full_output
            )
            reset_full_output = False # only reset once

            await self.agent.handle_intervention()  # wait for intervention and handle it, if paused

            if partial_output:
                PrintStyle(font_color="#85C1E9").stream(partial_output)
                self.log.update(content=full_output)
                idle = 0
            else:
                idle += 1
                if (full_output and idle > wait_with_output / SLEEP_TIME) or (
                    not full_output and idle > wait_without_output / SLEEP_TIME
                ):
                    break
        return full_output

    async def reset_terminal(self):
        self.state.shell.close()
        await self.prepare_state(reset=True)
        response = self.agent.read_prompt("fw.code_reset.md")
        self.log.update(content=response)
        return response
