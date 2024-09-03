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

    async def execute(self,**kwargs):

        await self.agent.handle_intervention() # wait for intervention and handle it, if paused
        
        await self.prepare_state()

        # os.chdir(files.get_abs_path("./work_dir")) #change CWD to work_dir
        
        runtime = self.args["runtime"].lower().strip()
        if runtime == "python":
            response = await self.execute_python_code(self.args["code"])
        elif runtime == "nodejs":
            response = await self.execute_nodejs_code(self.args["code"])
        elif runtime == "terminal":
            response = await self.execute_terminal_command(self.args["code"])
        elif runtime == "output":
            response = await self.get_terminal_output()
        else:
            response = self.agent.read_prompt("fw.code_runtime_wrong.md", runtime=runtime)

        if not response: response = self.agent.read_prompt("fw.code_no_output.md")
        return Response(message=response, break_loop=False)

    async def before_execution(self, **kwargs):
        await self.agent.handle_intervention() # wait for intervention and handle it, if paused
        PrintStyle(font_color="#1B4F72", padding=True, background_color="white", bold=True).print(f"{self.agent.agent_name}: Using tool '{self.name}':")
        self.log = self.agent.context.log.log(type="code_exe", heading=f"{self.agent.agent_name}: Using tool '{self.name}':", content="", kvps=self.args)
        if self.args and isinstance(self.args, dict):
            for key, value in self.args.items():
                PrintStyle(font_color="#85C1E9", bold=True).stream(self.nice_key(key)+": ")
                PrintStyle(font_color="#85C1E9", padding=isinstance(value,str) and "\n" in value).stream(value)
                PrintStyle().print()

    async def after_execution(self, response, **kwargs):
        msg_response = self.agent.read_prompt("fw.tool_response.md", tool_name=self.name, tool_response=response.message)
        await self.agent.append_message(msg_response, human=True)

    async def prepare_state(self):
        self.state = self.agent.get_data("cot_state")
        if not self.state:

            #initialize docker container if execution in docker is configured
            if self.agent.config.code_exec_docker_enabled:
                docker = DockerContainerManager(logger=self.agent.context.log,name=self.agent.config.code_exec_docker_name, image=self.agent.config.code_exec_docker_image, ports=self.agent.config.code_exec_docker_ports, volumes=self.agent.config.code_exec_docker_volumes)
                docker.start_container()
            else: docker = None

            #initialize local or remote interactive shell insterface
            if self.agent.config.code_exec_ssh_enabled:
                shell = SSHInteractiveSession(self.agent.context.log,self.agent.config.code_exec_ssh_addr,self.agent.config.code_exec_ssh_port,self.agent.config.code_exec_ssh_user,self.agent.config.code_exec_ssh_pass)
            else: shell = LocalInteractiveSession()
                
            self.state = State(shell=shell,docker=docker)
            await shell.connect()
        self.agent.set_data("cot_state", self.state)
    
    async def execute_python_code(self, code):
        escaped_code = shlex.quote(code)
        command = f'python3 -c {escaped_code}'
        return await self.terminal_session(command)

    async def execute_nodejs_code(self, code):
        escaped_code = shlex.quote(code)
        command = f'node -e {escaped_code}'
        return await self.terminal_session(command)

    async def execute_terminal_command(self, command):
        return await self.terminal_session(command)

    async def terminal_session(self, command):

        await self.agent.handle_intervention() # wait for intervention and handle it, if paused
       
        self.state.shell.send_command(command)

        PrintStyle(background_color="white",font_color="#1B4F72",bold=True).print(f"{self.agent.agent_name} code execution output:")
        return await self.get_terminal_output()

    async def get_terminal_output(self):
        idle=0
        while True:       
            await asyncio.sleep(0.1)  # Wait for some output to be generated
            full_output, partial_output = await self.state.shell.read_output()

            await self.agent.handle_intervention() # wait for intervention and handle it, if paused
        
            if partial_output:
                PrintStyle(font_color="#85C1E9").stream(partial_output)
                self.log.update(content=full_output)
                idle=0    
            else:
                idle+=1
                if ( full_output and idle > 30 ) or ( not full_output and idle > 100 ): return full_output
                           