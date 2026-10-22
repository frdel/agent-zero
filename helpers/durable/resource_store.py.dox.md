# Shared resource custody

`ResourceStore` supplies the PostgreSQL mixin's encrypted binary objects, versioned manifests and detached job receipts. Protocol 2 upgrades protocol 1 under the shared mutation lock. It preserves the existing JSON ledger's integrity and ownership contracts.

- Resource reads/writes are context-scoped, bounded and tombstone-aware. Admission may stage immutable objects without a run claim; only a claimed current run publishes manifests. Input/checkpoint publication verifies referenced objects in its transaction.
- A registered job gets a hashed opaque capability bound to run, generation and restore epoch. It may append immutable encrypted output and one known result after worker death. It cannot publish manifests, claim a context or advance execution. A completed receipt requires verified result bytes/digest, including retries.
- `begin_resource_job(job_id, token, broker_role)` additionally requires the broker's pinned PostgreSQL session role and commits `submitted → running` exactly once before sending to a persistent session. A running job never grants a replacement send; a recorded immutable result resolves it. Local noninteractive supervisors retain direct submitted-to-completed compatibility.
- GC validates retained roots and fingerprints before tracing resource IDs. It retains current heads/session/job state, allows a staging grace period, refreshes reused objects and aborts on corrupt/missing retained payloads. Context deletion removes objects, manifests and job receipts together.

The manager encrypts/decrypts; this layer verifies binary ciphertext integrity and declared references. Worker caches, remote receipts, WAL and backups have separate custody. Run disposable PostgreSQL resource, store, execution and process-recovery tests.

Background outboxes publish their manifest and every one-use phase capability in
one transaction via `publish_resource_outbox` (at most 64 phases). Discovery uses
`list_resource_manifests` with a bounded, stable context/kind cursor; listing grants
no execution rights. Explicit `allow_completed` grants let read-only/background
phases settle after normal parent completion while pause, cancellation, reset and
restore epochs still fence dispatch/publication. The default remains false.
