import asyncio
import json
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from plugins._browser.helpers import runtime as runtime_module
from plugins._browser.helpers.config import normalize_browser_config
from plugins._browser.helpers.runtime import BrowserPage, BrowserRuntime, _BrowserRuntimeCore
from plugins._browser.tools.browser import Browser


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["list", "list_all"])
@pytest.mark.parametrize("restorable", [False, True])
async def test_listing_only_starts_cold_browser_when_tabs_need_restoring(monkeypatch, method, restorable):
    core = _BrowserRuntimeCore("listing-test")
    started = AsyncMock()
    monkeypatch.setattr(core, "ensure_started", started)
    monkeypatch.setattr(runtime_module, "has_restorable_browser_tabs", lambda context_id: restorable)

    assert (await getattr(core, method)())["browsers"] == []
    assert started.await_count == int(restorable)


@pytest.mark.asyncio
@pytest.mark.parametrize("wait_until", ["commit", "domcontentloaded"])
async def test_navigation_uses_requested_readiness_without_extra_settling(monkeypatch, wait_until):
    core = _BrowserRuntimeCore("navigation-test")
    page = SimpleNamespace(
        goto=AsyncMock(), go_back=AsyncMock(), go_forward=AsyncMock(), reload=AsyncMock(),
    )
    core.pages[1] = BrowserPage(1, page, "navigation-test")
    core.context = SimpleNamespace(new_page=AsyncMock(return_value=page))
    monkeypatch.setattr(core, "ensure_started", AsyncMock())
    monkeypatch.setattr(core, "_state", AsyncMock(return_value={"id": 1}))
    monkeypatch.setattr(core, "_register_page", AsyncMock(return_value=core.pages[1]))
    monkeypatch.setattr(core, "_persist_browser_tabs", lambda: None)
    monkeypatch.setattr(core, "_settle", AsyncMock(side_effect=AssertionError("Redundant wait")))
    monkeypatch.setattr(runtime_module, "get_browser_config", lambda: {})

    await core.open("https://example.com", wait_until=wait_until)
    await core.navigate(1, "https://example.com", wait_until=wait_until)
    await core.back(1, wait_until=wait_until)
    await core.forward(1, wait_until=wait_until)
    await core.reload(1, wait_until=wait_until)
    for method in (page.goto, page.go_back, page.go_forward, page.reload):
        assert all(call.kwargs["wait_until"] == wait_until for call in method.await_args_list)
    core._settle.assert_not_awaited()


@pytest.mark.asyncio
async def test_browser_state_reads_metadata_once_and_reports_loading(monkeypatch):
    core = _BrowserRuntimeCore("state-test")
    page = SimpleNamespace(url="https://example.com", evaluate=AsyncMock(return_value={
        "title": "Example", "canGoBack": True, "loading": True, "zoom": 125,
    }))
    core.pages[1] = BrowserPage(1, page, "state-test")
    state = await core._state(1)
    assert state == {
        "id": 1, "context_id": "state-test", "currentUrl": page.url,
        "title": "Example", "canGoBack": True, "canGoForward": False, "loading": True,
        "zoom": 125, "zoom_available": False,
    }
    assert page.evaluate.await_count == 1
    page.evaluate.side_effect = RuntimeError("Execution context destroyed during navigation")
    assert (await core._state(1))["currentUrl"] == page.url


