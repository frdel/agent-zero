# Memory Plugin DOX

## Purpose

- Own persistent memory, knowledge import, vector indexing, and memory management UI.

## Ownership

- `helpers/memory.py` owns FAISS store loading, embedding metadata, and knowledge preload.
- `helpers/durable_memory.py` owns PostgreSQL-mode encrypted typed document/vector snapshots, first-scope legacy import, FAISS reconstruction and atomic revision/operation receipts. `helpers/durable/memory.py` recovers known tool mutations from these receipts without repeating embeddings or writes.
- `helpers/knowledge_import.py` and `helpers/memory_consolidation.py` own import and consolidation behavior.
- `tools/` owns memory save/load/delete/forget and behavior adjustment tools.
- `api/` and `webui/` own memory dashboard and knowledge reindex/import flows.
- `prompts/`, `default_config.yaml`, and `plugin.yaml` own memory and behavior-tool prompts, defaults, and metadata.

## Local Contracts

- Keep memory scoped by configured subdirectory/context.
- PostgreSQL memory uses the configured memory subdirectory as its shared scope. Persist strict JSON documents/vectors in authenticated encryption, never FAISS pickle. Bound each snapshot to 8 MiB, 10,000 documents and 16,384 vector dimensions. Replacement/deletion patches and immutable operation receipts commit atomically; stale revisions hold. Persistent scoped memory has separate deletion custody from chat history. Embedding identity drift requires reindexing; never silently search incompatible vectors.
- Shared knowledge preload uses the existing file parsers, deterministic source/version/chunk identities and one typed CAS patch after all parsing/embedding succeeds. Automatic preload imports new logical sources only; configured changes to an existing source require explicit `Memory.reload`/knowledge reindex (`force_knowledge=True`), preventing divergent hosts from overwriting one another during reads. An authenticated source-version manifest travels with the snapshot, including empty or explicitly deleted imports. Missing files/directories on another worker never authorize erasing shared knowledge. Agent preload requires its current run claim; explicit reindex/dashboard preload follows control ownership, and `preload_knowledge=False` skips it. Mutation receipts retain removed IDs/counts, never deleted document text or metadata. Historical receipt reads require the caller's explicit selected-run gate; new mutations retain strict restore-epoch checks.
- Snapshot encryption authenticates the scope, deployment epoch and SQL snapshot revision. Operation receipts additionally authenticate their full operation projection key and request fingerprint; public envelope metadata must match the authenticated body. PostgreSQL verifies both prepared envelopes still name its current epoch inside the mutation transaction.
- Preserve embedding metadata needed to rebuild indexes safely.
- Delayed recall results must survive `LoopData` replacement, stay scoped to the originating memory/profile/project, and be consumed once by the next prompt; do not persist live task objects into chat JSON.
- In shared durability mode, recall uses an encrypted frozen typed corpus and detached phase receipts. Automatic fragment/solution hooks atomically enqueue an outbox before returning; summary, consolidation and embeddings have one-use inference receipts, and deterministic document IDs commit through one revision-checked patch. Concurrent revisions settle as conflicts, never blind replacements. Legacy off/local paths retain their existing workers. `helpers/durable/background.py.dox.md` owns the broker contract.
- `memory_load` accepts numeric `threshold` and `limit` values as native numbers or numeric strings and coerces them before vector search.
- Grouped tool-prompt declarations must start with `arg` or `args` so native Responses models receive every memory tool.
- Auto-recall embeds each prepared query once and reuses that vector for the memory and solution filters; manual `memory_load` keeps the ordinary text-query path.
- Keep auto-recall context capability-neutral; memory-tool routing belongs in
  the policy-filtered memory tool prompt.
- Avoid storing transient action-history noise as durable memory.

## Work Guidance

- Both dashboard selection toolbars use icon-only actions with accessible labels and the shared borderless close control before the selection count.
- Dashboard selection checkboxes reuse the shared native theme from `webui/index.css`; keep header and row controls 16px and centered in their table cells.
- Keep dashboard metadata JSON-safe without changing shared API serialization.
- Coordinate tool, prompt, and consolidation changes so saved memories remain useful and bounded.

## Verification

- Smoke-test save, recall, delete, dashboard search/update, and knowledge import/reindex after changes.

## Child DOX Index

No child DOX files.
