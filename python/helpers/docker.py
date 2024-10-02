import time
import docker
from docker.client import DockerClient
import atexit
from typing import Dict, Optional, Union, List, Any, TYPE_CHECKING
from python.helpers.errors import format_error
from python.helpers.print_style import PrintStyle

if TYPE_CHECKING:
    from docker import DockerClient

# Type aliases
PortMapping = Dict[str, Union[int, List[int], tuple[str, int], None]]
VolumeMapping = Dict[str, Dict[str, str]]
Container = Any  # Use Any for docker types to avoid mypy errors
DockerClient = Any


class DockerContainerManager:
    def __init__(
        self,
        image: str,
        name: str,
        ports: Optional[PortMapping] = None,
        volumes: Optional[VolumeMapping] = None,
    ):
        self.image = image
        self.name = name
        self.ports = ports
        self.volumes = volumes
        self.client: Optional[DockerClient] = None
        self.container: Optional[Container] = None
        self.init_docker()

    def init_docker(self) -> Optional[DockerClient]:
        while self.client is None:
            try:
                self.client = DockerClient.from_env()
            except Exception as e:
                err = format_error(e)
                if "ConnectionRefusedError(61," in err or "Error while fetching server API version" in err:
                    PrintStyle.hint("Connection to Docker failed. Is Docker running?")
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

        if self.client:
            existing_container = next(
                (c for c in self.client.containers.list(all=True) if c.name == self.name),
                None,
            )

            if existing_container:
                if existing_container.status != "running":
                    print(f"Starting existing container: {self.name} " "for safe code execution...")
                    existing_container.start()
                    self.container = existing_container
                    time.sleep(2)  # this helps to get SSH ready
                else:
                    self.container = existing_container
            else:
                print(f"Initializing docker container {self.name} " "for safe code execution...")
                run_kwargs: Dict[str, Any] = {
                    "image": self.image,
                    "detach": True,
                    "name": self.name,
                }
                if self.ports:
                    run_kwargs["ports"] = self.ports
                if self.volumes:
                    run_kwargs["volumes"] = self.volumes

                self.container = self.client.containers.run(**run_kwargs)
                atexit.register(self.cleanup_container)
                if self.container:
                    print(f"Started container with ID: {self.container.id}")
                    time.sleep(5)  # this helps to get SSH ready
        else:
            print("Failed to initialize Docker client.")
