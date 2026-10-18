# call_subordinate.py DOX

## Purpose

- Own the `call_subordinate.py` agent tool.
- This module delegates work to a subordinate Agent Zero profile and returns its result.
- Keep this file-level DOX profile synchronized with `call_subordinate.py` because this directory is intentionally flat.

## Ownership

- `call_subordinate.py` owns the runtime implementation.
- `call_subordinate.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `Delegation` (`Tool`)
  - `async execute(self, message=..., reset=..., context_id=..., **kwargs)`
  - `get_log_object(self)`
- Top-level functions:
- `_subordinate_profile_labels(agent: Agent) -> dict[str, str]`
- `_validate_subordinate_profile(agent: Agent, profile: str) -> str`
- `get_or_create_subordinate(...) -> Agent`
- `run_subordinate(...) -> str`

## Runtime Contracts

- Tool modules must define `helpers.tool.Tool` subclasses and return `helpers.tool.Response` from `execute(...)`.
- Update this file whenever tool arguments, output shape, `break_loop` behavior, intervention handling, prompt instructions, or side effects change.
- `Delegation` is a `Tool`.
- `Delegation` defines `execute(...)`.
- Observed side-effect areas: filesystem writes, settings/state persistence.
- `profile`/`agent_profile` values are validated against available profile keys before use; unknown profiles raise `RepairableException` so the agent can retry with a real profile.
- Direct and parallel calls use the same creation, continuation, message, history, and persistence functions in this module.
- Direct delegation runs that helper through the separate child's `AgentContext.run_task`, so running status, intervention, Stop, and completion notifications use the normal context lifecycle. Cancelling the caller cancels its direct child; stopping only the child raises a recoverable error to the caller. Parallel jobs retain their own task ownership, and legacy same-context children remain inline.
- A non-empty `name` updates both the child context name and sidebar label on creation or continuation. Omission preserves an existing name; legacy same-context children must not rename the parent chat.
- Every fresh child is `Agent(parent.number + 1, ...)` in its own persisted child-chat context, so sibling A1 agents can each create their own A2 descendants without sharing streaming state.
- `reset=true` creates a fresh child. `reset=false` continues the caller's default child or the exact child named by `context_id`.
- Child context IDs are accepted only when their persisted parent context, parent agent number, and child depth match the caller.
- Supplying a different profile for an existing child without creating a fresh child raises `RepairableException` instead of silently changing its profile.
- Active children cannot be continued concurrently; wait for completion or stop them first.
- Child contexts inherit the caller's project. After project activation, copy the caller's chat-model override only when the child's resolved scoped preset is `Default` (including missing/invalid selections); non-default scoped presets keep their configured models. Continuing an existing child preserves its chat override.
- Child contexts are saved before execution and again on exit, and remain reusable after model/API failures.
- The direct tool result includes `context_id`; parallel job snapshots expose the same stable child ID separately from their per-invocation job ID.
- Legacy args `agent_id` for `context_id` and `agent_profile` for `profile` still resolve; prompts document only canonical names.
- Existing same-context linear subordinates remain reusable for saved-chat compatibility, but new children use child contexts and a private per-parent registry.
- Imported dependency areas include: `agent`, `extensions.python.hist_add_tool_result`, `helpers`, `helpers.errors`, `helpers.tool`.

## Key Concepts

- The `subagent` log headline is the static `icon://communication Calling Subordinate Agent` without an agent-name prefix.
- Important called helpers/classes observed in the source: `AgentContext.all`, `projects.get_context_project_name`, `projects.activate_project`, `subagents.get_available_agents_dict`, `RepairableException`, `initialize_agent`, `message_queue.log_user_message`, `persist_chat.save_tmp_chat`, `UserMessage`, `subordinate.monologue`, and `subordinate.history.new_topic`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with prompt tool instructions and skill guidance.
- Respect intervention flow for long-running, external, or user-visible operations.

## Verification

- Run targeted tool and prompt-contract tests for changed behavior; smoke-test agent execution when no focused test exists.
- `test_subordinate_preserves_scoped_model_preset` exercises real scoped config files and project activation with absent, default, custom, and invalid presets plus named/raw chat overrides; continued children retain their own override.
- Related tests observed by source search:
  - `tests/test_default_prompt_budget.py`
  - `tests/test_subagent_profiles.py`
  - `tests/test_parallel_tool.py`
  - `tests/test_subordinate_lifecycle.py` (direct and nested completion, failure, parent/child stop, intervention, and legacy shared-context execution)

## Child DOX Index

No child DOX files.
