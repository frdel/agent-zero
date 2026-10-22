# Portable resources and execution

The PostgreSQL backend can move attachments, managed project files and supported
execution/session state between workers. The shared ledger still distinguishes a
known result from an uncertain effect. Reconnecting or reopening state never
authorizes repeating an interrupted operation.

## Configuration and custody

Follow [PostgreSQL worker setup](durability-postgres.md). Every eligible worker
also needs the same private `A0_DURABILITY_RESOURCE_KEY`, a Fernet key generated
with the existing `cryptography` package. Generate it once into your secret store
and inject it through the deployment environment; do not generate a different key
per worker or place it in settings, source, requests or logs. Changing the key
requires an offline re-encryption migration; automatic key rotation is not
implemented. Missing/wrong keys hold resource recovery.

All resource bytes are encrypted before PostgreSQL writes. The authenticated
envelope binds the context, complete reference metadata and plaintext hash.
Contexts cannot resolve one another's resource IDs. A resource reference has
`id`, `kind`, `name`, `digest` and `size`; `a0-resource://<id>` is a stable logical
attachment reference. Source/version-pinned adapter declarations define capture,
validation and restore; a generic replay label supplies no authorization.

Objects are bounded to 8 MiB; encrypted storage is bounded to 256 MiB per context.
Private materializations use owner-only directories/files and reject symlinks,
hard links and conflicting existing bytes. These are execution artifacts, not an
operating-system sandbox.

## Attachments and managed workspaces

Existing multipart chat uploads enter shared encrypted custody before admission.
JSON clients may send `resources: ["a0-resource://<id>"]` for references already
owned by that context. The claimed worker materializes verified bytes before UI
preparation/history. Preparation records portable references rather than another
worker's absolute paths. Repeated input IDs retain their original content check.

A project snapshot captures regular files, empty directories, executable bits,
Git revision and dirty/untracked/deleted provenance. It includes ignored files
except explicit VCS/cache exclusions, preventing an ignored credential file from
being silently overlooked. Recognized credential files/material, nonregular files,
links, submodules, concurrent changes and oversized trees hold. Bounds are 2,000 file/directory entries,
64 MiB total, 8 MiB per file and 32 directory levels. Git metadata and hooks are
not restored; this is a file workspace with revision provenance, not a Git clone.

Workers restore into a fresh isolated directory before project-sensitive
constructors execute. ContextVar routing keeps other chats and the owner's
checkout unchanged. A tool body and its updated workspace checkpoint publish in
one claim/generation-fenced transaction. If capture fails after the tool has
completed, the plain known outcome is retained and the run holds for file
reconciliation. It never repeats the tool to recreate files. Shared workspace
publication does not automatically merge changes into the owner's checkout.

`POST /api/durability_resource` with `context` and `action: "workspace"` reads the
committed workspace manifest. With `context` and `resource_id`, it downloads the
verified resource as an attachment. Both retain normal authentication, origin and
CSRF protection; no public or path-based read endpoint is added.

## Execution adapters

| Adapter | Recovery behavior | Explicit boundary |
| --- | --- | --- |
| Local shell/Python/Node | A detached POSIX supervisor publishes encrypted output and a known exit result under an append-only job capability. Other workers reuse the result. | Submitted jobs never relaunch. A lost execution host with no result holds. No PTY, stdin continuation, aliases, functions or arbitrary shell-memory migration. |
| SSH | Reconnect to the same host-key-verified target and inspect the stable remote job receipt. | No command resubmission after uncertain dispatch. Target credentials remain worker configuration; database keys/credentials are never forwarded to the target. |
| Browser | Restore encrypted cookies, origin storage and HTTP(S) tabs into a separate durable context; expire old tab IDs and DOM refs. | No shared sign-in profile adoption, unpacked extensions, arbitrary JavaScript/POST/history/IndexedDB/cache/download replay or host-browser connector migration. Unknown actions hold. |
| MCP | Reinitialize a transport using local credentials and validate actual server identity, configuration and tool schema. | Read-only hints do not authorize replay. An explicitly registered, source-pinned query-only reconciler may retrieve a known outcome; otherwise an interrupted effect holds. |

Shell state retains cwd and exported-environment deltas privately. Managed path
values rebind to the successor's workspace; unmanaged absolute paths cannot
silently migrate. Normal tool/model output still passes masking. Stop may request
cancellation of the matching recorded job; it cannot promise to retract effects
already sent. Worker/session loss alone never requests cancellation. Reset and
restore epochs revoke old supervisor publication authority.

Execution hosts need stable, unique identities. Set `A0_DURABILITY_EXECUTION_HOST_ID`
when deployment hostnames are reused or are not unique. Cached browser runtimes
are invalidated by ownership, epoch, generation, configuration or manifest changes;
failed actions/capture cannot leave an uncommitted session eligible for reuse.

These resource adapters require PostgreSQL. Local/off legacy execution remains
separate. SQLite recovery does not acquire shared session capabilities merely
because an adapter is installed.

## Retention and verification

Verified retained runs, current chat heads, resource/session manifests and job
receipts protect reachable bytes. Unreferenced staging objects have a one-day
grace period, and reused objects refresh that period. Input/checkpoint admission
checks references transactionally before acknowledgment. Corrupt roots abort
resource collection. Job receipts and current session heads remain conversation
state until deletion; the context quota bounds their storage.

Deletion scrubs shared resource objects/manifests/jobs. Native database backups,
WAL, remote SSH receipts and private worker materializations have separate
retention and deletion custody; SQL deletion is not a distributed secure-erase
operation. Protect and clean those execution directories through the worker
deployment's lifecycle.

Run the resource, workspace, execution, session and PostgreSQL process suites
against an explicitly disposable `A0_TEST_DURABILITY_POSTGRES_DSN`. Recovery tests
remove the first worker's attachment files, kill actual workers, exercise a
detached supervisor and a loopback SSH target, and query a real MCP stdio server.
Browser tests use a simulated Chromium boundary. Physical multi-host,
network-partition, real-browser and real-service acceptance remain deployment
verification steps.
