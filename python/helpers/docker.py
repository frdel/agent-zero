import time
import docker
import atexit
from typing import Dict, Optional
from python.helpers.errors import format_error
from python.helpers.print_style import PrintStyle
from python.helpers.files import get_abs_path

class DockerContainerManager:
    def __init__(self, image: str, name: str, ports: Optional[Dict[str, str]] = None, volumes: Optional[Dict[str, Dict[str, str]]] = None):
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
                    PrintStyle.hint("Connection to Docker failed. Is Docker or Docker Desktop running?")
                    PrintStyle.error(err)
                    time.sleep(5)  # try again in 5 seconds
                else:
                    raise
        return self.client

    def cleanup_container(self) -> None:
        if self.container:
            try:
                self.container.stop()
                self.container.remove()
                print(f"Stopped and removed the container: {self.container.id}")
            except Exception as e:
                print(f"Failed to stop and remove the container: {e}")

    def start_container(self) -> None:
        if not self.client:
            self.client = self.init_docker()

        existing_container = None
        for container in self.client.containers.list(all=True):
            if container.name == self.name:
                existing_container = container
                break

        if existing_container:
            if existing_container.status != 'running':
                print(f"Starting existing container: {self.name} for safe code execution...")
                existing_container.start()
                self.container = existing_container
                time.sleep(2)  # This helps to get SSH ready
            else:
                self.container = existing_container
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
            time.sleep(5)  # This helps to get SSH ready