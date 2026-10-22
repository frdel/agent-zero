import asyncio
from pathlib import Path
import subprocess
import sys
import threading
import uuid
import weakref

import pytest

from helpers.defer import DeferredTask


def test_concurrent_first_use_shares_one_running_loop():
    # Isolate a broken cold start so stranded loop threads cannot leak into pytest.
    script = """
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from helpers.defer import DeferredTask

start = threading.Barrier(2)
creation = threading.Barrier(2)
new_event_loop = asyncio.new_event_loop
loops = []

def create_loop():
    loop = new_event_loop()
    loops.append(loop)
    try:
        creation.wait(timeout=0.2)
    except threading.BrokenBarrierError:
        pass  # With serialized creation, a second caller never enters here.
    return loop

def create_task(_):
    start.wait(timeout=2)
    return DeferredTask('concurrent-first-use')

asyncio.new_event_loop = create_loop
with ThreadPoolExecutor(max_workers=2) as pool:
    tasks = list(pool.map(create_task, range(2)))
asyncio.new_event_loop = new_event_loop
assert len(loops) == 1, f'Created {len(loops)} loops for one name'
assert tasks[0].event_loop_thread is tasks[1].event_loop_thread

async def current_loop():
    return asyncio.get_running_loop()

try:
    for task in tasks:
        task.start_task(current_loop)
    assert all(task.result_sync(timeout=2) is loops[0] for task in tasks)
finally:
    tasks[0].kill(terminate_thread=True)
"""
    result = subprocess.run(
        [sys.executable, "-c", script], timeout=10,
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


class Owner:
    pass


def make_task() -> DeferredTask:
    return DeferredTask(f"defer-lifecycle-{uuid.uuid4()}")


def test_completed_task_releases_call_references_and_children():
    task = make_task()
    owner = Owner()
    owner_ref = weakref.ref(owner)
    child_killed = threading.Event()

    class Child:
        def kill(self, terminate_thread: bool = False) -> None:
            assert terminate_thread
            child_killed.set()

    async def run(captured_owner):
        return "done"

    try:
        task.add_child_task(Child(), terminate_thread=True)  # type: ignore[arg-type]
        task.start_task(run, owner)
        assert task.result_sync(timeout=2) == "done"
        assert child_killed.wait(2)
        assert task.func is None
        assert task.args == ()
        assert task.kwargs == {}

        del owner
        assert owner_ref() is None
        assert task.result_sync(timeout=2) == "done"
        with pytest.raises(RuntimeError, match="Completed task cannot be restarted"):
            task.restart()
    finally:
        task.kill(terminate_thread=True)


def test_run_task_end_extension_marks_state_dirty_after_completion(monkeypatch):
    from extensions.python._functions.agent.AgentContext.run_task.end import (
        _10_mark_state_dirty as task_done_extension,
    )

    task = make_task()
    callback_called = threading.Event()
    observations: list[tuple[str | None, bool]] = []

    def mark_dirty(*, reason=None):
        observations.append((reason, bool(task.is_alive())))
        callback_called.set()

    monkeypatch.setattr(
        task_done_extension,
        "mark_dirty_all",
        mark_dirty,
    )

    async def run():
        return "done"

    try:
        with pytest.raises(RuntimeError, match="Task hasn't been started"):
            task.add_done_callback(lambda _future: None)
        task.start_task(run)
        task_done_extension.MarkStateDirty(agent=None).execute(
            data={"result": task}
        )
        assert task.result_sync(timeout=2) == "done"
        assert callback_called.wait(2)
        assert observations == [("agent.AgentContext.run_task_done", False)]
    finally:
        task.kill(terminate_thread=True)


def test_kill_clears_stored_call_without_clearing_running_arguments():
    task = make_task()
    owner = Owner()
    owner_ref = weakref.ref(owner)
    started = threading.Event()
    cancelled = threading.Event()
    finished = threading.Event()
    release: list[asyncio.Event] = []

    async def run(captured_owner):
        release.append(asyncio.Event())
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.set()
            await release[0].wait()
        finally:
            finished.set()

    try:
        task.start_task(run, owner)
        assert started.wait(2)
        task.kill()
        assert cancelled.wait(2)
        assert task.func is None
        assert task.args == ()
        assert task.kwargs == {}

        del owner
        assert owner_ref() is not None
        task.event_loop_thread.loop.call_soon_threadsafe(release[0].set)
        assert finished.wait(2)
        asyncio.run_coroutine_threadsafe(
            asyncio.sleep(0), task.event_loop_thread.loop
        ).result(2)
        assert owner_ref() is None
    finally:
        if release and task.event_loop_thread.loop:
            task.event_loop_thread.loop.call_soon_threadsafe(release[0].set)
        task.kill(terminate_thread=True)


def test_active_task_can_restart_from_its_snapshot():
    task = make_task()
    starts = [threading.Event(), threading.Event()]
    run_count = 0

    async def run(value):
        nonlocal run_count
        current_run = run_count
        run_count += 1
        assert value == "argument"
        starts[current_run].set()
        await asyncio.Future()

    try:
        task.start_task(run, "argument")
        assert starts[0].wait(2)
        task.restart()
        assert starts[1].wait(2)
        assert task.func is run
        assert task.args == ("argument",)
    finally:
        task.kill(terminate_thread=True)


def test_nonblocking_result_handles_deep_nesting_without_executor_workers():
    from concurrent.futures import ThreadPoolExecutor
    tasks = []
    loop_name = "nonblocking-join-" + uuid.uuid4().hex
    async def nested(depth):
        if depth == 0:
            return "Done"
        child = DeferredTask(loop_name).start_task(nested, depth - 1)
        tasks.append(child)
        return await child.result_async(timeout=3)
    task = DeferredTask(loop_name)
    tasks.append(task)
    # An executor with just one thread would deadlock on the second nesting
    # level if a result waiter consumed a worker.
    pool = ThreadPoolExecutor(max_workers=1)
    task.event_loop_thread.loop.call_soon_threadsafe(task.event_loop_thread.loop.set_default_executor, pool)
    try:
        task.start_task(nested, 40)
        assert task.result_sync(timeout=5) == "Done"
    finally:
        task.kill(terminate_thread=True)
        pool.shutdown(wait=True)


def test_nonblocking_result_timeout_does_not_cancel_owned_task():
    task = make_task()
    release = threading.Event()
    async def child():
        while not release.is_set():
            await asyncio.sleep(.01)
        return "Done"
    async def exercise():
        with pytest.raises(TimeoutError):
            await task.result_async(timeout=.01)
        assert task.is_alive()
        release.set()
        assert await task.result_async(timeout=2) == "Done"
    try:
        task.start_task(child)
        asyncio.run(exercise())
    finally:
        release.set()
        task.kill(terminate_thread=True)
