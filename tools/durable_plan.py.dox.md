# Durable Plan Tool

## Purpose and ownership

- Expose the `todo` typed document through `read` and revision-checked `replace`.
- `helpers/durable/documents.py` owns schema validation and per-body drafts; the store owns atomic body-result/document commits.

## Contracts

- Requires an active local durable turn. It never migrates arbitrary agent data or modifies files/external services.
- Read returns value and revision. Replace requires the complete typed value and expected revision; it stages one update, committed only with the successful body outcome.
- Concurrent app edits preserve the known body result and produce a reconciliation hold, never an external-effect retry.
- `safe` applies only to this pure body; source/audited lifecycle checks still govern replay.

## Verification

- Run durable document store/runtime/recovery tests and tool/prompt contract tests with the framework Python.
