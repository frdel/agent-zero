import json
import os
import re
from typing import Any, Optional, TypedDict
from . import files
from models import get_model, ModelProvider, ModelType
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings

class Settings(TypedDict):
    chat_model_provider: str
    chat_model_name: str
    chat_model_temperature: float
    chat_model_kwargs: dict[str, str]

    util_model_provider: str
    util_model_name: str
    util_model_temperature: float
    util_model_kwargs: dict[str, str]

    embed_model_provider: str
    embed_model_name: str
    embed_model_kwargs: dict[str, str]


class PartialSettings(Settings, total=False):
    pass


SETTINGS_FILE = files.get_abs_path("tmp/settings.json")
_settings: Settings | None = None


def convert_out(settings: Settings) -> dict[str, Any]:
    # main model section
    chat_model_fields = []
    chat_model_fields.append(
        {
            "id": "chat_model_provider",
            "title": "Chat model provider",
            "description": "Select provider for main chat model used by Agent Zero",
            "type": "select",
            "value": settings["chat_model_provider"],
            "options": [{"value": p.name, "label": p.value} for p in ModelProvider],
        }
    )
    chat_model_fields.append(
        {
            "id": "chat_model_name",
            "title": "Chat model name",
            "description": "Exact name of model from selected provider",
            "type": "input",
            "value": settings["chat_model_name"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_temperature",
            "title": "Chat model temperature",
            "description": "Determines the randomness of generated responses. 0 is deterministic, 1 is random",
            "type": "range",
            "min": 0,
            "max": 1,
            "step": 0.01,
            "value": settings["chat_model_temperature"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_kwargs",
            "title": "Chat model additional parameters",
            "description": "Any other parameters supported by the model. Format is KEY=VALUE on individual lines, just like .env file.",
            "type": "textarea",
            "value": _dict_to_env(settings["chat_model_kwargs"]),
        }
    )

    chat_model_section = {
        "title": "Chat Model",
        "description": "Selection and settings for main chat model used by Agent Zero",
        "fields": chat_model_fields,
    }

    # utility model section
    util_model_fields = []
    util_model_fields.append(
        {
            "id": "util_model_provider",
            "title": "Utility model provider",
            "description": "Select provider for utility model used by the framework",
            "type": "select",
            "value": settings["util_model_provider"],
            "options": [{"value": p.name, "label": p.value} for p in ModelProvider],
        }
    )
    util_model_fields.append(
        {
            "id": "util_model_name",
            "title": "Utility model name",
            "description": "Exact name of model from selected provider",
            "type": "input",
            "value": settings["util_model_name"],
        }
    )

    util_model_fields.append(
        {
            "id": "util_model_temperature",
            "title": "Utility model temperature",
            "description": "Determines the randomness of generated responses. 0 is deterministic, 1 is random",
            "type": "range",
            "min": 0,
            "max": 1,
            "step": 0.01,
            "value": settings["util_model_temperature"],
        }
    )

    util_model_fields.append(
        {
            "id": "util_model_kwargs",
            "title": "Utility model additional parameters",
            "description": "Any other parameters supported by the model. Format is KEY=VALUE on individual lines, just like .env file.",
            "type": "textarea",
            "value": _dict_to_env(settings["util_model_kwargs"]),
        }
    )

    util_model_section = {
        "title": "Utility Model",
        "description": "Smaller, cheaper, faster model for handling utility tasks like organizing memory, preparing prompts, summarizing.",
        "fields": util_model_fields,
    }

    # embedding model section
    embed_model_fields = []
    embed_model_fields.append(
        {
            "id": "embed_model_provider",
            "title": "Embedding model provider",
            "description": "Select provider for embedding model used by the framework",
            "type": "select",
            "value": settings["embed_model_provider"],
            "options": [{"value": p.name, "label": p.value} for p in ModelProvider],
        }
    )
    embed_model_fields.append(
        {
            "id": "embed_model_name",
            "title": "Embedding model name",
            "description": "Exact name of model from selected provider",
            "type": "input",
            "value": settings["embed_model_name"],
        }
    )

    embed_model_fields.append(
        {
            "id": "embed_model_kwargs",
            "title": "Embedding model additional parameters",
            "description": "Any other parameters supported by the model. Format is KEY=VALUE on individual lines, just like .env file.",
            "type": "textarea",
            "value": _dict_to_env(settings["embed_model_kwargs"]),
        }
    )

    embed_model_section = {
        "title": "Embedding Model",
        "description": "Settings for the embedding model used by Agent Zero.",
        "fields": embed_model_fields,
    }

    result = {"sections": [chat_model_section, util_model_section, embed_model_section]}
    return result

def convert_in(settings: dict[str, Any]) -> Settings:
    current = get_settings()
    for section in settings["sections"]:
        for field in section["fields"]:
            if field["id"].endswith("_kwargs"):
                current[field["id"]] = _env_to_dict(field["value"]) #parse KWARGS from env format
            else:
                current[field["id"]] = field["value"] 
    return current


def get_settings() -> Settings:
    global _settings
    if not _settings:
        _settings = _read_settings_file()
    if not _settings:
        _settings = _get_default_settings()
    return _settings.copy()


def set_settings(settings: Settings):
    global _settings
    _settings = normalize_settings(settings)
    _apply_settings() 
    _write_settings_file(_settings)


def normalize_settings(settings: Settings) -> Settings:
    copy = settings.copy()
    default = _get_default_settings()
    for key, value in default.items():
        if key not in copy:
            copy[key] = value
    return copy


def get_chat_model() -> BaseChatModel:
    settings = get_settings()
    return get_model(
        type=ModelType.CHAT,
        provider=ModelProvider[settings["chat_model_provider"]],
        name=settings["chat_model_name"],
        temperature=settings["chat_model_temperature"],
        **settings["chat_model_kwargs"],
    )


def get_utility_model() -> BaseChatModel:
    settings = get_settings()
    return get_model(
        type=ModelType.CHAT,
        provider=ModelProvider[settings["util_model_provider"]],
        name=settings["util_model_name"],
        temperature=settings["util_model_temperature"],
        **settings["util_model_kwargs"],
    )


def get_embedding_model() -> Embeddings:
    settings = get_settings()
    return get_model(
        type=ModelType.EMBEDDING,
        provider=ModelProvider[settings["embed_model_provider"]],
        name=settings["embed_model_name"],
        **settings["embed_model_kwargs"],
    )


def _read_settings_file() -> Settings | None:
    if os.path.exists(SETTINGS_FILE):
        content = files.read_file(SETTINGS_FILE)
        parsed = json.loads(content)
        return normalize_settings(parsed)


def _write_settings_file(settings: Settings):
    content = json.dumps(settings, indent=4)
    files.write_file(SETTINGS_FILE, content)


def _get_default_settings() -> Settings:
    return Settings(
        chat_model_provider=ModelProvider.OPENAI.name,
        chat_model_name="gpt-4o-mini",
        chat_model_temperature=0,
        chat_model_kwargs={},
        util_model_provider=ModelProvider.OPENAI.name,
        util_model_name="gpt-4o-mini",
        util_model_temperature=0,
        util_model_kwargs={},
        embed_model_provider=ModelProvider.OPENAI.name,
        embed_model_name="text-embedding-3-small",
        embed_model_kwargs={},
    )

def _apply_settings():
    global _settings
    if _settings:
        from agent import AgentContext
        from initialize import initialize

        for ctx in AgentContext._contexts.values():
            ctx.config = initialize() # reinitialize context config with new settings
            #apply config to agents
            agent = ctx.agent0
            while agent:
                agent.config = ctx.config
                agent = agent.get_data("subordinate")

def _env_to_dict(data:str):
    env_dict = {}
    line_pattern = re.compile(r'\s*([^#][^=]*)\s*=\s*(.*)')
    for line in data.splitlines():
        match = line_pattern.match(line)
        if match:
            key, value = match.groups()
            # Remove optional surrounding quotes (single or double)
            value = value.strip().strip('"').strip("'")
            env_dict[key.strip()] = value
    return env_dict

def _dict_to_env(data_dict):
    lines = []
    for key, value in data_dict.items():
        if '\n' in value:
            value = f"'{value}'"
        elif ' ' in value or value == '' or any(c in value for c in '"\''):
            value = f'"{value}"'
        lines.append(f"{key}={value}")
    return "\n".join(lines)