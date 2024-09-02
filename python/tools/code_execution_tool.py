from dataclasses import dataclass
import shlex
from python.helpers import files
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.docker import DockerContainerManager

@dataclass
class State:
    docker: DockerContainerManager | None

class CodeExecution(Tool):
    def execute(self, **kwargs):
        if self.agent.handle_intervention():
            return Response(message="", break_loop=False)

        self.prepare_state()

        runtime = self.args["runtime"].lower().strip()
        code = self.args["code"]

        if runtime == "python":
            command = f'python3 -c {shlex.quote(code)}'
        elif runtime == "nodejs":
            command = f'node -e {shlex.quote(code)}'
        elif runtime == "terminal":
            command = code
        else:
            return Response(message=files.read_file("./prompts/fw.code_runtime_wrong.md", runtime=runtime), break_loop=False)

        output = self.state.docker.execute_command(command)
        
        if not output:
            output = files.read_file("./prompts/fw.code_no_output.md")

        return Response(message=output, break_loop=False)

    def after_execution(self, response, **kwargs):
        msg_response = files.read_file("./prompts/fw.tool_response.md", tool_name=self.name, tool_response=response.message)
        self.agent.append_message(msg_response, human=True)

    def prepare_state(self):
        self.state = self.agent.get_data("cot_state")
        if not self.state:
            if self.agent.config.code_exec_docker_enabled:
                docker = DockerContainerManager(
                    name=self.agent.config.code_exec_docker_name,
                    image=self.agent.config.code_exec_docker_image,
                    ports=self.agent.config.code_exec_docker_ports,
                    volumes=self.agent.config.code_exec_docker_volumes
                )
                docker.start_container()
            else:
                docker = None

            self.state = State(docker=docker)
        self.agent.set_data("cot_state", self.state)