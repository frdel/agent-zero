"""Configuration module for the agent system."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


class AgentException(Exception):
    """Base exception class for agent configuration errors."""

    pass


@dataclass
class AgentConfig:
    """Configuration class for agent settings."""

    chat_model: Optional[str] = None
    utility_model: Optional[str] = None
    embeddings_model: Optional[str] = None
    knowledge_subdirs: List[str] = field(default_factory=lambda: ["default", "custom"])
    auto_memory_count: int = 3
    rate_limit_requests: int = 15
    max_tool_response_length: int = 3000
    code_exec_docker_enabled: bool = True
    code_exec_ssh_enabled: bool = True
    prompts_subdir: str = ""
    memory_subdir: str = ""
    rate_limit_seconds: int = 60
    rate_limit_input_tokens: int = 0
    rate_limit_output_tokens: int = 0
    msgs_keep_max: int = 25
    msgs_keep_start: int = 5
    msgs_keep_end: int = 10
    response_timeout_seconds: int = 60
    code_exec_docker_name: str = "agent-zero-exe"
    code_exec_docker_image: str = "frdel/agent-zero-exe:latest"
    code_exec_docker_ports: Dict[str, int] = field(
        default_factory=lambda: {"22/tcp": 50022}
    )
    code_exec_ssh_addr: str = "localhost"
    code_exec_ssh_port: int = 50022
    code_exec_ssh_user: str = "root"
    code_exec_ssh_pass: str = "toor"
    additional: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "chat_model": self.chat_model,
            "utility_model": self.utility_model,
            "embeddings_model": self.embeddings_model,
            "knowledge_subdirs": self.knowledge_subdirs,
            "auto_memory_count": self.auto_memory_count,
            "rate_limit_requests": self.rate_limit_requests,
            "max_tool_response_length": self.max_tool_response_length,
            "code_exec_docker_enabled": self.code_exec_docker_enabled,
            "code_exec_ssh_enabled": self.code_exec_ssh_enabled,
            "prompts_subdir": self.prompts_subdir,
            "memory_subdir": self.memory_subdir,
            "rate_limit_seconds": self.rate_limit_seconds,
            "rate_limit_input_tokens": self.rate_limit_input_tokens,
            "rate_limit_output_tokens": self.rate_limit_output_tokens,
            "msgs_keep_max": self.msgs_keep_max,
            "msgs_keep_start": self.msgs_keep_start,
            "msgs_keep_end": self.msgs_keep_end,
            "response_timeout_seconds": self.response_timeout_seconds,
            "code_exec_docker_name": self.code_exec_docker_name,
            "code_exec_docker_image": self.code_exec_docker_image,
            "code_exec_docker_ports": self.code_exec_docker_ports,
            "code_exec_ssh_addr": self.code_exec_ssh_addr,
            "code_exec_ssh_port": self.code_exec_ssh_port,
            "code_exec_ssh_user": self.code_exec_ssh_user,
            "code_exec_ssh_pass": self.code_exec_ssh_pass,
            "additional": self.additional,
        }


class ConfigValidator:
    """Validates agent configuration."""

    @staticmethod
    def validate_config(config: Optional[AgentConfig]) -> AgentConfig:
        """
        Validate the agent configuration.

        Args:
            config: Configuration to validate

        Returns:
            Validated configuration

        Raises:
            AgentException: If configuration is invalid
        """
        if config is None:
            raise AgentException("Configuration cannot be None")

        required_attrs = ["chat_model", "utility_model", "embeddings_model"]

        for attr in required_attrs:
            if not hasattr(config, attr) or getattr(config, attr) is None:
                msg = f"Missing required config attribute: {attr}"
                raise AgentException(msg)

        return config
