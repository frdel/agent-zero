# State adapter boundary

## Purpose and ownership

`state_adapters.py` owns explicit JSON projections for plugin context/agent/loop state, context-scoped KVP declarations, source-pinned constructor/hook manifests, and query-only reconciliation of uncertain scheduler callbacks. Registration is trusted startup code; a stored declaration never imports arbitrary code or grants replay permission.

## Contracts

- `StateAdapter(name,version,fields,sources,hooks)` and `Field(scope,key,type)` declare exact keys. `register` rejects competing ownership. Producer sources, declaration fields, version and codec source hash are committed in each active entry. Unknown versions/source drift hold before reconstruction.
- `capture(agent,mask=None,kvp=None)` walks the actual agent/subordinate chain, masks declared values, and returns a strict JSON manifest. It publishes nothing. `handled_keys(scope)` supports the caller's separate unknown-state gate: adapters do not silently authorize all remaining plugin keys.
- `validate(manifest)` is safe before constructors; `restore(agent,manifest,guard=...,kvp=...)` validates every entry, checks current claim/generation before audited local reconstructors, checks again, then applies detached state. Callers restore the loop first and commit the manifest with their normal fenced, masked checkpoint. The optional KVP map is context-local, never the process-global/file store.
- Bounds: 256 KiB total strict JSON, depth 24, 512 fields and 64 agents. Arbitrary objects, nonfinite values and unsupported task state fail closed. No pickle or object-attribute walking occurs.
- Bundled adapters preserve manual chat naming, retry counters, context-window usage/cache tuples, active browser model metadata, memory-recall scope/current-loop bindings, memory outbox references, history-compression tasks, and infection-checker configuration/clarification state. Exact detached background tasks restore as inert shared receipt references; generic pending tasks hold. Broker-owned inference can finish after a framework worker dies; a lost broker's unknown inference never repeats. Checker messages reconstruct only explicit plain system/human/AI text. See `background.py.dox.md` for outbox ownership and recovery.
- `capture_hooks` / `validate_hooks` compare explicit point/class/source declarations separately for `constructor` and `continuation`. Core initializer declarations cover reviewed local greeting/configuration hooks. The coordinator must retain its separate execution/replay rules, including unknown hook outcomes and configuration validation.
- `reconcile_callback(owner,run_id,call_id,query,implementation=...,mask=...)` accepts only a committed `scheduler_callback` intent whose query implementation matches the trusted function and source. It queries under current ownership and commits only an explicit known, masked receipt through `finish_call`. Unknown results hold; it never runs the original callback. This helper does not enable arbitrary task subclasses in the scheduler.

## Verification

Run `pytest tests/test_durable_state_adapters.py tests/test_durable_scheduler.py -q` in the framework runtime. The scheduled resource continuation case additionally requires disposable PostgreSQL via `A0_TEST_DURABILITY_POSTGRES_DSN`; tests never read a deployment DSN. It exercises actual bundled state producers, known task/checker restoration, source/claim rejection, concurrent KVP isolation, explicit hook declarations, callback receipt reuse, and two-worker scheduled project/attachment continuation.
