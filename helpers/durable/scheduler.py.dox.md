# Durable scheduler projections

`scheduler.py` owns source-audited built-in occurrence admission, idempotent preparation/completion, and cancellation/attention task projections. It never repeats arbitrary scheduler callbacks. Task UUID, configuration/source hashes, occurrence and run receipts fence projection ownership; a planned slot finishes at most once.

Shared submission stages immutable encrypted attachment/project resources before atomic admission. The claimed coordinator restores them before constructors/execution. Later occurrences retain their previous committed workspace for the same project instead of replacing worker edits with the submitting host checkout. Project changes capture a fresh source workspace. Resource capture failure does not acknowledge an occurrence. SQL admission validates resource references; normal resource reachability handles failed staging.

Custom task classes/callback implementations still require a separate execution/reconciliation adapter; state declarations alone do not authorize them. Source drift, disabled/reassigned tasks and invalid resource portability hold. Verify using `tests/test_durable_scheduler.py` and the PostgreSQL scheduled-resource continuation in `tests/test_durable_state_adapters.py`.
