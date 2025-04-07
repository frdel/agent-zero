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
            # Error patterns to detect process completion with errors
            r'.*Error:\s.*$',  # Generic Error pattern
            r'.*ValueError:\s.*$',  # ValueError
            r'.*TypeError:\s.*$',  # TypeError 
            r'.*KeyError:\s.*$',  # KeyError
            r'.*NameError:\s.*$',  # NameError
            r'.*ImportError:\s.*$',  # ImportError
            r'.*AttributeError:\s.*$',  # AttributeError
            r'.*Cannot dlopen some GPU libraries.*$',  # GPU libraries error
            r'.*Process still running.*waiting for output\.\.\.$',  # Status message
            r'Successfully uninstalled.*$',  # Package uninstallation
            r'.*Installing PyTorch with CUDA support.*$',  # PyTorch installation
        ]
        
        # Input prompt patterns to detect when a program is waiting for user input
        input_prompt_patterns = [
            r'.*:\s*$',  # Lines ending with colon followed by optional whitespace
            r'.*\?\s*$',  # Lines ending with question mark
            r'.*>\s*$',   # Lines ending with > (not captured by shell prompts)
            r'.*[Pp]assword.*:\s*$',  # Password prompts
            r'.*[Uu]sername.*:\s*$',  # Username prompts
            r'.*[Cc]ontinue.*\(y/n\).*:\s*$',  # Continue prompts (y/n)
            r'.*\(y/n\).*\s*$',  # Simple y/n prompts
            r'.*\[y/N\].*\s*$',  # Alternative y/N format
            r'.*\[Y/n\].*\s*$',  # Package manager confirmation prompt format
            r'.*[Dd]o you want to continue\?.*\[Y/n\].*\s*$',  # Exact apt-get prompt
            r'.*[Ee]nter.*start.*row.*:\s*$',  # User game input prompt
            r'.*[Ee]nter.*col.*:\s*$',  # User game input prompt
            r'.*[Ee]nter.*end.*row.*:\s*$',  # User game input prompt 
        ]
        
        import re
        shell_prompt_regex = re.compile('|'.join(shell_prompt_patterns))
        input_prompt_regex = re.compile('|'.join(input_prompt_patterns))
        
        waiting_for_process_termination = False
        input_detected = False
        
        while True:
            # Check if we've exceeded max_exec_time, but only enforce if process is not running
            elapsed_time = time.time() - start_time
            # Check if process is still running
            process_running = hasattr(self.state.shell, 'is_process_running') and self.state.shell.is_process_running()
            
            # Special handling for long-running ML processes and installations
            ml_process_keywords = [
                "Installing PyTorch with CUDA support", 
                "Successfully uninstalled",
                "Checking dependencies",
                "Downloading",
                "Generating image",
                "Loading model",
                "Training model",
                "Epoch",
                "Iteration",
                "Processing",
                "Computing",
                "Installing",
                "Building wheel",
                "Uninstalling",
                "step",
                "steps"
            ]
            
            # Special handling for package installation messages
            package_installation_detected = any(pattern in full_output for pattern in ml_process_keywords)
            
            # Additional check for installation process
            if package_installation_detected and process_running:
                PrintStyle(font_color="#85C1E9").stream("\n[Long-running process detected, process still considered running]\n")
                idle = 0  # Reset idle counter since we know process is actively running
                last_status_time = time.time()
            
            # Check for error patterns in the output that would indicate the process has terminated with error
            error_detected = False
            if full_output and (
                "Traceback (most recent call last)" in full_output or
                "Error:" in full_output or
                "ValueError:" in full_output or
                "TypeError:" in full_output or
                "KeyError:" in full_output or
                "NameError:" in full_output or
                "ImportError:" in full_output or
                "AttributeError:" in full_output or
                "Cannot dlopen some GPU libraries" in full_output
            ):
                error_detected = True
                # If error detected but process is still marked as running, override the status
                if process_running:
                    # Don't automatically override status during package installation
                    if not package_installation_detected:
                        process_running = False
                        PrintStyle(font_color="#FF6347").stream("\n[Error detected, overriding process running status]\n")
            
            # Detect if we're in a waiting state with an active process but no output
            inactive_but_running = (process_running and 
                                   idle > wait_with_output / SLEEP_TIME * 3 and 
                                   not waiting_for_process_termination and
                                   not package_installation_detected)
            
            if inactive_but_running:
                # For long-running processes with no output, periodically ping to ensure it's still alive
                idle_time = idle * SLEEP_TIME
                if idle_time > 30:  # Every 30 seconds for very quiet processes
                    PrintStyle(font_color="#FFA500").stream(f"\n[Process running but inactive for {idle_time:.1f}s - checking status]\n")
                    # Reset the idle counter but don't break yet - wait longer for truly long-running processes
                    idle = int(wait_with_output / SLEEP_TIME)
            
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
            
            # Also mark as terminated if we detected an error earlier
            if error_detected and not waiting_for_process_termination and not package_installation_detected:
                PrintStyle(font_color="#FF6347").stream("\n[Error detected, command appears to have failed]\n")
                waiting_for_process_termination = True
                # Shorter grace period for errors
                idle = int(wait_with_output / SLEEP_TIME) - 10  # 10 iterations = ~1 second left
            
            # Check if there's an input prompt in the output indicating the program is waiting for input
            last_lines = full_output.rstrip().split('\n')[-5:] if full_output else []
            
            # Enhanced input prompt detection, looking at the last few lines
            input_prompt_detected = False
            game_input_detected = False

            # Pattern for game-specific inputs
            game_input_patterns = [
                r'[Ee]nter.*start.*row', 
                r'[Ee]nter.*col', 
                r'[Ee]nter.*end.*row',
                r'[Pp]layer.*turn'
            ]

            # First check for game-specific patterns with higher priority
            for line in last_lines:
                for pattern in game_input_patterns:
                    if re.search(pattern, line):
                        game_input_detected = True
                        input_prompt_detected = True
                        PrintStyle(font_color="#00FF00").stream(f"\n[Game input prompt detected: '{line.strip()}']\n")
                        break
                if game_input_detected:
                    break

            # If no game input detected, check for other input prompts
            if not input_prompt_detected:
                for line in last_lines:
                    if input_prompt_regex.search(line) or \
                       "[Input prompt detected]" in line or \
                       "[Y/n]" in line or \
                       "Do you want to continue?" in line or \
                       "Enter" in line and ":" in line and not "error" in line.lower():
                        input_prompt_detected = True
                        PrintStyle(font_color="#FFA500").stream(f"\n[Generic input prompt detected: '{line.strip()}']\n")
                        break

            if process_running and input_prompt_detected and not input_detected:
                input_detected = True  # Set flag to avoid repeated detection
                input_needed_msg = "\n[Input prompt detected, returning to agent]\n"
                PrintStyle(font_color="#FFD700").stream(input_needed_msg)  # Gold color for input prompts
                full_output += input_needed_msg
                self.log.update(content=full_output)
                break

            if partial_output:
                PrintStyle(font_color="#85C1E9").stream(partial_output)
                self.log.update(content=full_output)
                idle = 0
                last_status_time = time.time()
                input_detected = False  # Reset flag if we get new output
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
