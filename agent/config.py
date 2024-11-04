"""Configuration module for the agent system."""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List


class AgentException(Exception):
    """Base exception class for agent configuration errors."""

    pass


@dataclass
class AgentConfig:
    """Configuration class for agent settings."""

    chat_model: Any
    utility_model: Any
    embeddings_model: Any
    knowledge_subdirs: List[str]
    auto_memory_count: int
    rate_limit_requests: int
    max_tool_response_length: int
    code_exec_docker_enabled: bool
    code_exec_ssh_enabled: bool

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
