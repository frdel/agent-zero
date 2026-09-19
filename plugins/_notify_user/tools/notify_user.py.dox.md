# notify_user.py DOX

## Purpose

- Own the `notify_user.py` agent tool.
- This module sends a user-facing notification from the agent.
- Keep this file-level DOX profile synchronized with `notify_user.py` because this directory is intentionally flat.

## Ownership

- `notify_user.py` owns the runtime implementation.
- `notify_user.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `NotifyUserTool` (`Tool`)
  - `async execute(self, **kwargs)`

## Runtime Contracts

- Tool modules must define `helpers.tool.Tool` subclasses and return `helpers.tool.Response` from `execute(...)`.
- Update this file whenever tool arguments, output shape, `break_loop` behavior, intervention handling, prompt instructions, or side effects change.
- `NotifyUserTool` is a `Tool`.
- `NotifyUserTool` defines `execute(...)`.
- Imported dependency areas include: `agent`, `helpers.notification`, `helpers.tool`.

## Key Concepts

- Important called helpers/classes observed in the source: `AgentContext.get_notification_manager.add_notification`, `Response`, `NotificationType`, `NotificationPriority`, `AgentContext.get_notification_manager`, `self.agent.read_prompt`.
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
