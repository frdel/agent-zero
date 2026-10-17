import os
from copy import deepcopy

import models
from helpers import cache, defer, plugins, files
from helpers.extension import call_extensions_async
from helpers import yaml as yaml_helper
from helpers.providers import get_provider_config, get_providers

PRESETS_FILE = "presets.yaml"
FALLBACK_PRESETS_FILE = "mode_presets_fallback.yaml"
PROVIDER_METADATA_FILE = "provider_metadata.yaml"
PRESETS_CACHE_AREA = "model_presets(plugins)"
DEFAULT_PRESET_NAME = "Default"
DEFAULT_VISION_TIMEOUT_SECONDS = 300
DEFAULT_VISION_MAX_TOKENS = 2000
MODEL_PRESET_CONFIG_KEY = "model_preset"
PRESET_SCOPE_GLOBAL = "global"
PRESET_SCOPE_PROJECT = "project"
PRESET_SLOT_CONFIG_SECTIONS = {
    "chat": "chat_model",
    "vision": "vision_model",
    "utility": "utility_model",
    "embedding": "embedding_model",
}
MODEL_SLOT_PRESET_REPLACE_FIELDS = {"kwargs"}
IMPLICIT_PRESET_SLOT_DEFAULTS = {
    "vision": {
        "vision": True,
        "max_embeds": 10,
        "timeout": DEFAULT_VISION_TIMEOUT_SECONDS,
        "max_tokens": DEFAULT_VISION_MAX_TOKENS,
        "override_main": False,
        "rl_requests": 0,
        "rl_input": 0,
        "rl_output": 0,
        "kwargs": {},
    },
    "utility": {
        "ctx_length": 128000,
        "ctx_input": 0.7,
        "rl_requests": 0,
        "rl_input": 0,
        "rl_output": 0,
        "kwargs": {},
    },
    "embedding": {
        "rl_requests": 0,
        "rl_input": 0,
        "kwargs": {},
    },
}
LOCAL_PROVIDERS = {"ollama", "lm_studio", "llama_cpp", "omlx", "vllm"}
LOCAL_EMBEDDING = {"huggingface"}
_PROVIDER_METADATA_CACHE: dict | None = None


def _get_provider_metadata_path() -> str:
    plugin_dir = plugins.find_plugin_dir("_model_config")
    return files.get_abs_path(plugin_dir, PROVIDER_METADATA_FILE) if plugin_dir else ""


def get_provider_metadata(model_type: str = "chat", provider: str = "") -> dict:
    """Get plugin-owned provider metadata that does not belong in conf/model_providers.yaml."""
    global _PROVIDER_METADATA_CACHE
    if _PROVIDER_METADATA_CACHE is None:
        path = _get_provider_metadata_path()
        if path and files.exists(path):
            data = yaml_helper.loads(files.read_file(path))
            _PROVIDER_METADATA_CACHE = data if isinstance(data, dict) else {}
        else:
            _PROVIDER_METADATA_CACHE = {}

    section = _PROVIDER_METADATA_CACHE.get(model_type, {})
    if not isinstance(section, dict):
        return {}
    meta = section.get(str(provider or "").strip().lower(), {})
    return meta if isinstance(meta, dict) else {}


def _model_type_for_label(label: str) -> str:
    return "embedding" if label == "Embedding Model" else "chat"


def provider_requires_api_key(provider: str, model_type: str = "chat") -> bool:
    provider_id = str(provider or "").strip().lower()
    if not provider_id:
        return False
    cfg = get_provider_config(model_type, provider_id) or get_provider_config("chat", provider_id) or {}
    meta = get_provider_metadata(model_type, provider_id) or get_provider_metadata("chat", provider_id)
    mode = str(meta.get("api_key_mode") or cfg.get("api_key_mode") or "required").strip().lower()
    return mode not in {"none", "optional", "oauth"}


def _get_presets_path(project_name: str | None = None) -> str:
    """Return the user-editable presets path for the requested scope."""
    if project_name:
        return plugins.determine_plugin_asset_path(
            "_model_config", project_name, "", PRESETS_FILE
        )
    return files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR, "_model_config", PRESETS_FILE)


def _get_fallback_presets_path() -> str:
    """Return the plugin-local fallback used when no saved presets exist."""
    plugin_dir = plugins.find_plugin_dir("_model_config")
    return files.get_abs_path(plugin_dir, FALLBACK_PRESETS_FILE) if plugin_dir else ""


