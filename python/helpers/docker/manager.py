import time
import docker
import atexit
from typing import Dict, Optional, Tuple, Union, List
from python.helpers.docker.container_utils import check_file_on_host, create_file_in_container, create_unique_filename, is_path_validated
from python.helpers.docker.docker_utils import handle_docker_connection_error
from python.helpers.envconfig import EnvConfigManager

class DockerContainerManager:
    def __init__(self, image: str, name: str, ports: Optional[Dict[str, int]] = None, volumes: Optional[Dict[str, Dict[str, str]]] = None, env_file='.env'):
        self.image = image
        self.name = name
        self.ports = ports
        self.volumes = volumes
        self.env_config = EnvConfigManager(env_file)
        self.init_docker()
                
    def init_docker(self):
        self.client = None
        while not self.client:
            try:
                self.client = docker.from_env()
                self.container = None
            except Exception as e:
                handle_docker_connection_error(e)
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

        # Check if the container already exists
        for container in self.client.containers.list(all=True):
            if container.name == self.name:
                existing_container = container
                break

        # Start existing or new container
        if existing_container:
            self.start_existing_container(existing_container)
        else:
            self.start_new_container()

        # Validate volumes using the running container
        if not self.validate_volumes():
            return

        # Proceed with other operations if needed...

    def validate_volume_for_path(self, container, host_path, container_path):
        unique_filename = create_unique_filename()
        if create_file_in_container(container, container_path, unique_filename):
            return check_file_on_host(host_path, unique_filename)
        return False

    def start_existing_container(self, existing_container):
        if existing_container.status != 'running':
            print(f"Starting existing container: {self.name} for safe code execution...")
            existing_container.start()
            self.container = existing_container
            time.sleep(2)  # This helps to get SSH ready
        else:
            self.container = existing_container
            print(f"Container with name '{self.name}' is already running with ID: {existing_container.id}")

    def start_new_container(self):
        print(f"Initializing docker container {self.name} for safe code execution...")
        
        if self.client is None:
            self.client = self.init_docker()

        # Convert volumes to the expected format
        if self.volumes:
            formatted_volumes = {host_path: config['bind'] for host_path, config in self.volumes.items()}
        else:
            formatted_volumes = None
        
        formatted_ports = self.format_ports(self.ports)

        self.container = self.client.containers.run(
            self.image,
            detach=True,
            ports=formatted_ports,
            name=self.name,
            volumes=formatted_volumes,
        )
        atexit.register(self.cleanup_container)
        print(f"Started container with ID: {self.container.id}")
        time.sleep(5)  # This helps to get SSH ready

    def format_ports(self, ports: Optional[Dict[str, int]]) -> Optional[Dict[str, Union[int, List[int], Tuple[str, int], None]]]:
        """Format the ports to match the expected structure for docker-py."""
        if ports is None:
            return None

        formatted_ports = {}
        for port, value in ports.items():
            if isinstance(value, (int, list, tuple)) or value is None:
                formatted_ports[port] = value
            elif isinstance(value, int):
                formatted_ports[port] = value
            else:
                raise ValueError(f"Invalid port mapping for '{port}': {value}")
        return formatted_ports

    def validate_volumes(self):
        if self.volumes is None:
            return True

        for host_path, volume_config in self.volumes.items():
            validated_paths = self.env_config.get_value("VALIDATED_DOCKER_PATH")
            if validated_paths and is_path_validated(host_path, validated_paths.split(',')):
                print(f"Path '{host_path}' is already validated. Skipping validation.")
                continue

            container_path = volume_config['bind']
            if self.validate_volume_for_path(self.container, host_path, container_path):
                self.env_config.add_validated_path(host_path)
            else:
                print(f"Failed to validate the volume for '{host_path}'. Exiting.")
                self.cleanup_container()
                return False
        return True
