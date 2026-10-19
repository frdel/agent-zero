# skills_tool.py DOX

## Purpose

- Own the `skills_tool.py` agent tool.
- This module searches, loads, and lists Agent Zero skills and exposes effective slash-command definitions for the agent.
- Keep this file-level DOX profile synchronized with `skills_tool.py` because this directory is intentionally flat.

## Ownership

- `skills_tool.py` owns the runtime implementation.
- `skills_tool.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `SkillsTool` (`Tool`)
  - `get_log_object(self)`
  - `get_heading(self)`
  - `async before_execution(self, **kwargs)`
  - `async execute(self, **kwargs) -> Response`
  - `_visible_skill_loaded(self, skill_name: str) -> bool`
- Top-level functions:
- `max_loaded_skills() -> int`
- Notable constants/configuration names: `DATA_NAME_LOADED_SKILLS`.

## Runtime Contracts

- Tool modules must define `helpers.tool.Tool` subclasses and return `helpers.tool.Response` from `execute(...)`.
- Update this file whenever tool arguments, output shape, `break_loop` behavior, intervention handling, prompt instructions, or side effects change.
- `SkillsTool` is a `Tool`.
- `SkillsTool` defines `execute(...)`.
- Loading a skill appends the full skill body as a normal tool-result history message with `skill_instructions` metadata containing name, path, source, and content visibility.
- Loaded skill IDs are stored in chat-wide context data.
- Duplicate loads omit the full body when the same skill name remains visible in model history.
- Missing or empty `action` defaults to `list`, and legacy `method` is accepted as a deprecated alias when `action` is absent.
- All actions log as the dedicated `skills_tool` type with an `icon://school` verb headline naming the skill, the query, or the skill file being read; `extensions/webui/get_message_handler/` owns the `SKL` badge presentation and `extensions/webui/get_process_step_types/` registers the type.
- Observed side-effect areas: filesystem reads, filesystem deletion, settings/state persistence, chat history persistence.
- Imported dependency areas include: `__future__`, `helpers`, `helpers.print_style`, `helpers.strings`, `helpers.tool`, `pathlib`, `typing`, `uuid`.

## Key Concepts

- Important called helpers/classes observed in the source: `str.strip.lower.replace`, `skill_name.strip`, `self.get_heading`, `self._normalize_skill_name`, `self.get_log_object`, `skills_helper.list_skills`, `join`, `skills_helper.search_skills`, `skills_helper.find_skill`, `skills_helper.load_skill_for_agent`, `skills_helper.add_loaded_skill_name`, `skills_helper.skill_instruction_name`, `skill.path.resolve`, `Path`, `resolved.read_text`, `skill_name.startswith`, `skill_name.endswith`, `self._current_action`, `self.agent.context.log.log`, `Response`, `strip`, `target.is_absolute`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with prompt tool instructions and skill guidance.
- Respect intervention flow for long-running, external, or user-visible operations.

## Verification

- Run targeted tool and prompt-contract tests for changed behavior; smoke-test agent execution when no focused test exists.
- Related tests observed by source search:
  - `tests/test_document_query_plugin.py`
  - `tests/test_tool_action_contracts.py`

## Child DOX Index

No child DOX files.
