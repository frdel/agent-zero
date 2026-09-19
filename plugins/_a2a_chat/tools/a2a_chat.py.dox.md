# a2a_chat.py DOX

## Purpose

- Own the `a2a_chat.py` agent tool.
- This module lets the agent message an external A2A agent and extract the assistant reply.
- Keep this file-level DOX profile synchronized with `a2a_chat.py` because this directory is intentionally flat.

## Ownership

- `a2a_chat.py` owns the runtime implementation.
- `a2a_chat.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `A2AChatTool` (`Tool`)
  - `async execute(self, **kwargs)`
- Top-level functions:
- `_session_key(agent_url: str) -> str`: Keep root and explicit /a2a URLs in the same conversation cache.
- `_text_from_part(part: Any) -> str`
- `_text_from_message(message: Any) -> str`
- `_extract_latest_assistant_text(task_response: Any) -> str`
- Notable constants/configuration names: `A2A_EMPTY_RESPONSE_ERROR`.

## Runtime Contracts

- Tool modules must define `helpers.tool.Tool` subclasses and return `helpers.tool.Response` from `execute(...)`.
- Update this file whenever tool arguments, output shape, `break_loop` behavior, intervention handling, prompt instructions, or side effects change.
- `A2AChatTool` is a `Tool`.
- `A2AChatTool` defines `execute(...)`.
- Observed side-effect areas: filesystem writes, scheduler state.
- Imported dependency areas include: `helpers.fasta2a_client`, `helpers.print_style`, `helpers.tool`, `typing`.

## Key Concepts

- Important called helpers/classes observed in the source: `agent_url.rstrip`, `normalized.endswith`, `_text_from_message`, `normalized.rstrip`, `message.strip`, `join`, `_session_key`, `value.strip`, `_text_from_part`, `is_client_available`, `Response`, `self.agent.get_data`, `sessions.pop`, `_extract_latest_assistant_text`, `PrintStyle.error`, `connect_to_agent`, `conn.send_message`, `conn.wait_for_completion`, `self.agent.set_data`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with prompt tool instructions and skill guidance.
- Respect intervention flow for long-running, external, or user-visible operations.

## Verification

- Run targeted tool and prompt-contract tests for changed behavior; smoke-test agent execution when no focused test exists.
- Related tests observed by source search:
  - `tests/test_tool_action_contracts.py`

## Child DOX Index

No child DOX files.
