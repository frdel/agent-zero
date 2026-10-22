# Durable execution and recovery

Durability is opt-in; the default is `off`. The `local` backend uses SQLite and
supports one framework process per local persistent data root. The `postgres`
backend coordinates workers across processes and hosts through one PostgreSQL
database, including recovery payloads and scheduler state. See
[PostgreSQL workers](durability-postgres.md) for configuration, ownership,
remote controls, backup, and portability requirements.

The local backend requires working OS locks and fsync. Sharing a SQLite data root
over a network filesystem does not provide distributed execution.

## Enable and inspect

Set the existing default-setting variable before startup:

```sh
export A0_SET_DURABILITY_BACKEND=local
python run_ui.py
```

Existing saved `durability_backend` settings take precedence over defaults. Change
the saved setting to `local` if one already exists, and restart the framework.
Discover the UI address from startup output or your container's port mappings.
Persist the `usr/` volume across container replacement. This feature is not enabled
on an existing running instance by changing source files alone.

The private ledger is `usr/durability/state.sqlite3`; SQLite's WAL/SHM and an
OS-owned `owner.lock` live beside it. A second owner is refused. Lock files are not
expiring leases: do not delete a lock to evict a live process. Stop that process.
Storage failures hold execution and leave the UI available for inspection.

Context state includes a `durability` status with the run ID. Held runs also show
a warning through the existing log/state-sync path. “Needs attention” means the
action was not automatically retried. Open **More → Recovery & documents** to inspect the affected action and review a decision. **Confirm completed** and **Confirm not completed** record operator evidence and stop the run; they never fabricate a tool result or continue an uncertain lifecycle. **Stop** also stops currently owned descendants. A separately authorized attempt is available only for supported adapters and can repeat provider charges; verify the outcome first. **Reset** fences the old generation.

## Current coverage

| Boundary | Durable behavior |
| --- | --- |
| New direct chat input | Input identity, genesis checkpoint and runnable run commit atomically before task dispatch. Repeated message IDs reuse the recorded run; changed content conflicts. |
| Model response | Normalized result and phase checkpoint commit together before completion hooks. Recorded results are reused without a replacement provider call. Unresolved requests hold. Framework retries are disabled for these calls. |
| Tool calls | Native, JSON and direct-parallel dispatch share a lifecycle. Intent precedes hooks; effective arguments are masked; body result precedes intervention/postprocessing. Final result and history projection commit together. |
| Completed native batch members | Retain native IDs and apply the saved projection once; resume at unfinished work. |
| Interrupted `never` body or postprocessing | Hold. A committed body is never reexecuted just to finish hooks/history. |
| Interrupted pure response tool | Retry only when recorded/current policy, source identity and audited lifecycle match. Other safe declarations require an adapter/audit. |
| Controls | Stop/cancel and reset fence the parent and currently owned descendants in one transaction. Delete also removes owned child snapshots. Interventions are durably accepted; interruption of an external call holds for resolution. |
| Scheduler | Built-in ad hoc, cron and planned occurrences share durable admission. Occurrence/run tokens reconcile atomic local JSON/YAML or shared PostgreSQL task projections and advance exactly the owning plan item once. Custom callbacks require an adapter. |
| Subordinates and parallel children | Ordered manifests retain child genesis, identities and joins. Completed children are reused; unresolved effects hold. Background job handles and collected-history watermarks survive parent turns. Disposable direct-worker objects are evicted after completion while their outcomes remain in the ledger. |
| Payload storage | Canonical JSON at least 64 KiB uses verified digest-addressed storage: private files in local mode, transactional database bytes in PostgreSQL mode. Reads verify size and digest. |
| Documents | The typed `todo` plan has schema 1, a 64 KiB limit and revision CAS. Tool drafts commit atomically with body results; concurrent app edits preserve the known body and create a separate conflict. |
| Recovery decisions | Opaque review versions reject stale actions. Stable request IDs make lost-response retries idempotent. Explicit new attempts have a three-attempt total budget per logical call. |
| UI | Recovery & documents provides recovery review, per-run restore selection and a typed plan editor through authenticated, CSRF-protected APIs. Existing `/webui` runtime-epoch resync and `Log` projection remain in use; recovery resets log generation. Stream previews are provisional. |

