import base64
import hashlib
import json
import os
import re
import subprocess
from typing import Any, Literal, TypedDict, cast

import models
from python.helpers import runtime, whisper, defer, git
from . import files, dotenv
from python.helpers.print_style import PrintStyle
from python.helpers.providers import get_providers


class Settings(TypedDict):
    version: str

    chat_model_provider: str
    chat_model_name: str
    chat_model_api_base: str
    chat_model_kwargs: dict[str, str]
    chat_model_ctx_length: int
    chat_model_ctx_history: float
    chat_model_vision: bool
    chat_model_rl_requests: int
    chat_model_rl_input: int
    chat_model_rl_output: int

    util_model_provider: str
    util_model_name: str
    util_model_api_base: str
    util_model_kwargs: dict[str, str]
    util_model_ctx_length: int
    util_model_ctx_input: float
    util_model_rl_requests: int
    util_model_rl_input: int
    util_model_rl_output: int

    embed_model_provider: str
    embed_model_name: str
    embed_model_api_base: str
    embed_model_kwargs: dict[str, str]
    embed_model_rl_requests: int
    embed_model_rl_input: int

    browser_model_provider: str
    browser_model_name: str
    browser_model_api_base: str
    browser_model_vision: bool
    browser_model_kwargs: dict[str, str]

    agent_profile: str
    agent_memory_subdir: str
    agent_knowledge_subdir: str

    memory_recall_enabled: bool
    memory_recall_interval: int
    memory_recall_history_len: int
    memory_recall_memories_max_search: int
    memory_recall_solutions_max_search: int
    memory_recall_memories_max_result: int
    memory_recall_solutions_max_result: int
    memory_recall_similarity_threshold: float
    memory_recall_query_prep: bool
    memory_recall_post_filter: bool
    memory_memorize_enabled: bool
    memory_memorize_consolidation: bool
    memory_memorize_replace_threshold: float
    

    api_keys: dict[str, str]

    auth_login: str
    auth_password: str
    root_password: str

    rfc_auto_docker: bool
    rfc_url: str
    rfc_password: str
    rfc_port_http: int
    rfc_port_ssh: int

    stt_model_size: str
    stt_language: str
    stt_silence_threshold: float
    stt_silence_duration: int
    stt_waiting_timeout: int

    tts_kokoro: bool

    mcp_servers: str
    mcp_client_init_timeout: int
    mcp_client_tool_timeout: int
    mcp_server_enabled: bool
    mcp_server_token: str


class PartialSettings(Settings, total=False):
    pass


class FieldOption(TypedDict):
    value: str
    label: str


class SettingsField(TypedDict, total=False):
    id: str
    title: str
    description: str
    type: Literal[
        "text", "number", "select", "range", "textarea", "password", "switch", "button", "html"
    ]
    value: Any
    min: float
    max: float
    step: float
    hidden: bool
    options: list[FieldOption]


class SettingsSection(TypedDict, total=False):
    id: str
    title: str
    description: str
    fields: list[SettingsField]
    tab: str  # Indicates which tab this section belongs to


class SettingsOutput(TypedDict):
    sections: list[SettingsSection]


PASSWORD_PLACEHOLDER = "****PSWD****"

SETTINGS_FILE = files.get_abs_path("tmp/settings.json")
_settings: Settings | None = None



