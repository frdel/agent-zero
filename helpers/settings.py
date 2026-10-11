import base64
from contextlib import contextmanager
from contextvars import ContextVar, Token
from copy import deepcopy
import hashlib
import json
import os
import re
import subprocess
from typing import Any, Literal, TypedDict, cast, TypeVar

import models
import pytz  # type: ignore
from helpers import runtime, defer, git, subagents
from . import files, dotenv
from helpers.print_style import PrintStyle
from helpers.providers import get_providers, FieldOption as ProvidersFO
from helpers.secrets import get_default_secrets_manager
from helpers import dirty_json
from helpers.notification import NotificationManager, NotificationType, NotificationPriority


T = TypeVar('T')

def get_default_value(name: str, value: T) -> T:
    """
    Load setting value from .env with A0_SET_ prefix, falling back to default.

    Args:
        name: Setting name (will be prefixed with A0_SET_)
        value: Default value to use if env var not set

    Returns:
        Environment variable value (type-normalized) or default value
    """
    env_value = dotenv.get_dotenv_value(f"A0_SET_{name}", dotenv.get_dotenv_value(f"A0_SET_{name.upper()}", None))

    if env_value is None:
        return value

    # Normalize type to match value param type
    try:
        if isinstance(value, bool):
            return env_value.strip().lower() in ('true', '1', 'yes', 'on')  # type: ignore
        elif isinstance(value, dict):
            return json.loads(env_value.strip())  # type: ignore
        elif isinstance(value, str):
            return str(env_value).strip()  # type: ignore
        else:
            return type(value)(env_value.strip())  # type: ignore
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        PrintStyle(background_color="yellow", font_color="black").print(
            f"Warning: Invalid value for A0_SET_{name}='{env_value}': {e}. Using default: {value}"
        )
        return value

class Settings(TypedDict):
    version: str

    agent_profile: str
    agent_knowledge_subdir: str
    max_consecutive_unusable_responses: int
    timezone: str
    time_format: str
    ui_control_visibility: dict[str, dict[str, bool]]

    workdir_path: str
    workdir_show: bool
    workdir_max_depth: int
    workdir_max_files: int
    workdir_max_folders: int
    workdir_max_lines: int
    workdir_gitignore: str
    file_browser_remember_last_directory: bool
    file_browser_max_text_size_mb: int
    file_browser_max_transfer_size_mb: int
    file_browser_max_extract_size_mb: int
    file_browser_max_archive_entries: int

    api_keys: dict[str, str]

    auth_login: str
    auth_password: str
    root_password: str

    rfc_auto_docker: bool
    rfc_url: str
    rfc_password: str
    rfc_port_http: int

    websocket_server_restart_enabled: bool
    uvicorn_access_logs_enabled: bool

    mcp_servers: str
    mcp_client_init_timeout: int
    mcp_client_tool_timeout: int
    mcp_server_enabled: bool
    mcp_server_token: str

    a2a_server_enabled: bool

    variables: str
    secrets: str

    # LiteLLM global kwargs applied to all model calls
    litellm_global_kwargs: dict[str, Any]

    update_check_enabled: bool
    chat_inherit_project: bool


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
        "text",
        "number",
        "select",
        "range",
        "textarea",
        "password",
        "switch",
        "button",
        "html",
    ]
    value: Any
    min: float
    max: float
    step: float
    hidden: bool
    options: list[FieldOption]
    style: str


class SettingsSection(TypedDict, total=False):
    id: str
    title: str
    description: str
    fields: list[SettingsField]
    tab: str  # Indicates which tab this section belongs to

class ModelProvider(ProvidersFO):
    pass

class SettingsOutputAdditional(TypedDict):
    chat_providers: list[ModelProvider]
    embedding_providers: list[ModelProvider]
    agent_subdirs: list[FieldOption]
    knowledge_subdirs: list[FieldOption]
    timezones: list[FieldOption]
    resolved_timezone: str
    is_dockerized: bool
    runtime_settings: dict[str, Any]


