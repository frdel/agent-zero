"""
Agent initialization module.

This module handles the initialization of language models and configuration
for the agent system. It provides a centralized way to configure model parameters,
knowledge directories, and system settings.
"""

import json
import os
from typing import Optional, Any
import models
from agent.config import AgentConfig, ConfigValidator
from python.helpers.log import Log, LogItem


# Default configuration values
DEFAULT_CHAT_MODEL = "claude-3-5-sonnet-20241022"
DEFAULT_UTILITY_MODEL = "claude-3-5-sonnet-20241022"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TEMPERATURE = 0.5
DEFAULT_KNOWLEDGE_SUBDIRS = ["default", "custom"]
DEFAULT_AUTO_MEMORY_COUNT = 0
DEFAULT_RATE_LIMIT = 30
DEFAULT_MAX_TOOL_RESPONSE = 3000
CONFIG_FILE = "config.json"


def get_model_provider(model_name: str) -> str:
    """Determine the model provider based on the model name."""
    model_name = model_name.lower()
    if "llama" in model_name:
        return "ollama"
    elif "claude" in model_name:
        return "anthropic"
    elif "gpt" in model_name or "text-embedding" in model_name:
        return "openai"
    elif "mistral" in model_name:
        return "mistral"
    elif "gemini" in model_name:
        return "google"
    elif "meta-llama" in model_name:
        return "lmstudio"
    return "openai"  # default fallback


def initialize_model(
    model_name: str, model_type: str, temperature: float = DEFAULT_TEMPERATURE
) -> Any:
    """Initialize a model based on its name and provider."""
    provider = get_model_provider(model_name)

    if model_type == "embedding":
        if provider == "openai":
            return models.get_openai_embedding(model_name)
        elif provider == "ollama":
            return models.get_ollama_embedding(model_name)
        elif provider == "lmstudio":
            return models.get_lmstudio_embedding(model_name)
        else:
            return models.get_huggingface_embedding(model_name)
    else:
        if provider == "anthropic":
            return models.get_anthropic_chat(model_name, temperature=temperature)
        elif provider == "openai":
            return models.get_openai_chat(model_name, temperature=temperature)
        elif provider == "ollama":
            return models.get_ollama_chat(model_name, temperature=temperature)
        elif provider == "mistral":
            return models.get_mistral_chat(model_name, temperature=temperature)
        elif provider == "google":
            return models.get_google_chat(model_name, temperature=temperature)
        elif provider == "lmstudio":
            return models.get_lmstudio_chat(model_name, temperature=temperature)
        else:
            return models.get_openai_chat(model_name, temperature=temperature)


def load_selected_models() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {
            "chat_model": DEFAULT_CHAT_MODEL,
            "utility_model": DEFAULT_UTILITY_MODEL,
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
        }
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def initialize(
    chat_model: Optional[str] = None,
    utility_model: Optional[str] = None,
    embedding_model: Optional[str] = None,
    temperature: float = DEFAULT_TEMPERATURE,
    knowledge_subdirs: Optional[list] = None,
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
        chat_model_name = chat_model or models_selected.get(
            "chat_model", DEFAULT_CHAT_MODEL
        )
        utility_model_name = utility_model or models_selected.get(
            "utility_model", DEFAULT_UTILITY_MODEL
        )
        embedding_model_name = embedding_model or models_selected.get(
            "embedding_model", DEFAULT_EMBEDDING_MODEL
        )

        # Initialize language models with proper provider routing
        chat_llm = initialize_model(chat_model_name, "chat", temperature)
        utility_llm = initialize_model(utility_model_name, "chat", temperature)
        embedding_llm = initialize_model(embedding_model_name, "embedding")

        # Create configuration
        config = AgentConfig(
            chat_model=chat_llm,
            utility_model=utility_llm,
            embeddings_model=embedding_llm,
            knowledge_subdirs=knowledge_subdirs or DEFAULT_KNOWLEDGE_SUBDIRS,
            auto_memory_count=auto_memory_count,
            rate_limit_requests=rate_limit,
            max_tool_response_length=max_tool_response,
            code_exec_docker_enabled=enable_docker,
            code_exec_ssh_enabled=enable_ssh,
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
