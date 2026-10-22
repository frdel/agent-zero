# defer.py DOX

## Purpose

- Own the `defer.py` helper module.
- This module runs deferred or child async tasks on managed event-loop threads.
- Keep this file-level DOX profile synchronized with `defer.py` because this directory is intentionally flat.

## Ownership

- `defer.py` owns the runtime implementation.
- `defer.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `EventLoopThread` (no explicit base class)
  - `terminate(self)`
  - `run_coroutine(self, coro)`
- `ChildTask` (no explicit base class)
- `DeferredTask` (no explicit base class)
  - `start_task(self, func: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs)`
  - `add_done_callback(self, callback: Callable[[Future], Any]) -> None`
  - `is_ready(self) -> bool`
  - `result_sync(self, timeout: Optional[float]=...) -> Any`
  - `async result(self, timeout: Optional[float]=...) -> Any`
  - `async result_async(self, timeout: Optional[float]=...) -> Any`
  - `kill(self, terminate_thread: bool=...) -> None`
  - `kill_children(self) -> None`
  - `is_alive(self) -> bool`
  - `restart(self, terminate_thread: bool=...) -> None`
- Notable constants/configuration names: `T`, `THREAD_BACKGROUND`.

## Runtime Contracts

- Named event-loop instances serialize loop and thread creation under the registry lock, including concurrent first use and lazy starts through `run_coroutine`. Cancelling a consumer task must not terminate its shared loop.
- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- `DeferredTask` retains its callable and arguments only while an invocation is active; completion and `kill()` clear those references after the running coroutine has taken its own snapshot.
- `add_done_callback()` forwards to the current invocation's concurrent future and rejects calls before `start_task()`; callbacks observe `is_alive() == False` and must remain lightweight.
- `result_async()` wraps the concurrent future without consuming an executor thread. Its shield keeps background work alive when a waiter times out or is cancelled; explicit `kill()` and owner controls cancel the invocation. Durable child joins use it to avoid executor exhaustion in deeply nested workflows.
- Task results remain available after completion. `restart()` can restart an active invocation, but a completed invocation has no retained call recipe and must be started again explicitly.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: scheduler state.
- Imported dependency areas include: `asyncio`, `concurrent.futures`, `dataclasses`, `threading`, `typing`.

## Key Concepts

- Important called helpers/classes observed in the source: `TypeVar`, `threading.Lock`, `self._start`, `asyncio.set_event_loop`, `self.loop.run_forever`, `loop.is_running`, `asyncio.run_coroutine_threadsafe`, `EventLoopThread`, `self._start_task`, `self.kill`, `self.event_loop_thread.run_coroutine`, `self.kill_children`, `asyncio.get_running_loop`, `func`, `asyncio.iscoroutine`, `Future`, `asyncio.wrap_future`, `asyncio.current_task`, `asyncio.new_event_loop`, `threading.Thread`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_defer_lifecycle.py`
  - `tests/test_office_document_store.py`

## Child DOX Index

No child DOX files.