Provider-hosted built-ins and arbitrary integration/session recovery require explicit adapters. A recovered turn holds before starting a new unaudited stateful target: old shell,
browser, SSH and connector session objects are not portable checkpoints.

Arbitrary plugin checkpoint state and side effects in interrupted hooks require
adapters. Recovery checks configuration and source fingerprints. An interrupted
preparation, model-processing or finalization phase may therefore hold even when
some output was saved. A result can be known while its surrounding lifecycle is
uncertain. This preserves outcomes without pretending to resume Python coroutines.

## Core integration and compatibility

Durability needs a few framework boundaries that a removable plugin cannot own safely. The implementation keeps policy and storage in `helpers/durable/`; core methods enter those services only where an authoritative commit must precede execution or acknowledgment.

| Core surface | Why it changes | Compatibility boundary |
| --- | --- | --- |
| `agent.py`: `AgentContext.communicate`, `kill_process`, `reset` | Admit input before starting a task, retain intervention identity, and fence stop/reset before stale workers can continue. A hook after dispatch would be too late to establish ownership. | Off mode with no ledger follows the original path. Existing held journals prevent legacy execution from bypassing a stop or unresolved run. |
| `agent.py`: model loop and `call_chat_model_turn` | Reuse the existing streaming implementation through `_call_model_with_stream`; commit the final prepared request immediately before `unified_turn` and its normalized result immediately afterward. Named continuation phases replace restarting a whole monologue. | Legacy streaming, callbacks, native IDs, result processing and response-tool completion remain owned by their existing methods. The durable branch disables automatic provider retries and holds unsupported recovery hooks instead of repeating them. `hist_add_ai_response` still owns Responses-state advancement. |
| `agent.py`, `helpers/tool_execution.py`, `helpers/parallel_tools.py` | One native/JSON/direct-parallel lifecycle commits body outcomes before intervention and postprocessing, then commits finalized history. Separate implementations could journal a result at different points or replay a body after a post-hook crash. | Tool construction, hook order, native output factories and each caller's return/`break_loop` behavior remain intact. `Tool.documents` is additive. |
| `initialize.py`, `run_ui.py` | Open one ledger owner before chat restoration, then recover supported work from authoritative checkpoints after framework startup preparation begins. Independent scans or chat snapshots cannot safely elect a driver. | Startup remains best effort for embedding warmup. Local mode needs no database service; PostgreSQL mode uses the declared driver and an operator-managed database. Unadapted connector/session targets remain held; starting MCP is not treated as evidence that their sessions can resume. |
| `helpers/defer.py`, `agent.py` intervention waits | Await child futures across event loops without reserving one executor thread per ancestor, and release/reacquire the bounded execution slot while waiting. | Existing result methods remain available. A timed-out/shielded join leaves child execution alive; explicit ownership controls cancel it. Read-only timeout receipts are settled, later waits have distinct identities, and collected workflows can expire through retention. |
| `helpers/task_scheduler.py` and child tool adapters | A scheduler occurrence or child manifest must own admission and completion. Persist checked atomic task projections and original child order/join cursors; cancel one durable task without terminating the shared event loop. | Built-in callbacks have explicit adapters; custom callbacks hold. Scheduler receipts are private, legacy scheduler behavior remains available when durability is off, and old future callbacks cannot unregister a newer occurrence. |
| `helpers/persist_chat.py`, `api/pause.py`, settings | Delete/fence journal data with chat data, include retained normalized provider-response IDs in existing cleanup, and prevent unpause from bypassing review. Three settings expose opt-in mode and retention. | Provider-deletion opt-out remains respected; failures are reported separately with a sanitized count. `chat.json` stays a compatibility/export projection. Default mode is `off`. |

