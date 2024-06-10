import os, json, contextlib
from io import StringIO
from tools.helpers import files
import ast
from agent import Agent


def execute(agent:Agent ,code_text:str, **kwargs):

    return execute_user_code(code_text)
    
    def execute_code(code_string, input=None):
        os.chdir(files.get_abs_path("./work_dir")) #change CWD to work_dir
        buffer = StringIO()
        local_vars = {} # {"input": input}

        with contextlib.redirect_stdout(buffer):
            try:        
                indented_code = "\n    ".join(code_string.strip().split("\n"))
                wrapped_code = f"""def isolate(input):\n    {indented_code}"""        
                exec(wrapped_code, None, local_vars) # exec(code_string, {"__builtins__": __builtins__}, local_vars)
                return local_vars.get('isolate', lambda: None)(input)  # type: ignore # calling main if defined to get its return value

            except Exception as e:
                import traceback
                error_info = traceback.format_exc()
                return json.dumps({"error": str(e), "details": error_info})
        # return local_vars.get("output", buffer.getvalue())

    result = json.dumps(output) if (output := execute_code(code_text)) else files.read_file("./prompts/fw.code_no_output.md")
    return result



def wrap_code_with_return_and_function(code):
    # Parse the code into an AST
    parsed_code = ast.parse(code)
    # Filter out only executable statements, ignoring comments and empty lines
    executable_statements = [stmt for stmt in parsed_code.body if not isinstance(stmt, ast.Pass)]
    
    if not executable_statements:
        raise Exception("There are no executable statements in the code.")
    else:
        # Get the last executable statement in the code
        last_statement = executable_statements[-1]

        # Check if the last statement is an expression (including function calls)
        if isinstance(last_statement, ast.Expr):
            # Convert the expression into a return statement
            return_stmt = ast.Return(value=last_statement.value)
            return_stmt.lineno = last_statement.lineno
            return_stmt.col_offset = last_statement.col_offset
            parsed_code.body[parsed_code.body.index(last_statement)] = return_stmt

        # Wrap the entire code in a function definition
        function_def = ast.FunctionDef(
            name="isolate",
            args=ast.arguments(
                posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=parsed_code.body,
            decorator_list=[],
            lineno=1,
            col_offset=0
        ) # type: ignore

    # Create a new module with the function definition
    module = ast.Module(body=[function_def], type_ignores=[])
    
    # Convert the AST back to source code
    wrapped_code = compile(module, filename="<ast>", mode="exec")
    return wrapped_code
def execute_user_code(code):
    try:
        wrapped_code = wrap_code_with_return_and_function(code)
        exec_globals = {}
        exec_locals = {}
        exec(wrapped_code, exec_globals, exec_locals)
        os.chdir(files.get_abs_path("./work_dir")) #change CWD to work_dir
        try:
            return exec_locals.get('isolate', lambda: None)()
        except Exception as e:
                    import traceback
                    error_info = traceback.format_exc()
                    return json.dumps({"error": str(e), "details": error_info})

    except Exception as e:
        return "Error: " + str(e)