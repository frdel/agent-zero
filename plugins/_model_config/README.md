# Model Configuration

Manage the reusable model presets used for Agent Zero's main, utility, and embedding models.

## Model Presets

- `Default` is always present, appears first, and cannot be renamed or deleted.
- Every runtime configuration resolves from a preset. There is no separate durable model configuration layer.
- Preset definitions are global and live in `usr/plugins/_model_config/presets.yaml`. Plugin defaults in `mode_presets_fallback.yaml` are used only when a saved collection cannot be initialized.
- Non-default presets may omit advanced fields or model slots; omitted values resolve from `Default`, while provider-specific `kwargs` are replaced or cleared instead of leaking between providers.
- API keys remain in the approved environment/settings flow and are never written into preset YAML.
- Models whose provider or name contains `anthropic`, or whose name contains `claude`, receive public-action-summary wording for the bundled `thoughts` instructions. Matching is case-insensitive and applies regardless of provider, including third-party and OpenAI-compatible routes. Shared prompt files and the `thoughts` JSON field stay unchanged.

## Scoped Selection

Global, project, project/profile, and agent-profile scopes store only a preset name in their standard plugin `config.json`:

```json
{"model_preset": "Balance"}
```

For example, a project selection is stored at:

```text
/a0/usr/projects/<project>/.a0proj/plugins/_model_config/config.json
```

The normal plugin resolution order selects the most specific available reference. A missing or deleted reference safely resolves to `Default`. Chats may store an explicit preset reference in `chat_model_override`; clearing it returns the chat to its scoped selection.

## User Interfaces

- Agent Settings shows the global selection, its three resolved models, and actions for preset editing, API keys, and per-project/agent settings.
- The full plugin settings modal uses the generic scope selector and stores only the chosen preset at that scope.
- The closed chat switcher shows the effective preset plus the main model's short name; its menu supports a chat-only selection or returning to the scoped preset. Preset and profile menus shrink to fit short windows so the full scroll track stays reachable.
- The adjacent profile switcher shows the active agent's effective title and avatar and links to Create, Edit, and Manage agents.
- The preset editor exposes the shared API key for each selected provider and saves key changes separately from secret-free preset definitions.
- Project Settings selects from the same global preset definitions.

## Cache Routing

Venice and Agent Zero API send a stable `prompt_cache_key` derived from the model, leading instructions, and tool definitions. This is a routing hint; cache availability and retention remain provider-controlled. Venice documents it in its [Chat Completions API](https://docs.venice.ai/api-reference/endpoint/chat/completions).

In a chat model's **Advanced Settings → Additional parameters**, set `a0_prompt_cache_mode=prompt_cache_key` or `a0_prompt_cache_mode=cache_control` to match a custom provider's supported format. `auto` keeps the existing provider detection; `off` disables automatic hints. Explicit keys, including `extra_body` keys, remain unchanged. Marker mode keeps marked requests on Chat Completions and uses the existing stable message/tool boundaries.

## Initial Presets And Migration

The startup migration converts the prior global full model configuration into `Default`, preserves existing global presets, promotes distinct scoped full configurations and legacy project presets into uniquely named global presets, and rewrites scoped config files to selection-only JSON. Original files receive a `.pre-unified-presets.bak` backup before replacement; the migration is idempotent.

At every startup, legacy migration runs first. If `usr/plugins/_model_config/presets.yaml` then exists, initialization returns immediately without network access. Otherwise the plugin makes one bounded request for [`agent0ai/a0-presets/model_presets.yaml`](https://github.com/agent0ai/a0-presets/blob/main/model_presets.yaml), validates the whole collection, removes secret fields, and saves it locally. A download, parse, or validation failure processes and saves plugin-local `mode_presets_fallback.yaml` through the same validation path, so initialization remains usable offline.

## Key Files

- `helpers/model_config.py` owns preset validation, resolution, compatibility config shapes, and runtime model construction.
- `api/model_presets.py` owns global preset editing, scoped selection, and reference repair after rename/delete/reset.
- `extensions/python/startup_migration/_10_migrate_model_config.py` owns legacy conversion.
- `extensions/python/startup_migration/_20_bootstrap_model_presets.py` owns missing-collection initialization and plugin-local fallback.
- `webui/preset-overview.html` is the shared Settings/plugin-settings summary widget.
- `webui/main.html` is the preset editor.

## Plugin Metadata

- Name: `_model_config`
- Settings section: `agent`
- Per-project config: `true`
- Per-agent config: `true`
- Always enabled: `true`