Recovered admissions retain their restored provenance even when a saved workflow manifest creates the child only after restart. This prevents a new `admitted` phase from granting portability to an unknown stateful target. Implicit `monologue` function wrappers and unresolved model-completion function hooks require a recovery adapter; recovery does not rerun or silently skip their uncertain effects.

## Plans and operator review

The **Chat plan** tab exposes only the registered `todo` document: title, stable item IDs, text and completion flags. Limits are 160 characters per title, 100 items, 2000 characters per item and 64 KiB of strict JSON. Reads do not persist initializer or migration values. App saves require the exact revision and a stable mutation ID. A stale save preserves the complete draft for comparison before another save. Newer unsupported schemas cannot be overwritten by this editor.

Core tools may use `Tool.documents.read(kind)` and `stage(kind, value, expected_revision=revision)` during a durable invocation. `durable_plan` is the concrete model-visible adapter. Drafts remain private to the body; failures and process death before commit leave the prior revision intact. Result and document edits commit in one transaction. If any edit conflicts, no proposed edit applies, the known body result is retained, and each proposal gets an explicit reconciliation record. Keeping the current value or applying a proposal requires current document and review versions. Finishing postprocessing after reconciliation reuses the body and prehooks; interruption after finalization begins stays held.

Explicit model retries require a complete version-2 prepared plain-inference descriptor, unchanged model/configuration, supported text/transport inputs and no hosted built-ins or unknown request options. They reuse the saved request without rerunning preparation hooks and disable internal automatic retries. Each operator grant creates one attempt alias before invocation; a consumed grant with no known outcome requires another review. The original uncertainty remains recorded. Only exact source-audited `response` and `durable_plan` tool implementations have explicit tool retry support; shell, browser, SSH, MCP and other stateful/effectful targets require their own adapters. A generic `safe` label is insufficient.

The status endpoint returns active work first in bounded pages, never raw provider/configuration envelopes or tool arguments. **Load more** exposes additional runs; **Refresh** revalidates every loaded page before replacing the inventory. Restore selection supports up to 1000 explicitly reviewed runs. A failed decision acknowledgment can resend only its exact approved payload and request ID, even after the inventory version changes; it cannot turn a stale decision into a new authorization. Proposed document values and private evidence notes use existing masking. Notifications invalidate existing context state after commit; document revisions and durable review versions remain separate from WebSocket cursors.

## Data and operational limits

Recovery uses a versioned JSON codec, credential masking and private file modes.
SDK `.raw`, settings objects and resolved provider credentials are excluded;
required opaque provider reasoning items remain private. Histories, prompts and
tool results are still private user data. Storage encryption is deployment-owned.
Delete applies to ledger payloads as well as chat files. Backups have separate
custody and retention; local deletion cannot erase an independently retained backup.

Each JSON record/checkpoint remains bounded to 16 MiB, including offloaded values.
Oversized or unsupported state holds execution. Blobs live under
`usr/durability/blobs/<sha256>.json`, centralizing custody and backup with the ledger;
this replaces the specification's proposed per-chat blob-directory layout.
Recovery isolates corrupt/missing dependencies rather than replacing them. Retained input, checkpoints, events, call fingerprints, completed results and document/conflict payloads require valid integrity digests; a missing digest is corruption, not permission to skip verification.

Automatic maintenance runs at startup and after runners exit. Defaults retain up
to 100 eligible terminal payloads for at most 30 days. Change
`durability_retention_runs` / `durability_retention_days` through saved settings or
`A0_SET_DURABILITY_RETENTION_RUNS` / `A0_SET_DURABILITY_RETENTION_DAYS` defaults,
then restart. Zero expires eligible payloads immediately. Active runs, unresolved
intents, uncollected jobs and the graph of necessary manifests, child outcomes and
collection receipts remain protected regardless of age/count. Retention never
turns an old message or intervention retry into new work: payload-free IDs and
fingerprints remain, and retries report expiry instead of executing again.