@pytest.mark.asyncio
@pytest.mark.parametrize("action,calls,capture", [
    *[(action, None, False) for action in ("list", "state", "content", "detail", "evaluate", "close", "close_all")],
    ("multi", [{"action": "content"}, {"action": "evaluate", "script": "document.title"}], False),
    ("multi", [{"action": "content"}, {"action": "click", "ref": 1}], True),
    ("screenshot", None, True),
])
async def test_browser_inspection_skips_history_capture_but_preserves_visual_actions(monkeypatch, action, calls, capture):
    from plugins._browser.tools import browser as tool_module

    screenshot = {"browser_id": 1, "ephemeral_ref": "a0-ephemeral-image://test"}
    runtime = SimpleNamespace(call=AsyncMock(side_effect=lambda method, *a, **kw:
        screenshot if method == "screenshot_file" else {}))
    monkeypatch.setattr(tool_module, "get_runtime", AsyncMock(return_value=runtime))
    monkeypatch.setattr(tool_module, "activate_browser_model", lambda agent: None)
    tool = object.__new__(Browser)
    tool.agent = SimpleNamespace(context=SimpleNamespace(id="test"))
    tool.method = ""
    tool.log = SimpleNamespace(update=Mock())

    response = await tool.execute(action=action, browser_id=1, ref=1, script="document.title", calls=calls)

    assert not response.message.startswith("Browser "), response.message
    assert sum(call.args[0] == "screenshot_file" for call in runtime.call.await_args_list) == int(capture)
    assert tool.log.update.call_count == int(capture)


def test_format_result_minifies_tool_json() -> None:
    result = {"browsers": [{"id": "b1", "title": "Example"}]}

    formatted = Browser._format_result("list", result)

    assert "\n" not in formatted
    assert json.loads(formatted) == result


def test_format_result_keeps_content_document_plain() -> None:
    formatted = Browser._format_result("content", {"document": "<html></html>"})

    assert formatted == "<html></html>"


@pytest.mark.asyncio
async def test_evaluate_uses_script_arg(monkeypatch) -> None:
    core = _BrowserRuntimeCore("ctx")
    seen: list[str] = []

    async def fake_evaluate(bid, script):
        seen.append(script)
        return 7

    monkeypatch.setattr(core, "evaluate", fake_evaluate)

    result = await core._dispatch_call({"action": "evaluate", "script": "1+1"})

    assert result == 7
    assert seen == ["1+1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("args", [{"expression": "document.title"}, {}, {"script": " "}, {"script": 42}])
async def test_evaluate_rejects_missing_or_invalid_script(monkeypatch, args) -> None:
    core = _BrowserRuntimeCore("ctx")
    started = AsyncMock()
    monkeypatch.setattr(core, "ensure_started", started)
    with pytest.raises(ValueError, match="non-empty 'script'"):
        await core._dispatch_call({"action": "evaluate", **args})
    result = await core.multi([{"action": "evaluate", **args}])
    assert result == [{"ok": False, "error": "evaluate requires a non-empty 'script' string"}]
    started.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [2, None, False, 0, {"answer": 42}])
async def test_evaluate_preserves_javascript_results(monkeypatch, value) -> None:
    core, page, session = _evaluate_runtime(monkeypatch)
    page.evaluate.return_value = value
    script = "() => " + json.dumps(value)
    result = await core.evaluate(3, script)
    assert result == {"result": value, "state": {"id": 3}}
    page.evaluate.assert_awaited_once_with(script, isolated_context=False)
    session.detach.assert_awaited_once()
    session.send.assert_not_awaited()


def _evaluate_runtime(monkeypatch, timeout=0.1):
    core = _BrowserRuntimeCore("evaluate-test")
    session = SimpleNamespace(send=AsyncMock(), detach=AsyncMock())
    page = SimpleNamespace(
        evaluate=AsyncMock(return_value=2),
        context=SimpleNamespace(new_cdp_session=AsyncMock(return_value=session)),
        reload=AsyncMock(), close=AsyncMock(), is_closed=lambda: False,
    )
    core.pages[3] = BrowserPage(3, page, "evaluate-test")
    monkeypatch.setattr(core, "ensure_started", AsyncMock())
    monkeypatch.setattr(core, "_state", AsyncMock(return_value={"id": 3}))
    monkeypatch.setattr(core, "_persist_browser_tabs", lambda: None)
    monkeypatch.setattr(runtime_module, "get_browser_config", lambda agent=None: {
        "evaluate_timeout_seconds": timeout,
    })
    return core, page, session