def get_config(agent=None, project_name=None, agent_profile=None):
    """Get the resolved model config for an agent or selected scope."""
    config = plugins.get_plugin_config(
        "_model_config",
        agent=agent,
        project_name=project_name,
        agent_profile=agent_profile,
    ) or {}
    # The plugin hook resolves selection-only config. Keep this boundary robust
    # when hooks are disabled by tests or embedding applications.
    if any(section in config for section in PRESET_SLOT_CONFIG_SECTIONS.values()):
        return config
    return resolve_config_settings(config)


def get_configured_preset_name(agent=None, project_name=None, agent_profile=None) -> str:
    """Return the valid scoped preset selection, falling back to Default."""
    config = plugins.get_plugin_config(
        "_model_config",
        agent=agent,
        project_name=project_name,
        agent_profile=agent_profile,
    ) or {}
    name = str(config.get(MODEL_PRESET_CONFIG_KEY) or DEFAULT_PRESET_NAME).strip()
    return name if resolve_preset(name) else DEFAULT_PRESET_NAME


def preset_to_config(preset: dict) -> dict:
    """Convert a complete preset into the legacy runtime model-config shape."""
    config: dict = {}
    for slot, section in PRESET_SLOT_CONFIG_SECTIONS.items():
        slot_config = preset.get(slot) if isinstance(preset, dict) else None
        config[section] = (
            _strip_ui_fields(slot_config, strip_api_key=False)
            if isinstance(slot_config, dict)
            else {}
        )
    return config


def config_to_preset(config: dict, name: str = DEFAULT_PRESET_NAME) -> dict:
    """Convert legacy full model config into a preset without UI/API-key fields."""
    preset = {"name": str(name or "").strip()}
    for slot, section in PRESET_SLOT_CONFIG_SECTIONS.items():
        slot_config = config.get(section) if isinstance(config, dict) else None
        if isinstance(slot_config, dict):
            preset[slot] = _strip_ui_fields(slot_config, strip_api_key=True)
    return preset


def resolve_config_settings(settings: dict | None) -> dict:
    """Resolve selection-only settings to the complete runtime config shape."""
    raw = settings if isinstance(settings, dict) else {}
    selected_name = str(raw.get(MODEL_PRESET_CONFIG_KEY) or DEFAULT_PRESET_NAME).strip()
    default_preset = resolve_preset(DEFAULT_PRESET_NAME) or {"name": DEFAULT_PRESET_NAME}
    selected = resolve_preset(selected_name) or default_preset
    config = preset_to_config(default_preset)
    if selected.get("name") != DEFAULT_PRESET_NAME:
        config = build_config_from_preset(selected, config, strip_api_key=False)
    config[MODEL_PRESET_CONFIG_KEY] = str(selected.get("name") or DEFAULT_PRESET_NAME)
    # Retained as a read-only compatibility flag for integrations that still
    # inspect it. The switcher is always available in the unified preset model.
    config["allow_chat_override"] = True
    return config


def has_project_config(project_name: str) -> bool:
    path = plugins.determine_plugin_asset_path(
        "_model_config", project_name, "", plugins.CONFIG_FILE_NAME
    )
    return files.exists(path)


def load_project_llm_data(project_name: str) -> dict:
    """Build the preset-selection payload shown in Project Settings."""
    project_config_exists = has_project_config(project_name)
    preset_name = get_configured_preset_name(project_name=project_name)
    return {
        "has_project_config": project_config_exists,
        "selected_preset": {
            "scope": PRESET_SCOPE_GLOBAL,
            "project_name": "",
            "name": preset_name,
        },
        "presets": get_combined_presets(),
        "global_presets": get_presets(),
        "project_presets": [],
    }


def save_project_llm_settings(project_name: str, llm_data: object) -> None:
    """Persist only a project preset selection from Project Settings."""
    if not isinstance(llm_data, dict):
        return
    selected_preset = llm_data.get("selected_preset")
    if not isinstance(selected_preset, dict):
        return
    name = str(selected_preset.get("name") or "").strip()
    if resolve_preset(name):
        if not has_project_config(project_name) and name == get_configured_preset_name():
            return
        previous_embedding = get_config(project_name=project_name).get(
            "embedding_model",
            {},
        )
        plugins.save_plugin_config(
            "_model_config",
            project_name,
            "",
            {MODEL_PRESET_CONFIG_KEY: name},
        )
        current_embedding = get_config(project_name=project_name).get(
            "embedding_model",
            {},
        )
        if previous_embedding != current_embedding:
            defer.DeferredTask().start_task(
                call_extensions_async,
                "embedding_model_changed",
            )


