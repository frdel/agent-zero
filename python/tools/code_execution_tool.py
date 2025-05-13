import asyncio
from dataclasses import dataclass
import shlex
import time
from python.helpers.tool import Tool, Response
from python.helpers import files, rfc_exchange
from python.helpers.print_style import PrintStyle
from python.helpers.shell_local import LocalInteractiveSession
from python.helpers.shell_ssh import SSHInteractiveSession
from python.helpers.docker import DockerContainerManager
import re


@dataclass
class State:
    shells: dict[int, LocalInteractiveSession | SSHInteractiveSession]
    docker: DockerContainerManager | None


class CodeExecution(Tool):

    async def execute(self, **kwargs):

        await self.agent.handle_intervention()  # wait for intervention and handle it, if paused

        await self.prepare_state()

        # os.chdir(files.get_abs_path("./work_dir")) #change CWD to work_dir

        runtime = self.args.get("runtime", "").lower().strip()
        session = int(self.args.get("session", 0))

        if runtime == "python":
            response = await self.execute_python_code(
                code=self.args["code"], session=session
            )
        elif runtime == "nodejs":
            response = await self.execute_nodejs_code(
                code=self.args["code"], session=session
            )
        elif runtime == "terminal":
            response = await self.execute_terminal_command(
                command=self.args["code"], session=session
            )
        elif runtime == "output":
            response = await self.get_terminal_output(
                session=session, first_output_timeout=60, between_output_timeout=5
            )
        elif runtime == "reset":
            response = await self.reset_terminal(session=session)
        else:
            response = self.agent.read_prompt(
                "fw.code_runtime_wrong.md", runtime=runtime
            )

        if not response:
            response = self.agent.read_prompt("fw.code_no_output.md")
        return Response(message=response, break_loop=False)

    # async def before_execution(self, **kwargs):
    #     await self.agent.handle_intervention()  # wait for intervention and handle it, if paused
    #     PrintStyle(
    #         font_color="#1B4F72", padding=True, background_color="white", bold=True
    #     ).print(f"{self.agent.agent_name}: Using tool '{self.name}'")
    #     self.log = self.agent.context.log.log(
    #         type="code_exe",
    #         heading=f"{self.agent.agent_name}: Using tool '{self.name}'",
    #         content="",
    #         kvps=self.args,
    #     )
    #     if self.args and isinstance(self.args, dict):
    #         for key, value in self.args.items():
    #             PrintStyle(font_color="#85C1E9", bold=True).stream(
    #                 self.nice_key(key) + ": "
    #             )
    #             PrintStyle(
    #                 font_color="#85C1E9",
    #                 padding=isinstance(value, str) and "\n" in value,
    #             ).stream(value)
    #             PrintStyle().print()

    def get_log_object(self):
        return self.agent.context.log.log(
            type="code_exe",
            heading=f"{self.agent.agent_name}: Using tool '{self.name}'",
            content="",
            kvps=self.args,
        )

    async def after_execution(self, response, **kwargs):
        self.agent.hist_add_tool_result(self.name, response.message)

    async def prepare_state(self, reset=False, session=None):
        self.state = self.agent.get_data("_cot_state")
        if not self.state or reset:

            # initialize docker container if execution in docker is configured
            if not self.state and self.agent.config.code_exec_docker_enabled:
                docker = DockerContainerManager(
                    logger=self.agent.context.log,
                    name=self.agent.config.code_exec_docker_name,
                    image=self.agent.config.code_exec_docker_image,
                    ports=self.agent.config.code_exec_docker_ports,
                    volumes=self.agent.config.code_exec_docker_volumes,
                )
                docker.start_container()
            else:
                docker = self.state.docker if self.state else None

            # initialize shells dictionary if not exists
            shells = {} if not self.state else self.state.shells.copy()
            
            # Only reset the specified session if provided
            if session is not None and session in shells:
                shells[session].close()
                del shells[session]
            elif reset and not session:
                # Close all sessions if full reset requested
                for s in list(shells.keys()):
                    shells[s].close()
                shells = {}

            # initialize local or remote interactive shell interface for session 0 if needed
            if 0 not in shells:
                if self.agent.config.code_exec_ssh_enabled:
                    pswd = (
                        self.agent.config.code_exec_ssh_pass
                        if self.agent.config.code_exec_ssh_pass
                        else await rfc_exchange.get_root_password()
                    )
                    shell = SSHInteractiveSession(
                        self.agent.context.log,
                        self.agent.config.code_exec_ssh_addr,
                        self.agent.config.code_exec_ssh_port,
                        self.agent.config.code_exec_ssh_user,
                        pswd,
                    )
                else:
                    shell = LocalInteractiveSession()

                shells[0] = shell
                await shell.connect()
            
            self.state = State(shells=shells, docker=docker)
        self.agent.set_data("_cot_state", self.state)

    async def execute_python_code(self, session: int, code: str, reset: bool = False):
        escaped_code = shlex.quote(code)
        command = f"ipython -c {escaped_code}"
        return await self.terminal_session(session, command, reset)

    async def execute_nodejs_code(self, session: int, code: str, reset: bool = False):
        escaped_code = shlex.quote(code)
        command = f"node /exe/node_eval.js {escaped_code}"
        return await self.terminal_session(session, command, reset)

    async def execute_terminal_command(
        self, session: int, command: str, reset: bool = False
    ):
        return await self.terminal_session(session, command, reset)

    async def terminal_session(self, session: int, command: str, reset: bool = False):

        await self.agent.handle_intervention()  # wait for intervention and handle it, if paused
        # try again on lost connection
        for i in range(2):
            try:

                if reset:
                    await self.reset_terminal()

                if session not in self.state.shells:
                    if self.agent.config.code_exec_ssh_enabled:
                        pswd = (
                            self.agent.config.code_exec_ssh_pass
                            if self.agent.config.code_exec_ssh_pass
                            else await rfc_exchange.get_root_password()
                        )
                        shell = SSHInteractiveSession(
                            self.agent.context.log,
                            self.agent.config.code_exec_ssh_addr,
                            self.agent.config.code_exec_ssh_port,
                            self.agent.config.code_exec_ssh_user,
                            pswd,
                        )
                    else:
                        shell = LocalInteractiveSession()
                    self.state.shells[session] = shell
                    await shell.connect()

                self.state.shells[session].send_command(command)

                PrintStyle(
                    background_color="white", font_color="#1B4F72", bold=True
                ).print(f"{self.agent.agent_name} code execution output")
                return await self.get_terminal_output(session)

            except Exception as e:
                if i == 1:
                    # try again on lost connection
                    PrintStyle.error(str(e))
                    await self.prepare_state(reset=True)
                    continue
                else:
                    raise e

    async def get_terminal_output(
        self,
        session=0,
        reset_full_output=True,
        first_output_timeout=30,   # Wait up to 60s for first output
        between_output_timeout=10, # Wait up to 10s between outputs
        sleep_time=0.1,
    ):
        """
        Waits for terminal output with a sliding window idle timeout:
        - Waits up to first_output_timeout (default 60s) for the first output.
        - After any output, waits up to between_output_timeout (default 10s) for more output.
        - Each new output resets the between_output_timeout timer.
        - No hard cap on total runtime.
        - If no output for between_output_timeout after last output, or no output at all for first_output_timeout, returns.
        - If a common shell prompt is detected, returns immediately.
        """
        # Common shell prompt regex patterns (add more as needed)
        prompt_patterns = [
            re.compile(r"\\(venv\\).+[$#] ?$"),  # (venv) ...$ or (venv) ...#
            re.compile(r"root@[^:]+:[^#]+# ?$"),    # root@container:~#
            re.compile(r"[a-zA-Z0-9_.-]+@[^:]+:[^$#]+[$#] ?$"), # user@host:~$
        ]

        start_time = time.time()
        last_output_time = start_time
        full_output = ""
        got_output = False
        # --- Configuration for repetition detection ---
        chunk_size = 128  # Size of the block to check for repetition
        repeat_threshold = 5  # How many times the block must repeat consecutively

        while True:
            await asyncio.sleep(sleep_time)
            current_full_output, partial_output = await self.state.shells[session].read_output(
                timeout=between_output_timeout, reset_full_output=reset_full_output
            )
            reset_full_output = False

            await self.agent.handle_intervention()

            now = time.time()
            if partial_output:
                PrintStyle(font_color="#85C1E9").stream(partial_output)
                full_output += partial_output # Append new output
                self.log.update(content=full_output)
                last_output_time = now
                got_output = True

                # --- Check for repeating output pattern ---
                required_len = chunk_size * repeat_threshold
                if len(full_output) >= required_len:
                    check_segment = full_output[-required_len:]
                    last_chunk = full_output[-chunk_size:]
                    expected_segment = last_chunk * repeat_threshold
                    if check_segment == expected_segment:
                        loop_detected_msg = f"Detected repeating output pattern (last {chunk_size} chars repeated {repeat_threshold} times), likely an infinite loop."
                        PrintStyle.error(f"{loop_detected_msg} Resetting session {session}.")
                        self.log.update(content=full_output + f"\n--- LOOP DETECTED --- Session {session} reset.")
                        # Automatically reset the problematic session
                        await self.reset_terminal(session=session)
                        # Return informative message to the agent
                        return f"{full_output}\n--- LOOP DETECTED & SESSION RESET ---\n{loop_detected_msg}\nThe terminal session {session} was automatically reset.\nPlease review the code or command that caused the loop to prevent recurrence."
                # --- End of repetition check ---


            # Check for shell prompt at the end of output
            last_lines = full_output.splitlines()[-3:] if full_output else []
            for line in last_lines:
                for pat in prompt_patterns:
                    if pat.search(line.strip()):
                        PrintStyle(font_color="#229954").print("Detected shell prompt, returning output early.")
                        return full_output

            if not got_output:
                # Waiting for first output
                if now - start_time > first_output_timeout:
                    PrintStyle.error(f"No output for {first_output_timeout}s after start, returning.")
                    break
            else:
                # Waiting for more output after first output
                if now - last_output_time > between_output_timeout:
                    PrintStyle.error(f"No output for {between_output_timeout}s after last output, returning.")
                    break

        return full_output

    async def reset_terminal(self, session=0):
        # Only reset the specified session while preserving others
        await self.prepare_state(reset=True, session=session)
        response = self.agent.read_prompt("fw.code_reset.md")
        self.log.update(content=response)
        return response