def _hang_until_recovery(page):
    started, stopped = asyncio.Event(), asyncio.Event()
    operations = []

    async def evaluate(script, **kwargs):
        if script != "hang":
            return 2
        operations.append(asyncio.current_task())
        started.set()
        # Independently bounded even if the production deadline is removed.
        try:
            await asyncio.wait_for(stopped.wait(), 1)
        except asyncio.TimeoutError:
            raise RuntimeError("Fake backend watchdog expired") from None
        raise RuntimeError("Execution context destroyed")

    async def recover(**kwargs):
        stopped.set()

    page.evaluate.side_effect = evaluate
    page.reload.side_effect = recover
    page.close.side_effect = recover
    return started, stopped, operations


@pytest.mark.asyncio
async def test_evaluate_timeout_recovers_and_multi_continues(monkeypatch):
    core, page, session = _evaluate_runtime(monkeypatch)
    _, stopped, operations = _hang_until_recovery(page)
    pending_before = asyncio.all_tasks()
    result = await asyncio.wait_for(core.multi([
        {"action": "evaluate", "browser_id": 3, "script": "hang"},
        {"action": "evaluate", "browser_id": 3, "script": "1+1"},
    ]), 2)
    assert result == [
        {"ok": False, "error": "evaluate timed out after 0.1 seconds; affected tab reloaded to cancel pending JavaScript"},
        {"ok": True, "result": {"result": 2, "state": {"id": 3}}},
    ]
    session.send.assert_awaited_once_with("Runtime.terminateExecution")
    assert stopped.is_set() and all(task.done() for task in operations)
    assert not core.pages[3].evaluate_lock.locked()
    assert not (asyncio.all_tasks() - pending_before)
    assert session.detach.await_count == 2
    page.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_evaluate_timeout_is_non_breaking_tool_error(monkeypatch):
    from plugins._browser.tools import browser as tool_module

    core, page, _ = _evaluate_runtime(monkeypatch)
    _hang_until_recovery(page)
    tool = object.__new__(Browser)
    tool.agent = SimpleNamespace(context=SimpleNamespace(id="evaluate-test"))
    tool.method = ""
    monkeypatch.setattr(tool_module, "activate_browser_model", lambda agent: None)
    monkeypatch.setattr(tool_module, "get_runtime", AsyncMock(return_value=SimpleNamespace(
        call=None,
    )))

    async def call(method, *args, **kwargs):
        return await getattr(core, method)(*args, **kwargs)

    tool_module.get_runtime.return_value.call = call
    result = await asyncio.wait_for(tool.execute(action="evaluate", browser_id=3, script="hang"), 2)
    assert result.break_loop is False
    assert result.message == "Browser evaluate failed: evaluate timed out after 0.1 seconds; affected tab reloaded to cancel pending JavaScript"


@pytest.mark.asyncio
@pytest.mark.parametrize("caller_cancel", [False, True])
async def test_confirmed_evaluate_interruption_preserves_page(monkeypatch, caller_cancel):
    core, page, session = _evaluate_runtime(monkeypatch)
    started, stopped, operations = _hang_until_recovery(page)
    session.send.side_effect = lambda method: stopped.set()
    task = asyncio.create_task(core.evaluate(3, "hang"))
    await asyncio.wait_for(started.wait(), 1)
    if caller_cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if caller_cancel else TimeoutError) as error:
        await asyncio.wait_for(task, 2)
    if not caller_cancel:
        assert str(error.value) == "evaluate timed out after 0.1 seconds"
    page.reload.assert_not_awaited()
    page.close.assert_not_awaited()
    session.detach.assert_awaited_once()
    assert core.pages[3].page is page
    assert all(operation.done() and not operation.cancelled() for operation in operations)
    assert (await core.evaluate(3, "1+1"))["result"] == 2


