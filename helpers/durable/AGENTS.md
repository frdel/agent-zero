# Local Durability DOX

## Purpose

- Own opt-in, private recovery storage and the services that resume supported local runs.

## Ownership

- `store.py` owns atomic admission, call outcomes, event sequences, checkpoints, controls, consistent backups, blob publication/reachability, terminal retention, typed document CAS/conflicts, operator review versions, retry aliases, restore epochs/selections, and process ownership.
- `codec.py` owns versioned, masked context/loop/result projections and implementation/configuration fingerprints. `runtime.py` owns opt-in admission, recovery dispatch and conservative holds. `replay.py` pins explicitly audited pure tool/hook implementations by source digest.
- `scheduler.py` owns built-in occurrence admission and idempotent task/plan projections. `workflows.py` owns ordered child manifests, joins, collection watermarks and graph protection/controls.
- `documents.py` owns typed declarations, pure migration/read semantics, masking and per-body drafts. `review.py` owns safe UI projections, versioned decisions and restore dependency review; `retry.py` owns complete plain-inference descriptors and narrow current retry eligibility.
- The store accepts bounded JSON values. Its callers own allowlisted recovery codecs and must never pass resolved credentials or arbitrary runtime objects.

## Local Contracts

- Importing this package is inert. Constructing `LocalStore(root)` acquires a process-lifetime OS lock; a second owner fails immediately and a live owner never expires.
- SQLite uses WAL, FULL synchronous writes and foreign keys. Events, run state and checkpoint changes commit together; outcomes commit before caller finalization.
- `admit` atomically records input and genesis. An identical `(context_id, input_id)` is idempotent; changed content conflicts. Only one nonterminal run per context is admitted.
- `transition`, `start_call` and `finish_call` fence writes against the current context generation. Cancel prevents new work but retains late outcomes; reset and delete fence all older writes. Delete tombstones the context and scrubs payload rows, then checkpoints WAL and vacuums freed pages. Caller-managed backups require their own retention and deletion.
- `finish_call(..., checkpoint=..., phase=...)` atomically commits an outcome with its history/continuation projection. Repeating the same completed outcome never reapplies its checkpoint or overwrites later projections. Cancelled runs accept only plain late body outcomes.
- Schema 4 migrates earlier inline ledgers. JSON at least 64 KiB offloads into private `blobs/<sha256>.json`; file fsync and atomic publication precede SQL references. Retained input/checkpoint/event/result/document/conflict digests and call fingerprints must be present and valid when read; missing integrity fields fail closed. Corruption and write failure raise explicit errors; never fall back to unjournaled effects.
- Owner-only directories/files, regular files and symlink rejection are required. Local mode is one framework process per local persistent data root; network filesystem locking semantics are unsupported.
- `backup(destination)` uses SQLite's consistent backup API and refuses overwrites. It contains private recovery data and must receive the same custody as the source.
- Backup publication is atomic, embeds referenced blob bytes in one portable SQLite file, and stamps a permanent review marker in the copy. Restores verify/hydrate bytes on demand. Each backup rotates its deployment epoch and invalidates copied selections and retry grants. Old runs require explicit per-run selection; uncertain runs require separate resolution. New admissions in the restored deployment are selected atomically; the marker is never cleared globally. `list_run_headers()` inventories metadata without decoding checkpoint payloads, isolating corrupt contexts from healthy candidates.
- Replay labels are metadata only. The runner must revalidate authorization, implementation identity and actual replay safety.
- `runtime.initialize()` is called once before legacy chat loading; `initialize_recovery()` dispatches after restoration. Settings changes require restart. Off mode still opens an existing ledger to prevent rollback from bypassing held work.
- Model outcomes and finalized tool projections commit atomically with their phase checkpoint. Raw tool-body results commit before intervention/postprocessing. Never replay a body merely because postprocessing was interrupted.
- Snapshots preserve only explicit JSON loop state and temporary log identities; arbitrary plugin objects require adapters. Unknown phases/hooks, custom scheduler callbacks, provider built-ins and new unaudited stateful targets after recovery are held.
- Accepted interventions are recorded before acknowledgement and remain deduplicated after stop. Unpause must respect disabled-backend and backup-review holds. Runner reservations must release even if cancellation interrupts the first storage read. If they interrupt an external call, retain the message and hold the uncertain run. Pause, stop, reset and deletion must pass through the coordinator.

