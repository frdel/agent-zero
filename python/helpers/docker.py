import time
import docker
from docker.errors import NotFound
import atexit
from typing import Dict, Optional
import threading
from python.helpers.files import get_abs_path

class DockerContainerManager:
    def __init__(self, image: str, name: str, ports: Optional[Dict[str, int]] = None, volumes: Optional[Dict[str, Dict[str, str]]] = None):
        self.client = docker.from_env()
        self.image = image
        self.name = name
        self.ports = ports
        self.volumes = volumes
        self.container = None
        self.health_check_interval = 60  # Time in seconds between health checks
        self.running = True

    def cleanup_container(self) -> None:
        if self.container:
            try:
                self.container.stop()
                self.container.remove()
                print(f"Stopped and removed the container: {self.container.id}")
            except Exception as e:
                print(f"Failed to stop and remove the container: {e}")
            finally:
                self.running = False

    def check_and_reconnect(self):
        try:
            if self.container and self.container.status != 'running':
                print(f"Attempting to reconnect to container: {self.name}")
                self.container.start()
                time.sleep(5)  # Allow time for the container to be ready
                print(f"Reconnected to container: {self.name}")
            elif not self.container:
                print(f"No container found. Starting a new one.")
                self.start_container()
        except Exception as e:
            print(f"Failed to reconnect to the container: {e}")

    def start_container(self) -> None:
        try:
            existing_container = self.client.containers.get(self.name)
        except NotFound:
            existing_container = None

        if existing_container:
            if existing_container.status != 'running':
                print(f"Starting existing container: {self.name} for safe code execution...")
                existing_container.start()
                self.container = existing_container
                time.sleep(5)  # This helps to get SSH ready
            else:
                self.container = existing_container
                print(f"Container with name '{self.name}' is already running with ID: {existing_container.id}")
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
            self.start_health_check_thread()

    def health_check(self):
        while self.running:
            try:
                if self.container:
                    self.container.reload()
                    if self.container.status != 'running':
                        print(f"Container {self.container.id} is not running, attempting to restart.")
                        self.check_and_reconnect()
                time.sleep(self.health_check_interval)
            except Exception as e:
                print(f"Health check failed: {e}")
                time.sleep(self.health_check_interval)

    def start_health_check_thread(self):
        health_thread = threading.Thread(target=self.health_check, daemon=True)
        health_thread.start()