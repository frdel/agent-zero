# PostgreSQL workers

The `postgres` durability backend coordinates framework processes on separate
hosts through one database. Input identities, checkpoints, outcomes, typed
documents, recovery decisions, command receipts, scheduler projections, and large
JSON payloads share that authority. Workers do not need a shared SQLite volume or
another host's `chat.json` to resume compatible portable work.

Portable attachments, managed project snapshots and explicit shell/SSH/browser/MCP
adapters use [encrypted shared resources](durability-resources.md). Each adapter
declares what it can restore and reconcile; arbitrary process/plugin memory is
not implicitly portable. Source/configuration drift and unresolved external
effects still hold for review.

## Deployment

Use a dedicated PostgreSQL database and a private schema namespace per deployment.
Workers sharing a namespace must run the same source and compatible model,
profile, extension, and policy configuration. Provider credentials are configured
on each eligible worker; they are never stored in recovery checkpoints. Configure
worker authentication, encrypted database transport, database storage encryption,
backups, and access privileges as deployment infrastructure.

Set the following before starting each worker:

```sh
export A0_SET_DURABILITY_BACKEND=postgres
export A0_DURABILITY_POSTGRES_NAMESPACE=agent_zero
export A0_DURABILITY_POSTGRES_DSN='host=db.example dbname=agent_zero user=agent_zero sslmode=verify-full sslrootcert=/run/secrets/pg-ca.crt passfile=/run/secrets/pgpass'
python run_ui.py
```

Keep the password file private and use your platform's secret mount. The DSN is
an environment-only configuration value, never a returned settings field. Saved
`durability_backend` values take precedence over defaults; update an existing saved
value and restart. Shared resource adapters additionally require the common private `A0_DURABILITY_RESOURCE_KEY`; see [resource custody](durability-resources.md). The declared `psycopg[binary]` dependency also has a framework
startup migration for self-updated instances.

The store requires server `fsync` and `full_page_writes`, and forces synchronous
commit for its session. For automatic database-primary failover, configure a
single writer and synchronous replication consistent with your recovery-point
requirements; switching to a stale replica can lose acknowledged intent records
and is a database restore event requiring review, not safe worker takeover.

