from typing import Optional
import subprocess
import docker
import time
import docker
import atexit
from typing import Optional
from python.helpers.files import get_abs_path
from python.helpers.errors import format_error
from python.helpers.print_style import PrintStyle
from python.helpers.log import Log
import os

class DockerContainerManager:
    def __init__(self, image: str, name: str, ports: Optional[dict[str, int]] = None, volumes: Optional[dict[str, dict[str, str]]] = None):
        self.image = image
        self.name = name
        self.ports = ports
        self.volumes = volumes
        self.init_docker()

    def init_docker(self):
        self.client = None
        while not self.client:
            try:
                self.client = docker.from_env()
                self.container = None
            except Exception as e:
                err = format_error(e)
                if ("ConnectionRefusedError(61," in err or "Error while fetching server API version" in err):
                    PrintStyle.hint("Connection to Docker failed. Is docker or Docker Desktop running?")
                    Log.log(type="hint", content="Connection to Docker failed. Is docker or Docker Desktop running?")
                    PrintStyle.error(err)
                    Log.log(type="error", content=err)
                    time.sleep(5) # try again in 5 seconds
                else: raise
        return self.client

    def cleanup_container(self) -> None:
        subprocess.run(["docker-compose", "-f", os.path.join("..", "docker", "docker-compose.yml"), "down"])
        print(f"Stopped and removed the container: {self.name}")
        Log.log(type="info", content=f"Stopped and removed the container: {self.name}")

    def start_container(self) -> None:
        if not self.client: self.client = self.init_docker()
        existing_container = None
        for container in self.client.containers.list(all=True):
            if container.name == self.name:
                existing_container = container
                break

        if existing_container:
            if existing_container.status != "running":
                print(f"Starting existing container: {self.name} for safe code execution...")
                Log.log(type="info", content=f"Starting existing container: {self.name} for safe code execution...")
                existing_container.start()
                self.container = existing_container
                time.sleep(2) # this helps to get SSH ready
            else:
                self.container = existing_container
        else:
            # Assuming that self.name is set correctly
            compose_file_path = os.path.join("..", "docker", "docker-compose.yml")

            # Check if the file exists before running the command
            if not os.path.exists(compose_file_path):
                print(f"Error: docker-compose.yml not found at {compose_file_path}")
                Log.log(type="error", content=f"docker-compose.yml not found at {compose_file_path}")

            try:
                print(f"Initializing docker container {self.name} for safe code execution...")
                Log.log(type="info", content=f"Initializing docker container {self.name} for safe code execution...")

                # Run docker-compose command
                result = subprocess.run(["docker-compose", "-f", compose_file_path, "up", "-d"], check=True, capture_output=True, text=True)

                # Debug output of the subprocess result
                print(f"Docker-compose output: {result.stdout}")
                print(f"Docker-compose error (if any): {result.stderr}")

                self.container = self.client.containers.get(self.name)
                atexit.register(self.cleanup_container)

                print(f"Started container with ID: {self.container.id}")
                Log.log(type="info", content=f"Started container with ID: {self.container.id}")

                time.sleep(5)  # this helps to get SSH ready
            except subprocess.CalledProcessError as e:
                print(f"Failed to run docker-compose: {e}")
                print(f"Error output: {e.stderr}")
                Log.log(type="error", content=f"Failed to run docker-compose: {e.stderr}")

