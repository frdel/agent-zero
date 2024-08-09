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
        try:
            if self.container:
                self.container.stop()
                print(f"Stopped container: {self.container.id}")
                self.container.remove()
                print(f"Removed container: {self.container.id}")
        except docker.errors.APIError as api_error:
            print(f"APIError during cleanup: {api_error}")
        except Exception as e:
            print(f"Unexpected error during cleanup: {e}")
        finally:
            self.running = False

    def check_and_reconnect(self):
        try:
            if self.container and self.container.status != 'running':
                print(f"Restarting container: {self.name}")
                self.container.start()
                time.sleep(5)
                print(f"Successfully reconnected to container: {self.name}")
            elif not self.container:
                print("No container found. Starting a new one.")
                self.start_container()
        except docker.errors.APIError as api_error:
            print(f"Failed to reconnect: Docker API error: {api_error}")
        except Exception as e:
            print(f"Failed to reconnect to container: {e}")

    def start_container(self) -> None:
        try:
            existing_container = self.client.containers.get(self.name)
            if existing_container.status != 'running':
                print(f"Starting existing container: {self.name}")
                existing_container.start()
                self.container = existing_container
                time.sleep(2)
            else:
                self.container = existing_container
                print(f"Container {self.name} is already running.")
        except NotFound:
            try:
                print(f"Creating new container: {self.name}")
                self.container = self.client.containers.run(
                    self.image,
                    detach=True,
                    ports=self.ports,
                    name=self.name,
                    volumes=self.volumes,
                )
                print(f"Started new container with ID: {self.container.id}")
            except docker.errors.ImageNotFound as inf:
                print(f"Image not found: {inf}")
            except docker.errors.APIError as api_error:
                print(f"Docker API error: {api_error}")
            except Exception as e:
                print(f"Unexpected error when starting container: {e}")
            finally:
                atexit.register(self.cleanup_container)
                time.sleep(5)
                self.start_health_check_thread()

    def health_check(self):
        while self.running:
            try:
                if self.container:
                    self.container.reload()
                    if self.container.status != 'running':
                        print(f"Container {self.container.id} not running, attempting restart.")
                        self.check_and_reconnect()
                time.sleep(self.health_check_interval)
            except docker.errors.APIError as api_error:
                print(f"Docker API error during health check: {api_error}")
            except Exception as e:
                print(f"Unexpected error in health check: {e}")
                time.sleep(self.health_check_interval)

    def start_health_check_thread(self):
        health_thread = threading.Thread(target=self.health_check, daemon=True)
        health_thread.start()