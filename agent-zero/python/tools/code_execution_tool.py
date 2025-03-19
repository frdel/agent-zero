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
        return self.agent.context.log.log(type="code_exe", heading=f"{self.agent.agent_name}: Using tool '{self.name}'", content="", kvps=self.args)


    async def after_execution(self, response, **kwargs):
        await self.agent.hist_add_tool_result(self.name, response.message)

    async def prepare_state(self, reset=False):
        self.state = self.agent.get_data("_cot_state")
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
                pswd = self.agent.config.code_exec_ssh_pass if self.agent.config.code_exec_ssh_pass else await rfc_exchange.get_root_password()
                shell = SSHInteractiveSession(
                    self.agent.context.log,
                    self.agent.config.code_exec_ssh_addr,
                    self.agent.config.code_exec_ssh_port,
                    self.agent.config.code_exec_ssh_user,
                    pswd,
                )
            else:
                shell = LocalInteractiveSession()

            self.state = State(shell=shell, docker=docker)
            await shell.connect()
        self.agent.set_data("_cot_state", self.state)

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
        # try again on lost connection
        for i in range(2):
            try:
            
                if reset:
                    await self.reset_terminal()

                self.state.shell.send_command(command)

                PrintStyle(background_color="white", font_color="#1B4F72", bold=True).print(
                    f"{self.agent.agent_name} code execution output"
                )
                return await self.get_terminal_output()

            except Exception as e:
                if i==1:
                    # try again on lost connection
                    PrintStyle.error(str(e))
                    await self.prepare_state(reset=True)
                    continue
                else:
                    raise e

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
        status_update_interval = 5  # How often to print status updates (in seconds)
        last_status_time = time.time()

        # Common shell prompts to detect when a process has completed
        shell_prompt_patterns = [
            r'\(venv\).*?[#$]\s*$',  # Virtual env prompts like (venv) root@hostname:~#
            r'root@[a-zA-Z0-9\-]+:.+?[#$]\s*$',  # Standard root prompt
            r'[a-zA-Z0-9_\-]+@[a-zA-Z0-9\-]+:.+?[#$]\s*$',  # Standard user prompt
            r'[#$>]\s*$',  # Simple shell prompt
            r'bash-\d+\.\d+[#$]\s*$',  # Bash version prompt
            r'[a-zA-Z0-9_\-]+:.+?[#$]\s*$',  # Shortened prompts
        ]
        import re
        shell_prompt_regex = re.compile('|'.join(shell_prompt_patterns))
        
        waiting_for_process_termination = False
        
        while True:
            # Check if we've exceeded max_exec_time, but only enforce if process is not running
            elapsed_time = time.time() - start_time
            # Check if process is still running
            process_running = hasattr(self.state.shell, 'is_process_running') and self.state.shell.is_process_running()
            
            # Only enforce timeout if the process is not running AND max_exec_time is positive
            # Never timeout a running process - let it complete or detect a shell prompt
            if max_exec_time > 0 and elapsed_time > max_exec_time and not process_running:
                # Add a timeout message to the output
                timeout_msg = f"\n[Process execution timed out after {max_exec_time} seconds]\n"
                full_output += timeout_msg
                PrintStyle(font_color="#FF6347").stream(timeout_msg)  # Tomato red for warnings
                self.log.update(content=full_output)
                break
                
            await asyncio.sleep(SLEEP_TIME)  # Wait for some output to be generated
            full_output, partial_output = await self.state.shell.read_output(
                timeout=max_exec_time, reset_full_output=reset_full_output
            )
            reset_full_output = False # only reset once

            await self.agent.handle_intervention()  # wait for intervention and handle it, if paused

            # Check if there's a shell prompt in the output indicating command completion
            if full_output and shell_prompt_regex.search(full_output.rstrip()):
                # If we detect a shell prompt at the end, the process has completed
                if not waiting_for_process_termination:
                    PrintStyle(font_color="#85C1E9").stream("\n[Shell prompt detected, command appears to have completed]\n")
                    waiting_for_process_termination = True
                    # Set a short grace period (2 seconds) to wait for any final output
                    idle = int(wait_with_output / SLEEP_TIME) - 20  # 20 iterations = ~2 seconds left

            if partial_output:
                PrintStyle(font_color="#85C1E9").stream(partial_output)
                self.log.update(content=full_output)
                idle = 0
                last_status_time = time.time()
                waiting_for_process_termination = False  # Reset if we get new output
            else:
                idle += 1
                current_time = time.time()
                
                # If no output but process is still running, provide occasional status updates
                if process_running and not waiting_for_process_termination and (current_time - last_status_time) > status_update_interval:
                    # Show elapsed time in status message
                    elapsed_time = current_time - start_time
                    status_msg = f"Process still running ({elapsed_time:.1f}s elapsed), waiting for output...\n"
                    PrintStyle(font_color="#85C1E9").stream(status_msg)
                    self.log.update(content=full_output + status_msg)
                    last_status_time = current_time
                    idle = 0  # Reset idle counter since process is still active
                    
                # Break conditions:
                # 1. We detected a shell prompt and waited the grace period, OR
                # 2. Process not running AND we've been idle too long
                #
                # Important: We don't break if the process is running (even if idle),
                # unless we've found a shell prompt (waiting_for_process_termination)
                if waiting_for_process_termination and idle > 20:
                    PrintStyle(font_color="#85C1E9").stream("[Command completed, returning to agent]\n")
                    break
                elif not process_running and ((full_output and idle > wait_with_output / SLEEP_TIME) or 
                                           (not full_output and idle > wait_without_output / SLEEP_TIME)):
                    # Only break if the process isn't running
                    break
        return full_output

    async def reset_terminal(self):
        self.state.shell.close()
        await self.prepare_state(reset=True)
        response = self.agent.read_prompt("fw.code_reset.md")
        self.log.update(content=response)
        return response
