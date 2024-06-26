import os, json, contextlib, subprocess, ast, shlex
from io import StringIO
from tools.helpers import files, messages
from agent import Agent
from tools.helpers.tool import Tool, Response
from tools.helpers import files
from tools.helpers.print_style import PrintStyle

class CodeExecution(Tool):

    def execute(self,**kwargs):

        # os.chdir(files.get_abs_path("./work_dir")) #change CWD to work_dir
        
        runtime = self.args["runtime"].lower().strip()
        if runtime == "python":
            response = self.execute_python_code(self.args["code"])
        elif runtime == "nodejs":
            response = self.execute_nodejs_code(self.args["code"])
        elif runtime == "terminal":
            response = self.execute_terminal_command(self.args["code"])
        else:
            response = files.read_file("./prompts/fw.code_runtime_wrong.md", runtime=runtime)

        if not response: response = files.read_file("./prompts/fw.code_no_output.md")
        return Response(message=response, break_loop=False)

    def execute_python_code(self, code, input_data="y\n"):
        result = subprocess.run(['python', '-c', code], capture_output=True, text=True, input=input_data)
        return result.stdout + result.stderr

    def execute_nodejs_code(self, code, input_data="y\n"):
        result = subprocess.run(['node', '-e', code], capture_output=True, text=True, input=input_data)
        return result.stdout + result.stderr

    def execute_terminal_command(self, command, input_data="y\n"):
        result = subprocess.run(command, shell=True, capture_output=True, text=True, input=input_data)
        return result.stdout + result.stderr