class SettingsOutput(TypedDict):
    settings: Settings
    additional: SettingsOutputAdditional


PASSWORD_PLACEHOLDER = "****PSWD****"
API_KEY_PLACEHOLDER = "************"
TIMEZONE_AUTO = "auto"
TIME_FORMAT_12H = "12h"
TIME_FORMAT_24H = "24h"
UI_CONTROL_VISIBILITY_DEFAULTS = {
    "projectSelector": {"mobile": True, "desktop": True},
    "time": {"mobile": False, "desktop": True},
    "connectionStatus": {"mobile": True, "desktop": True},
    "contextWindowUsage": {"mobile": True, "desktop": True},
    "rightCanvasRail": {"mobile": True, "desktop": True},
}

SETTINGS_FILE = files.get_abs_path("usr/settings.json")
_settings: Settings | None = None
_settings_version_cache: ContextVar[dict[str, str] | None] = ContextVar(
    "settings_version_cache", default=None
)
_runtime_settings_snapshot: Settings | None = None
_prompt_settings_snapshot: ContextVar[Settings | None] = ContextVar(
    "prompt_settings_snapshot", default=None
)

OptionT = TypeVar("OptionT", bound=FieldOption)

def _ensure_option_present(options: list[OptionT] | None, current_value: str | None) -> list[OptionT]:
    """
    Ensure the currently selected value exists in a dropdown options list.
    If missing, inserts it at the front as {value: current_value, label: current_value}.
    """
    opts = list(options or [])
    if not current_value:
        return opts
    for o in opts:
        if o.get("value") == current_value:
            return opts
    opts.insert(0, cast(OptionT, {"value": current_value, "label": current_value}))
    return opts


def _is_valid_timezone(value: str) -> bool:
    try:
        pytz.timezone(value)
        return True
    except pytz.exceptions.UnknownTimeZoneError:
        return False


def _normalize_timezone_setting(value: Any, default: str = TIMEZONE_AUTO) -> str:
    timezone = str(value or "").strip()
    if timezone.lower() == TIMEZONE_AUTO:
        return TIMEZONE_AUTO
    if _is_valid_timezone(timezone):
        return timezone
    return default if default == TIMEZONE_AUTO or _is_valid_timezone(default) else TIMEZONE_AUTO


def _normalize_time_format(value: Any, default: str = TIME_FORMAT_12H) -> str:
    time_format = str(value or "").strip().lower()
    if time_format in {TIME_FORMAT_12H, TIME_FORMAT_24H}:
        return time_format
    return default if default in {TIME_FORMAT_12H, TIME_FORMAT_24H} else TIME_FORMAT_12H


def _normalize_ui_control_visibility(value: Any) -> dict[str, dict[str, bool]]:
    submitted = value if isinstance(value, dict) else {}
    normalized = {}
    defaults = {
        **{control: {"mobile": True, "desktop": True} for control in submitted
           if isinstance(control, str) and control.startswith("canvas:") and len(control) > 7},
        **UI_CONTROL_VISIBILITY_DEFAULTS,
    }
    for control, devices in defaults.items():
        submitted_devices = submitted.get(control, {})
        if not isinstance(submitted_devices, dict):
            submitted_devices = {}
        normalized[control] = {
            device: submitted_devices.get(device)
            if isinstance(submitted_devices.get(device), bool)
            else default
            for device, default in devices.items()
        }
    return normalized


def _resolve_runtime_timezone(setting_value: str, browser_timezone: str | None = None) -> str:
    if setting_value == TIMEZONE_AUTO:
        candidate = str(browser_timezone or "").strip()
        if _is_valid_timezone(candidate):
            return candidate
        try:
            from helpers.localization import Localization

            return Localization.get().get_timezone()
        except Exception:
            return "UTC"
    return _normalize_timezone_setting(setting_value, default="UTC")


