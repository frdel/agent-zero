# parallel_tools.py DOX

## Purpose

- Own the shared runtime for parallel tool-call jobs.
- Normalize wrapped tool-call payloads, start background jobs, await or cancel jobs, and render prompt extras for active parallel work.
- Keep this file-level DOX profile synchronized with `parallel_tools.py` because this directory is intentionally flat.

## Ownership

- `parallel_tools.py` owns the runtime implementation.
- `parallel_tools.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Public concepts:
- `NormalizedToolCall`
- `ParallelJob`
- `start_parallel_jobs(...)`
- `await_parallel_jobs(...)`
- `cancel_parallel_jobs(...)`
- `build_parallel_jobs_extras(...)`
- `format_parallel_results(...)`

## Runtime Contracts

- Direct dispatch uses `helpers.tool_execution.execute_tool` for the shared lifecycle, retaining its existing extension dispatcher, child log object and string response contract. With local durability enabled, the explicit workflow adapter owns child admission and join records, while this module retains normalization, output formatting and execution behavior.

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Wrapped tool-call items must use the same shape as normal tool calls: a tool name plus arguments.
- Normalization accepts full agent-reply-shaped objects when `tool_name` and `tool_args` are present; non-contract planning fields such as `thoughts` or `headline` are ignored.
- `tool_calls` should be an array, but normalization also accepts a valid JSON string encoding of that array to recover provider/model stringification.
- Shared validation rejects `document_query`, `response`, `input`, `input_remote`, and `goal` inside direct `parallel` workers: document parsing stays sequential, `response` ends the parent loop, and goals belong to the calling context. Local and remote execution output/reset follow-ups also stay sequential. Validate the whole batch before registering jobs and recheck at direct dispatch. Retained subordinates keep their own state.
- `call_subordinate` jobs first enforce the actual calling agent's delegation policy, then call the same creation and execution functions as direct delegation in `tools/call_subordinate.py`; this helper does not construct or prompt a second kind of subordinate.
- Fresh parallel sibling calls create distinct `parent.number + 1` child agents. Their job snapshots expose stable `context_id` values that direct or parallel `reset=false` calls can continue after success or failure.
- Jobs retain their actual parent agent so parallel calls made by A1 create A2 rather than falling back to a context's A0.
- Subordinate child chats are tagged with job metadata, remain outside the scheduler task list, and may use normal child-chat tools including `parallel`.
- Nested parallel jobs started by a parallel subordinate are registered as child `DeferredTask` instances so stopping the ancestor also stops its descendants.
- Direct tool jobs run in isolated background contexts and are blocked from recursively invoking `parallel`.
- Direct tool jobs inherit the parent's active per-chat model override and current user message.
- Direct tool background context cleanup removes both the in-memory context and any transient chat folder left on disk.
- Parent-visible child log items are created for each wrapped call so the WebUI can inspect concurrent children separately while the wrapper result remains model-history-only.
- Child tool logs mirror normal tool-call visible args; job ids remain available through wrapper results and prompt extras rather than visible process-step args.
- Job completion fills child log content only when it is still empty; streamed or tool-written content is user-visible state and is never replaced by the job result or error string.
- Wrapped tool child logs use each tool's native `get_log_object()` output when available, preserving special log rendering (for example: `code_execution_tool` uses `code_exe`, `wait` uses `progress`, MCP tools use `mcp`, and regular tools use `tool`).
- Direct parallel worker execution reuses the parent-visible child log item so tool `before_execution()` cannot create a second generic worker log or lose the native badge type.
- Direct tools may explicitly queue model-visible history for their parent. Terminal collection records the outer `parallel` result first, promotes queued messages in job order, and only then removes disposable worker state; background jobs retain queued history until they are collected.
- Job IDs are stable handles for later await, collect, or cancel operations. Local code jobs keep their worker until the command completes; reject new-worker output/reset requests.
- `get_parallel_worker_job(...)` resolves only a registered direct worker. A stateful tool may publish its own model-facing progress to that job while retaining its original resource/event-loop owner; do not substitute arbitrary UI logs for model output.
- Prompt extras must stay bounded and expose only job IDs, tool names, status, and compact result/error summaries.

## Key Concepts

- The parent context stores in-flight jobs under a private data key; collected terminal jobs are removed from that registry.
- `wait=True` starts jobs and awaits them before returning until all requested jobs finish or the wait timeout is reached; the timeout stops waiting but does not cancel running jobs.
- `collect` returns already-finished job results without waiting; `await` waits for requested job IDs.
- Canceled jobs should be marked terminal and should stop their background `DeferredTask` when cancellation is possible. Direct-worker finally owns context cleanup on its event loop; collection/cancellation must not race it with a second context reset.
- Durable direct workers obtain a transient worker handle for stateful tool cleanup; this object is never serialized or used to infer durable completion.
- `queue_parallel_parent_history(...)` commits explicit queued history to the child journal in durable mode; prompt extras rebuild job handles from manifests. In legacy mode it accepts messages only from registered direct tool workers. `collect_parallel_jobs(...)` optionally promotes those messages while collecting terminal jobs; arbitrary worker history is never copied.

## Work Guidance

- Keep normalization compatible with provider tool-call envelopes and direct JSON objects.
- Avoid importing heavy runtime modules at import time unless startup behavior is verified.
- Coordinate argument, output, or status changes with `tools/parallel.py`, prompt instructions, and tests.

## Verification

- Run targeted tests for normalization, recursion guard, prompt extras, and tool result formatting.
- Run a live Agent Zero chat when changing parallel execution, child chat metadata, or subordinate task behavior.

## Child DOX Index

No child DOX files.