def _load_presets_from_path(path: str, *, raise_on_error: bool = False) -> list | None:
    if files.exists(path):
        try:
            data = yaml_helper.loads(files.read_file(path))
        except Exception:
            if raise_on_error:
                raise
            return None
        if isinstance(data, list):
            return data
    return None


def _strip_ui_fields(value: dict, *, strip_api_key: bool) -> dict:
    cleaned = deepcopy(value)
    for key in list(cleaned.keys()):
        if key.startswith("_"):
            cleaned.pop(key, None)
    if strip_api_key:
        cleaned.pop("api_key", None)
    return cleaned


def _preset_default_values_equal(value, default) -> bool:
    if isinstance(default, float):
        try:
            return float(value) == default
        except (TypeError, ValueError):
            return False
    return value == default


def _strip_implicit_preset_defaults(slot: str, slot_config: dict) -> dict:
    cleaned = deepcopy(slot_config)
    defaults = IMPLICIT_PRESET_SLOT_DEFAULTS.get(slot, {})
    for key, default in defaults.items():
        if key in cleaned and _preset_default_values_equal(cleaned[key], default):
            cleaned.pop(key, None)
    return cleaned


def _clean_preset_for_file(preset: dict) -> dict:
    name = str(preset.get("name", "") or "").strip()
    if name.casefold() == DEFAULT_PRESET_NAME.casefold():
        name = DEFAULT_PRESET_NAME
    cleaned = {
        "name": name,
    }
    has_named_slots = any(
        isinstance(preset.get(slot), dict) for slot in PRESET_SLOT_CONFIG_SECTIONS
    )
    for slot in PRESET_SLOT_CONFIG_SECTIONS:
        slot_config = preset.get(slot)
        if isinstance(slot_config, dict):
            slot_clean = _strip_ui_fields(slot_config, strip_api_key=True)
            cleaned[slot] = (
                slot_clean
                if name == DEFAULT_PRESET_NAME
                else _strip_implicit_preset_defaults(slot, slot_clean)
            )
    # Very old presets stored the main model directly beside ``name``. Preserve
    # those definitions while bringing them into the canonical slot schema.
    if not has_named_slots and _slot_has_identity(preset):
        raw_chat = {
            key: value
            for key, value in preset.items()
            if key not in {"name", "scope", "project_name"}
        }
        raw_chat["name"] = name
        cleaned["chat"] = _strip_ui_fields(raw_chat, strip_api_key=True)
    return cleaned


def clean_presets_for_file(presets: list) -> list:
    """Return presets without API/UI metadata, preserving the plain YAML schema."""
    cleaned = []
    for preset in presets:
        if isinstance(preset, dict):
            cleaned.append(_clean_preset_for_file(preset))
    return cleaned


def validate_presets(presets: list, *, require_default: bool = True) -> list:
    """Validate and clean the durable global preset collection."""
    if not isinstance(presets, list):
        raise ValueError("Presets must be a list.")

    cleaned: list[dict] = []
    seen: set[str] = set()
    for raw in presets:
        if not isinstance(raw, dict):
            raise ValueError("Every preset must be an object.")
        preset = _clean_preset_for_file(raw)
        name = str(preset.get("name") or "").strip()
        if not name:
            raise ValueError("Preset names cannot be empty.")
        normalized = name.casefold()
        if normalized in seen:
            raise ValueError(f"Preset names must be unique: '{name}'.")
        if normalized == DEFAULT_PRESET_NAME.casefold():
            preset["name"] = DEFAULT_PRESET_NAME
            for slot, label in (
                ("chat", "main"),
                ("utility", "utility"),
                ("embedding", "embedding"),
            ):
                if not _slot_has_identity(preset.get(slot) or {}):
                    raise ValueError(
                        f"The Default preset requires a {label} model."
                    )
        seen.add(normalized)
        cleaned.append(preset)

    default_index = next(
        (i for i, preset in enumerate(cleaned) if preset["name"] == DEFAULT_PRESET_NAME),
        None,
    )
    if require_default and default_index is None:
        raise ValueError("The Default preset cannot be deleted or renamed.")
    if default_index not in (None, 0):
        cleaned.insert(0, cleaned.pop(default_index))
    return cleaned


