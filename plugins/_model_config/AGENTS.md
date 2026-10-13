# Model Configuration Plugin DOX

## Purpose

- Own global LLM preset definitions, scoped preset selection, API-key checks, chat overrides, migration, and model settings UI.

## Ownership

- `helpers/model_config.py` owns config resolution, presets, overrides, and runtime model object construction.
- `api/` owns model config, override, preset, search, and API-key endpoints.
- `webui/` owns model settings, summaries, switcher, and API-key UI.
- `extensions/python/startup_migration/` owns conversion from legacy full configs and project presets, followed by first-launch preset initialization.
- `default_config.yaml`, `mode_presets_fallback.yaml`, `provider_metadata.yaml`, `hooks.py`, and `plugin.yaml` own plugin defaults, offline presets, metadata, hooks, and manifest.

## Local Contracts

- API-key reveal returns the complete stored key list without advancing rotation, so editing a provider preserves every configured key.
- `Default` is the first global preset and cannot be deleted or renamed. It owns the complete main, utility, and embedding baseline; its Vision Model slot is optional.
- Preset definitions are global. Global, project, agent-profile, and project/profile plugin configs persist only `model_preset`; chats may persist a preset reference as their explicit override.
- Preserve scoped plugin resolution order and fall back invalid or missing scope/chat references to `Default`.
- `get_presets()` caches the parsed global collection in `model_presets(plugins)`, keyed by the stat signature of the user, fallback, and legacy config files, and returns deep copies. Missing files allow caching; read or parse failures return uncached fallback results so recovery needs no file edit. `save_presets` and `reset_presets` clear it; other writers must change those files or clear the area.
- Project Settings `llm` payloads are owned here through the generic `helpers.projects` project extension-data hooks; keep project helper code agnostic to `_model_config` paths, presets, and inheritance rules.
- Keep provider metadata and API-key checks safe around secrets.
- Check API-key readiness only for the effective model configuration; unused global presets must not produce Welcome-screen warnings.
- Coordinate OAuth-backed providers with `_oauth` instead of hardcoding provider-specific auth here.
- Model discovery never substitutes the generic LiteLLM registry for an OAuth account catalog (`api_key_mode: oauth`). Preserve source/error details; label API-key-provider registry suggestions as unverified and report failed discovery through standard notifications without exposing raw endpoint URLs.
- `model_config_get` exposes `model_configured` as a derived chat-model readiness flag from provider, model name, and API-key availability.
- Non-default presets may inherit omitted main, utility, or embedding slots and durable tuning from `Default`, but must replace or clear per-slot `kwargs` so provider-specific extra params never leak across model providers.
- The optional `vision` slot is strictly per preset and never inherited from `Default`; an empty slot disables the separate Vision Model for that preset.
- Main native vision wins by default. A configured Vision Model handles `vision_load` when Main lacks vision, or when that preset explicitly enables `override_main`.
- Keep the optional Vision provider/model selector inside the Main Model card and flush with Main's field alignment, without a nested left inset. Show it only while Main vision is disabled or `override_main` is enabled; do not render a standalone Vision Model card.
- Keep Vision timeout and maximum-output-token controls, plus the Agent Editor prompt-customization note, inside the visible Vision sidecar's Advanced Settings only. The Vision call limits belong to the preset/model builder, not to `vision_load` call-site constants.
- Show `Use separate Vision Model` immediately below `Supports Vision` while Main vision is enabled, not inside Advanced Settings; describe the disabled state as using Main's native vision.
- In model overviews, render the effective Vision Model as a text-only `Vision override / Provider / Model` child aligned with Main's provider column, not as an icon-bearing peer row.
- Changing a model provider in the settings UI must clear `api_base` and `kwargs` because both may be provider-specific.
- Repair provider-specific model-config aliases at the model-config read/build boundary; keep provider-specific repairs out of provider-agnostic core wrappers such as `models.py`.
- The `Agent.read_prompt/end` Anthropic hook adapts only the two bundled thoughts instructions in main/communication/solving prompt results when the effective main provider or model name contains `anthropic`, or the model name contains `claude` (case-insensitive, regardless of provider). Keep prompt files, JSON fields, history, custom wording, and other models unchanged; standalone communication reads must match main-prompt rendering for native protocol projection. Verify with `tests/test_anthropic_thoughts_prompt.py`.
- `modelConfig.createPresetEditor()` owns local preset drafts, row actions, and stable UI-only row keys so deletion or renaming cannot rebind nested model fields.
- Presets may change outside the editor, so the `open_modal_before` hook reloads them before every preset-editor open, including `/presets`, and resolves the chat's active preset unless `openPresetEditor()` pinned one.
- The preset editor maps each model provider's API-key field to the shared API-key store; saving the editor persists dirty keys separately and never writes secrets into preset YAML.
- The compact chat selector label combines the effective preset with only the leaf name of its main model; utility and provider text stay out of the closed selector.
- The compact selector strip exposes `model-context-strip-end` after the agent
  profile selector so adjacent bundled controls can stay plugin-owned.
