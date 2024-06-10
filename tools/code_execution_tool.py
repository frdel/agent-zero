import os, json, contextlib, subprocess, ast, shlex
from io import StringIO
from tools.helpers import files, messages
from agent import Agent


def execute(agent:Agent , code_text:str, runtime:str, **kwargs):

    os.chdir(files.get_abs_path("./work_dir")) #change CWD to work_dir
    
    if runtime == "python":
        response = execute_python_code(code_text)
    elif runtime == "nodejs":
        response = execute_nodejs_code(code_text)
    elif runtime == "terminal":
        response = execute_terminal_command(code_text)
    else:
        return files.read_file("./prompts/fw.code_runtime_wrong.md", runtime=runtime)

    return messages.truncate_text(response, 2000) # TODO parameterize

def execute_python_code(code, input_data="y\n"):
    result = subprocess.run(['python', '-c', code], capture_output=True, text=True, input=input_data)
    return result.stdout + result.stderr

def execute_nodejs_code(code, input_data="y\n"):
    result = subprocess.run(['node', '-e', code], capture_output=True, text=True, input=input_data)
    return result.stdout + result.stderr

def execute_terminal_command(command, input_data="y\n"):
    result = subprocess.run(command, shell=True, capture_output=True, text=True, input=input_data)
    return result.stdout + result.stderr