def normalize_config_for_save(config: dict) -> dict:
    """Remove UI-only fields and inline API keys before storing scoped config."""
    cleaned = deepcopy(config or {})
    for section_name in (
        "chat_model",
        "vision_model",
        "utility_model",
        "embedding_model",
    ):
        section = cleaned.get(section_name)
        if isinstance(section, dict):
            cleaned[section_name] = _strip_ui_fields(section, strip_api_key=True)
    return cleaned


def _legacy_default_preset(*, raise_on_error: bool = False) -> dict | None:
    """Build Default from a pre-v2 global config when startup migration has not run."""
    path = plugins.determine_plugin_asset_path(
        "_model_config", "", "", plugins.CONFIG_FILE_NAME
    )
    if not files.exists(path):
        return None
    try:
        raw = files.read_file_json(path)
    except Exception:
        if raise_on_error:
            raise
        return None
    if not isinstance(raw, dict) or not any(
        section in raw for section in PRESET_SLOT_CONFIG_SECTIONS.values()
    ):
        return None
    return config_to_preset(raw, DEFAULT_PRESET_NAME)


def parse_preset_collection(text: str) -> list:
    """Parse, validate, and sanitize a preset YAML document."""
    return validate_presets(yaml_helper.loads(text))


def _fallback_presets(*, raise_on_error: bool = False) -> list:
    path = _get_fallback_presets_path()
    if not files.exists(path):
        return []
    try:
        return parse_preset_collection(files.read_file(path))
    except Exception:
        if raise_on_error:
            raise
        return []


def _ensure_default_preset(presets: list, *, raise_on_error: bool = False) -> list:
    result = [deepcopy(preset) for preset in presets if isinstance(preset, dict)]
    legacy_default = _legacy_default_preset(raise_on_error=raise_on_error)
    bundled_default = next(
        (
            deepcopy(preset)
            for preset in _fallback_presets(raise_on_error=raise_on_error)
            if isinstance(preset, dict)
            and str(preset.get("name") or "").strip().casefold()
            == DEFAULT_PRESET_NAME.casefold()
        ),
        None,
    )
    fallback_default = bundled_default or {"name": DEFAULT_PRESET_NAME}
    if legacy_default:
        for slot in PRESET_SLOT_CONFIG_SECTIONS:
            legacy_slot = legacy_default.get(slot)
            if _slot_has_identity(legacy_slot or {}):
                fallback_default[slot] = deepcopy(legacy_slot)
    default_index = next(
        (
            i
            for i, preset in enumerate(result)
            if str(preset.get("name") or "").strip().casefold()
            == DEFAULT_PRESET_NAME.casefold()
        ),
        None,
    )
    if default_index is not None:
        result[default_index]["name"] = DEFAULT_PRESET_NAME
        for slot in PRESET_SLOT_CONFIG_SECTIONS:
            if not _slot_has_identity(result[default_index].get(slot) or {}):
                fallback_slot = fallback_default.get(slot)
                if isinstance(fallback_slot, dict):
                    result[default_index][slot] = deepcopy(fallback_slot)
        if default_index:
            result.insert(0, result.pop(default_index))
        return result

    result.insert(0, fallback_default)
    return result


def get_presets(project_name: str | None = None) -> list:
    """Get global presets with the required Default preset first."""
    if project_name:
        return get_project_presets(project_name)

    # config resolution reads presets many times per model call, parse once per file version
    signature = _presets_signature()
    presets = cache.get(PRESETS_CACHE_AREA, signature)
    if presets is None:
        try:
            presets = _load_global_presets(raise_on_error=True)
        except Exception:
            # Preserve fallback behavior without caching a failed read.
            return _load_global_presets()
        cache.add(PRESETS_CACHE_AREA, signature, presets)
    return deepcopy(presets)


def _load_global_presets(*, raise_on_error: bool = False) -> list:
    presets = _load_presets_from_path(_get_presets_path(), raise_on_error=raise_on_error)
    if presets is not None:
        return _ensure_default_preset(presets, raise_on_error=raise_on_error)

    # Fall back to the repository-shipped offline collection.
    return _ensure_default_preset(
        _fallback_presets(raise_on_error=raise_on_error), raise_on_error=raise_on_error
    )