def _timezone_options() -> list[FieldOption]:
    return [{"value": timezone, "label": timezone} for timezone in pytz.common_timezones]


def convert_out(settings: Settings) -> SettingsOutput:
    out = SettingsOutput(
        settings = settings.copy(),
        additional = SettingsOutputAdditional(
            chat_providers=get_providers("chat"),
            embedding_providers=get_providers("embedding"),
            is_dockerized=runtime.is_dockerized(),
            agent_subdirs=[
                {"value": key, "label": item.title or key}
                for key, item in sorted(
                    subagents.get_available_agents_dict(None).items()
                )
                if key != "default"
            ],
            knowledge_subdirs=[{"value": subdir, "label": subdir}
                for subdir in files.get_subdirectories("knowledge", exclude="default")],
            timezones=_timezone_options(),
            resolved_timezone="UTC",
            runtime_settings={},
        ),
    )

    # ensure dropdown options include currently selected values
    additional = out["additional"]
    current = out["settings"]

    default_settings = get_default_settings()
    runtime_settings = _runtime_settings_snapshot or settings
    additional["runtime_settings"] = {
        "uvicorn_access_logs_enabled": bool(
            runtime_settings.get(
                "uvicorn_access_logs_enabled",
                default_settings["uvicorn_access_logs_enabled"],
            )
        ),
    }

    current_profile = current.get("agent_profile")
    if current_profile and current_profile != "default" and not any(
        option["value"] == current_profile
        for option in additional["agent_subdirs"]
    ):
        additional["agent_subdirs"].append(
            {"value": current_profile, "label": f"{current_profile} (unavailable)"}
        )
    additional["knowledge_subdirs"] = _ensure_option_present(additional.get("knowledge_subdirs"), current.get("agent_knowledge_subdir"))
    if current.get("timezone") != TIMEZONE_AUTO:
        additional["timezones"] = _ensure_option_present(additional.get("timezones"), current.get("timezone"))
    additional["resolved_timezone"] = _resolve_runtime_timezone(current.get("timezone", TIMEZONE_AUTO))

    # masked api keys
    providers = get_providers("chat") + get_providers("embedding")
    for provider in providers:
        provider_name = provider["value"]
        api_key = settings["api_keys"].get(provider_name, models.get_api_key_raw(provider_name))
        settings["api_keys"][provider_name] = API_KEY_PLACEHOLDER if api_key and api_key != "None" else ""

    # load auth from dotenv
    out["settings"]["auth_login"] = dotenv.get_dotenv_value(dotenv.KEY_AUTH_LOGIN) or ""
    out["settings"]["auth_password"] = (
        PASSWORD_PLACEHOLDER if dotenv.get_dotenv_value(dotenv.KEY_AUTH_PASSWORD) else ""
    )
    out["settings"]["rfc_password"] = (
        PASSWORD_PLACEHOLDER if dotenv.get_dotenv_value(dotenv.KEY_RFC_PASSWORD) else ""
    )
    out["settings"]["root_password"] = (
        PASSWORD_PLACEHOLDER if dotenv.get_dotenv_value(dotenv.KEY_ROOT_PASSWORD) else ""
    )

    #secrets
    secrets_manager = get_default_secrets_manager()
    try:
        out["settings"]["secrets"] = secrets_manager.get_masked_secrets()
    except Exception:
        out["settings"]["secrets"] = ""

    # mask API keys before sending to frontend
    if isinstance(out["settings"].get("api_keys"), dict):
        for provider, value in list(out["settings"]["api_keys"].items()):
            if value:
                out["settings"]["api_keys"][provider] = API_KEY_PLACEHOLDER

    # normalize certain fields
    for key, value in list(out["settings"].items()):
        # convert kwargs dicts to .env format
        if (key.endswith("_kwargs")) and isinstance(value, dict):
            out["settings"][key] = _dict_to_env(value)
    return out

