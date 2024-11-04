"""
Agent initialization module.

This module handles the initialization of language models and configuration
for the agent system. It provides a centralized way to configure model parameters,
knowledge directories, and system settings.
"""

import json
import os
from typing import List, Optional
import models
from agent.config import AgentConfig, ConfigValidator
from python.helpers.log import Log, LogItem

# Default configuration values
DEFAULT_CHAT_MODEL = "claude-3-5-sonnet-20241022"
DEFAULT_UTILITY_MODEL = "llama-3.2-90b-text-preview"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TEMPERATURE = 0.5
DEFAULT_KNOWLEDGE_SUBDIRS = ["default", "custom"]
DEFAULT_AUTO_MEMORY_COUNT = 0
DEFAULT_RATE_LIMIT = 30
DEFAULT_MAX_TOOL_RESPONSE = 3000
CONFIG_FILE = "config.json"


def load_selected_models():
    if not os.path.exists(CONFIG_FILE):
        return {
            "chat_model": "gpt-4o-mini",
            "utility_model": "gpt-4o-mini",
            "embedding_model": "text-embedding-3-small",
        }
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def load_config():
    with open("config.json", "r") as f:
        return json.load(f)


config = load_config()
default_model = config.get("default_model", "default_model_name")
temperature = config.get("default_temperature", 0.7)


def initialize(
    chat_model: Optional[str] = None,
    utility_model: Optional[str] = None,
    embedding_model: Optional[str] = None,
    temperature: float = DEFAULT_TEMPERATURE,
    knowledge_subdirs: Optional[List[str]] = None,
    auto_memory_count: int = DEFAULT_AUTO_MEMORY_COUNT,
    rate_limit: int = DEFAULT_RATE_LIMIT,
    max_tool_response: int = DEFAULT_MAX_TOOL_RESPONSE,
    enable_docker: bool = True,
    enable_ssh: bool = True,
) -> AgentConfig:
    """
    Initialize the agent configuration with language models and settings.

    Args:
        chat_model: Name of the chat model to use
        utility_model: Name of the utility model to use
        embedding_model: Name of the embedding model to use
        temperature: Temperature setting for model responses
        knowledge_subdirs: List of knowledge subdirectories to use
        auto_memory_count: Number of automatic memories to maintain
        rate_limit: Rate limit for API requests
        max_tool_response: Maximum length for tool responses
        enable_docker: Whether to enable Docker-based code execution
        enable_ssh: Whether to enable SSH-based code execution

    Returns:
        AgentConfig: Configured agent settings

    Raises:
        Exception: If model initialization fails
    """
    try:
        models_selected = load_selected_models()
        chat_model = chat_model or models_selected.get("chat_model", DEFAULT_CHAT_MODEL)
        utility_model = utility_model or models_selected.get(
            "utility_model", DEFAULT_UTILITY_MODEL
        )
        embedding_model = embedding_model or models_selected.get(
            "embedding_model", DEFAULT_EMBEDDING_MODEL
        )

        # Initialize language models
        chat_llm = models.get_openai_chat(
            model_name=chat_model, temperature=temperature
        )
        utility_llm = models.get_openai_chat(
            model_name=utility_model, temperature=temperature
        )
        embedding_llm = models.get_openai_embedding(model_name=embedding_model)

        # Create configuration
        config = AgentConfig(
            chat_model=chat_llm,
            utility_model=utility_llm,
            embeddings_model=embedding_llm,
            knowledge_subdirs=knowledge_subdirs or DEFAULT_KNOWLEDGE_SUBDIRS,
            auto_memory_count=auto_memory_count,
            rate_limit_seconds=60,  # Example value
            rate_limit_requests=rate_limit,
            rate_limit_input_tokens=0,
            rate_limit_output_tokens=0,
            msgs_keep_max=25,
            max_tool_response_length=max_tool_response,  # Add this line
            code_exec_docker_enabled=enable_docker,     # Add this line
            code_exec_ssh_enabled=enable_ssh,           # Add this line
        )

        # Validate configuration
        config = ConfigValidator.validate_config(config)

        return config

    except Exception as e:
        Log().logs.append(
            LogItem(
                log=Log(),
                no=len(Log().logs),
                type="error",
                heading="Initialization Error",
                content=f"Failed to initialize agent: {str(e)}",
                temp=False,
            )
        )
        raise Exception(f"Failed to initialize agent: {str(e)}")