def _presets_signature() -> tuple:
    paths = (
        _get_presets_path(),
        _get_fallback_presets_path(),
        plugins.determine_plugin_asset_path(
            "_model_config", "", "", plugins.CONFIG_FILE_NAME
        ),
    )
    signature = []
    for path in paths:
        try:
            stat = os.stat(path)
            signature.append((path, stat.st_mtime_ns, stat.st_size))
        except OSError:
            signature.append((path, None, None))
    return tuple(signature)


def get_project_presets(project_name: str) -> list:
    """Load legacy project presets for migration/compatibility only."""
    return _load_presets_from_path(_get_presets_path(project_name)) or []


def _with_preset_metadata(preset: dict, scope: str, project_name: str = "") -> dict:
    item = deepcopy(preset)
    item["scope"] = scope
    item["project_name"] = project_name if scope == PRESET_SCOPE_PROJECT else ""
    item["name"] = str(item.get("name", "") or "")
    return item


def get_combined_presets(project_name: str | None = None) -> list:
    """Get global presets with API metadata (project definitions are retired)."""
    return [
        _with_preset_metadata(preset, PRESET_SCOPE_GLOBAL)
        for preset in get_presets()
        if isinstance(preset, dict)
    ]


def save_presets(presets: list, project_name: str | None = None) -> None:
    """Save global presets while enforcing the immutable Default identity."""
    if project_name:
        raise ValueError("Project-specific preset definitions are no longer supported.")
    cleaned = validate_presets(presets)
    path = _get_presets_path(project_name)
    files.write_file(path, yaml_helper.dumps(cleaned))
    cache.clear(PRESETS_CACHE_AREA)


def update_preset_from_config(name: str, config: dict) -> dict:
    """Replace one global preset's model slots from a legacy config payload."""
    target = resolve_preset(name)
    if not target:
        raise ValueError(f"Preset '{name}' was not found.")
    canonical_name = str(target.get("name") or DEFAULT_PRESET_NAME)
    replacement = config_to_preset(config, canonical_name)
    if canonical_name == DEFAULT_PRESET_NAME:
        for slot in PRESET_SLOT_CONFIG_SECTIONS:
            if not _slot_has_identity(replacement.get(slot) or {}):
                current_slot = target.get(slot)
                if isinstance(current_slot, dict):
                    replacement[slot] = deepcopy(current_slot)
    presets = get_presets()
    updated = False
    for index, preset in enumerate(presets):
        if str(preset.get("name") or "").casefold() == canonical_name.casefold():
            presets[index] = replacement
            updated = True
            break
    if not updated:
        raise ValueError(f"Preset '{name}' was not found.")
    save_presets(presets)
    return replacement


def reset_presets(project_name: str | None = None) -> list:
    """Delete user presets for the scope. Global reset falls back to bundled defaults."""
    if project_name:
        raise ValueError("Project-specific preset definitions are no longer supported.")
    path = _get_presets_path(project_name)
    if os.path.exists(path):
        os.remove(path)
    cache.clear(PRESETS_CACHE_AREA)
    return get_presets()


def resolve_preset(
    name: str,
    *,
    scope: str = PRESET_SCOPE_GLOBAL,
    project_name: str | None = None,
) -> dict | None:
    """Resolve a preset by explicit scope so same-name presets are unambiguous."""
    if scope == PRESET_SCOPE_PROJECT:
        return None
    presets = get_presets()

    for p in presets:
        if str(p.get("name") or "").casefold() == str(name or "").strip().casefold():
            return p
    return None


def resolve_preset_selection(selection: dict | str, project_name: str | None = None) -> dict | None:
    """Resolve a UI/API preset selection payload to a preset dict."""
    if isinstance(selection, str):
        return resolve_preset(selection)
    if not isinstance(selection, dict):
        return None

    scope = str(selection.get("scope") or PRESET_SCOPE_GLOBAL)
    if scope == "current":
        return None
    name = str(selection.get("name") or "")
    selected_project = str(selection.get("project_name") or project_name or "")
    return resolve_preset(name, scope=scope, project_name=selected_project or None)


def get_preset_by_name(
    name: str,
    *,
    scope: str = PRESET_SCOPE_GLOBAL,
    project_name: str | None = None,
) -> dict | None:
    """Find a preset by name. Defaults to global presets for legacy callers."""
    return resolve_preset(name, scope=scope, project_name=project_name)