def _get_api_key_field(settings: Settings, provider: str, title: str) -> SettingsField:
    key = settings["api_keys"].get(provider, models.get_api_key_raw(provider))
    # For API keys, use simple asterisk placeholder for existing keys
    return {
        "id": f"api_key_{provider}",
        "title": title,
        "type": "text",
        "value": (API_KEY_PLACEHOLDER if key and key != "None" else ""),
    }


def convert_in(settings: Settings) -> Settings:
    current = get_settings()

    for key, value in settings.items():
        # Special handling for *_kwargs (stored as .env text)
        if (key.endswith("_kwargs")) and isinstance(value, str):
            current[key] = _env_to_dict(value)
            continue

        current[key] = value
    return current


def get_settings() -> Settings:
    global _settings
    if not _settings:
        _settings = _read_settings_file()
    if not _settings:
        _settings = get_default_settings()
    norm = normalize_settings(_settings)
    _load_sensitive_settings(norm)
    return norm


def get_settings_for_prompt() -> Settings:
    if (snapshot := _prompt_settings_snapshot.get()) is not None:
        return deepcopy(snapshot)
    return get_settings()


def begin_prompt_settings_snapshot() -> Token:
    return _prompt_settings_snapshot.set(get_settings())


def end_prompt_settings_snapshot(token: Token) -> None:
    _prompt_settings_snapshot.reset(token)


def reload_settings() -> Settings:
    global _settings
    _settings = None
    current = get_settings()
    if _prompt_settings_snapshot.get() is not None:
        _prompt_settings_snapshot.set(deepcopy(current))
    return current


def set_runtime_settings_snapshot(settings: Settings) -> None:
    global _runtime_settings_snapshot
    _runtime_settings_snapshot = settings.copy()


@contextmanager
def version_cache_scope(version: str | None = None):
    cached = {"version": version or _get_version()}
    token = _settings_version_cache.set(cached)
    try:
        yield
    finally:
        # Expire the cache in inherited task contexts too.
        cached.clear()
        _settings_version_cache.reset(token)


def set_settings(settings: Settings, apply: bool = True, browser_timezone: str | None = None):
    global _settings
    previous = _settings
    _settings = normalize_settings(settings)
    _write_settings_file(_settings)
    if apply:
        with version_cache_scope(_settings["version"]):
            _apply_settings(previous, browser_timezone)
    return reload_settings()


def set_settings_delta(delta: dict, apply: bool = True):
    current = get_settings()
    new = {**current, **delta}
    return set_settings(new, apply)  # type: ignore


def merge_settings(original: Settings, delta: dict) -> Settings:
    merged = original.copy()
    merged.update(delta)
    return merged


def normalize_settings(settings: Settings) -> Settings:
    copy = settings.copy()
    default = get_default_settings()

    # adjust settings values to match current version if needed
    if "version" not in copy or copy["version"] != default["version"]:
        _adjust_to_version(copy, default)
        copy["version"] = default["version"]  # sync version

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
                    copy[key] = copy[key].strip()  # strip strings
            except (ValueError, TypeError):
                copy[key] = value  # make default instead

    copy["file_browser_max_text_size_mb"] = max(1, min(100, copy["file_browser_max_text_size_mb"]))
    copy["file_browser_max_transfer_size_mb"] = max(1, copy["file_browser_max_transfer_size_mb"])
    copy["file_browser_max_extract_size_mb"] = max(1, copy["file_browser_max_extract_size_mb"])
    copy["file_browser_max_archive_entries"] = max(1, copy["file_browser_max_archive_entries"])
    if copy["agent_profile"] == "default":
        copy["agent_profile"] = "agent0"

    # mcp server token is set automatically
    copy["mcp_server_token"] = create_auth_token()
    copy["max_consecutive_unusable_responses"] = max(
        1, copy["max_consecutive_unusable_responses"]
    )
    copy["timezone"] = _normalize_timezone_setting(copy.get("timezone"), default["timezone"])
    copy["time_format"] = _normalize_time_format(copy.get("time_format"), default["time_format"])
    copy["ui_control_visibility"] = _normalize_ui_control_visibility(copy.get("ui_control_visibility"))

    return copy


