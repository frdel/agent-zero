from typing import Dict, Any


class AgentConfig:
    def __init__(self) -> None:
        self.max_tool_response_length: int = 1000
        self.code_exec_docker_enabled: bool = True
        self.code_exec_docker_name: str = "agent-zero-container"
        self.code_exec_docker_image: str = "agent-zero-image"
        self.code_exec_docker_ports: Dict[str, int] = {"80": 8080}
        self.code_exec_ssh_enabled: bool = False
        self.code_exec_ssh_addr: str = ""
        self.code_exec_ssh_port: int = 22
        self.code_exec_ssh_user: str = ""
        self.code_exec_ssh_pass: str = ""
        self.memory_subdir: str = "memory"
        self.knowledge_subdir: str = "knowledge"
        self.response_timeout_seconds: int = 60
        self.chat_model_name: str = "default_chat_model"
        self.utility_model_name: str = "default_utility_model"
        self.embedding_model_name: str = "default_embedding_model"
        self.chat_model: Any = None
        self.utility_model: Any = None
        self.embeddings_model: Any = None


# Define missing constants
DEFAULT_MODEL = "gpt-4"
FALLBACK_MODEL = "gpt-3"
MODEL_SPECS = {
    "gpt-4": {"version": "4.0", "capabilities": ["chat", "code"]},
    "gpt-3": {"version": "3.5", "capabilities": ["chat"]},
}