def _deep_merge_dict(base: dict, override: dict) -> dict:
    """Recursively overlay override onto base without mutating either input."""
    result = deepcopy(base) if isinstance(base, dict) else {}
    for key, value in override.items():
        if (
            isinstance(value, dict)
            and isinstance(result.get(key), dict)
        ):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _replace_preset_model_slot_fields(base: dict, override: dict, result: dict) -> dict:
    """Clear or replace provider-specific fields that must not leak across presets."""
    for key in MODEL_SLOT_PRESET_REPLACE_FIELDS:
        if key in override:
            value = override.get(key)
            result[key] = deepcopy(value) if isinstance(value, dict) else {}
        elif key in base:
            result[key] = {}
    return result


def _slot_has_identity(slot_config: dict) -> bool:
    return bool(slot_config.get("provider") or slot_config.get("name"))


def _get_preset_slot_config(preset: dict, slot: str) -> dict | None:
    """Return the preset payload for a slot.

    Legacy raw overrides store the main/chat model directly at the top level,
    while named presets store it under the "chat" key.
    """
    if not isinstance(preset, dict):
        return None

    slot_config = preset.get(slot)
    if isinstance(slot_config, dict):
        return slot_config

    if slot == "chat" and not any(key in preset for key in PRESET_SLOT_CONFIG_SECTIONS):
        if _slot_has_identity(preset):
            return preset

    return None


def _should_apply_preset_slot(slot: str, slot_config: dict | None) -> bool:
    if not isinstance(slot_config, dict):
        return False

    cleaned = _strip_implicit_preset_defaults(
        slot,
        _strip_ui_fields(slot_config, strip_api_key=False),
    )
    meaningful = {
        key: value
        for key, value in cleaned.items()
        if key != "api_key"
    }
    if not meaningful:
        return False

    # Slots inherit the configured model unless the preset declares a model
    # identity for that slot. This keeps empty UI placeholders from accidentally
    # overriding context/rate-limit settings.
    return _slot_has_identity(cleaned)


def _merge_model_slot(
    slot: str,
    base_slot: dict,
    preset_slot: dict,
    *,
    strip_api_key: bool,
) -> dict:
    cleaned = _strip_implicit_preset_defaults(
        slot,
        _strip_ui_fields(preset_slot, strip_api_key=strip_api_key),
    )
    if not strip_api_key and not str(cleaned.get("api_key") or "").strip():
        cleaned.pop("api_key", None)
    base = base_slot if isinstance(base_slot, dict) else {}
    return _replace_preset_model_slot_fields(base, cleaned, _deep_merge_dict(base, cleaned))


def build_config_from_preset(
    preset: dict,
    base_config: dict,
    *,
    strip_api_key: bool = True,
    slots: tuple[str, ...] | None = None,
) -> dict:
    """Overlay preset settings onto a standalone model config.

    Presets are intentionally partial: omitted fields inherit from the current
    config, so selecting a preset does not reset tuned values such as context
    windows or rate limits. Provider-specific kwargs are replaced when present
    and cleared when omitted so stale params do not leak between providers.
    """
    config = (
        normalize_config_for_save(base_config)
        if strip_api_key
        else deepcopy(base_config or {})
    )

    for slot in slots or tuple(PRESET_SLOT_CONFIG_SECTIONS):
        section = PRESET_SLOT_CONFIG_SECTIONS.get(slot)
        if not section:
            continue
        slot_config = _get_preset_slot_config(preset, slot)
        if not _should_apply_preset_slot(slot, slot_config):
            if slot == "vision":
                config[section] = {}
            continue
        config[section] = _merge_model_slot(
            slot,
            {} if slot == "vision" else config.get(section, {}),
            slot_config,
            strip_api_key=strip_api_key,
        )

    return config


def _resolve_override(agent) -> dict | None:
    """Resolve the active per-chat override config dict.
    Supports both raw override dicts and preset-based overrides.
    Returns None if no override is active or if override is not allowed."""
    if not agent:
        return None
    if not is_chat_override_allowed(agent):
        return None
    override = agent.context.get_data("chat_model_override")
    if not override:
        return None

    # If this is a preset reference, resolve it
    if "preset_name" in override:
        preset = get_preset_by_name(override["preset_name"])
        if not preset:
            return None
        return preset

    return override


