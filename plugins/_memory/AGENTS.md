# Memory Plugin DOX

## Purpose

- Own persistent memory, knowledge import, vector indexing, and memory management UI.

## Ownership

- `helpers/memory.py` owns FAISS store loading, embedding metadata, and knowledge preload.
- `helpers/knowledge_import.py` and `helpers/memory_consolidation.py` own import and consolidation behavior.
- `tools/` owns memory save/load/delete/forget tools.
- `api/` and `webui/` own memory dashboard and knowledge reindex/import flows.
- `prompts/`, `default_config.yaml`, and `plugin.yaml` own memory prompts, defaults, and metadata.

## Local Contracts

- Keep memory scoped by configured subdirectory/context.
- Preserve embedding metadata needed to rebuild indexes safely.
- Delayed recall results must survive `LoopData` replacement, stay scoped to the originating memory/profile/project, and be consumed once by the next prompt; do not persist live task objects into chat JSON.
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
