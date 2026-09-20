# skills.py DOX

## Purpose

- Own the `skills.py` helper module.
- This module discovers, parses, filters, and resolves Agent Zero skills.
- Keep this file-level DOX profile synchronized with `skills.py` because this directory is intentionally flat.

## Ownership

- `skills.py` owns the runtime implementation.
- `skills.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `ActiveSkillEntry` (`TypedDict`)
- `CatalogSkill` (`TypedDict`)
- `Skill` (no explicit base class)
- Top-level functions:
- `get_skills_base_dir() -> Path`
- `get_skill_roots(agent: Agent | None=...) -> List[str]`
- `_is_hidden_path(path: Path) -> bool`
- `discover_skill_md_files(root: Path) -> List[Path]`: Recursively discover SKILL.md files under a root directory.
- `_coerce_list(value: Any) -> List[str]`
- `_normalize_name(name: str) -> str`
- `_read_text(path: Path) -> str`
- `split_frontmatter(markdown: str) -> Tuple[Dict[str, Any], str, List[str]]`: Splits a SKILL.md into (frontmatter_dict, body_text, errors).
- `_parse_frontmatter_fallback(frontmatter_text: str) -> Dict[str, Any]`
- `parse_frontmatter(frontmatter_text: str) -> Tuple[Dict[str, Any], List[str]]`: Parse YAML frontmatter with PyYAML when available,
- `skill_from_markdown(skill_md_path: Path, include_content: bool=..., validate: bool=...) -> Optional[Skill]`
- `list_skills(agent: Agent | None=..., include_content: bool=..., include_hidden: bool=...) -> List[Skill]`: List skills, optionally filtered by agent scope.
- `delete_skill(skill_path: str) -> None`: Delete a skill directory.
- `find_skill(skill_name: str, agent: Agent | None=..., include_content: bool=..., include_hidden: bool=..., validate: bool=...) -> Optional[Skill]`
- `load_skill_for_agent(skill_name: str, agent: Agent | None=...) -> str`: Load skill and format it as a complete string for agent context.
- `skill_instruction_name(message: Any) -> str`
- `_get_skill_files(skill_dir: Path) -> str`: Get file tree for skill directory.
- `search_skills(query: str, limit: int=..., agent: Agent | None=..., include_hidden: bool=...) -> List[Skill]`
- `validate_skill(skill: Skill) -> List[str]`
- `validate_skill_md(skill_md_path: Path) -> List[str]`
- `_normalize_max_active_skills(value: Any) -> int`
- `get_max_active_skills(agent: Agent | None=..., project_name: str | None=...) -> int`
- `normalize_skills_config(config: dict[str, Any] | None) -> dict[str, Any]`
- `normalize_visibility_policy(raw: Any) -> dict[str, Any]`
- `get_visibility_policy(agent: Agent | None) -> dict[str, Any]`
- `is_skill_allowed(policy, skill_or_entry) -> bool`
- `ensure_skill_visible(agent, entry) -> None`
- `normalize_active_skills(raw: Any, limit: int | None=...) -> list[ActiveSkillEntry]`
- `normalize_hidden_skills(raw: Any) -> list[ActiveSkillEntry]`
- `normalize_skill_entries(raw: Any, limit: int | None=...) -> list[ActiveSkillEntry]`
- `list_skill_catalog(project_name: str=..., agent: Agent | None=...) -> list[CatalogSkill]`
- `get_scope_active_skills(agent: Agent | None) -> list[ActiveSkillEntry]`
- `get_scope_hidden_skills(agent: Agent | None) -> list[ActiveSkillEntry]`
- `get_chat_active_skills(context: Any | None) -> list[ActiveSkillEntry]`
- `get_chat_disabled_skills(context: Any | None) -> list[ActiveSkillEntry]`
- `get_loaded_skill_names(agent: Agent | None) -> list[str]`
- `set_loaded_skill_names(agent: Agent | None, skill_names: Any) -> list[str]`
- `add_loaded_skill_name(agent: Agent | None, skill_name: str, limit: int | None=...) -> list[str]`
- Notable constants/configuration names: `MAX_ACTIVE_SKILLS`, `ACTIVE_SKILLS_PLUGIN_NAME`, `AGENT_DATA_NAME_LOADED_SKILLS`, `CONTEXT_DATA_NAME_LOADED_SKILLS`, `CONTEXT_DATA_NAME_CHAT_ACTIVE_SKILLS`, `CONTEXT_DATA_NAME_CHAT_DISABLED_SKILLS`, `CONTEXT_DATA_NAME_CHAT_VISIBLE_SKILLS`, `_NAME_RE`.

## Runtime Contracts

- `get_skill_roots` is extensible. Plugin end hooks may filter agent-scoped roots from current runtime state; do not mutate cached path lists. Global discovery without an agent resolves the bundled `skills` root, user, project, agent-profile, and plugin roots; the bundled skill collection additionally remains reachable through the always-enabled `_bundled_skills` plugin root `plugins/_bundled_skills/skills`. Listing, search, lookup, and skill reattachment use this resolver.

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Loaded skill names are chat-wide context data under `CONTEXT_DATA_NAME_LOADED_SKILLS`; legacy agent-local `loaded_skills` lists are migrated into context data and cleared when read.
- Loaded skill bodies live in chat history; hiding a skill changes catalog visibility but does not remove the loaded-skill ledger.
- `_skills.visibility_policy` is profile-aware and uses explicit future-skill
  allow/block defaults. It filters discovery, search, new loading, chat
  activation, and active-skill resolution without removing instructions already
  stored in chat history.
- Visibility policy IDs match both canonical skill paths and their directory
  names, and bulk discovery resolves the effective policy only once.
- Legacy `hidden_skills` remains default-allow with blocked exceptions; a chat
  visibility override cannot bypass profile visibility policy.
- `build_active_skills_prompt()` returns empty because selected skills are loaded through history, not prompt protocol.
- `search_skills()` normalizes query words, scores normal terms against skill names, and scores only long terms against tags/triggers; descriptions match only full query phrases so generic prose does not produce irrelevant suggestions.
- `find_skill(validate=False)` lets validation tooling resolve a skill with incomplete metadata while preserving runtime validation by default.
- Slash command discovery is delegated to the built-in `_commands` helper through a local import, preserving its project/global/bundled/plugin precedence and avoiding its `split_frontmatter` import cycle. Picker-hidden commands remain hidden from Skills; reading a command returns its definition without executing it.
- Invalid `SKILL.md` frontmatter emits a once-per-path scan warning with the skipped skill path/name and a line number when the parser can identify one directly.
- Observed side-effect areas: filesystem reads, filesystem deletion, plugin state, settings/state persistence, context data, secret handling.
- Imported dependency areas include: `__future__`, `dataclasses`, `helpers`, `os`, `pathlib`, `re`, `typing`.

## Key Concepts

- Important called helpers/classes observed in the source: `dataclass`, `re.compile`, `field`, `Path`, `root.rglob`, `results.sort`, `re.sub`, `path.read_text`, `text.splitlines`, `join.strip`, `parse_frontmatter`, `frontmatter_text.splitlines`, `_parse_frontmatter_fallback`, `split_frontmatter`, `str.strip`, `_coerce_list`, `Skill`, `get_skill_roots`, `_filter_hidden_skills`, `files.get_abs_path`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_a0_connector_prompt_gating.py`
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_document_query_plugin.py`
  - `tests/test_fasta2a_client.py`
  - `tests/test_office_canvas_setup.py`
  - `tests/test_office_document_store.py`
  - `tests/test_skills_runtime.py`
  - `tests/test_time_travel.py`

## Child DOX Index

No child DOX files.