def get_effective_preset_name(agent=None) -> str:
    """Return the valid preset used by a chat, including its explicit override."""
    if agent:
        override = getattr(agent, "context", None)
        override = override.get_data("chat_model_override") if override else None
        if isinstance(override, dict):
            name = str(override.get("preset_name") or "").strip()
            preset = resolve_preset(name) if name else None
            if preset:
                return str(preset.get("name") or DEFAULT_PRESET_NAME)
    config = get_config(agent)
    return str(config.get(MODEL_PRESET_CONFIG_KEY) or DEFAULT_PRESET_NAME)


def get_effective_config(agent=None) -> dict:
    """Resolve the complete model config, including a per-chat preset selection."""
    config = get_config(agent)
    raw_override = None
    if agent and getattr(agent, "context", None):
        raw_override = agent.context.get_data("chat_model_override")
    uses_named_preset = isinstance(raw_override, dict) and bool(
        raw_override.get("preset_name")
    )
    override = _resolve_override(agent)
    if override:
        base = (
            preset_to_config(resolve_preset(DEFAULT_PRESET_NAME) or {})
            if uses_named_preset
            else config
        )
        config = build_config_from_preset(
            override,
            base,
            strip_api_key=False,
        )
        if uses_named_preset:
            config[MODEL_PRESET_CONFIG_KEY] = get_effective_preset_name(agent)
        config["allow_chat_override"] = True
    return config


def get_chat_model_config(agent=None) -> dict:
    """Get chat model config, with per-chat override if active."""
    return get_effective_config(agent).get("chat_model", {})


def get_vision_model_config(agent=None) -> dict:
    """Get the active Vision Model config after applying Main-first routing."""
    cfg = get_effective_config(agent)
    vision_cfg = cfg.get("vision_model", {})
    if not all(
        str(vision_cfg.get(key) or "").strip() for key in ("provider", "name")
    ):
        return {}
    chat_cfg = cfg.get("chat_model", {})
    return (
        vision_cfg
        if not chat_cfg.get("vision") or vision_cfg.get("override_main")
        else {}
    )


def get_utility_model_config(agent=None) -> dict:
    """Get utility model config, with per-chat override if active."""
    return get_effective_config(agent).get("utility_model", {})


def get_embedding_model_config(agent=None) -> dict:
    """Get embedding model config from the effective preset."""
    cfg = get_effective_config(agent)
    model_cfg = deepcopy(cfg.get("embedding_model", {}))
    provider = str(model_cfg.get("provider") or "").strip().lower()
    name = str(model_cfg.get("name") or "").strip().strip('"').strip("'")

    if provider:
        model_cfg["provider"] = provider
    if name:
        model_cfg["name"] = name

    if name.startswith("huggingface/sentence-transformers/"):
        model_cfg["provider"] = "huggingface"
        model_cfg["name"] = name.removeprefix("huggingface/")
    elif name.startswith("sentence-transformers/") and provider in {"", "openai", "other"}:
        model_cfg["provider"] = "huggingface"
    elif provider == "huggingface" and name == "all-MiniLM-L6-v2":
        model_cfg["name"] = "sentence-transformers/all-MiniLM-L6-v2"

    return model_cfg


def is_chat_override_allowed(agent=None) -> bool:
    """The unified preset switcher is always enabled."""
    return True


def get_ctx_history(agent=None) -> float:
    """Get the chat model context history ratio."""
    cfg = get_chat_model_config(agent)
    return float(cfg.get("ctx_history", 0.7))


def get_ctx_input(agent=None) -> float:
    """Get the utility model context input ratio."""
    cfg = get_utility_model_config(agent)
    return float(cfg.get("ctx_input", 0.7))


def _normalize_kwargs(kwargs: dict) -> dict:
    """Convert string values that are valid numbers to numeric types."""
    result = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            try:
                result[key] = int(value)
            except ValueError:
                try:
                    result[key] = float(value)
                except ValueError:
                    result[key] = value
        else:
            result[key] = value
    return result


def build_model_config(cfg: dict, model_type: models.ModelType) -> models.ModelConfig:
    """Build a ModelConfig from a config dict section."""
    return models.ModelConfig(
        type=model_type,
        provider=cfg.get("provider", ""),
        name=cfg.get("name", ""),
        api_key=cfg.get("api_key", ""),
        api_base=cfg.get("api_base", ""),
        ctx_length=int(cfg.get("ctx_length", 0)),
        vision=bool(cfg.get("vision", False)),
        limit_requests=int(cfg.get("rl_requests", 0)),
        limit_input=int(cfg.get("rl_input", 0)),
        limit_output=int(cfg.get("rl_output", 0)),
        kwargs=_normalize_kwargs(cfg.get("kwargs", {})),
    )


