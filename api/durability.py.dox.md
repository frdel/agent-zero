# Durability endpoint

## Purpose and contract

`POST /durability` uses the standard authenticated, origin-checked and CSRF-protected `ApiHandler` route. `status` returns active work first with `offset`, `next_offset` and `total`, at most 50 masked run summaries per page, each with at most 20 logical calls and the next two pending document proposals, opaque review versions, safe action flags and restore epoch. Resolving proposals exposes subsequent conflicts. It never creates a context or returns provider request envelopes, tool arguments or raw exceptions.

`resolve` requires context/run identity, the exact review version, a stable request ID and a decision. Completion/non-completion confirmations require evidence and stop the run and owned descendants without fabricating an outcome. Resume and bounded new attempts pass current compatibility, control, policy and replay checks. Repeating an accepted request cannot dispatch another attempt.

`restore_select` supports at most 1000 explicitly reviewed run IDs and requires explicit run IDs, versions and epoch. Active workflow dependencies must be reviewed together; missing IDs are returned without silently selecting them. Selection leaves uncertain work held.

`document_read` exposes the registered `todo` schema. `document_update` requires a complete validated value, expected revision and mutation ID. `document_conflict` reconciles a known body result's proposed edit against the current document revision and review version, without replaying its body.

## Side effects and verification

Mutations use short transactions through `helpers.durable.store`, then existing StateMonitor invalidation. Errors return bounded JSON (400 validation, 404 missing, 409 stale/conflicting, 503 storage). RecoveryHeld is explicitly handled. Verify with `tests/test_durable_review.py`, document/store suites and the isolated real browser harness; no real providers or user state are required.
