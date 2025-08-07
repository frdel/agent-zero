"""
RFC-accessible system command execution functions.
This module provides functions that can be called via RFC from the host to execute
system commands inside the Docker container.
"""

import subprocess
import tempfile
import os


def execute_system_command(command, capture_output=True, text=True, check=False, input_data=None):
    """Execute a system command inside the container via RFC"""
    try:
        return subprocess.run(
            command,
            capture_output=capture_output,
            text=text,
            check=check,
            input=input_data
        )
    except Exception as e:
        # Return a mock CompletedProcess for consistency
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr=str(e)
        )


def write_file_as_root(file_path, content, permissions="644"):
    """Write a file with root permissions inside the container"""
    try:
        # Write to temp file first
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        # Move to final location with sudo
        result = subprocess.run(['sudo', 'mv', temp_path, file_path], capture_output=True)
        if result.returncode != 0:
            os.remove(temp_path)  # Clean up temp file
            return False

        # Set permissions
        subprocess.run(['sudo', 'chmod', permissions, file_path])
        subprocess.run(['sudo', 'chown', 'root:root', file_path])
        return True
    except Exception:
        return False


def test_connection():
    """Simple test function to verify RFC connectivity"""
    return "RFC connection successful"


def get_container_info():
    """Get information about the container environment"""
    try:
        hostname = subprocess.run(['hostname'], capture_output=True, text=True)
        pwd = subprocess.run(['pwd'], capture_output=True, text=True)
        whoami = subprocess.run(['whoami'], capture_output=True, text=True)

        return {
            'hostname': hostname.stdout.strip() if hostname.returncode == 0 else 'unknown',
            'pwd': pwd.stdout.strip() if pwd.returncode == 0 else 'unknown',
            'user': whoami.stdout.strip() if whoami.returncode == 0 else 'unknown',
            'status': 'container_accessible'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


