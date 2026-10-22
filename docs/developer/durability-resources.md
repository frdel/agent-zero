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
| Local shell/Python/Node | Detached PTY/batch actors retain one operation identity, actual output, exit status, and settled shell state. A successor attaches or queries the same operation. | A missing execution host cannot fabricate an unknown foreground result. Unserializable process memory remains on the anchored actor. |
| SSH | Pinned host-key verification, detached remote PTY/receipt, reconnect and private managed-project staging/export. | No resubmission of an uncertain command. Database credentials, resource keys and job capabilities never enter the target shell. |
| Browser | Detached browser actor with coherent encrypted Chromium profile checkpoints: cookies, origin/session storage, IndexedDB, cache/service workers, extension storage and downloads. Requester loss does not cancel an action; successors reuse its actual receipt. | DOM refs expire after profile reconstruction. Restore does not repeat POSTs or JavaScript. Agent profiles remain separate from personal profiles. Profiles are bounded to 128 MiB and total context custody to 256 MiB. |
| Host browser | Companion journal pins the exact connector/browser instance, records intent before dispatch and exposes authoritative operation status. Agent profile export/import uses encrypted chunks. | Existing personal profiles stay on the selected host. A replaced browser instance cannot settle an old unknown action. Requires the matching companion durability protocol. |
| Computer use | Companion desktop journal retains per-operation receipts, session/instance binding and actual screenshot bytes. A successor queries the original operation before sending anything. | Desktop permissions and re-arming remain host-owned; an unconfirmed action is never resent or reported completed. |
| MCP | Detached transport actor validates server configuration/schema before dispatch and retains the actual CallToolResult. Successors reuse it after worker loss; unsent grants can reconstruct private transport setup using matching local credentials. | Resolved headers/env remain in the actor's encrypted local spool, outside shared requests. Running unknown effects never resubmit. |
| Memory | Encrypted typed documents/vectors rebuild a fresh FAISS index on another worker. Revision CAS and immutable mutation receipts commit complete replacement/deletion patches atomically. | Embedding identity changes require an explicit reindex; stale writers cannot overwrite newer data. No pickle is stored in PostgreSQL. |

Host Browser and Computer use require the matching `a0-connector` companion
durability implementation. Configure its private `A0_CONNECTOR_DURABILITY_KEY`
and, optionally, `A0_CONNECTOR_DURABILITY_ROOT` through the companion environment;
the companion key need not equal the framework resource key. The companion
records encrypted requests before host delivery and advertises a stable instance
identity. Losing a reply triggers a query for that exact operation, not a second
action. Retain its journal and private agent profiles across companion restarts.
Personal profiles and desktop permission/re-arm decisions remain host-owned.

The detached container Browser actor exposes a same-host viewer relay. Tool
actions and full private profile checkpoints recover across workers; moving an
interactive live viewer across hosts requires deployment routing to that actor.

Shell state retains cwd, exported environment, aliases, functions and settled shell variables privately. Interactive input is an operation with its own receipt. Managed path
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
Set `A0_TEST_DURABLE_CHROMIUM` to an installed Chromium executable for native
profile tests, and `A0_TEST_CONNECTOR_SOURCE` to the matching companion source for
the real manager/controller wire tests. These tests exercise actual browser
storage, POSTs and process termination, plus the companion operation journal.
Physical multi-host, network-partition, personal-browser and external-service
acceptance remain deployment verification steps.
