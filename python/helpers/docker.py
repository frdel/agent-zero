import time
import docker
import atexit
from typing import Dict, Optional
from python.helpers.files import get_abs_path

class DockerContainerManager:
    def __init__(self, image:str, name:str, ports: Optional[Dict[str, int]] = None, volumes: Optional[Dict[str, Dict[str, str]]] = None):
        self.client = docker.from_env()
        self.image = image
        self.name = name
        self.ports = ports
        self.volumes = volumes
        self.container = None

            

    def cleanup_container(self) -> None:
        if self.container:
            try:
                self.container.stop()
                self.container.remove()
                print(f"Stopped and removed the container: {self.container.id}")
            except Exception as e:
                print(f"Failed to stop and remove the container: {e}")

    def start_container(self) -> None:
        existing_container = None
        for container in self.client.containers.list():
            if container.name == self.name:
                existing_container = container
                break

        if existing_container:
            #print(f"Container with name '{self.name}' is already running with ID: {existing_container.id}")
            pass
        else:
            print(f"Initializing docker container {self.name}...")
            self.container = self.client.containers.run(
                self.image,
                detach=True,
                ports=self.ports,
                name=self.name,
                volumes=self.volumes,
            )
            atexit.register(self.cleanup_container)
            print(f"Started container with ID: {self.container.id}")
            time.sleep(1) # this helps to get SSH ready