def _adjust_to_version(settings: Settings, default: Settings):
    # starting with 0.9, the default prompt subfolder for agent no. 0 is agent0
    # switch to agent0 if the old default is used from v0.8
    if "version" not in settings or settings["version"].startswith("v0.8"):
        if "agent_profile" not in settings or settings["agent_profile"] == "default":
            settings["agent_profile"] = "agent0"



def _load_sensitive_settings(settings: Settings):
    # load api keys from .env
    providers = get_providers("chat") + get_providers("embedding")
    for provider in providers:
        provider_name = provider["value"]
        api_key = settings["api_keys"].get(provider_name) or models.get_api_key_raw(provider_name)
        if api_key and api_key != "None":
            settings["api_keys"][provider_name] = api_key

    # load auth fields from .env
    settings["auth_login"] = dotenv.get_dotenv_value(dotenv.KEY_AUTH_LOGIN) or ""
    settings["auth_password"] = dotenv.get_dotenv_value(dotenv.KEY_AUTH_PASSWORD) or ""
    settings["rfc_password"] = dotenv.get_dotenv_value(dotenv.KEY_RFC_PASSWORD) or ""
    settings["root_password"] = dotenv.get_dotenv_value(dotenv.KEY_ROOT_PASSWORD) or ""

    # load secrets raw content
    secrets_manager = get_default_secrets_manager()
    try:
        settings["secrets"] = secrets_manager.read_secrets_raw()
    except Exception:
        settings["secrets"] = ""


def _read_settings_file() -> Settings | None:
    if os.path.exists(SETTINGS_FILE):
        content = files.read_file(SETTINGS_FILE)
        parsed = json.loads(content)
        return normalize_settings(parsed)


def _write_settings_file(settings: Settings):
    settings = settings.copy()
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
    settings["secrets"] = ""


def _write_sensitive_settings(settings: Settings):
    for key, val in settings["api_keys"].items():
        if val != API_KEY_PLACEHOLDER:
            dotenv.save_dotenv_value(f"API_KEY_{key.upper()}", val)

    dotenv.save_dotenv_value(dotenv.KEY_AUTH_LOGIN, settings["auth_login"])
    if settings["auth_password"] != PASSWORD_PLACEHOLDER:
        dotenv.save_dotenv_value(dotenv.KEY_AUTH_PASSWORD, settings["auth_password"])
    if settings["rfc_password"] != PASSWORD_PLACEHOLDER:
        dotenv.save_dotenv_value(dotenv.KEY_RFC_PASSWORD, settings["rfc_password"])
    if settings["root_password"] != PASSWORD_PLACEHOLDER:
        if runtime.is_dockerized():
            dotenv.save_dotenv_value(dotenv.KEY_ROOT_PASSWORD, settings["root_password"])
            set_root_password(settings["root_password"])

    # Handle secrets separately - merge with existing preserving comments/order and support deletions
    secrets_manager = get_default_secrets_manager()
    submitted_content = settings["secrets"]
    secrets_manager.save_secrets_with_merge(submitted_content)