- Retention preserves active/unresolved runs and protected workflow dependency graphs. Eligible terminal payloads expire by count/age; identity fingerprints remain for retries. Missing retained payloads never authorize new execution. Reachability GC removes only unreferenced blobs; delete also reclaims private SQL pages.
- `control_many` fences parent/descendant generations and stop decisions in one transaction. Discover descendants from verified manifests and latest ownership, including when a child checkpoint is corrupt. Unrelated later child ownership wins over historical links.
- Scheduler task files are checked atomic projections with private occurrence/run/completion tokens. Finish the owning plan slot once before outer run completion; resume `scheduler_finalizing` without repeating inference or raw callbacks. Removed, reassigned or disabled tasks cannot be resurrected.
- Child constructors/genesis commit before admission. Wrapper recovery requires exact audited core source plus committed effective args; unknown creation and body/finalization uncertainty hold. Keep parent history collection and its checkpoint atomic. Two execution slots are shared by roots/children; waiting/paused parents yield capacity. Nonblocking shielded child waits avoid one executor thread per nested ancestor and never cancel background work merely because a join times out. Retention closes over all ancestors so live grandchildren retain control ancestry. Evict terminal disposable workers without deleting journals.

- Documents use strict JSON up to 64 KiB, registered schemas and revision CAS. Reads and pure migrations never write. Per-tool drafts commit with the known body result; any CAS conflict applies none of the drafts and retains the body plus proposed conflicts. Reconciliation never replays the body. Distinct finalization intent precedes post hooks; only resolved document-conflict bodies with no finalization intent may finish postprocessing.
- Review actions compare an opaque version covering current generation, events, documents, controls and epoch. Operator confirmations record evidence and stop, without inventing outcomes. Stable request IDs deduplicate accepted decisions; retention keeps payload-free receipt identity and note digests while deleting expired private notes.
- Explicit retries create at most two alias attempts beyond the original call. Only complete version-2 plain inference descriptors or exact audited pure tools qualify under current policy. One-use grants are consumed atomically with alias intent; lost outcomes require fresh review, and known results never replay. Restore selection requires active dependency closure and never authorizes uncertain effects by itself.

- Restored provenance survives an `admitted` phase and admission from a saved child manifest. Recovery may start only source-audited portable targets; a newly admitted restored child cannot bypass that gate. Implicit monologue wrappers and unresolved model-completion function hooks require adapters before continuation.
- Timed-out read-only child joins commit explicit waiting outcomes and never count as successful joins/collections. Later waits use distinct identities; settled timeouts do not retain old parent payloads indefinitely.
- Scheduler attention continuations require a later journaled operator approval for the same run/occurrence. Reopening retains an already-completed plan slot and never advances it twice.
- Scheduler cancellation must never terminate the shared AgentContext event loop. Occurrence callbacks compare the actual future and input identity, not only the reused DeferredTask handle. Cancellation projections must also finish when called from an async API.
- Recovery inventory is active-first and paged, with explicit loading and refresh of all loaded pages. Lost decision acknowledgments retry only the exact approved request/version/ID; new stale decisions still fail. Restore selection is bounded to 1000 explicitly reviewed runs.

## Work Guidance

- Keep storage transactions short; never hold one while awaiting a provider or tool.
- Keep cancellation distinct from failure. Do not infer external completion from an unresolved intent.
- Schema upgrades must explicitly migrate supported versions; unknown schemas fail closed without replacement.

## Verification

- Run `pytest tests/test_durable_store.py tests/test_durable_integrity.py tests/test_durable_blobs.py tests/test_durable_documents.py tests/test_durable_review_store.py tests/test_durable_review.py tests/test_durable_response_deletion.py tests/test_durable_function_hooks.py tests/test_durable_retry.py tests/test_durable_runtime.py tests/test_durable_scheduler.py tests/test_durable_workflows.py tests/test_durable_process_recovery.py tests/test_durable_workflow_process.py -q` with the framework Python runtime. Tests use temporary storage and real subprocess termination; no live user state or provider is required.

## Child DOX Index

No child DOX files.
