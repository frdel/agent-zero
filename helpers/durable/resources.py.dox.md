# Resource adapter contract

`ResourceManager` binds immutable bytes and versioned manifests to one context, optional claimed run or append-only job capability. `ResourceAdapter` declares kind/version/capture/validate/restore; explicit registration pins inspectable source and rejects changed implementations. The attachment adapter uses this contract. Workspace and session modules own their additional typed manifests and safety rules.

Bytes use authenticated encrypted envelopes, never plaintext database blobs. `cipher()` reads the deployment environment key without exposing it. `put_bytes` hashes and scopes references; `get_bytes` verifies ciphertext, metadata, context, size and plaintext hash. `materialize` privately stages complete bytes and publishes without overwriting an existing path; conflicting bytes/links hold. `read_regular` bounds and verifies stable regular files.

`capture_context` gathers immutable admission resources. `checkpoint_state`/`snapshot_context` capture portable checkpoint state, including managed edits. `canonical_value`/`local_value` translate exact attachment tokens and bounded workspace path prefixes; sibling paths and invalid reference suffixes must never rebind. `restore_attachment_paths` only materializes after ownership is established by its coordinator.

PostgreSQL store methods own reference validation, CAS, tombstones, quotas and GC. Files materialized on workers have independent execution-cache custody. Verify through encrypted-resource, workspace and process recovery tests, including corruption, stale claims, staged-object collection, path boundaries and first-host file loss.