def get_default_settings() -> Settings:
    gitignore = files.read_file(files.get_abs_path("conf/workdir.gitignore"))
    return Settings(
        version=_get_version(),
        api_keys={},
        auth_login="",
        auth_password="",
        root_password="",
        agent_profile=get_default_value("agent_profile", "agent0"),
        agent_knowledge_subdir=get_default_value("agent_knowledge_subdir", "custom"),
        max_consecutive_unusable_responses=get_default_value(
            "max_consecutive_unusable_responses", 5
        ),
        timezone=_normalize_timezone_setting(get_default_value("timezone", TIMEZONE_AUTO)),
        time_format=_normalize_time_format(get_default_value("time_format", TIME_FORMAT_12H)),
        ui_control_visibility=_normalize_ui_control_visibility(
            get_default_value("ui_control_visibility", UI_CONTROL_VISIBILITY_DEFAULTS)
        ),
        workdir_path=get_default_value("workdir_path", files.get_abs_path_dockerized("usr/workdir")),
        workdir_show=get_default_value("workdir_show", True),
        workdir_max_depth=get_default_value("workdir_max_depth", 5),
        workdir_max_files=get_default_value("workdir_max_files", 20),
        workdir_max_folders=get_default_value("workdir_max_folders", 20),
        workdir_max_lines=get_default_value("workdir_max_lines", 250),
        workdir_gitignore=get_default_value("workdir_gitignore", gitignore),
        file_browser_remember_last_directory=get_default_value(
            "file_browser_remember_last_directory",
            True,
        ),
        file_browser_max_text_size_mb=get_default_value("file_browser_max_text_size_mb", 10),
        file_browser_max_transfer_size_mb=get_default_value("file_browser_max_transfer_size_mb", 100),
        file_browser_max_extract_size_mb=get_default_value("file_browser_max_extract_size_mb", 100),
        file_browser_max_archive_entries=get_default_value("file_browser_max_archive_entries", 1000),
        rfc_auto_docker=get_default_value("rfc_auto_docker", True),
        rfc_url=get_default_value("rfc_url", "localhost"),
        rfc_password="",
        rfc_port_http=get_default_value("rfc_port_http", 55080),
        websocket_server_restart_enabled=get_default_value("websocket_server_restart_enabled", True),
        uvicorn_access_logs_enabled=get_default_value("uvicorn_access_logs_enabled", False),
        mcp_servers=get_default_value("mcp_servers", '{\n    "mcpServers": {}\n}'),
        mcp_client_init_timeout=get_default_value("mcp_client_init_timeout", 10),
        mcp_client_tool_timeout=get_default_value("mcp_client_tool_timeout", 120),
        mcp_server_enabled=get_default_value("mcp_server_enabled", False),
        mcp_server_token=create_auth_token(),
        a2a_server_enabled=get_default_value("a2a_server_enabled", False),
        variables="",
        secrets="",
        litellm_global_kwargs=get_default_value("litellm_global_kwargs", {}),
        update_check_enabled=get_default_value("update_check_enabled", True),
        chat_inherit_project=get_default_value("chat_inherit_project", True),
    )


def _apply_timezone_setting(previous: Settings | None, browser_timezone: str | None = None) -> None:
    if not _settings:
        return

    from helpers.localization import Localization

    localization = Localization.get()
    previous_timezone = localization.get_timezone()
    target_timezone = _resolve_runtime_timezone(_settings["timezone"], browser_timezone)
    if (
        previous
        and _settings["timezone"] == previous.get("timezone")
        and _settings["timezone"] != TIMEZONE_AUTO
        and previous_timezone == target_timezone
    ):
        return

    localization.set_timezone(target_timezone)
    current_timezone = localization.get_timezone()
    if current_timezone == previous_timezone:
        return

    try:
        from helpers import plugins

        plugins.call_plugin_hook(
            "_office",
            "timezone_changed",
            None,
            previous_timezone=previous_timezone,
            timezone=current_timezone,
        )
    except Exception:
        return


