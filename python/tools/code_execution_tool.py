from dataclasses import dataclass
import os, json, contextlib, subprocess, ast, shlex
from io import StringIO
import time
from typing import Literal
from python.helpers import files, messages
from agent import Agent
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

    def execute(self,**kwargs):

        if self.agent.handle_intervention(): return Response(message="", break_loop=False)  # wait for intervention and handle it, if paused
        
        self.prepare_state()

        # os.chdir(files.get_abs_path("./work_dir")) #change CWD to work_dir
        
        runtime = self.args["runtime"].lower().strip()
        if runtime == "python":
            response = self.execute_python_code(self.args["code"])
        elif runtime == "nodejs":
            response = self.execute_nodejs_code(self.args["code"])
        elif runtime == "terminal":
            response = self.execute_terminal_command(self.args["code"])
        elif runtime == "output":
            response = self.get_terminal_output()
        else:
            response = files.read_file("./prompts/fw.code_runtime_wrong.md", runtime=runtime)

        if not response: response = files.read_file("./prompts/fw.code_no_output.md")
        return Response(message=response, break_loop=False)

    def after_execution(self, response, **kwargs):
        msg_response = files.read_file("./prompts/fw.tool_response.md", tool_name=self.name, tool_response=response.message)
        self.agent.append_message(msg_response, human=True)

    def prepare_state(self):
        self.state = self.agent.get_data("cot_state")
        if not self.state:

            #initialize docker container if execution in docker is configured
            if self.agent.config.code_exec_docker_enabled:
                docker = DockerContainerManager(name=self.agent.config.code_exec_docker_name, image=self.agent.config.code_exec_docker_image, ports=self.agent.config.code_exec_docker_ports, volumes=self.agent.config.code_exec_docker_volumes)
                docker.start_container()
            else: docker = None

            #initialize local or remote interactive shell insterface
            if self.agent.config.code_exec_ssh_enabled:
                shell = SSHInteractiveSession(self.agent.config.code_exec_ssh_addr,self.agent.config.code_exec_ssh_port,self.agent.config.code_exec_ssh_user,self.agent.config.code_exec_ssh_pass)
            else: shell = LocalInteractiveSession()
                
            self.state = State(shell=shell,docker=docker)
            shell.connect()
        self.agent.set_data("cot_state", self.state)
    
    def execute_python_code(self, code):
        escaped_code = shlex.quote(code)
        command = f'python3 -c {escaped_code}'
        return self.terminal_session(command)

    def execute_nodejs_code(self, code):
        escaped_code = shlex.quote(code)
        command = f'node -e {escaped_code}'
        return self.terminal_session(command)

    def execute_terminal_command(self, command):
        return self.terminal_session(command)

    def terminal_session(self, command):

        if self.agent.handle_intervention(): return ""  # wait for intervention and handle it, if paused
       
        self.state.shell.send_command(command)

        PrintStyle(background_color="white",font_color="#1B4F72",bold=True).print(f"{self.agent.agent_name} code execution output:")
        return self.get_terminal_output()

    def get_terminal_output(self):
        idle = 0
        max_idle_cycles = 300  # Example idle timeout cycles (adjust as needed)
        full_output = ""
        displayed_output = set()
        last_partial_output = None  # To track the last piece of output
        prompt_detected = False

        while True:
            time.sleep(0.1)  # Wait for some output to be generated
            output_tuple = self.state.shell.read_output()

            if self.agent.handle_intervention():
                return self.summarize_output(full_output)

            if output_tuple:
                partial_output = output_tuple[0] if isinstance(output_tuple, tuple) else output_tuple
                if partial_output:
                    # Stream all unique outputs to the user
                    if partial_output not in displayed_output:
                        PrintStyle(font_color="#85C1E9").stream(partial_output)
                        displayed_output.add(partial_output)

                    full_output += partial_output

                    # Reset idle counter if new output differs from last output
                    if partial_output != last_partial_output:
                        idle = 0
                        last_partial_output = partial_output
                    else:
                        idle += 1

                    # Check for interaction prompts (like `[Y/n]`)
                    if any(prompt in partial_output.lower() for prompt in
                           ["[y/n]", "proceed (y/n)", "continue (y/n)", "do you want to continue", "yes/no"]):
                        prompt_detected = True
                        break

                    # Check for the command prompt indicating the end of output
                    if "root@" in partial_output and partial_output.strip().endswith("#"):
                        break  # End the loop when the prompt is detected
                else:
                    idle += 1
            else:
                idle += 1

            # Exit the loop if no new output has been received for a while
            if idle > max_idle_cycles:
                PrintStyle(font_color="yellow", padding=True).print("Idle timeout reached. No new output detected.")
                break

        return self.summarize_output(full_output, prompt_detected)

    def summarize_output(self, full_output, prompt_detected=False):
        # Log the summary attempt
        PrintStyle(font_color="blue", padding=True).print("Attempting to summarize output...")

        # Capture the last 2000 characters
        summarized_output = full_output[-2000:].strip()

        # Check if summarized output is not empty and log
        if summarized_output:
            PrintStyle(font_color="green", padding=True).print(
                f"Relevant output captured: {summarized_output[:100]}...")  # Log a snippet of the output
        else:
            summarized_output = "No relevant output captured."
            PrintStyle(font_color="red", padding=True).print("No relevant output captured; returning default message.")

        # If a prompt was detected, inform the agent
        if prompt_detected:
            PrintStyle(font_color="yellow", padding=True).print(
                "Interaction prompt detected, returning to agent for handling.")

        return summarized_output