def convert_out(settings: Settings) -> SettingsOutput:
    default_settings = get_default_settings()

    # main model section
    chat_model_fields: list[SettingsField] = []
    chat_model_fields.append(
        {
            "id": "chat_model_provider",
            "title": "Chat model provider",
            "description": "Select provider for main chat model used by Agent Zero",
            "type": "select",
            "value": settings["chat_model_provider"],
            "options": cast(list[FieldOption], get_providers("chat")),
        }
    )
    chat_model_fields.append(
        {
            "id": "chat_model_name",
            "title": "Chat model name",
            "description": "Exact name of model from selected provider",
            "type": "text",
            "value": settings["chat_model_name"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_api_base",
            "title": "Chat model API base URL",
            "description": "API base URL for main chat model. Leave empty for default. Only relevant for Azure, local and custom (other) providers.",
            "type": "text",
            "value": settings["chat_model_api_base"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_ctx_length",
            "title": "Chat model context length",
            "description": "Maximum number of tokens in the context window for LLM. System prompt, chat history, RAG and response all count towards this limit.",
            "type": "number",
            "value": settings["chat_model_ctx_length"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_ctx_history",
            "title": "Context window space for chat history",
            "description": "Portion of context window dedicated to chat history visible to the agent. Chat history will automatically be optimized to fit. Smaller size will result in shorter and more summarized history. The remaining space will be used for system prompt, RAG and response.",
            "type": "range",
            "min": 0.01,
            "max": 1,
            "step": 0.01,
            "value": settings["chat_model_ctx_history"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_vision",
            "title": "Supports Vision",
            "description": "Models capable of Vision can for example natively see the content of image attachments.",
            "type": "switch",
            "value": settings["chat_model_vision"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_rl_requests",
            "title": "Requests per minute limit",
            "description": "Limits the number of requests per minute to the chat model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["chat_model_rl_requests"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_rl_input",
            "title": "Input tokens per minute limit",
            "description": "Limits the number of input tokens per minute to the chat model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["chat_model_rl_input"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_rl_output",
            "title": "Output tokens per minute limit",
            "description": "Limits the number of output tokens per minute to the chat model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["chat_model_rl_output"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_kwargs",
            "title": "Chat model additional parameters",
            "description": "Any other parameters supported by <a href='https://docs.litellm.ai/docs/set_keys' target='_blank'>LiteLLM</a>. Format is KEY=VALUE on individual lines, just like .env file.",
            "type": "textarea",
            "value": _dict_to_env(settings["chat_model_kwargs"]),
        }
    )

    chat_model_section: SettingsSection = {
        "id": "chat_model",
        "title": "Chat Model",
        "description": "Selection and settings for main chat model used by Agent Zero",
        "fields": chat_model_fields,
        "tab": "agent",
    }

    # main model section
    util_model_fields: list[SettingsField] = []
    util_model_fields.append(
        {
            "id": "util_model_provider",
            "title": "Utility model provider",
            "description": "Select provider for utility model used by the framework",
            "type": "select",
            "value": settings["util_model_provider"],
            "options": cast(list[FieldOption], get_providers("chat")),
        }
    )
    util_model_fields.append(
        {
            "id": "util_model_name",
            "title": "Utility model name",
            "description": "Exact name of model from selected provider",
            "type": "text",
            "value": settings["util_model_name"],
        }
    )

    util_model_fields.append(
        {
            "id": "util_model_api_base",
            "title": "Utility model API base URL",
            "description": "API base URL for utility model. Leave empty for default. Only relevant for Azure, local and custom (other) providers.",
            "type": "text",
            "value": settings["util_model_api_base"],
        }
    )

    util_model_fields.append(
        {
            "id": "util_model_rl_requests",
            "title": "Requests per minute limit",
            "description": "Limits the number of requests per minute to the utility model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["util_model_rl_requests"],
        }
    )

    util_model_fields.append(
        {
            "id": "util_model_rl_input",
            "title": "Input tokens per minute limit",
            "description": "Limits the number of input tokens per minute to the utility model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["util_model_rl_input"],
        }
    )

    util_model_fields.append(
        {
            "id": "util_model_rl_output",
            "title": "Output tokens per minute limit",
            "description": "Limits the number of output tokens per minute to the utility model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["util_model_rl_output"],
        }
    )

    util_model_fields.append(
        {
            "id": "util_model_kwargs",
            "title": "Utility model additional parameters",
            "description": "Any other parameters supported by <a href='https://docs.litellm.ai/docs/set_keys' target='_blank'>LiteLLM</a>. Format is KEY=VALUE on individual lines, just like .env file.",
            "type": "textarea",
            "value": _dict_to_env(settings["util_model_kwargs"]),
        }
    )

    util_model_section: SettingsSection = {
        "id": "util_model",
        "title": "Utility model",
        "description": "Smaller, cheaper, faster model for handling utility tasks like organizing memory, preparing prompts, summarizing.",
        "fields": util_model_fields,
        "tab": "agent",
    }

    # embedding model section
    embed_model_fields: list[SettingsField] = []
    embed_model_fields.append(
        {
            "id": "embed_model_provider",
            "title": "Embedding model provider",
            "description": "Select provider for embedding model used by the framework",
            "type": "select",
            "value": settings["embed_model_provider"],
            "options": cast(list[FieldOption], get_providers("embedding")),
        }
    )
    embed_model_fields.append(
        {
            "id": "embed_model_name",
            "title": "Embedding model name",
            "description": "Exact name of model from selected provider",
            "type": "text",
            "value": settings["embed_model_name"],
        }
    )

    embed_model_fields.append(
        {
            "id": "embed_model_api_base",
            "title": "Embedding model API base URL",
            "description": "API base URL for embedding model. Leave empty for default. Only relevant for Azure, local and custom (other) providers.",
            "type": "text",
            "value": settings["embed_model_api_base"],
        }
    )

    embed_model_fields.append(
        {
            "id": "embed_model_rl_requests",
            "title": "Requests per minute limit",
            "description": "Limits the number of requests per minute to the embedding model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["embed_model_rl_requests"],
        }
    )

    embed_model_fields.append(
        {
            "id": "embed_model_rl_input",
            "title": "Input tokens per minute limit",
            "description": "Limits the number of input tokens per minute to the embedding model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["embed_model_rl_input"],
        }
    )

    embed_model_fields.append(
        {
            "id": "embed_model_kwargs",
            "title": "Embedding model additional parameters",
            "description": "Any other parameters supported by <a href='https://docs.litellm.ai/docs/set_keys' target='_blank'>LiteLLM</a>. Format is KEY=VALUE on individual lines, just like .env file.",
            "type": "textarea",
            "value": _dict_to_env(settings["embed_model_kwargs"]),
        }
    )

    embed_model_section: SettingsSection = {
        "id": "embed_model",
        "title": "Embedding Model",
        "description": f"Settings for the embedding model used by Agent Zero.<br><h4>⚠️ No need to change</h4>The default HuggingFace model {default_settings['embed_model_name']} is preloaded and runs locally within the docker container and there's no need to change it unless you have a specific requirements for embedding.",
        "fields": embed_model_fields,
        "tab": "agent",
    }

    # embedding model section
    browser_model_fields: list[SettingsField] = []
    browser_model_fields.append(
        {
            "id": "browser_model_provider",
            "title": "Web Browser model provider",
            "description": "Select provider for web browser model used by <a href='https://github.com/browser-use/browser-use' target='_blank'>browser-use</a> framework",
            "type": "select",
            "value": settings["browser_model_provider"],
            "options": cast(list[FieldOption], get_providers("chat")),
        }
    )
    browser_model_fields.append(
        {
            "id": "browser_model_name",
            "title": "Web Browser model name",
            "description": "Exact name of model from selected provider",
            "type": "text",
            "value": settings["browser_model_name"],
        }
    )

    browser_model_fields.append(
        {
            "id": "browser_model_api_base",
            "title": "Web Browser model API base URL",
            "description": "API base URL for web browser model. Leave empty for default. Only relevant for Azure, local and custom (other) providers.",
            "type": "text",
            "value": settings["browser_model_api_base"],
        }
    )

    browser_model_fields.append(
        {
            "id": "browser_model_vision",
            "title": "Use Vision",
            "description": "Models capable of Vision can use it to analyze web pages from screenshots. Increases quality but also token usage.",
            "type": "switch",
            "value": settings["browser_model_vision"],
        }
    )

    browser_model_fields.append(
        {
            "id": "browser_model_kwargs",
            "title": "Web Browser model additional parameters",
            "description": "Any other parameters supported by <a href='https://docs.litellm.ai/docs/set_keys' target='_blank'>LiteLLM</a>. Format is KEY=VALUE on individual lines, just like .env file.",
            "type": "textarea",
            "value": _dict_to_env(settings["browser_model_kwargs"]),
        }
    )

    browser_model_section: SettingsSection = {
        "id": "browser_model",
        "title": "Web Browser Model",
        "description": "Settings for the web browser model. Agent Zero uses <a href='https://github.com/browser-use/browser-use' target='_blank'>browser-use</a> agentic framework to handle web interactions.",
        "fields": browser_model_fields,
        "tab": "agent",
    }


    # basic auth section
    auth_fields: list[SettingsField] = []

    auth_fields.append(
        {
            "id": "auth_login",
            "title": "UI Login",
            "description": "Set user name for web UI",
            "type": "text",
            "value": dotenv.get_dotenv_value(dotenv.KEY_AUTH_LOGIN) or "",
        }
    )

    auth_fields.append(
        {
            "id": "auth_password",
            "title": "UI Password",
            "description": "Set user password for web UI",
            "type": "password",
            "value": (
                PASSWORD_PLACEHOLDER
                if dotenv.get_dotenv_value(dotenv.KEY_AUTH_PASSWORD)
                else ""
            ),
        }
    )

    if runtime.is_dockerized():
        auth_fields.append(
            {
                "id": "root_password",
                "title": "root Password",
                "description": "Change linux root password in docker container. This password can be used for SSH access. Original password was randomly generated during setup.",
                "type": "password",
                "value": "",
            }
        )

    auth_section: SettingsSection = {
        "id": "auth",
        "title": "Authentication",
        "description": "Settings for authentication to use Agent Zero Web UI.",
        "fields": auth_fields,
        "tab": "external",
    }

    # api keys model section
    api_keys_fields: list[SettingsField] = []

    # Collect unique providers from both chat and embedding sections
    providers_seen: set[str] = set()
    for p_type in ("chat", "embedding"):
        for provider in get_providers(p_type):
            pid_lower = provider["value"].lower()
            if pid_lower in providers_seen:
                continue
            providers_seen.add(pid_lower)
            api_keys_fields.append(
                _get_api_key_field(settings, pid_lower, provider["label"])
            )

    api_keys_section: SettingsSection = {
        "id": "api_keys",
        "title": "API Keys",
        "description": "API keys for model providers and services used by Agent Zero.",
        "fields": api_keys_fields,
        "tab": "external",
    }

    # Agent config section
    agent_fields: list[SettingsField] = []

    agent_fields.append(
        {
            "id": "agent_profile",
            "title": "Default agent profile",
            "description": "Subdirectory of /agents folder to be used by default agent no. 0. Subordinate agents can be spawned with other profiles, that is on their superior agent to decide. This setting affects the behaviour of the top level agent you communicate with.",
            "type": "select",
            "value": settings["agent_profile"],
            "options": [
                {"value": subdir, "label": subdir}
                for subdir in files.get_subdirectories("agents") if subdir != "_example"
            ],
        }
    )

    agent_fields.append(
        {
            "id": "agent_knowledge_subdir",
            "title": "Knowledge subdirectory",
            "description": "Subdirectory of /knowledge folder to use for agent knowledge import. 'default' subfolder is always imported and contains framework knowledge.",
            "type": "select",
            "value": settings["agent_knowledge_subdir"],
            "options": [
                {"value": subdir, "label": subdir}
                for subdir in files.get_subdirectories("knowledge", exclude="default")
            ],
        }
    )

    agent_section: SettingsSection = {
        "id": "agent",
        "title": "Agent Config",
        "description": "Agent parameters.",
        "fields": agent_fields,
        "tab": "agent",
    }


    memory_fields: list[SettingsField] = []

    memory_fields.append(
        {
            "id": "agent_memory_subdir",
            "title": "Memory Subdirectory",
            "description": "Subdirectory of /memory folder to use for agent memory storage. Used to separate memory storage between different instances.",
            "type": "text",
            "value": settings["agent_memory_subdir"],
            # "options": [
            #     {"value": subdir, "label": subdir}
            #     for subdir in files.get_subdirectories("memory", exclude="embeddings")
            # ],
        }
    )

    memory_fields.append(
        {
            "id": "memory_recall_enabled",
            "title": "Memory auto-recall enabled",
            "description": "Agent Zero will automatically recall memories based on convesation context.",
            "type": "switch",
            "value": settings["memory_recall_enabled"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_recall_query_prep",
            "title": "Auto-recall AI query preparation",
            "description": "Enables vector DB query preparation from conversation context by utility LLM for auto-recall. Improves search quality, adds 1 utility LLM call per auto-recall.",
            "type": "switch",
            "value": settings["memory_recall_query_prep"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_recall_post_filter",
            "title": "Auto-recall AI post-filtering",
            "description": "Enables memory relevance filtering by utility LLM for auto-recall. Improves search quality, adds 1 utility LLM call per auto-recall.",
            "type": "switch",
            "value": settings["memory_recall_post_filter"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_recall_interval",
            "title": "Memory auto-recall interval",
            "description": "Memories are recalled after every user or superior agent message. During agent's monologue, memories are recalled every X turns based on this parameter.",
            "type": "range",
            "min": 1,
            "max": 10,
            "step": 1,
            "value": settings["memory_recall_interval"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_recall_history_len",
            "title": "Memory auto-recall history length",
            "description": "The length of conversation history passed to memory recall LLM for context (in characters).",
            "type": "number",
            "value": settings["memory_recall_history_len"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_recall_similarity_threshold",
            "title": "Memory auto-recall similarity threshold",
            "description": "The threshold for similarity search in memory recall (0 = no similarity, 1 = exact match).",
            "type": "range",
            "min": 0,
            "max": 1,
            "step": 0.01,
            "value": settings["memory_recall_similarity_threshold"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_recall_memories_max_search",
            "title": "Memory auto-recall max memories to search",
            "description": "The maximum number of memories returned by vector DB for further processing.",
            "type": "number",
            "value": settings["memory_recall_memories_max_search"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_recall_memories_max_result",
            "title": "Memory auto-recall max memories to use",
            "description": "The maximum number of memories to inject into A0's context window.",
            "type": "number",
            "value": settings["memory_recall_memories_max_result"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_recall_solutions_max_search",
            "title": "Memory auto-recall max solutions to search",
            "description": "The maximum number of solutions returned by vector DB for further processing.",
            "type": "number",
            "value": settings["memory_recall_solutions_max_search"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_recall_solutions_max_result",
            "title": "Memory auto-recall max solutions to use",
            "description": "The maximum number of solutions to inject into A0's context window.",
            "type": "number",
            "value": settings["memory_recall_solutions_max_result"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_memorize_enabled",
            "title": "Auto-memorize enabled",
            "description": "A0 will automatically memorize facts and solutions from conversation history.",
            "type": "switch",
            "value": settings["memory_memorize_enabled"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_memorize_consolidation",
            "title": "Auto-memorize AI consolidation",
            "description": "A0 will automatically consolidate similar memories using utility LLM. Improves memory quality over time, adds 2 utility LLM calls per memory.",
            "type": "switch",
            "value": settings["memory_memorize_consolidation"],
        }
    )

    memory_fields.append(
        {
            "id": "memory_memorize_replace_threshold",
            "title": "Auto-memorize replacement threshold",
            "description": "Only applies when AI consolidation is disabled. Replaces previous similar memories with new ones based on this threshold. 0 = replace even if not similar at all, 1 = replace only if exact match.",
            "type": "range",
            "min": 0,
            "max": 1,
            "step": 0.01,
            "value": settings["memory_memorize_replace_threshold"],
        }
    )

    memory_section: SettingsSection = {
        "id": "memory",
        "title": "Memory",
        "description": "Configuration of A0's memory system. A0 memorizes and recalls memories automatically to help it's context awareness.",
        "fields": memory_fields,
        "tab": "agent",
    }

    dev_fields: list[SettingsField] = []

    if runtime.is_development():
        # dev_fields.append(
        #     {
        #         "id": "rfc_auto_docker",
        #         "title": "RFC Auto Docker Management",
        #         "description": "Automatically create dockerized instance of A0 for RFCs using this instance's code base and, settings and .env.",
        #         "type": "text",
        #         "value": settings["rfc_auto_docker"],
        #     }
        # )

        dev_fields.append(
            {
                "id": "rfc_url",
                "title": "RFC Destination URL",
                "description": "URL of dockerized A0 instance for remote function calls. Do not specify port here.",
                "type": "text",
                "value": settings["rfc_url"],
            }
        )

    dev_fields.append(
        {
            "id": "rfc_password",
            "title": "RFC Password",
            "description": "Password for remote function calls. Passwords must match on both instances. RFCs can not be used with empty password.",
            "type": "password",
            "value": (
                PASSWORD_PLACEHOLDER
                if dotenv.get_dotenv_value(dotenv.KEY_RFC_PASSWORD)
                else ""
            ),
        }
    )

    if runtime.is_development():
        dev_fields.append(
            {
                "id": "rfc_port_http",
                "title": "RFC HTTP port",
                "description": "HTTP port for dockerized instance of A0.",
                "type": "text",
                "value": settings["rfc_port_http"],
            }
        )

        dev_fields.append(
            {
                "id": "rfc_port_ssh",
                "title": "RFC SSH port",
                "description": "SSH port for dockerized instance of A0.",
                "type": "text",
                "value": settings["rfc_port_ssh"],
            }
        )

    dev_section: SettingsSection = {
        "id": "dev",
        "title": "Development",
        "description": "Parameters for A0 framework development. RFCs (remote function calls) are used to call functions on another A0 instance. You can develop and debug A0 natively on your local system while redirecting some functions to A0 instance in docker. This is crucial for development as A0 needs to run in standardized environment to support all features.",
        "fields": dev_fields,
        "tab": "developer",
    }

    # Speech to text section
    stt_fields: list[SettingsField] = []

    stt_fields.append(
        {
            "id": "stt_microphone_section",
            "title": "Microphone device",
            "description": "Select the microphone device to use for speech-to-text.",
            "value": "<x-component path='/settings/speech/microphone.html' />",
            "type": "html",
        }
    )

    stt_fields.append(
        {
            "id": "stt_model_size",
            "title": "Speech-to-text model size",
            "description": "Select the speech-to-text model size",
            "type": "select",
            "value": settings["stt_model_size"],
            "options": [
                {"value": "tiny", "label": "Tiny (39M, English)"},
                {"value": "base", "label": "Base (74M, English)"},
                {"value": "small", "label": "Small (244M, English)"},
                {"value": "medium", "label": "Medium (769M, English)"},
                {"value": "large", "label": "Large (1.5B, Multilingual)"},
                {"value": "turbo", "label": "Turbo (Multilingual)"},
            ],
        }
    )

    stt_fields.append(
        {
            "id": "stt_language",
            "title": "Speech-to-text language code",
            "description": "Language code (e.g. en, fr, it)",
            "type": "text",
            "value": settings["stt_language"],
        }
    )

    stt_fields.append(
        {
            "id": "stt_silence_threshold",
            "title": "Microphone silence threshold",
            "description": "Silence detection threshold. Lower values are more sensitive to noise.",
            "type": "range",
            "min": 0,
            "max": 1,
            "step": 0.01,
            "value": settings["stt_silence_threshold"],
        }
    )

    stt_fields.append(
        {
            "id": "stt_silence_duration",
            "title": "Microphone silence duration (ms)",
            "description": "Duration of silence before the system considers speaking to have ended.",
            "type": "text",
            "value": settings["stt_silence_duration"],
        }
    )

    stt_fields.append(
        {
            "id": "stt_waiting_timeout",
            "title": "Microphone waiting timeout (ms)",
            "description": "Duration of silence before the system closes the microphone.",
            "type": "text",
            "value": settings["stt_waiting_timeout"],
        }
    )

    # TTS fields
    tts_fields: list[SettingsField] = []
    
    tts_fields.append(
        {
            "id": "tts_kokoro",
            "title": "Enable Kokoro TTS",
            "description": "Enable higher quality server-side AI (Kokoro) instead of browser-based text-to-speech.",
            "type": "switch",
            "value": settings["tts_kokoro"],
        }
    )

    speech_section: SettingsSection = {
        "id": "speech",
        "title": "Speech",
        "description": "Voice transcription and speech synthesis settings.",
        "fields": stt_fields + tts_fields,
        "tab": "agent",
    }

    # MCP section
    mcp_client_fields: list[SettingsField] = []

    mcp_client_fields.append(
        {
            "id": "mcp_servers_config",
            "title": "MCP Servers Configuration",
            "description": "External MCP servers can be configured here.",
            "type": "button",
            "value": "Open",
        }
    )

    mcp_client_fields.append(
        {
            "id": "mcp_servers",
            "title": "MCP Servers",
            "description": "(JSON list of) >> RemoteServer <<: [name, url, headers, timeout (opt), sse_read_timeout (opt), disabled (opt)] / >> Local Server <<: [name, command, args, env, encoding (opt), encoding_error_handler (opt), disabled (opt)]",
            "type": "textarea",
            "value": settings["mcp_servers"],
            "hidden": True,
        }
    )

    mcp_client_fields.append(
        {
            "id": "mcp_client_init_timeout",
            "title": "MCP Client Init Timeout",
            "description": "Timeout for MCP client initialization (in seconds). Higher values might be required for complex MCPs, but might also slowdown system startup.",
            "type": "number",
            "value": settings["mcp_client_init_timeout"],
        }
    )

    mcp_client_fields.append(
        {
            "id": "mcp_client_tool_timeout",
            "title": "MCP Client Tool Timeout",
            "description": "Timeout for MCP client tool execution. Higher values might be required for complex tools, but might also result in long responses with failing tools.",
            "type": "number",
            "value": settings["mcp_client_tool_timeout"],
        }
    )

    mcp_client_section: SettingsSection = {
        "id": "mcp_client",
        "title": "External MCP Servers",
        "description": "Agent Zero can use external MCP servers, local or remote as tools.",
        "fields": mcp_client_fields,
        "tab": "mcp",
    }

    mcp_server_fields: list[SettingsField] = []

    mcp_server_fields.append(
        {
            "id": "mcp_server_enabled",
            "title": "Enable A0 MCP Server",
            "description": "Expose Agent Zero as an SSE MCP server. This will make this A0 instance available to MCP clients.",
            "type": "switch",
            "value": settings["mcp_server_enabled"],
        }
    )

    mcp_server_fields.append(
        {
            "id": "mcp_server_token",
            "title": "MCP Server Token",
            "description": "Token for MCP server authentication.",
            "type": "text",
            "hidden": True,
            "value": settings["mcp_server_token"],
        }
    )

    mcp_server_section: SettingsSection = {
        "id": "mcp_server",
        "title": "A0 MCP Server",
        "description": "Agent Zero can be exposed as an SSE MCP server. See <a href=\"javascript:openModal('settings/mcp/server/example.html')\">connection example</a>.",
        "fields": mcp_server_fields,
        "tab": "mcp",
    }

    # Backup & Restore section
    backup_fields: list[SettingsField] = []

    backup_fields.append(
        {
            "id": "backup_create",
            "title": "Create Backup",
            "description": "Create a backup archive of selected files and configurations "
            "using customizable patterns.",
            "type": "button",
            "value": "Create Backup",
        }
    )

    backup_fields.append(
        {
            "id": "backup_restore",
            "title": "Restore from Backup",
            "description": "Restore files and configurations from a backup archive "
            "with pattern-based selection.",
            "type": "button",
            "value": "Restore Backup",
        }
    )

    backup_section: SettingsSection = {
        "id": "backup_restore",
        "title": "Backup & Restore",
        "description": "Backup and restore Agent Zero data and configurations "
        "using glob pattern-based file selection.",
        "fields": backup_fields,
        "tab": "backup",
    }

    # Add the section to the result
    result: SettingsOutput = {
        "sections": [
            agent_section,
            chat_model_section,
            util_model_section,
            browser_model_section,
            embed_model_section,
            memory_section,
            speech_section,
            api_keys_section,
            auth_section,
            mcp_client_section,
            mcp_server_section,
            backup_section,
            dev_section,
        ]
    }
    return result


def _get_api_key_field(settings: Settings, provider: str, title: str) -> SettingsField:
    key = settings["api_keys"].get(provider, models.get_api_key(provider))
    return {
        "id": f"api_key_{provider}",
        "title": title,
        "type": "password",
        "value": (PASSWORD_PLACEHOLDER if key and key != "None" else ""),
    }


def convert_in(settings: dict) -> Settings:
    current = get_settings()
    for section in settings["sections"]:
        if "fields" in section:
            for field in section["fields"]:
                if field["value"] != PASSWORD_PLACEHOLDER:
                    if field["id"].endswith("_kwargs"):
                        current[field["id"]] = _env_to_dict(field["value"])
                    elif field["id"].startswith("api_key_"):
                        current["api_keys"][field["id"]] = field["value"]
                    else:
                        current[field["id"]] = field["value"]
    return current


def get_settings() -> Settings:
    global _settings
    if not _settings:
        _settings = _read_settings_file()
    if not _settings:
        _settings = get_default_settings()
    norm = normalize_settings(_settings)
    return norm


def set_settings(settings: Settings, apply: bool = True):
    global _settings
    previous = _settings
    _settings = normalize_settings(settings)
    _write_settings_file(_settings)
    if apply:
        _apply_settings(previous)


def set_settings_delta(delta: dict, apply: bool = True):
    current = get_settings()
    new = {**current, **delta}
    set_settings(new, apply)  # type: ignore


def normalize_settings(settings: Settings) -> Settings:
    copy = settings.copy()
    default = get_default_settings()

    # adjust settings values to match current version if needed
    if "version" not in copy or copy["version"] != default["version"]:
        _adjust_to_version(copy, default)
        copy["version"] = default["version"] # sync version

    # remove keys that are not in default
    keys_to_remove = [key for key in copy if key not in default]
    for key in keys_to_remove:
        del copy[key]

    # add missing keys and normalize types
    for key, value in default.items():
        if key not in copy:
            copy[key] = value
        else:
            try:
                copy[key] = type(value)(copy[key])  # type: ignore
                if isinstance(copy[key], str):
                    copy[key] = copy[key].strip() # strip strings
            except (ValueError, TypeError):
                copy[key] = value  # make default instead

    # mcp server token is set automatically
    copy["mcp_server_token"] = create_auth_token()

    return copy


def _adjust_to_version(settings: Settings, default: Settings):
    # starting with 0.9, the default prompt subfolder for agent no. 0 is agent0
    # switch to agent0 if the old default is used from v0.8
    if "version" not in settings or settings["version"].startswith("v0.8"):
        if "agent_profile" not in settings or settings["agent_profile"] == "default":
            settings["agent_profile"] = "agent0"

def _read_settings_file() -> Settings | None:
    if os.path.exists(SETTINGS_FILE):
        content = files.read_file(SETTINGS_FILE)
        parsed = json.loads(content)
        return normalize_settings(parsed)


def _write_settings_file(settings: Settings):
    _write_sensitive_settings(settings)
    _remove_sensitive_settings(settings)

    # write settings
    content = json.dumps(settings, indent=4)
    files.write_file(SETTINGS_FILE, content)


def _remove_sensitive_settings(settings: Settings):
    settings["api_keys"] = {}
    settings["auth_login"] = ""
    settings["auth_password"] = ""
    settings["rfc_password"] = ""
    settings["root_password"] = ""
    settings["mcp_server_token"] = ""


def _write_sensitive_settings(settings: Settings):
    for key, val in settings["api_keys"].items():
        dotenv.save_dotenv_value(key.upper(), val)

    dotenv.save_dotenv_value(dotenv.KEY_AUTH_LOGIN, settings["auth_login"])
    if settings["auth_password"]:
        dotenv.save_dotenv_value(dotenv.KEY_AUTH_PASSWORD, settings["auth_password"])
    if settings["rfc_password"]:
        dotenv.save_dotenv_value(dotenv.KEY_RFC_PASSWORD, settings["rfc_password"])

    if settings["root_password"]:
        dotenv.save_dotenv_value(dotenv.KEY_ROOT_PASSWORD, settings["root_password"])
    if settings["root_password"]:
        set_root_password(settings["root_password"])


def get_default_settings() -> Settings:
    return Settings(
        version=_get_version(),
        chat_model_provider="openrouter",
        chat_model_name="openai/gpt-4.1",
        chat_model_api_base="",
        chat_model_kwargs={"temperature": "0"},
        chat_model_ctx_length=100000,
        chat_model_ctx_history=0.7,
        chat_model_vision=True,
        chat_model_rl_requests=0,
        chat_model_rl_input=0,
        chat_model_rl_output=0,
        util_model_provider="openrouter",
        util_model_name="openai/gpt-4.1-mini",
        util_model_api_base="",
        util_model_ctx_length=100000,
        util_model_ctx_input=0.7,
        util_model_kwargs={"temperature": "0"},
        util_model_rl_requests=0,
        util_model_rl_input=0,
        util_model_rl_output=0,
        embed_model_provider="huggingface",
        embed_model_name="sentence-transformers/all-MiniLM-L6-v2",
        embed_model_api_base="",
        embed_model_kwargs={},
        embed_model_rl_requests=0,
        embed_model_rl_input=0,
        browser_model_provider="openrouter",
        browser_model_name="openai/gpt-4.1",
        browser_model_api_base="",
        browser_model_vision=True,
        browser_model_kwargs={"temperature": "0"},
        memory_recall_enabled=True,
        memory_recall_interval=3,
        memory_recall_history_len=10000,
        memory_recall_memories_max_search=12,
        memory_recall_solutions_max_search=8,
        memory_recall_memories_max_result=5,
        memory_recall_solutions_max_result=3,
        memory_recall_similarity_threshold=0.7,
        memory_recall_query_prep=True,
        memory_recall_post_filter=True,
        memory_memorize_enabled=True,
        memory_memorize_consolidation=True,
        memory_memorize_replace_threshold=0.9,
        api_keys={},
        auth_login="",
        auth_password="",
        root_password="",
        agent_profile="agent0",
        agent_memory_subdir="default",
        agent_knowledge_subdir="custom",
        rfc_auto_docker=True,
        rfc_url="localhost",
        rfc_password="",
        rfc_port_http=55080,
        rfc_port_ssh=55022,
        stt_model_size="base",
        stt_language="en",
        stt_silence_threshold=0.3,
        stt_silence_duration=1000,
        stt_waiting_timeout=2000,
        tts_kokoro=True,
        mcp_servers='{\n    "mcpServers": {}\n}',
        mcp_client_init_timeout=10,
        mcp_client_tool_timeout=120,
        mcp_server_enabled=False,
        mcp_server_token=create_auth_token(),
    )


def _apply_settings(previous: Settings | None):
    global _settings
    if _settings:
        from agent import AgentContext
        from initialize import initialize_agent

        config = initialize_agent()
        for ctx in AgentContext._contexts.values():
            ctx.config = config  # reinitialize context config with new settings
            # apply config to agents
            agent = ctx.agent0
            while agent:
                agent.config = ctx.config
                agent = agent.get_data(agent.DATA_NAME_SUBORDINATE)

        # reload whisper model if necessary
        if not previous or _settings["stt_model_size"] != previous["stt_model_size"]:
            task = defer.DeferredTask().start_task(
                whisper.preload, _settings["stt_model_size"]
            )  # TODO overkill, replace with background task

        # force memory reload on embedding model change
        if not previous or (
            _settings["embed_model_name"] != previous["embed_model_name"]
            or _settings["embed_model_provider"] != previous["embed_model_provider"]
            or _settings["embed_model_kwargs"] != previous["embed_model_kwargs"]
        ):
            from python.helpers.memory import reload as memory_reload

            memory_reload()

        # update mcp settings if necessary
        if not previous or _settings["mcp_servers"] != previous["mcp_servers"]:
            from python.helpers.mcp_handler import MCPConfig

            async def update_mcp_settings(mcp_servers: str):
                PrintStyle(
                    background_color="black", font_color="white", padding=True
                ).print("Updating MCP config...")
                AgentContext.log_to_all(
                    type="info", content="Updating MCP settings...", temp=True
                )

                mcp_config = MCPConfig.get_instance()
                try:
                    MCPConfig.update(mcp_servers)
                except Exception as e:
                    AgentContext.log_to_all(
                        type="error",
                        content=f"Failed to update MCP settings: {e}",
                        temp=False,
                    )
                    (
                        PrintStyle(
                            background_color="red", font_color="black", padding=True
                        ).print("Failed to update MCP settings")
                    )
                    (
                        PrintStyle(
                            background_color="black", font_color="red", padding=True
                        ).print(f"{e}")
                    )

                PrintStyle(
                    background_color="#6734C3", font_color="white", padding=True
                ).print("Parsed MCP config:")
                (
                    PrintStyle(
                        background_color="#334455", font_color="white", padding=False
                    ).print(mcp_config.model_dump_json())
                )
                AgentContext.log_to_all(
                    type="info", content="Finished updating MCP settings.", temp=True
                )

            task2 = defer.DeferredTask().start_task(
                update_mcp_settings, config.mcp_servers
            )  # TODO overkill, replace with background task

        # update token in mcp server
        current_token = (
            create_auth_token()
        )  # TODO - ugly, token in settings is generated from dotenv and does not always correspond
        if not previous or current_token != previous["mcp_server_token"]:

            async def update_mcp_token(token: str):
                from python.helpers.mcp_server import DynamicMcpProxy

                DynamicMcpProxy.get_instance().reconfigure(token=token)

            task3 = defer.DeferredTask().start_task(
                update_mcp_token, current_token
            )  # TODO overkill, replace with background task


def _env_to_dict(data: str):
    env_dict = {}
    line_pattern = re.compile(r"\s*([^#][^=]*)\s*=\s*(.*)")
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
        if "\n" in value:
            value = f"'{value}'"
        elif " " in value or value == "" or any(c in value for c in "\"'"):
            value = f'"{value}"'
        lines.append(f"{key}={value}")
    return "\n".join(lines)


def set_root_password(password: str):
    if not runtime.is_dockerized():
        raise Exception("root password can only be set in dockerized environments")
    _result = subprocess.run(
        ["chpasswd"],
        input=f"root:{password}".encode(),
        capture_output=True,
        check=True,
    )
    dotenv.save_dotenv_value(dotenv.KEY_ROOT_PASSWORD, password)


def get_runtime_config(set: Settings):
    if runtime.is_dockerized():
        return {
            "code_exec_ssh_addr": "localhost",
            "code_exec_ssh_port": 22,
            "code_exec_http_port": 80,
            "code_exec_ssh_user": "root",
        }
    else:
        host = set["rfc_url"]
        if "//" in host:
            host = host.split("//")[1]
        if ":" in host:
            host, port = host.split(":")
        if host.endswith("/"):
            host = host[:-1]
        return {
            "code_exec_ssh_addr": host,
            "code_exec_ssh_port": set["rfc_port_ssh"],
            "code_exec_http_port": set["rfc_port_http"],
            "code_exec_ssh_user": "root",
        }


def create_auth_token() -> str:
    runtime_id = runtime.get_persistent_id()
    username = dotenv.get_dotenv_value(dotenv.KEY_AUTH_LOGIN) or ""
    password = dotenv.get_dotenv_value(dotenv.KEY_AUTH_PASSWORD) or ""
    # use base64 encoding for a more compact token with alphanumeric chars
    hash_bytes = hashlib.sha256(f"{runtime_id}:{username}:{password}".encode()).digest()
    # encode as base64 and remove any non-alphanumeric chars (like +, /, =)
    b64_token = base64.urlsafe_b64encode(hash_bytes).decode().replace("=", "")
    return b64_token[:16]


def _get_version():
    try:
        git_info = git.get_git_info()
        return str(git_info.get("short_tag", "")).strip() or "unknown"
    except Exception:
        return "unknown"
