# KVP storage and durable context overlay

## Purpose and ownership

`kvp.py` owns runtime process KVP, atomic local-file persistent KVP, and an optional context-local durable overlay. Existing public get/set/remove/find APIs preserve their legacy behavior outside an overlay.

## Contracts and side effects

- Legacy runtime state uses an `RLock`. Persistent keys map to `usr/kvp/<key>.json`; writes fsync a temporary file and atomically replace the target under the persistent lock. Keys reject empty values, NUL and path separators.
- `context_scope(context_id, values, allowed, guard=...)` routes both families to the supplied checkpoint map. Keys are qualified `runtime:<key>` / `persistent:<key>`. Explicit trusted state adapters own `allowed`. Unknown scoped keys fail closed; reads never fall back to global state, and no persistent file is read/written/deleted while scoped.
- ContextVar propagation isolates concurrent async contexts while allowing their child tasks to share the same declared map. The supplied guard checks the current run claim and generation before entering and before every scoped access. A child task retaining an old context cannot keep writing after ownership ends.
- Scoped values use strict bounded JSON and reads return detached copies. The durability coordinator owns masking/encryption, restoring and atomically checkpointing this map. The overlay never copies global browser tabs/sidebar/pins state to another worker.
- `find_*` enumerates only the overlay's actual qualified keys in scope; unscoped callers keep ordinary process/file enumeration.

## Verification

Run `tests/test_durable_state_adapters.py` for concurrent context isolation, unknown-key rejection, guarded mutation and absence of global filesystem access; existing KVP callers remain covered by their owning plugin tests.