- The selector strip uses the shared `x-overflow` directive for built-in and plugin controls. Its root must remain shrinkable; overflow entries open the original selector panels and retain their Alpine state. The profile avatar uses `data-overflow-icon` so its color, initials, or image also appear in overflow.
- The adjacent agent-profile selector reads the always-enabled Agent Editor list
  endpoint directly so the active profile shows its effective title and avatar,
  and omits profiles disabled in the chat's current scope plus the exact
  `default` utility profile. A chat already using `default` may still show that
  current status without adding a selectable or editable row.
- Reload the agent-profile selector catalog when a chat changes project or
  active profile so project-only profiles never linger in the visible choices.
- Concurrent agent-profile catalog loads for the same chat share one request;
  across chats, only the newest request may replace selector state or finish
  its loading lifecycle.
- Snapshot-triggered profile and preset refreshes run independently of chat
  rendering and of each other. Only the latest refresh for the selected chat
  may apply selector state; older completions must not clear a newer loading flag.
- Ignore refreshes for unselected chats before advancing the request sequence.
  Pending preset/profile saves keep their original chat target; preset save or
  clear results may update the selector only while that chat is selected.
- Preset editor reset actions must remove the user override through the preset API and refresh the open draft from bundled defaults.
- Preset rename, delete, and reset actions must repair scoped config and durable/live chat references; removed definitions fall back to `Default`.
- Save/reset embedding comparisons use the matching before/after preset snapshots, including Default inheritance. Do not reload the collection per preset or persist a cross-request cache for this comparison.
- Migration must preserve existing definitions and distinct scoped model choices, back up replaced user files once, strip inline secrets, and remain idempotent.
- Venice migration applies chat-only kwargs to chat slots and removes them from embedding slots without discarding embedding-specific kwargs.
- On every startup after migration, short-circuit when `usr/plugins/_model_config/presets.yaml` exists. Only a missing collection may fetch `agent0ai/a0-presets`; parse remote and plugin-local fallback YAML through the same validator, strip secrets before persistence, and persist `mode_presets_fallback.yaml` when download or validation fails.
- Model-name catalogs open below the input from either a field click or the embedded magnifier. Discard asynchronous results if their provider, API base, model draft, or query changed while the request was pending.
- Keep the model-search magnifier and loading spinner in the same grid cell by targeting the button's `x-icon` children.
- Additional parameter drafts retain plain-string compatibility but reject malformed JSON-shaped values and invalid KEY=VALUE lines with a standard notification. Reparse every preset slot before saving presets or API keys; invalid drafts stay editable and never silently save stale kwargs. Save errors identify the preset and model slot even when that draft is no longer selected.

## Work Guidance

- Keep backend model config shape and frontend settings fields synchronized.

## Verification

- Run model-config and onboarding-related tests when model provider, preset, or API-key behavior changes.

## Child DOX Index

No child DOX files.
