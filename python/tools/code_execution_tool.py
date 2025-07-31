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
from python.helpers.strings import truncate_text as truncate_text_string
from python.helpers.messages import truncate_text as truncate_text_agent
import re


@dataclass
class State:
    shells: dict[int, LocalInteractiveSession | SSHInteractiveSession]
    docker: DockerContainerManager | None


class CodeExecution(Tool):

    async def execute(self, **kwargs):

        await self.agent.handle_intervention()  # wait for intervention and handle it, if paused

        # HumanLayer integration: check for high-risk operations requiring approval
        if self.agent.config.additional.get("humanlayer_enabled", False):
            approval_result = await self._check_humanlayer_approval()
            if approval_result and "denied" in approval_result.lower():
                return Response(message=approval_result, break_loop=False)

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
                "fw.code.runtime_wrong.md", runtime=runtime
            )

        if not response:
            response = self.agent.read_prompt(
                "fw.code.info.md", info=self.agent.read_prompt("fw.code.no_output.md")
            )
        return Response(message=response, break_loop=False)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="code_exe",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
        )

    def get_heading(self, text: str = ""):
        if not text:
            text = f"{self.name} - {self.args['runtime']}"
        text = truncate_text_string(text, 60)
        session = self.args.get("session", None)
        session_text = f"[{session}] " if session or session == 0 else ""
        return f"icon://terminal {session_text}{text}"

    async def after_execution(self, response, **kwargs):
        self.agent.hist_add_tool_result(self.name, response.message)

    async def prepare_state(self, reset=False, session=None):
        self.state = self.agent.get_data("_cet_state")
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
        self.agent.set_data("_cet_state", self.state)

    async def execute_python_code(self, session: int, code: str, reset: bool = False):
        escaped_code = shlex.quote(code)
        command = f"ipython -c {escaped_code}"
        prefix = "python> " + self.format_command_for_output(code) + "\n\n"
        return await self.terminal_session(session, command, reset, prefix)

    async def execute_nodejs_code(self, session: int, code: str, reset: bool = False):
        escaped_code = shlex.quote(code)
        command = f"node /exe/node_eval.js {escaped_code}"
        prefix = "node> " + self.format_command_for_output(code) + "\n\n"
        return await self.terminal_session(session, command, reset, prefix)

    async def execute_terminal_command(
        self, session: int, command: str, reset: bool = False
    ):
        prefix = "bash> " + self.format_command_for_output(command) + "\n\n"
        return await self.terminal_session(session, command, reset, prefix)

    async def terminal_session(
        self, session: int, command: str, reset: bool = False, prefix: str = ""
    ):

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
                return await self.get_terminal_output(session=session, prefix=prefix)

            except Exception as e:
                if i == 1:
                    # try again on lost connection
                    PrintStyle.error(str(e))
                    await self.prepare_state(reset=True)
                    continue
                else:
                    raise e

    def format_command_for_output(self, command: str):
        # truncate long commands
        short_cmd = command[:200]
        # normalize whitespace for cleaner output
        short_cmd = " ".join(short_cmd.split())
        # replace any sequence of ', ", or ` with a single '
        # short_cmd = re.sub(r"['\"`]+", "'", short_cmd) # no need anymore
        # final length
        short_cmd = truncate_text_string(short_cmd, 100)
        return f"{short_cmd}"

    async def get_terminal_output(
        self,
        session=0,
        reset_full_output=True,
        first_output_timeout=30,  # Wait up to x seconds for first output
        between_output_timeout=15,  # Wait up to x seconds between outputs
        dialog_timeout=5,  # potential dialog detection timeout
        max_exec_timeout=180,  # hard cap on total runtime
        sleep_time=0.1,
        prefix="",
    ):
        # Common shell prompt regex patterns (add more as needed)
        prompt_patterns = [
            re.compile(r"\\(venv\\).+[$#] ?$"),  # (venv) ...$ or (venv) ...#
            re.compile(r"root@[^:]+:[^#]+# ?$"),  # root@container:~#
            re.compile(r"[a-zA-Z0-9_.-]+@[^:]+:[^$#]+[$#] ?$"),  # user@host:~$
        ]

        # potential dialog detection
        dialog_patterns = [
            re.compile(r"Y/N", re.IGNORECASE),  # Y/N anywhere in line
            re.compile(r"yes/no", re.IGNORECASE),  # yes/no anywhere in line
            re.compile(r":\s*$"),  # line ending with colon
            re.compile(r"\?\s*$"),  # line ending with question mark
        ]

        start_time = time.time()
        last_output_time = start_time
        full_output = ""
        truncated_output = ""
        got_output = False

        # if prefix, log right away
        if prefix:
            self.log.update(content=prefix)

        while True:
            await asyncio.sleep(sleep_time)
            full_output, partial_output = await self.state.shells[session].read_output(
                timeout=1, reset_full_output=reset_full_output
            )
            reset_full_output = False  # only reset once

            await self.agent.handle_intervention()

            now = time.time()
            if partial_output:
                PrintStyle(font_color="#85C1E9").stream(partial_output)
                # full_output += partial_output # Append new output
                truncated_output = self.fix_full_output(full_output)
                heading = self.get_heading_from_output(truncated_output, 0)
                self.log.update(content=prefix + truncated_output, heading=heading)
                last_output_time = now
                got_output = True

                # Check for shell prompt at the end of output
                last_lines = (
                    truncated_output.splitlines()[-3:] if truncated_output else []
                )
                last_lines.reverse()
                for idx, line in enumerate(last_lines):
                    for pat in prompt_patterns:
                        if pat.search(line.strip()):
                            PrintStyle.info(
                                "Detected shell prompt, returning output early."
                            )
                            last_lines.reverse()
                            heading = self.get_heading_from_output(
                                "\n".join(last_lines), idx + 1, True
                            )
                            self.log.update(heading=heading)
                            return truncated_output

            # Check for max execution time
            if now - start_time > max_exec_timeout:
                sysinfo = self.agent.read_prompt(
                    "fw.code.max_time.md", timeout=max_exec_timeout
                )
                response = self.agent.read_prompt("fw.code.info.md", info=sysinfo)
                if truncated_output:
                    response = truncated_output + "\n\n" + response
                PrintStyle.warning(sysinfo)
                heading = self.get_heading_from_output(truncated_output, 0)
                self.log.update(content=prefix + response, heading=heading)
                return response

            # Waiting for first output
            if not got_output:
                if now - start_time > first_output_timeout:
                    sysinfo = self.agent.read_prompt(
                        "fw.code.no_out_time.md", timeout=first_output_timeout
                    )
                    response = self.agent.read_prompt("fw.code.info.md", info=sysinfo)
                    PrintStyle.warning(sysinfo)
                    self.log.update(content=prefix + response)
                    return response
            else:
                # Waiting for more output after first output
                if now - last_output_time > between_output_timeout:
                    sysinfo = self.agent.read_prompt(
                        "fw.code.pause_time.md", timeout=between_output_timeout
                    )
                    response = self.agent.read_prompt("fw.code.info.md", info=sysinfo)
                    if truncated_output:
                        response = truncated_output + "\n\n" + response
                    PrintStyle.warning(sysinfo)
                    heading = self.get_heading_from_output(truncated_output, 0)
                    self.log.update(content=prefix + response, heading=heading)
                    return response

                # potential dialog detection
                if now - last_output_time > dialog_timeout:
                    # Check for dialog prompt at the end of output
                    last_lines = (
                        truncated_output.splitlines()[-2:] if truncated_output else []
                    )
                    for line in last_lines:
                        for pat in dialog_patterns:
                            if pat.search(line.strip()):
                                PrintStyle.info(
                                    "Detected dialog prompt, returning output early."
                                )

                                sysinfo = self.agent.read_prompt(
                                    "fw.code.pause_dialog.md", timeout=dialog_timeout
                                )
                                response = self.agent.read_prompt(
                                    "fw.code.info.md", info=sysinfo
                                )
                                if truncated_output:
                                    response = truncated_output + "\n\n" + response
                                PrintStyle.warning(sysinfo)
                                heading = self.get_heading_from_output(
                                    truncated_output, 0
                                )
                                self.log.update(
                                    content=prefix + response, heading=heading
                                )
                                return response

    async def reset_terminal(self, session=0, reason: str | None = None):
        # Print the reason for the reset to the console if provided
        if reason:
            PrintStyle(font_color="#FFA500", bold=True).print(
                f"Resetting terminal session {session}... Reason: {reason}"
            )
        else:
            PrintStyle(font_color="#FFA500", bold=True).print(
                f"Resetting terminal session {session}..."
            )

        # Only reset the specified session while preserving others
        await self.prepare_state(reset=True, session=session)
        response = self.agent.read_prompt(
            "fw.code.info.md", info=self.agent.read_prompt("fw.code.reset.md")
        )
        self.log.update(content=response)
        return response

    def get_heading_from_output(self, output: str, skip_lines=0, done=False):
        done_icon = " icon://done_all" if done else ""

        if not output:
            return self.get_heading() + done_icon

        # find last non-empty line with skip
        lines = output.splitlines()
        # Start from len(lines) - skip_lines - 1 down to 0
        for i in range(len(lines) - skip_lines - 1, -1, -1):
            line = lines[i].strip()
            if not line:
                continue
            return self.get_heading(line) + done_icon

        return self.get_heading() + done_icon

    def fix_full_output(self, output: str):
        # remove any single byte \xXX escapes
        output = re.sub(r"(?<!\\)\\x[0-9A-Fa-f]{2}", "", output)
        # Strip every line of output before truncation
        output = "\n".join(line.strip() for line in output.splitlines())
        output = truncate_text_agent(agent=self.agent, output=output, threshold=10000)
        return output

    async def _check_humanlayer_approval(self) -> str | None:
        """
        Check if code execution requires HumanLayer approval for high-risk operations.
        Returns None if no approval needed, or approval result message if approval was requested.
        """
        try:
            code = self.args.get("code", "")
            runtime = self.args.get("runtime", "").lower().strip()
            
            # Define high-risk patterns that require approval
            high_risk_patterns = [
                # Destructive file operations
                "rm -rf", "rmdir", "del /s", "shutil.rmtree", "os.remove", 
                # System administration
                "sudo", "chmod 777", "chown", "passwd", "useradd", "userdel",
                # Service management
                "systemctl", "service", "systemd", "init.d",
                # Package management
                "apt-get install", "yum install", "pip install", "npm install", "gem install",
                # Network operations
                "curl", "wget", "ssh", "scp", "rsync", "nc ", "netcat",
                # Database operations
                "DROP TABLE", "DROP DATABASE", "DELETE FROM", "TRUNCATE",
                # Docker operations
                "docker run", "docker exec", "docker rm", "docker rmi",
                # Git operations that could be destructive
                "git push", "git reset --hard", "git clean -fd", "git rm",
                # Process management
                "kill -9", "killall", "pkill",
                # File permissions and ownership
                "chmod +x", "chgrp", "umask"
            ]
            
            # Check if code contains high-risk patterns
            code_lower = code.lower()
            found_patterns = []
            for pattern in high_risk_patterns:
                if pattern.lower() in code_lower:
                    found_patterns.append(pattern)
            
            # If high-risk patterns found, request approval
            if found_patterns:
                try:
                    # Import HumanLayer approval tool
                    from python.tools.humanlayer_approval import HumanLayerApproval
                    
                    # Create approval request
                    approval_tool = HumanLayerApproval(
                        self.agent,
                        "humanlayer_approval",
                        None,
                        {
                            "operation": f"Execute {runtime} code with potentially risky operations",
                            "context": f"Code contains high-risk patterns: {', '.join(found_patterns[:3])}{'...' if len(found_patterns) > 3 else ''}\n\nCode to execute:\n{code[:500]}{'...' if len(code) > 500 else ''}",
                            "timeout": 300
                        },
                        "",
                        self.loop_data
                    )
                    
                    # Request approval
                    approval_response = await approval_tool.execute()
                    return approval_response.message
                    
                except Exception as e:
                    # If approval system fails, allow execution but log warning
                    if hasattr(self.agent, 'context') and hasattr(self.agent.context, 'log'):
                        self.agent.context.log.log(
                            type="warning",
                            heading="HumanLayer Approval System Warning",
                            content=f"Could not request approval for high-risk code execution: {str(e)}",
                            kvps={"code_preview": code[:200]}
                        )
                    return None
            
            return None  # No high-risk patterns found
            
        except Exception as e:
            # If approval check fails completely, log error but don't block execution
            if hasattr(self.agent, 'context') and hasattr(self.agent.context, 'log'):
                self.agent.context.log.log(
                    type="error",
                    heading="HumanLayer Approval Check Error",
                    content=f"Error in approval check: {str(e)}",
                    kvps={}
                )
            return None