def build_chat_model(agent=None):
    """Build and return a LiteLLMChatWrapper from config."""
    cfg = get_chat_model_config(agent)
    mc = build_model_config(cfg, models.ModelType.CHAT)
    return models.get_chat_model(
        mc.provider, mc.name, model_config=mc, **mc.build_kwargs()
    )


def build_utility_model(agent=None):
    """Build and return a LiteLLMChatWrapper for utility tasks."""
    cfg = get_utility_model_config(agent)
    mc = build_model_config(cfg, models.ModelType.CHAT)
    return models.get_chat_model(
        mc.provider, mc.name, model_config=mc, **mc.build_kwargs()
    )


def build_vision_model(agent=None):
    """Build the optional Vision Model selected by the effective preset."""
    cfg = get_vision_model_config(agent)
    mc = build_model_config(cfg, models.ModelType.CHAT)
    mc.vision = True
    kwargs = mc.build_kwargs()
    for key, default in (
        ("timeout", DEFAULT_VISION_TIMEOUT_SECONDS),
        ("max_tokens", DEFAULT_VISION_MAX_TOKENS),
    ):
        if key == "max_tokens" and "max_completion_tokens" in kwargs:
            # OpenAI rejects requests that set both max_tokens and
            # max_completion_tokens; preset kwargs already set the limit.
            continue
        value = cfg.get(key)
        if value not in (None, ""):
            kwargs[key] = _normalize_kwargs({key: value})[key]
        else:
            kwargs.setdefault(key, default)
    return models.get_chat_model(
        mc.provider, mc.name, model_config=mc, **kwargs
    )


def build_embedding_model(agent=None):
    """Build and return an embedding model wrapper."""
    cfg = get_embedding_model_config(agent)
    mc = build_model_config(cfg, models.ModelType.EMBEDDING)
    return models.get_embedding_model(
        mc.provider, mc.name, model_config=mc, **mc.build_kwargs()
    )


def get_embedding_model_config_object(agent=None) -> models.ModelConfig:
    """Get a ModelConfig object for embeddings (needed by memory plugin)."""
    cfg = get_embedding_model_config(agent)
    return build_model_config(cfg, models.ModelType.EMBEDDING)


def get_chat_providers():
    """Get list of chat providers for UI dropdowns."""
    return get_providers("chat")


def get_embedding_providers():
    """Get list of embedding providers for UI dropdowns."""
    return get_providers("embedding")


def has_provider_api_key(provider: str, configured_api_key: str = "", model_type: str = "chat") -> bool:
    if not provider_requires_api_key(provider, model_type):
        return True
    configured_value = (configured_api_key or "").strip()
    if configured_value and configured_value != "None":
        return True

    api_key = models.get_api_key(provider.lower())
    return bool(api_key and api_key.strip() and api_key != "None")


def get_missing_api_key_providers(agent=None) -> list[dict]:
    """Check which configured providers are missing API keys."""
    cfg = get_effective_config(agent)
    missing = []

    checks = [
        ("Chat Model", cfg.get("chat_model", {})),
        ("Utility Model", cfg.get("utility_model", {})),
        ("Embedding Model", get_embedding_model_config(agent)),
    ]
    vision_cfg = get_vision_model_config(agent)
    if vision_cfg:
        checks.insert(1, ("Vision Model", vision_cfg))

    for label, model_cfg in checks:
        provider = model_cfg.get("provider", "")
        if not provider:
            continue
        provider_lower = provider.lower()
        if provider_lower in LOCAL_PROVIDERS:
            continue
        if label == "Embedding Model" and provider_lower in LOCAL_EMBEDDING:
            continue

        if not has_provider_api_key(provider_lower, model_cfg.get("api_key", ""), _model_type_for_label(label)):
            missing.append({"model_type": label, "provider": provider})

    return missing


def is_chat_model_configured(config: dict | None = None) -> bool:
    cfg = config if isinstance(config, dict) else get_config()
    chat_cfg = cfg.get("chat_model", {}) if isinstance(cfg, dict) else {}
    provider = str(chat_cfg.get("provider") or "").strip()
    name = str(chat_cfg.get("name") or "").strip()
    if not provider or not name:
        return False
    return has_provider_api_key(provider.lower(), chat_cfg.get("api_key", ""), "chat")