def _apply_settings(previous: Settings | None, browser_timezone: str | None = None):
    global _settings
    if _settings:
        _apply_timezone_setting(previous, browser_timezone)

        from agent import Agent, AgentContext
        from initialize import initialize_agent

        for ctx in AgentContext.all():
            profile = str(
                getattr(ctx.config, "profile", "") or _settings["agent_profile"]
            )
            ctx.config = initialize_agent(override_settings={"agent_profile": profile})
            agent = ctx.agent0
            while agent:
                agent_profile = str(
                    getattr(getattr(agent, "config", None), "profile", "") or profile
                )
                agent.config = (
                    ctx.config
                    if agent is ctx.agent0 and agent_profile == profile
                    else initialize_agent(
                        override_settings={"agent_profile": agent_profile}
                    )
                )
                agent = agent.get_data(Agent.DATA_NAME_SUBORDINATE)

        # update mcp settings if necessary
        if not previous or _settings["mcp_servers"] != previous["mcp_servers"]:
            from helpers.mcp_handler import MCPConfig

            async def update_mcp_settings(mcp_servers: str):
                PrintStyle(
                    background_color="black", font_color="white", padding=True
                ).print("Updating MCP config...")
                NotificationManager.send_notification(
                    type=NotificationType.INFO,
                    priority=NotificationPriority.NORMAL,
                    message="Updating MCP settings...",
                    display_time=999,
                    group="settings-mcp"
                )

                mcp_config = MCPConfig.get_instance()
                try:
                    MCPConfig.update(mcp_servers)
                except Exception as e:
                    
                    NotificationManager.send_notification(
                        type=NotificationType.ERROR,
                        priority=NotificationPriority.HIGH,
                        message="Failed to update MCP settings",
                        detail=str(e),                        
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
                NotificationManager.send_notification(
                    type=NotificationType.INFO,
                    priority=NotificationPriority.NORMAL,
                    message="Finished updating MCP settings.",
                    group="settings-mcp"
                )

            task2 = defer.DeferredTask().start_task(
                update_mcp_settings, _settings["mcp_servers"]
            )  # TODO overkill, replace with background task

        # update token in mcp server
        current_token = (
            create_auth_token()
        )  # TODO - ugly, token in settings is generated from dotenv and does not always correspond
        if not previous or current_token != previous["mcp_server_token"]:

            async def update_mcp_token(token: str):
                from helpers.mcp_server import DynamicMcpProxy

                DynamicMcpProxy.get_instance().reconfigure(token=token)

            task3 = defer.DeferredTask().start_task(
                update_mcp_token, current_token
            )  # TODO overkill, replace with background task

        # update token in a2a server
        if not previous or current_token != previous["mcp_server_token"]:

            async def update_a2a_token(token: str):
                from helpers.fasta2a_server import DynamicA2AProxy

                DynamicA2AProxy.get_instance().reconfigure(token=token)

            task4 = defer.DeferredTask().start_task(
                update_a2a_token, current_token
            )  # TODO overkill, replace with background task


def _env_to_dict(data: str):
    result = {}
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        if '=' not in line:
            continue
            
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        
        # If quoted, treat as string
        if value.startswith('"') and value.endswith('"'):
            result[key] = value[1:-1].replace('\\"', '"')  # Unescape quotes
        elif value.startswith("'") and value.endswith("'"):
            result[key] = value[1:-1].replace("\\'", "'")  # Unescape quotes
        else:
            # Not quoted, try JSON parse
            try:
                result[key] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                result[key] = value
    
    return result


def _dict_to_env(data_dict):
    lines = []
    for key, value in data_dict.items():
        if isinstance(value, str):
            # Quote strings and escape internal quotes
            escaped_value = value.replace('"', '\\"')
            lines.append(f'{key}="{escaped_value}"')
        elif isinstance(value, (dict, list, bool)) or value is None:
            # Serialize as unquoted JSON
            lines.append(f'{key}={json.dumps(value, separators=(",", ":"))}')
        else:
            # Numbers and other types as unquoted strings
            lines.append(f'{key}={value}')
    
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
    # SSH config is now managed by the code_execution plugin.
    # This function is kept for backward compatibility but returns an empty dict.
    return {}


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
    return (_settings_version_cache.get() or {}).get("version") or git.get_version()
