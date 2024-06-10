import subprocess

def execute_terminal_command(command, input_data=None):
    result = subprocess.run(command, shell=True, capture_output=True, text=True, input=input_data)
    return result.stdout + result.stderr

print("1",execute_terminal_command("ls", "y\n"))
print("2",execute_terminal_command("ls", None))