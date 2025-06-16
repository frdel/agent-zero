#!/usr/bin/env python3
import subprocess
import shlex
import os

def execute_local_command(command_string: str, timeout: int = 60) -> dict:
    """
    Executes a shell command on the local host, captures its output,
    and returns it in a structured dictionary.
    """
    env = os.environ.copy()
    # Ensure standard system paths are included for the command
    env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:' + env.get('PATH', '')

    try:
        command_parts = shlex.split(command_string)
        result = subprocess.run(
            command_parts,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env
        )
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
    except FileNotFoundError:
        return {
            "success": False, "return_code": -1, "stdout": "",
            "stderr": f"Command not found: '{command_parts[0]}'. Please ensure it is installed and in the system's PATH."
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False, "return_code": -1, "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds."
        }
    except Exception as e:
        return {
            "success": False, "return_code": -1, "stdout": "",
            "stderr": f"An unexpected error occurred: {str(e)}"
        }
