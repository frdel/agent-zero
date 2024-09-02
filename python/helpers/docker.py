import time
import docker
import atexit
from typing import Dict, Optional
from python.helpers.files import get_abs_path
from python.helpers.errors import format_error
from python.helpers.print_style import PrintStyle

class DockerContainerManager:
    def __init__(self, image: str, name: str, ports: Optional[Dict[str, int]] = None, volumes: Optional[Dict[str, Dict[str, str]]] = None):
        self.image = image
        self.name = name
        self.ports = ports
        self.volumes = volumes
        self.client = self.init_docker()
        self.container = None

    def init_docker(self):
        while True:
            try:
                return docker.from_env()
            except Exception as e:
                err = format_error(e)
                if "ConnectionRefusedError(61," in err or "Error while fetching server API version" in err:
                    PrintStyle.hint("Connection to Docker failed. Is Docker running?")
                    PrintStyle.error(err)
                    time.sleep(5)
                else:
                    raise

    def start_container(self) -> None:
        existing_container = self.client.containers.list(filters={"name": self.name}, all=True)
        
        if existing_container:
            self.container = existing_container[0]
            if self.container.status != 'running':
                print(f"Starting existing container: {self.name} for safe code execution...")
                self.container.start()
            time.sleep(2)
        else:
            print(f"Initializing docker container {self.name} for safe code execution...")
            self.container = self.client.containers.run(
                self.image,
                detach=True,
                ports=self.ports,
                name=self.name,
                volumes=self.volumes,
            )
            atexit.register(self.cleanup_container)
            print(f"Started container with ID: {self.container.id}")
            time.sleep(5)

    def execute_command(self, command: str) -> str:
        if not self.container:
            raise Exception("Docker container is not initialized or started")

        exec_result = self.container.exec_run(command, demux=True)
        exit_code, output = exec_result.exit_code, exec_result.output

        if exit_code == 0:
            stdout, stderr = output
            return stdout.decode('utf-8') if stdout else stderr.decode('utf-8') if stderr else "Command executed successfully, but produced no output."
        else:
            stdout, stderr = output
            error_message = stderr.decode('utf-8') if stderr else stdout.decode('utf-8') if stdout else "Unknown error occurred"
            return f"Error (exit code {exit_code}): {error_message}"

    def cleanup_container(self) -> None:
        if self.container:
            try:
                self.container.stop()
                self.container.remove()
                print(f"Stopped and removed the container: {self.container.id}")
            except Exception as e:
                print(f"Failed to stop and remove the container: {e}")