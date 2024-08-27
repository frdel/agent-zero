import os
import subprocess
import re
import time

from python.helpers.print_style import PrintStyle


def handle_docker_connection_error(e):
    """Handle Docker connection errors with appropriate messaging."""
    err = str(e)
    if "FileNotFoundError(2," in err:
        PrintStyle.hint("Connection to Docker failed. Is Docker or Docker Desktop running?")
        check_docker_context(show_details=False)  # Check context without showing details
        time.sleep(1000)  # Try again in 5 seconds
    elif "ConnectionRefusedError(61," in err or "Error while fetching server API version" in err:
        PrintStyle.hint("Connection to Docker failed. Is Docker or Docker Desktop running?")
        PrintStyle.error(err)
        time.sleep(5)  # Try again in 5 seconds
    else:
        raise

def check_docker_context(show_details=True):
    """Check Docker context, showing details only if requested or if there's a mismatch."""
    try:
        context_lines = get_docker_contexts()
        active_context, all_contexts = parse_docker_contexts(context_lines)

        if show_details:
            if len(context_lines) > 1:
                PrintStyle.warning("Found multiple Docker contexts on your machine:")
            display_contexts(all_contexts)

        if active_context:
            if not validate_docker_host(active_context, show_details) and not show_details:
                # If mismatch is detected and details are not shown, show them now
                check_docker_context(show_details=True)

    except subprocess.CalledProcessError as ex:
        PrintStyle.error(f"Failed to check Docker context: {ex}")
        exit(1)

def get_docker_contexts():
    """Retrieve the list of Docker contexts."""
    result = subprocess.run(["docker", "context", "ls"], capture_output=True, text=True, check=True)
    return result.stdout.splitlines()

def parse_docker_contexts(context_lines):
    """Parse the Docker contexts and identify the active one."""
    active_context = None
    all_contexts = []

    for line in context_lines:
        if line.startswith('NAME'):  # Skip the header
            continue
        
        # Split the line by two or more spaces
        parts = re.split(r'\s{2,}', line.strip())
        
        # The format should be [context_name, description, context_endpoint, (optional) error]
        context_name = parts[0]
        context_endpoint = parts[2]  # The Docker endpoint is always the third part
        is_active = '*' in context_name

        if is_active:
            context_name = context_name.replace('*', '').strip()
            active_context = context_endpoint

        all_contexts.append((context_name, context_endpoint, is_active))

    return active_context, all_contexts

def display_contexts(all_contexts):
    """Display all Docker contexts, highlighting the active one."""
    for context_name, context_endpoint, is_active in all_contexts:
        if is_active:
            PrintStyle.warning(f"  * {context_name} (active) - {context_endpoint}")
        else:
            PrintStyle.warning(f"    {context_name} - {context_endpoint}")

def validate_docker_host(active_context, show_details):
    """Validate the DOCKER_HOST environment variable against the active Docker context."""
    env_docker_host = os.getenv("DOCKER_HOST") or "unix:///var/run/docker.sock"

    if env_docker_host and env_docker_host != active_context:
        
        if show_details == False:
            return False

        print_docker_host_mismatch(active_context, env_docker_host)

    return True
def print_docker_host_mismatch(active_context, env_docker_host):
    """Print a warning message about the mismatch between Docker context and DOCKER_HOST."""
    PrintStyle.error(
            f"Mismatch between DOCKER_HOST on your machine and the environment; this is most likely not intended.\n"
            f"Your current Docker context on your machine is using '{active_context}',\n"
            f"but your DOCKER_HOST environment that DockerManager is trying to connect to is set to '{env_docker_host}'."
        )

    # Provide the correct hint depending on the platform
    if os.name == 'nt':  # Windows
        PrintStyle.hint(f"To fix this, run: set DOCKER_HOST={active_context} or add it to your .env file.")
    else:  # macOS/Linux
        PrintStyle.hint(f"To fix this, run: export DOCKER_HOST={active_context} or add it to your .env file.")