@pytest.mark.asyncio
async def test_evaluate_stuck_recovery_is_bounded(monkeypatch):
    core, page, session = _evaluate_runtime(monkeypatch)
    _hang_until_recovery(page)
    monkeypatch.setattr(runtime_module, "EVALUATE_RECOVERY_TIMEOUT_SECONDS", 0.03)
    monkeypatch.setattr(runtime_module, "EVALUATE_TERMINATION_GRACE_SECONDS", 0.005)

    async def stuck_reload(**kwargs):
        await asyncio.sleep(1)

    page.reload.side_effect = stuck_reload
    with pytest.raises(TimeoutError, match="0.1 seconds"):
        await asyncio.wait_for(core.evaluate(3, "hang"), 0.5)
    page.close.assert_awaited_once()
    session.detach.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_wait_timeout_is_not_proof_of_javascript_cancellation(monkeypatch):
    core, page, session = _evaluate_runtime(monkeypatch)
    page.evaluate.side_effect = asyncio.TimeoutError
    with pytest.raises(TimeoutError, match="reloaded to cancel pending JavaScript"):
        await core.evaluate(3, "hang")
    session.send.assert_awaited_once_with("Runtime.terminateExecution")
    page.reload.assert_awaited_once()


@pytest.mark.asyncio
async def test_evaluate_caller_cancellation_recovers_before_return(monkeypatch):
    core, page, session = _evaluate_runtime(monkeypatch)
    started, stopped, operations = _hang_until_recovery(page)
    task = asyncio.create_task(core.evaluate(3, "hang"))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 2)
    assert stopped.is_set() and all(task.done() for task in operations)
    session.send.assert_awaited_once_with("Runtime.terminateExecution")
    session.detach.assert_awaited_once()
    assert not core.pages[3].evaluate_lock.locked()
    assert (await core.evaluate(3, "1+1"))["result"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("closed", [False, True])
async def test_evaluate_javascript_or_closed_page_error_is_preserved(monkeypatch, closed):
    core, page, session = _evaluate_runtime(monkeypatch)
    page.is_closed = lambda: closed
    page.evaluate.side_effect = RuntimeError("page closed" if closed else "script error")
    with pytest.raises(RuntimeError, match="page closed" if closed else "script error"):
        await core.evaluate(3, "1+1")
    page.reload.assert_not_awaited()
    session.send.assert_not_awaited()
    session.detach.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("close_fails", [False, True])
async def test_evaluate_recovery_failure_closes_only_affected_page(monkeypatch, close_fails):
    core, page, session = _evaluate_runtime(monkeypatch)
    _, _, operations = _hang_until_recovery(page)
    unrelated = BrowserPage(4, SimpleNamespace(), "other-chat")
    core.pages[4] = unrelated
    page.reload.side_effect = RuntimeError("reload failed")
    if close_fails:
        page.close.side_effect = RuntimeError("close failed")
    with pytest.raises(TimeoutError, match="evaluate timed out after 0.1 seconds") as error:
        await asyncio.wait_for(core.evaluate(3, "hang"), 2)
    assert ("recovery failed" in str(error.value)) is close_fails
    assert (3 in core.pages) is close_fails
    assert core.pages[4] is unrelated
    page.close.assert_awaited_once_with(run_before_unload=False)
    assert all(task.done() for task in operations)
    session.detach.assert_awaited_once()


@pytest.mark.parametrize("value", [0, -1, True, None, "", "bad", "nan", "inf", float("nan"), float("inf"), 0.09, 60.1])
def test_evaluate_timeout_rejects_invalid_settings(value):
    with pytest.raises(ValueError, match="between 0.1 and 60 seconds"):
        normalize_browser_config({"evaluate_timeout_seconds": value})


def test_evaluate_timeout_defaults_and_numeric_strings():
    assert normalize_browser_config({})["evaluate_timeout_seconds"] == 30
    assert normalize_browser_config({"evaluate_timeout_seconds": "0.1"})["evaluate_timeout_seconds"] == 0.1
    assert normalize_browser_config({"evaluate_timeout_seconds": 60})["evaluate_timeout_seconds"] == 60


@pytest.mark.asyncio
async def test_browser_worker_propagates_cancellation_and_waits_for_cleanup(monkeypatch):
    runtime = BrowserRuntime("evaluate-worker-test")
    loop = asyncio.get_running_loop()
    started = loop.create_future()
    cleaned = []

    async def work():
        loop.call_soon_threadsafe(started.set_result, None)
        try:
            await asyncio.sleep(1)
        finally:
            await asyncio.sleep(0.01)
            cleaned.append(True)

    monkeypatch.setattr(runtime._core, "evaluate", work)
    try:
        task = asyncio.create_task(runtime.call("evaluate"))
        await asyncio.wait_for(started, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert cleaned == [True]

        async def pending():
            return len([task for task in asyncio.all_tasks() if task is not asyncio.current_task()])

        monkeypatch.setattr(runtime._core, "state", pending)
        assert await runtime.call("state") == 0
    finally:
        runtime._worker.kill(terminate_thread=True)


def _stop_worker_thread(runtime):
    # A worker thread that exits on its own leaves its loop stopped but not closed.
    worker = runtime._worker.event_loop_thread
    worker.loop.call_soon_threadsafe(worker.loop.stop)
    worker.thread.join(2)
    assert not worker.thread.is_alive()


async def _dispose_worker(runtime, *tasks):
    # Rerun a stopped loop so stranded work drains and no caller outlives the test.
    worker = runtime._worker.event_loop_thread
    if worker.thread is not None and not worker.thread.is_alive():
        worker.thread = threading.Thread(target=worker.loop.run_forever, daemon=True)
        worker.thread.start()
    tasks = [task for task in tasks if task is not None]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.wait(tasks, timeout=5)
    runtime._worker.kill(terminate_thread=True)


def _hanging_navigate(monkeypatch, runtime, cleanup_seconds=0.0):
    loop = asyncio.get_running_loop()
    started = loop.create_future()
    cleaned = []

    async def navigate():
        loop.call_soon_threadsafe(started.set_result, None)
        try:
            await asyncio.sleep(60)
        finally:
            await asyncio.sleep(cleanup_seconds)
            cleaned.append(True)

    monkeypatch.setattr(runtime._core, "navigate", navigate)
    return started, cleaned


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["before_call", "during_call", "cancelled"])
async def test_browser_call_ends_when_worker_thread_stops(monkeypatch, case):
    # before_call must fail before dispatch, not through the liveness poll.
    poll = 60 if case == "before_call" else 0.05
    monkeypatch.setattr(runtime_module, "WORKER_LIVENESS_POLL_SECONDS", poll, raising=False)
    runtime = BrowserRuntime(f"stopped-worker-test-{case}")
    started, _ = _hanging_navigate(monkeypatch, runtime)
    call = None
    try:
        if case != "before_call":
            call = asyncio.create_task(runtime.call("navigate"))
            await asyncio.wait_for(started, 2)
        _stop_worker_thread(runtime)
        if case == "before_call":
            call = asyncio.create_task(runtime.call("navigate"))
        elif case == "cancelled":
            call.cancel()
        done, _ = await asyncio.wait({call}, timeout=2)
        assert done, "a call on a stopped Browser worker never returned"
        if case == "cancelled":
            assert call.cancelled()
        else:
            with pytest.raises(RuntimeError, match="Browser worker stopped before 'navigate' finished"):
                call.result()
        assert started.done() == (case != "before_call")
    finally:
        await _dispose_worker(runtime, call)


@pytest.mark.asyncio
async def test_browser_call_cancelled_by_runtime_close_is_an_error(monkeypatch):
    runtime = BrowserRuntime("closed-during-call-test")
    started, _ = _hanging_navigate(monkeypatch, runtime)
    monkeypatch.setattr(runtime._core, "close", AsyncMock())
    call = asyncio.create_task(runtime.call("navigate"))
    try:
        await asyncio.wait_for(started, 2)
        # Settings saves, extension installs and shutdown close the runtime mid-call.
        await asyncio.wait_for(runtime.close(), 5)
        done, _ = await asyncio.wait({call}, timeout=2)
        assert done, "a call interrupted by a runtime close never returned"
        assert not call.cancelled()
        with pytest.raises(RuntimeError, match="Browser worker cancelled 'navigate'"):
            call.result()
    finally:
        await _dispose_worker(runtime, call)


@pytest.mark.asyncio
async def test_cancelling_a_call_behind_a_blocked_worker_is_bounded_and_never_runs_it(monkeypatch):
    monkeypatch.setattr(runtime_module, "WORKER_LIVENESS_POLL_SECONDS", 0.05, raising=False)
    monkeypatch.setattr(runtime_module, "WORKER_CANCEL_START_TIMEOUT_SECONDS", 0.2, raising=False)
    warnings = []
    monkeypatch.setattr(runtime_module.PrintStyle, "warning", warnings.append)
    runtime = BrowserRuntime("blocked-worker-test")
    clicked = []

    async def click():
        clicked.append(True)

    async def state():
        return "state"

    monkeypatch.setattr(runtime._core, "click", click)
    monkeypatch.setattr(runtime._core, "state", state)
    blocked, release = threading.Event(), threading.Event()

    def block():
        blocked.set()
        release.wait(10)

    # A synchronous step, such as first-run setup, blocks the live worker loop.
    runtime._worker.event_loop_thread.loop.call_soon_threadsafe(block)
    assert blocked.wait(2)
    call = asyncio.create_task(runtime.call("click"))
    try:
        await asyncio.sleep(0.05)
        call.cancel()
        done, _ = await asyncio.wait({call}, timeout=2)
        assert done and call.cancelled()
        assert len(warnings) == 1 and "'click' cancellation was not confirmed" in warnings[0]
        release.set()
        assert await asyncio.wait_for(runtime.call("state"), 2) == "state"
        assert clicked == []
    finally:
        release.set()
        await _dispose_worker(runtime, call)


@pytest.mark.asyncio
async def test_started_worker_cleanup_is_awaited_past_the_response_bound(monkeypatch):
    monkeypatch.setattr(runtime_module, "WORKER_LIVENESS_POLL_SECONDS", 0.05, raising=False)
    monkeypatch.setattr(runtime_module, "WORKER_CANCEL_START_TIMEOUT_SECONDS", 0.1, raising=False)
    runtime = BrowserRuntime("slow-cleanup-test")
    started, cleaned = _hanging_navigate(monkeypatch, runtime, cleanup_seconds=0.5)
    call = asyncio.create_task(runtime.call("navigate"))
    try:
        await asyncio.wait_for(started, 2)
        call.cancel()
        await asyncio.sleep(0.2)
        call.cancel()
        done, _ = await asyncio.wait({call}, timeout=3)
        assert done and call.cancelled()
        assert cleaned == [True]
    finally:
        await _dispose_worker(runtime, call)


@pytest.mark.asyncio
async def test_cancelled_call_ends_when_worker_thread_stops_during_cleanup(monkeypatch):
    monkeypatch.setattr(runtime_module, "WORKER_LIVENESS_POLL_SECONDS", 0.05, raising=False)
    runtime = BrowserRuntime("stopped-during-cleanup-test")
    loop = asyncio.get_running_loop()
    started, cleaning = loop.create_future(), loop.create_future()

    async def navigate():
        loop.call_soon_threadsafe(started.set_result, None)
        try:
            await asyncio.sleep(60)
        finally:
            loop.call_soon_threadsafe(cleaning.set_result, None)
            await asyncio.sleep(60)

    monkeypatch.setattr(runtime._core, "navigate", navigate)
    call = asyncio.create_task(runtime.call("navigate"))
    try:
        await asyncio.wait_for(started, 2)
        call.cancel()
        await asyncio.wait_for(cleaning, 2)
        _stop_worker_thread(runtime)
        done, _ = await asyncio.wait({call}, timeout=2)
        assert done, "a cancelled call stayed wedged after the worker stopped during cleanup"
        assert call.cancelled()
    finally:
        await _dispose_worker(runtime, call)


@pytest.mark.asyncio
async def test_uncancelled_call_waits_out_a_blocked_worker_loop(monkeypatch):
    monkeypatch.setattr(runtime_module, "WORKER_LIVENESS_POLL_SECONDS", 0.05, raising=False)
    monkeypatch.setattr(runtime_module, "WORKER_CANCEL_START_TIMEOUT_SECONDS", 0.1, raising=False)
    warnings = []
    monkeypatch.setattr(runtime_module.PrintStyle, "warning", warnings.append)
    runtime = BrowserRuntime("slow-setup-test")

    async def state():
        return "state"

    monkeypatch.setattr(runtime._core, "state", state)
    blocked = threading.Event()

    def block():
        blocked.set()
        threading.Event().wait(0.5)

    # First-run setup blocks the live worker loop past every poll and cancel bound.
    runtime._worker.event_loop_thread.loop.call_soon_threadsafe(block)
    assert blocked.wait(2)
    try:
        assert await asyncio.wait_for(runtime.call("state"), 3) == "state"
        assert warnings == []
    finally:
        await _dispose_worker(runtime)


@pytest.mark.asyncio
async def test_browser_cleanup_and_restart_work_after_worker_thread_stops(monkeypatch):
    warnings = []
    monkeypatch.setattr(runtime_module.PrintStyle, "warning", warnings.append)
    monkeypatch.setattr(runtime_module, "_runtimes", {})
    monkeypatch.setattr(runtime_module, "_shared_runtime", None)
    monkeypatch.setattr(runtime_module, "_forget_browser_context", lambda context_id: None)
    for method in ("state", "close_context", "close"):
        monkeypatch.setattr(_BrowserRuntimeCore, method, AsyncMock(return_value=method))
    await runtime_module.get_runtime("stopped-worker-chat")
    stopped = runtime_module._shared_runtime
    try:
        _stop_worker_thread(stopped)
        # Chat reset/removal, then a settings save that restarts the Browser.
        await asyncio.wait_for(asyncio.to_thread(runtime_module.close_runtime_sync, "stopped-worker-chat"), 5)
        await asyncio.wait_for(asyncio.to_thread(runtime_module.close_all_runtimes_sync), 5)
        assert len(warnings) == 2 and all("Browser worker stopped" in warning for warning in warnings)
        session = await runtime_module.get_runtime("stopped-worker-chat")
        assert runtime_module._shared_runtime is not stopped
        assert await asyncio.wait_for(session.call("state"), 2) == "state"
    finally:
        await _dispose_worker(stopped)
        if runtime_module._shared_runtime is not None:
            runtime_module._shared_runtime._worker.kill(terminate_thread=True)


def test_webui_beautifier_formats_objects_and_arrays() -> None:
    source = (
        PROJECT_ROOT
        / "plugins"
        / "_browser"
        / "extensions"
        / "webui"
        / "get_tool_message_handler"
        / "browser-tool-handler.js"
    ).read_text(encoding="utf-8")
    start = source.index("function beautifyJsonForDisplay")
    end = source.index("\n}", start) + 2
    object_literal = json.dumps({"browsers": [{"id": 1}]})
    array_literal = json.dumps([{"id": 1}, {"id": 2}])
    script = (
        source[start:end]
        + "\nconst pretty = beautifyJsonForDisplay(" + json.dumps(object_literal) + ");\n"
        + "if (!pretty.includes('\\n')) throw new Error('object JSON was not beautified');\n"
        + "if (pretty !== " + json.dumps(json.dumps({"browsers": [{"id": 1}]}, indent=2)) + ") throw new Error('object JSON content changed');\n"
        + "const arrayPretty = beautifyJsonForDisplay(" + json.dumps(array_literal) + ");\n"
        + "if (!arrayPretty.includes('\\n')) throw new Error('array JSON was not beautified');\n"
        + "if (JSON.parse(arrayPretty).length !== 2) throw new Error('array content changed');\n"
        + "const padded = beautifyJsonForDisplay('  ' + " + json.dumps(json.dumps({"a": 1})) + "  );\n"
        + "if (padded !== " + json.dumps('{\n  "a": 1\n}') + ") throw new Error('padded JSON was not trimmed');\n"
        + "if (beautifyJsonForDisplay('plain document') !== 'plain document') throw new Error('plain text changed');\n"
        + "if (beautifyJsonForDisplay('{broken') !== '{broken') throw new Error('invalid JSON changed');\n"
    )

    subprocess.run(["node", "--input-type=module", "-e", script], check=True, text=True)
