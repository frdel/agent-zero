# Shared Tool Execution DOX

## Purpose

- Own the common invocation lifecycle used by native Responses, JSON tools and direct parallel dispatch.

## Ownership

- `execute_tool(tool, tool_args, *, agent, tool_name, extension_call, responses_item_factory)` preserves caller resolution, argument normalization and return semantics.
- Tool/extension implementations retain their existing ownership.

## Contracts

- Preserve intervention checks, before/after methods and extension order. Restore `loop_data.current_tool` in `finally`.
- Caller-supplied agent/name/extension dispatch preserve adapters that do not expose every `Tool` attribute.
- When a durable turn is active, commit intent before lifecycle effects, effective masked arguments before execute, and body result before the next intervention check. Finalization and its history checkpoint commit together.
- A recorded finalized call returns its stored response without reexecuting hooks or appending history. Unknown finalization holds; it never repeats the body.
- Commit a distinct finalization intent before postprocessing/intervention. A body held solely by document CAS conflicts may continue postprocessing after every conflict is explicitly resolved, provided finalization has not started. Its body and prehooks never repeat.
- Effective-argument results atomically retain the pre-body log/checkpoint. Exact audited workflow wrappers resume from committed args and their recorded log identity without replaying tool prehooks; current audited policy/secret preparation still runs. Active call ownership spans join/collection finalization. Child waits yield execution slots and reacquire before post-body effects.
- Native output factories run before tool `after_execution`, preserving provider call identities. Parallel callers retain their string-return behavior and log-object override.

## Verification

- Run durable runtime/process-recovery, Responses architecture and parallel-tool suites in the framework runtime.
