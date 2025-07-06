import sys
import io
import contextlib
import traceback
import ast
import types
import importlib
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle


class DirectCodeExecution(Tool):
    """
    Execute Python code directly in the current process without external dependencies.
    This replaces the SSH/RFC-based code_execution_tool for local development.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Create a persistent namespace for code 
        if not hasattr(self.agent, '_code_namespace'):
            self.agent._code_namespace = {
                '__builtins__': __builtins__,
                'print': print,
                'len': len,
                'range': range,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'set': set,
                'tuple': tuple,
                'type': type,
                'isinstance': isinstance,
                'hasattr': hasattr,
                'getattr': getattr,
                'setattr': setattr,
                'dir': dir,
                'help': help,
                'abs': abs,
                'max': max,
                'min': min,
                'sum': sum,
                'sorted': sorted,
                'reversed': reversed,
                'enumerate': enumerate,
                'zip': zip,
                'map': map,
                'filter': filter,
                'any': any,
                'all': all,
            }

    async def execute(self, **kwargs) -> Response:
        runtime = self.args.get("runtime", "python").lower().strip()
        code = self.args.get("code", "")
        
        if not code:
            return Response(message="No code provided", break_loop=False)

        if runtime == "python":
            return await self.execute_python_code(code)
        elif runtime == "terminal":
            return await self.execute_terminal_command(code)
        elif runtime == "nodejs":
            return Response(message="Node.js execution not supported in direct mode. Use Python instead.", break_loop=False)
        else:
            return Response(message=f"Runtime '{runtime}' not supported", break_loop=False)

    async def execute_python_code(self, code: str) -> Response:
        """Execute Python code directly in the current process."""
        try:
            # Create output capture
            output_buffer = io.StringIO()
            error_buffer = io.StringIO()
            
            # Parse the code to check if it's an expression or statement
            try:
                # Try to parse as expression first
                ast.parse(code, mode='eval')
                is_expression = True
            except SyntaxError:
                # If that fails, it's a statement
                is_expression = False

            with contextlib.redirect_stdout(output_buffer), \
                 contextlib.redirect_stderr(error_buffer):
                
                try:
                    if is_expression:
                        # Execute as expression and capture result
                        result = eval(code, self.agent._code_namespace)
                        if result is not None:
                            print(repr(result))
                    else:
                        # Execute as statement
                        exec(code, self.agent._code_namespace)
                        
                except Exception as e:
                    # Print the exception to stderr
                    traceback.print_exc()

            # Get output and errors
            stdout = output_buffer.getvalue()
            stderr = error_buffer.getvalue()
            
            # Combine output
            result_text = ""
            if stdout:
                result_text += f"Output:\n{stdout}"
            if stderr:
                if result_text:
                    result_text += "\n"
                result_text += f"Error:\n{stderr}"
            
            if not result_text:
                result_text = "Code executed successfully (no output)"

            return Response(message=result_text, break_loop=False)

        except Exception as e:
            error_msg = f"Execution failed: {str(e)}\n{traceback.format_exc()}"
            return Response(message=error_msg, break_loop=False)

    async def execute_terminal_command(self, command: str) -> Response:
        """
        Limited terminal command support using Python libraries where possible.
        """
        import os
        import subprocess
        import shlex
        
        try:
            # Handle common commands with Python equivalents
            command = command.strip()
            
            if command.startswith('ls'):
                # List directory
                path = '.' if len(command.split()) == 1 else command.split()[1]
                try:
                    files = os.listdir(path)
                    result = '\n'.join(files)
                    return Response(message=result, break_loop=False)
                except Exception as e:
                    return Response(message=f"Error listing directory: {e}", break_loop=False)
            
            elif command.startswith('pwd'):
                # Print working directory
                return Response(message=os.getcwd(), break_loop=False)
            
            elif command.startswith('cd'):
                # Change directory
                if len(command.split()) > 1:
                    path = command.split()[1]
                    try:
                        os.chdir(path)
                        return Response(message=f"Changed to {os.getcwd()}", break_loop=False)
                    except Exception as e:
                        return Response(message=f"Error changing directory: {e}", break_loop=False)
                else:
                    return Response(message="No directory specified", break_loop=False)
            
            elif command.startswith('mkdir'):
                # Make directory
                if len(command.split()) > 1:
                    path = command.split()[1]
                    try:
                        os.makedirs(path, exist_ok=True)
                        return Response(message=f"Directory created: {path}", break_loop=False)
                    except Exception as e:
                        return Response(message=f"Error creating directory: {e}", break_loop=False)
                else:
                    return Response(message="No directory specified", break_loop=False)
            
            elif command.startswith('cat'):
                # Read file
                if len(command.split()) > 1:
                    filename = command.split()[1]
                    try:
                        with open(filename, 'r') as f:
                            content = f.read()
                        return Response(message=content, break_loop=False)
                    except Exception as e:
                        return Response(message=f"Error reading file: {e}", break_loop=False)
                else:
                    return Response(message="No file specified", break_loop=False)
            
            else:
                # For other commands, try to execute safely with subprocess
                try:
                    # Only allow safe commands
                    safe_commands = ['echo', 'date', 'whoami', 'which', 'python', 'pip']
                    cmd_parts = shlex.split(command)
                    if cmd_parts and cmd_parts[0] in safe_commands:
                        result = subprocess.run(
                            command, 
                            shell=True, 
                            capture_output=True, 
                            text=True, 
                            timeout=30
                        )
                        output = result.stdout + result.stderr
                        return Response(message=output if output else "Command executed", break_loop=False)
                    else:
                        return Response(
                            message=f"Command '{cmd_parts[0] if cmd_parts else command}' not allowed in direct mode. Use Python code instead.", 
                            break_loop=False
                        )
                except Exception as e:
                    return Response(message=f"Error executing command: {e}", break_loop=False)

        except Exception as e:
            return Response(message=f"Terminal command failed: {e}", break_loop=False)

    async def before_execution(self, **kwargs):
        """Setup before execution."""
        # Import commonly used libraries into namespace
        try:
            import_statements = [
                "import os",
                "import sys", 
                "import json",
                "import datetime",
                "import math",
                "import random",
                "import re",
                "from pathlib import Path",
            ]
            
            for stmt in import_statements:
                try:
                    exec(stmt, self.agent._code_namespace)
                except ImportError:
                    # Skip if module not available
                    pass
        except:
            pass

    async def after_execution(self, response: Response, **kwargs):
        """Cleanup after execution."""
        # Log the execution
        self.log.update(result=response.message)
        
        # Print result
        PrintStyle(
            font_color="#1B4F72", background_color="white", padding=True, bold=True
        ).print(f"{self.agent.agent_name}: Response from tool '{self.name}'")
        
        # Truncate very long outputs for display
        display_message = response.message
        if len(display_message) > 1000:
            display_message = display_message[:1000] + "... (truncated)"
        
        PrintStyle(font_color="#85C1E9").print(display_message)
