import time
import docker
import atexit
from typing import Dict, Optional
from python.helpers.files import get_abs_path
from python.helpers.errors import format_error
from python.helpers.print_style import PrintStyle

class DockerContainerManager:
    def __init__(self, image: str, name: str, ports: Optional[Dict[str, int]] = None, volumes: Optional[Dict[str, Dict[str, str]]] = None):
        """
        Initialize a DockerContainerManager.

        Args:
        - image (str): Name of the Docker image to use.
        - name (str): Name of the Docker container.
        - ports (Dict[str, int], optional): A dictionary of {host_port: container_port} to map ports from the container to the host. Defaults to None.
        - volumes (Dict[str, Dict[str, str]], optional): A dictionary of {host_path: {container_path: mode}} to mount volumes from the host to the container. Defaults to None.
        """
        self.image = image
        self.name = name
        self.ports = ports
        self.volumes = volumes
        self.client = self.init_docker()
        self.container = None

    def init_docker(self):
        """
        Initialize a Docker client.

        This method will retry indefinitely until a connection to Docker can be established.
        """
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
        """
        Start a Docker container.

        If a container with the given name already exists and is not running,
        start it. Otherwise, create a new container with the given image and
        name.

        Args:
        - None

        Returns:
        - None

        Raises:
        - None
        """
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
        """
        Execute a command in the Docker container.

        Args:
            command (str): The command to execute.

        Returns:
            str: The output of the command, or an error message if the command failed.

        Raises:
            Exception: If the Docker container is not initialized or started.
        """
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
        """
        Clean up the Docker container.

        Stop and remove the container if it exists.

        Returns:
            None

        Raises:
            Exception: If the Docker container is not initialized or started.
        """
        if self.container:
            try:
                self.container.stop()
                self.container.remove()
                print(f"Stopped and removed the container: {self.container.id}")
            except Exception as e:
                print(f"Failed to stop and remove the container: {e}")