Use direct PostgreSQL connections or a pooler in **session** mode. Transaction
pooling cannot preserve a worker's session ownership. A worker does not silently
reconnect a lost database session under its old claims. Restart that worker after
restoring connectivity. Session lock lifetime follows the [PostgreSQL locking contract](https://www.postgresql.org/docs/17/explicit-locking.html#ADVISORY-LOCKS). Database failures hold execution rather than enabling the
legacy path.

An existing local SQLite ledger is not silently abandoned when changing backends.
Use a fresh deployment root for a new PostgreSQL deployment. Migrating existing
local recovery data requires an explicit offline migration; changing a setting is
not a data migration. Likewise, disabling the backend while its DSN remains
configured opens shared state with execution disabled, preserving held work.
Remove database configuration only after stopping all shared work; an older
framework cannot enforce this rollback boundary.

## Ownership and recovery

Each run has one pinned PostgreSQL session claim and an increasing fence token.
A live claimant excludes competing workers. Claim loss prevents the old worker
from starting calls or advancing outcomes/checkpoints. PostgreSQL session locks
are released when their session ends; elapsed wall-clock time is never permission
to repeat an effect. The database must detect a disconnected session before a
successor can claim its runs.

Periodic scans claim and audit constructor hooks before constructing a live context, so another process does
not overwrite its local registry with a remote worker's context. A successor reads
the shared checkpoint, verifies portability and source/configuration, then resumes
a supported phase or records a hold. Losing ownership cannot retract an HTTP
request already sent: an unresolved tool/provider intent remains uncertain and
requires the existing review/reconciliation policy. Exactly-once external effects
still require target-side idempotency.

Short ledger mutations serialize through a database transaction advisory lock.
Provider and tool calls execute outside that transaction. PostgreSQL owns shared timestamps and retention cutoffs; journal admission sequences determine conversation order even when worker clocks differ. This preserves the
existing admission, generation, document CAS, review version, and retention
invariants across writers. Large values use verified database bytes in the same
transaction as their references; no worker-local blob directory is authoritative.
One verified current checkpoint per chat is retained independently of old run payloads, so terminal journal retention cannot erase the conversation required for its next turn. Deletion scrubs this checkpoint too. Execution has two slots **per worker**. This is not a deployment-wide provider
rate or concurrency limit.

## Core integration rationale

| Boundary | Why shared execution changes it |
| --- | --- |
| Recovery service factory and runner saves | Backend selection must happen before startup restoration or admission. A claimant must be established before reconstructing a context, and an acknowledged command must survive the next worker snapshot. These checks cannot be supplied by a post-dispatch hook. |
| Shared API context lookup and message/pause/reset handlers | A requester host's in-memory registry cannot prove ownership. Existing chat messages route to shared admission or the owner inbox before requester-side hooks/logging; new chats retain first-Send creation. Mutation paths refuse stale shadows. |
| Chat persistence | A host's `chat.json` cannot overwrite shared history, configuration or deletion policy. Shared projections require claim ownership and revision CAS; recovery constructs contexts from the ledger. Local files remain compatibility projections. |
| Scheduler persistence and framework job loop | Independent task files and pollers can launch duplicate work. Shared definitions/projections need CAS; pinned roles elect due-task and integration pollers, and occurrence claims arbitrate execution. |
| Dependency declarations and startup migration | New images and self-updated instances both need the PostgreSQL driver and its binary extra. Backend import stays lazy; an unavailable driver holds PostgreSQL mode without changing the local/off execution path. |

The PostgreSQL adapter reuses strict JSON, generation, review, document, retry and
retention business rules instead of maintaining a second execution engine. Its SQL
translation is limited to the repository's static store statements; native
PostgreSQL schema, transaction, blob and ownership semantics remain explicit.

## Commands, children, and scheduler

Remote input/control/review commands commit before acknowledgment. UI input preparation runs only on the claimed worker, with its own intent/result and source fingerprint; only exact audited built-in preparation may repeat an unknown preparation. UI interventions use the same owner preparation and portable attachment path. The current provider/tool outcome settles before input is consumed at a committed iteration boundary. New input during terminal finalization is rejected for a later send; a queued input's receipt never reports the previous run's answer as its own success. Stable request
IDs deduplicate delivery; the owner applies commands under its snapshot lock and
records a separate receipt. A queued decision is not an applied decision. The
Recovery modal's explicit **Refresh** checks pending/applied/rejected receipts.
The worker revalidates the original review version and current policy; queueing
never upgrades a stale authorization. Pause prevents new effect dispatch after
application; an already-sent request can still finish. Reset requests retain stable client IDs and atomically recorded receipts; retrying a lost acknowledgment cannot reset a newer run. Reset clears the next admission's history under a generation check. Stop/reset generation fences
apply in shared storage even when the requesting host has no local task to kill.

Child joins await shared run identities rather than requiring the originating
process's `DeferredTask`. Known child results can be collected from another host.
Waiting parents yield their local execution slot. Timeouts leave background work
alive and are recorded separately from successful collection.

Built-in scheduler definitions and occurrence projections use a versioned database
projection. A session role elects the scheduler poller; failover reads shared task
state. Per-run claims still arbitrate actual execution. Concurrent scheduler edits
must pass projection CAS. A separate pinned `job-loop` role excludes simultaneous integration pollers while their database sessions are healthy. Plugin polling effects, delivery cursors and in-flight disconnect reconciliation still require each integration's adapter; they are not journaled workflow outcomes. Local JSON/YAML task files remain authoritative only for
the local/off backends; they are not replicated scheduler storage.

Normal chat snapshots read committed logs and task metadata from shared storage on
any host without creating an executable context. A shared revision watermark
invalidates local WebSocket projections after another worker commits. Updates to
existing log items retain their cursor contract; a new run/reset changes the
projection generation. Cross-host views show saved progress, not replicated
provisional streaming tokens. Host-local notifications remain local.

The API reads committed masked state on any host. Document edits, conflict decisions
and removal requests enter an encrypted, generation/epoch/version-bound command
inbox. A compatible claimed worker applies them without starting an agent message
loop. Terminal and unsent chats use the same maintenance path; an unsent draft
receives an inert maintenance anchor, never an inference request. The UI reports
queued acceptance separately from an applied receipt and preserves unsaved edits.
Terminal retention removes private command payloads while retaining sanitized
acceptance/deletion receipts, so retrying an applied command remains applied.

Provider deletion pins the actual model's provider/account/endpoint proof before
request dispatch. Cleanup rechecks current matching credentials and the saved
opt-out, then journals each idempotent DELETE. A successor can repeat that precise
DELETE after a lost acknowledgment; a matching 404 means already absent. Changed
account proof holds cleanup. Removal reports the count of unknown requests with
no returned provider identifier; it cannot promise erasure of those unknown
provider objects or independently managed WAL, replicas and backups.

## Background work and shared memory

Built-in recall, infection checking, automatic fragment/solution memorization and
history summarization use detached outboxes. Frozen inputs, implementation/model
identity, send grants and phase results live in shared custody. A worker can
recover an unsent phase or query its known result without reconstructing the
original deferred Python task. A running phase without target evidence remains
uncertain; worker loss alone never authorizes another provider request.

Memory documents and numeric vectors use an encrypted typed shared index with
revision CAS and atomic mutation receipts. Another worker rebuilds FAISS locally
without unpickling database data or re-embedding committed vectors. Knowledge
imports retain source versions; an absent local file cannot delete shared
knowledge. Explicit reload/reindex can update changed local sources. Historical
mutation receipts may supply known outcomes after restore selection, but never
authorize writes in the old epoch.

History projection runs on the claimed loop. Deterministic large-message
compression handles oversized recent inputs before detached summarization of
older history, and committed summaries preserve input appended while they ran.
Pending outboxes and their resource roots survive retention. Completed outboxes
can expire only after their originating run and all retained task handles expire.

When upgrading from protocol 1 or 2, stop all workers and detached jobs first.
Protocol 3 refuses mixed active owners/jobs rather than changing their contract
under an in-flight process. All workers must use the same new source before
restarting.

## Backup and restore

Use PostgreSQL's consistent native backup tools with database-owned retention and
custody. The SQLite `LocalStore.backup()` file API is not a PostgreSQL backup API.
SQL deletion does not erase independent backups, WAL archives, or replicas.

Stop every worker before restoring a database. After restoring, rotate its
recovery deployment epoch and require explicit selection of restored runs before
starting workers:

```python
import os
from helpers.durable.postgres import PostgresStore

with PostgresStore(os.environ["A0_DURABILITY_POSTGRES_DSN"],
                   namespace=os.environ.get("A0_DURABILITY_POSTGRES_NAMESPACE", "agent_zero")) as store:
    store.begin_restore_review()
```

This maintenance operation refuses live worker claims or roles. Then use explicit
per-run restore selection in Recovery & documents. Never attach workers to an old snapshot as though it were the
current live database: previously sent external effects may have no outcome in
that snapshot. Retry grants and prior restore selections cannot authorize replay
in the new deployment epoch. Workspace/configuration/credentials have their own
backup and consistency requirements.

## Verification

Use a disposable PostgreSQL database and the framework Python environment. The
integration tests run only when an explicit test DSN is present; they never fall
back to the deployment DSN:

```sh
export A0_TEST_DURABILITY_POSTGRES_DSN='host=127.0.0.1 port=5432 dbname=a0_test user=a0_test'
python -m pytest tests/test_durable_postgres.py tests/test_durable_cluster.py tests/test_durable_cluster_api.py tests/test_durable_postgres_process.py -q
node --test tests/test_durability_ui.mjs
```

The process tests kill actual framework workers at committed model/tool
boundaries, exclude a competing live claimant, and recover in a fresh process
with an independent empty chat directory. They check known-result reuse and
uncertainty holds with synthetic providers. Database session termination tests
check stale-writer fencing. These tests establish process isolation and shared
custody locally; they are not a live multi-region deployment or network-partition
acceptance test.