Maintenance removes unreachable blobs. SQLite mode checkpoints WAL and reclaims private SQL
pages after pruning; PostgreSQL MVCC/WAL/replica custody is deployment-owned. It does not compact unresolved work or impose a total disk
quota. Monitor disk growth, especially long-lived background jobs and unresolved
calls. Generic connector/effectful-tool retry adapters remain unimplemented. PostgreSQL workers use database session ownership rather than time-expiring replay permission.
Disk-full never falls back to unjournaled effects; do not enable the feature by
default before sustained workload/latency/storage acceptance.

`chat.json` remains a readable compatibility/export snapshot, not an unwatermarked
recovery source. Imported/branched history does not carry runnable ledger entries.
Keep the ledger when disabling the feature: off mode opens existing durable state
and holds active work, preventing accidental legacy replay. Code older than this
feature cannot enforce that rollback guard; stop all durable runs before running
such a version against the same data root.

## Backup and recovery

For local mode, use the store backup API rather than copying a live main database without its WAL
or its referenced blobs. The resulting SQLite file embeds every referenced blob;
restoring it into `usr/durability/state.sqlite3` hydrates verified private blob files
on demand. A damaged embedded blob holds only its affected dependencies.
For an offline backup, stop the framework, then run from the project root:

```python
from pathlib import Path
from helpers.durable.store import LocalStore

with LocalStore(Path("usr/durability")) as store:
    store.backup(Path("/backups/agent-zero-recovery.sqlite3"))
```

The backup destination must be new and private. Each backup carries a permanent review marker and a fresh deployment epoch: restoring it never automatically dispatches old runs or consumes copied retry grants. In **Recovery & documents**, explicitly select the runs to restore. Active parent/child dependencies must be reviewed together; unrelated runs stay unselected. Compatible known-safe running checkpoints can continue after selection. Uncertain actions remain held for a separate resolution. New admissions are authorized in the current epoch; the marker is never globally cleared. Workspace files, uploads,
plugins, configuration and credentials require their own consistent backups; a
recovery database alone does not restore the execution environment.

## Verification

Run with the framework Python environment:

```sh
python -m pytest tests/test_durable_store.py tests/test_durable_integrity.py tests/test_durable_blobs.py tests/test_durable_documents.py tests/test_durable_review_store.py tests/test_durable_review.py tests/test_durable_response_deletion.py tests/test_durable_function_hooks.py tests/test_durable_retry.py tests/test_durable_runtime.py tests/test_durable_process_recovery.py tests/test_durable_scheduler.py tests/test_durable_workflows.py tests/test_durable_workflow_process.py -q
```

The tests use temporary data, fake providers and real process termination. They
cover admission/outcome/finalization crash boundaries, ownership, reset fencing,
deletion, native IDs, known-result reuse, portable backups, retention identities,
scheduler occurrence reconciliation, child joins and conservative uncertainty holds.
Each worker limits active execution to two slots; parents release their slot
while waiting for children or paused. Child waits do not occupy executor threads,
and a timed-out join leaves its background work running. Paused ancestry blocks
new child effects until unpaused; retention preserves the complete live ancestry.
Run `node --test tests/test_durability_ui.mjs` for modal state/race checks. The real-browser harness `tests/test_durability_browser.mjs` targets an isolated synthetic API sidecar and verifies real authentication/CSRF, stale review rejection, restore selection, draft conflicts and responsive modal lifecycle. It must never target live user state.

They do not establish live-provider billing guarantees or physical disk failure
acceptance. Exactly-once external effects need target-side idempotency or
reconciliation, independently of the local journal.
