from __future__ import annotations

import atexit
import asyncio
import base64
import contextlib
import contextvars
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from helpers import chat_media, files, kvp
from helpers.defer import DeferredTask
from helpers.errors import RepairableException
from helpers.print_style import PrintStyle

from plugins._browser.helpers.config import (
    DEFAULT_BROWSER_TAB_SCOPE,
    DEFAULT_HOMEPAGE_KEY,
    DEFAULT_MAX_OPEN_TABS,
    DEFAULT_EVALUATE_TIMEOUT_SECONDS,
    EVALUATE_TIMEOUT_KEY,
    MAX_OPEN_TABS_KEY,
    TAB_SCOPE_KEY,
    build_browser_launch_config,
    get_browser_config,
    normalize_evaluate_timeout,
)
from plugins._browser.helpers.interactive_view import BrowserInteractiveView
from plugins._browser.helpers.url import normalize_url


PLUGIN_DIR = Path(__file__).resolve().parents[1]
DOM_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-dom-helper.js"
CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"
RUNTIME_DATA_KEY = "_browser_runtime"
SHARED_RUNTIME_ID = "shared"
BROWSER_TABS_KEY = "browser_open_tabs"
BROWSER_TABS_VERSION = 1
DEFAULT_VIEWPORT = {"width": 1024, "height": 768}
CHROME_SINGLETON_FILES = ("SingletonLock", "SingletonCookie", "SingletonSocket")
SCREENCAST_MAX_WIDTH = 4096
SCREENCAST_MAX_HEIGHT = 4096
VIEWPORT_SIZE_TOLERANCE = 4
EVALUATE_RECOVERY_TIMEOUT_SECONDS = 5.0
EVALUATE_TERMINATION_GRACE_SECONDS = 0.25
WORKER_LIVENESS_POLL_SECONDS = 1.0
WORKER_CANCEL_START_TIMEOUT_SECONDS = 15.0
WORKER_STOPPED_ERROR = (
    "Browser worker stopped before {method!r} finished; retry the call, and if it fails "
    "again, restart Agent Zero or change Browser proxy, keyboard or extension settings."
)
CLIPBOARD_BRIDGE_SCRIPT = r"""
(payload) => {
  const action = String(payload?.action || "").trim().toLowerCase();
  const text = String(payload?.text || "");
  const result = {
    action,
    text: "",
    changed: false,
    default_prevented: false,
    handled: false,
    method: "dom",
  };
  const textInputTypes = new Set([
    "",
    "email",
    "number",
    "password",
    "search",
    "tel",
    "text",
    "url",
  ]);

  function deepestActiveElement() {
    let active = document.activeElement || document.body || document.documentElement;
    while (active?.shadowRoot?.activeElement) {
      active = active.shadowRoot.activeElement;
    }
    return active || document.body || document.documentElement;
  }

  function editableTarget(element) {
    if (!element) return null;
    if (isTextControl(element) || element.isContentEditable) return element;
    const closest = element.closest?.("input, textarea, [contenteditable]");
    if (closest && (isTextControl(closest) || closest.isContentEditable)) return closest;
    return element;
  }

  function isTextControl(element) {
    if (!element) return false;
    const tagName = String(element.tagName || "").toLowerCase();
    if (tagName === "textarea") {
      return !element.disabled && !element.readOnly;
    }
    if (tagName !== "input") return false;
    const type = String(element.type || "text").toLowerCase();
    return textInputTypes.has(type) && !element.disabled && !element.readOnly;
  }

  function selectedText(element) {
    if (isTextControl(element)) {
      try {
        const start = Number(element.selectionStart);
        const end = Number(element.selectionEnd);
        if (Number.isFinite(start) && Number.isFinite(end) && end > start) {
          return String(element.value || "").slice(start, end);
        }
      } catch {}
      return "";
    }
    const selection = globalThis.getSelection?.();
    return selection ? String(selection.toString() || "") : "";
  }

  function makeClipboardData(seedText = "") {
    let transfer = null;
    try {
      transfer = new DataTransfer();
    } catch {}
    if (transfer && seedText) {
      transfer.setData("text/plain", seedText);
      transfer.setData("text", seedText);
    }
    return transfer;
  }

  function clipboardDataText(transfer) {
    if (!transfer) return "";
    return String(transfer.getData("text/plain") || transfer.getData("text") || "");
  }

  function makeClipboardEvent(type, transfer) {
    let event = null;
    try {
      event = new ClipboardEvent(type, {
        bubbles: true,
        cancelable: true,
        clipboardData: transfer,
      });
    } catch {}
    if (!event) {
      event = new Event(type, { bubbles: true, cancelable: true });
    }
    if (transfer && !event.clipboardData) {
      try {
        Object.defineProperty(event, "clipboardData", { value: transfer });
      } catch {}
    }
    return event;
  }

  function dispatchClipboardEvent(target, type, seedText = "") {
    const transfer = makeClipboardData(seedText);
    const event = makeClipboardEvent(type, transfer);
    (target || document.body || document.documentElement).dispatchEvent(event);
    return {
      defaultPrevented: Boolean(event.defaultPrevented),
      text: clipboardDataText(event.clipboardData || transfer),
    };
  }

  function dispatchInputEvent(element, type, inputType, data = null) {
    let event = null;
    try {
      event = new InputEvent(type, {
        bubbles: true,
        cancelable: type === "beforeinput",
        inputType,
        data,
      });
    } catch {}
    if (!event) {
      event = new Event(type, {
        bubbles: true,
        cancelable: type === "beforeinput",
      });
    }
    return element.dispatchEvent(event);
  }

  function insertIntoTextControl(element, value) {
    if (!isTextControl(element)) return false;
    let start = 0;
    let end = 0;
    try {
      start = Number(element.selectionStart);
      end = Number(element.selectionEnd);
    } catch {
      return false;
    }
    if (!Number.isFinite(start) || !Number.isFinite(end)) return false;
    if (!dispatchInputEvent(element, "beforeinput", "insertFromPaste", value)) {
      return false;
    }
    element.setRangeText(value, start, end, "end");
    dispatchInputEvent(element, "input", "insertFromPaste", value);
    return true;
  }

  function insertIntoContentEditable(element, value) {
    if (!element?.isContentEditable) return false;
    if (!dispatchInputEvent(element, "beforeinput", "insertFromPaste", value)) {
      return false;
    }
    const selection = globalThis.getSelection?.();
    if (!selection || selection.rangeCount === 0) return false;
    try {
      if (document.queryCommandSupported?.("insertText") && document.execCommand("insertText", false, value)) {
        return true;
      }
    } catch {}
    const range = selection.getRangeAt(0);
    range.deleteContents();
    const node = document.createTextNode(value);
    range.insertNode(node);
    range.setStartAfter(node);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    dispatchInputEvent(element, "input", "insertFromPaste", value);
    return true;
  }

  function insertText(element, value) {
    return insertIntoTextControl(element, value) || insertIntoContentEditable(element, value);
  }

  function removeSelectedText(element) {
    if (isTextControl(element)) {
      let start = 0;
      let end = 0;
      try {
        start = Number(element.selectionStart);
        end = Number(element.selectionEnd);
      } catch {
        return false;
      }
      if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return false;
      if (!dispatchInputEvent(element, "beforeinput", "deleteByCut", null)) {
        return false;
      }
      element.setRangeText("", start, end, "start");
      dispatchInputEvent(element, "input", "deleteByCut", null);
      return true;
    }
    if (!element?.isContentEditable) return false;
    const selection = globalThis.getSelection?.();
    if (!selection || selection.rangeCount === 0 || !String(selection.toString() || "")) {
      return false;
    }
    if (!dispatchInputEvent(element, "beforeinput", "deleteByCut", null)) {
      return false;
    }
    selection.deleteFromDocument();
    dispatchInputEvent(element, "input", "deleteByCut", null);
    return true;
  }

  const target = editableTarget(deepestActiveElement());
  if (action === "paste") {
    const event = dispatchClipboardEvent(target, "paste", text);
    result.default_prevented = event.defaultPrevented;
    result.handled = true;
    result.text = text;
    if (!event.defaultPrevented) {
      result.changed = insertText(target, text);
    }
    return result;
  }

  if (action === "copy" || action === "cut") {
    const selectionText = selectedText(target);
    const event = dispatchClipboardEvent(target, action, selectionText);
    result.default_prevented = event.defaultPrevented;
    result.text = event.text || selectionText;
    result.handled = Boolean(result.text || event.defaultPrevented);
    if (action === "cut" && result.text && !event.defaultPrevented) {
      result.changed = removeSelectedText(target);
    }
    return result;
  }

  result.error = `Unsupported clipboard action: ${action}`;
  return result;
}
"""

_SAFE_CONTEXT_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


def _safe_context_id(context_id: str) -> str:
    return _SAFE_CONTEXT_RE.sub("_", str(context_id or "default")).strip("._") or "default"


def _load_browser_tabs() -> tuple[bool, list[dict[str, Any]]]:
    try:
        payload = kvp.get_persistent(BROWSER_TABS_KEY, None)
    except Exception as exc:
        PrintStyle.warning(f"Browser tab recovery state could not be read: {exc}")
        return False, []
    if payload is None:
        return False, []
    if not isinstance(payload, dict) or not isinstance(payload.get("tabs"), list):
        PrintStyle.warning("Browser tab recovery state is invalid; starting without it.")
        return False, []

    tabs: list[dict[str, Any]] = []
    for entry in payload["tabs"]:
        if not isinstance(entry, dict):
            continue
        context_id = str(entry.get("context_id") or "").strip()
        url = str(entry.get("url") or "").strip()
        if not context_id or not url:
            continue
        tabs.append(
            {
                "context_id": context_id,
                "url": url,
                "active": bool(entry.get("active")),
            }
        )
    return True, tabs


def _save_browser_tabs(tabs: list[dict[str, Any]]) -> None:
    kvp.set_persistent(
        BROWSER_TABS_KEY,
        {"version": BROWSER_TABS_VERSION, "tabs": tabs},
    )


def _forget_browser_context(context_id: str) -> None:
    exists, tabs = _load_browser_tabs()
    if not exists:
        return
    remaining = [entry for entry in tabs if entry["context_id"] != context_id]
    if len(remaining) != len(tabs):
        try:
            _save_browser_tabs(remaining)
        except Exception as exc:
            PrintStyle.warning(f"Browser tab recovery state could not be updated: {exc}")


def has_restorable_browser_tabs(context_id: str) -> bool:
    exists, tabs = _load_browser_tabs()
    if not exists:
        for runtime_id in (SHARED_RUNTIME_ID, _safe_context_id(context_id)):
            session_dir = Path(
                files.get_abs_path(
                    "tmp",
                    "browser",
                    "sessions",
                    runtime_id,
                    "Default",
                    "Sessions",
                )
            )
            try:
                if any(session_dir.glob("Session_*")) or any(session_dir.glob("Tabs_*")):
                    return True
            except OSError:
                continue
        return False
    if not tabs:
        return False
    if str(
        get_browser_config().get(TAB_SCOPE_KEY, DEFAULT_BROWSER_TAB_SCOPE)
        or DEFAULT_BROWSER_TAB_SCOPE
    ) == "shared":
        return True
    return any(entry["context_id"] == str(context_id) for entry in tabs)


@dataclass
class BrowserPage:
    id: int
    page: Any
    context_id: str = ""
    evaluate_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class _BrowserScreencast:
    def __init__(
        self,
        *,
        stream_id: str,
        browser_id: int,
        session: Any,
        mime: str,
    ):
        self.id = stream_id
        self.browser_id = browser_id
        self.session = session
        self.mime = mime
        self.frame_consumer: Any | None = None
        self.stop_callback: Any | None = None
        self.queue = asyncio.Queue(maxsize=1)
        self.stopped = False
        self._closed = False
        self._ack_tasks: set[asyncio.Task] = set()
        self._expected_width = 0
        self._expected_height = 0

    async def start(
        self,
        *,
        quality: int,
        every_nth_frame: int,
        viewport: dict[str, int],
        capture_scale: float = 1.0,
    ) -> None:
        self.session.on("Page.screencastFrame", self._on_frame)
        width = max(320, min(4096, int(viewport.get("width") or DEFAULT_VIEWPORT["width"])))
        height = max(200, min(4096, int(viewport.get("height") or DEFAULT_VIEWPORT["height"])))
        scale = max(1.0, min(2.0, float(capture_scale or 1.0)))
        max_width = max(320, min(SCREENCAST_MAX_WIDTH, int(round(width * scale))))
        max_height = max(200, min(SCREENCAST_MAX_HEIGHT, int(round(height * scale))))
        self._expected_width = width
        self._expected_height = height
        with contextlib.suppress(Exception):
            await self.session.send("Page.enable")
        await self._apply_cdp_viewport({"width": width, "height": height})
        await self.session.send(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": max(20, min(95, int(quality))),
                "maxWidth": max_width,
                "maxHeight": max_height,
                "everyNthFrame": max(1, int(every_nth_frame)),
            },
        )

    async def _apply_cdp_viewport(self, viewport: dict[str, int]) -> None:
        width = max(320, min(4096, int(viewport.get("width") or DEFAULT_VIEWPORT["width"])))
        height = max(200, min(4096, int(viewport.get("height") or DEFAULT_VIEWPORT["height"])))
        await self.session.send(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": 1,
                "mobile": False,
                "dontSetVisibleSize": True,
            },
        )
        with contextlib.suppress(Exception):
            await self.session.send(
                "Emulation.setVisibleSize",
                {
                    "width": width,
                    "height": height,
                },
            )

    async def next_frame(self, timeout: float = 1.0) -> dict[str, Any]:
        frame = await asyncio.wait_for(self.queue.get(), timeout=max(0.1, float(timeout)))
        if frame is None:
            raise RuntimeError("Browser screencast stopped.")
        return frame

    async def pop_frame(self) -> dict[str, Any] | None:
        try:
            frame = self.queue.get_nowait()
        except asyncio.QueueEmpty:
            return None
        if frame is None:
            raise RuntimeError("Browser screencast stopped.")
        return frame

    async def attach_consumer(self, frame_consumer: Any, stop_callback: Any | None = None) -> None:
        self.frame_consumer = frame_consumer
        self.stop_callback = stop_callback
        frame = await self.pop_frame()
        if frame:
            await self._deliver_frame(frame)

    async def stop(self) -> None:
        if self._closed:
            return
        was_stopped = self.stopped
        self._closed = True
        self.stopped = True
        if not was_stopped:
            self._notify_stopped()
        self._drop_queued_frames()
        with contextlib.suppress(asyncio.QueueFull):
            self.queue.put_nowait(None)
        with contextlib.suppress(Exception):
            await self.session.send("Page.stopScreencast")
        for task in list(self._ack_tasks):
            task.cancel()
        if self._ack_tasks:
            await asyncio.gather(*self._ack_tasks, return_exceptions=True)
            self._ack_tasks.clear()
        with contextlib.suppress(Exception):
            await self.session.detach()

    def _on_frame(self, params: dict[str, Any]) -> None:
        if self.stopped:
            return
        task = asyncio.create_task(self._handle_frame(params or {}))
        self._ack_tasks.add(task)
        task.add_done_callback(self._ack_tasks.discard)

    async def _handle_frame(self, params: dict[str, Any]) -> None:
        stop_after_ack = False
        notify_stop = False
        try:
            data = params.get("data") or ""
            if data:
                metadata = dict(params.get("metadata") or {})
                size = self._jpeg_size(data)
                if size:
                    metadata["jpegWidth"], metadata["jpegHeight"] = size
                metadata["expectedWidth"] = self._expected_width
                metadata["expectedHeight"] = self._expected_height
                await self._deliver_frame(
                    {
                        "browser_id": self.browser_id,
                        "mime": self.mime,
                        "image": data,
                        "metadata": metadata,
                    }
                )
        except asyncio.CancelledError:
            stop_after_ack = True
        except Exception:
            if self.frame_consumer:
                stop_after_ack = True
                notify_stop = True
            else:
                raise
        finally:
            session_id = params.get("sessionId")
            if session_id is not None and not self.stopped:
                with contextlib.suppress(Exception):
                    await self.session.send(
                        "Page.screencastFrameAck",
                        {"sessionId": int(session_id)},
                    )
            if stop_after_ack:
                self.stopped = True
                if notify_stop:
                    self._notify_stopped()

    def _notify_stopped(self) -> None:
        if not self.stop_callback:
            return
        with contextlib.suppress(Exception):
            self.stop_callback()

    async def _deliver_frame(self, frame: dict[str, Any]) -> None:
        if not self.frame_consumer:
            self._queue_latest(frame)
            return
        future = self.frame_consumer(frame)
        if future is not None:
            await asyncio.wrap_future(future)

    def _queue_latest(self, frame: dict[str, Any]) -> None:
        self._drop_queued_frames()
        with contextlib.suppress(asyncio.QueueFull):
            self.queue.put_nowait(frame)

    @staticmethod
    def _jpeg_size(data: str) -> tuple[int, int] | None:
        try:
            raw = base64.b64decode(data, validate=False)
        except Exception:
            return None
        if len(raw) < 10 or raw[:2] != b"\xff\xd8":
            return None
        index = 2
        standalone_markers = {0x01, *range(0xD0, 0xD8)}
        size_markers = {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }
        while index < len(raw) - 9:
            if raw[index] != 0xFF:
                index += 1
                continue
            while index < len(raw) and raw[index] == 0xFF:
                index += 1
            if index >= len(raw):
                return None
            marker = raw[index]
            index += 1
            if marker in standalone_markers:
                continue
            if index + 2 > len(raw):
                return None
            segment_length = int.from_bytes(raw[index : index + 2], "big")
            if segment_length < 2 or index + segment_length > len(raw):
                return None
            if marker in size_markers and segment_length >= 7:
                height = int.from_bytes(raw[index + 3 : index + 5], "big")
                width = int.from_bytes(raw[index + 5 : index + 7], "big")
                return width, height
            index += segment_length
        return None

    def _drop_queued_frames(self) -> None:
        while True:
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                return


async def run_browser_calls(calls: list[dict[str, Any]], dispatch: Any) -> list[dict[str, Any]]:
    if not isinstance(calls, list) or not calls:
        raise ValueError("multi requires a non-empty list of calls")
    groups: dict[Any, list[tuple[int, dict[str, Any]]]] = {}
    for idx, call in enumerate(calls):
        if not isinstance(call, dict):
            raise ValueError(f"calls[{idx}] is not an object")
        groups.setdefault(_BrowserRuntimeCore._multi_group_key(call), []).append((idx, call))

    results: list[dict[str, Any]] = [{"ok": False, "error": "missing"} for _ in calls]

    async def run_group(group: list[tuple[int, dict[str, Any]]]) -> None:
        for idx, call in group:
            try:
                results[idx] = {"ok": True, "result": await dispatch(call)}
            except Exception as exc:
                results[idx] = {"ok": False, "error": str(exc)}

    await asyncio.gather(*(run_group(group) for group in groups.values()))
    return results


class BrowserWorkerStoppedError(RuntimeError):
    """The Browser worker thread exited; work sent to its loop never runs or finishes."""


class BrowserRuntime:
    def __init__(self, context_id: str):
        self.context_id = str(context_id)
        self._core = _BrowserRuntimeCore(self.context_id)
        self._worker = DeferredTask(thread_name=f"BrowserRuntime-{self.context_id}")
        self._closed = False

    async def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        return await self.call_for(self.context_id, method, *args, **kwargs)

    async def call_for(
        self,
        context_id: str,
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if self._closed and method != "close":
            raise RuntimeError("Browser runtime is closed.")

        event_loop_thread = self._worker.event_loop_thread
        # terminate() clears the thread and the next dispatch restarts it. A thread that
        # exited on its own leaves a stopped loop that never runs or finishes queued work.
        # A restart assigns the thread before starting it, under the same lock.
        with event_loop_thread._lock:
            thread = event_loop_thread.thread
            stopped = thread is not None and not thread.is_alive()
        if stopped:
            raise BrowserWorkerStoppedError(WORKER_STOPPED_ERROR.format(method=method))

        running_task = None
        cancel_requested = False
        cleanup_started = False

        async def runner():
            nonlocal running_task
            if cancel_requested:
                # The caller stopped waiting while this call was queued behind a blocked loop.
                raise asyncio.CancelledError
            running_task = asyncio.current_task()
            token = self._core.request_context_id.set(str(context_id or self.context_id))
            try:
                fn = getattr(self._core, method)
                return await fn(*args, **kwargs)
            finally:
                self._core.request_context_id.reset(token)

        future = event_loop_thread.run_coroutine(runner())
        worker_thread = event_loop_thread.thread

        def worker_alive() -> bool:
            return worker_thread is not None and worker_thread.is_alive()

        result = asyncio.wrap_future(future)
        try:
            # Like shield(), wait() leaves the worker call running when this caller is
            # cancelled. Legitimate calls may block the worker for minutes (first-run
            # setup), so only a stopped worker thread ends the wait early.
            while not result.done():
                await asyncio.wait({result}, timeout=WORKER_LIVENESS_POLL_SECONDS)
                # Check liveness first: a dead thread runs no more callbacks, so a
                # future still pending after that will never complete.
                if not worker_alive() and not future.done():
                    raise BrowserWorkerStoppedError(WORKER_STOPPED_ERROR.format(method=method))
        except asyncio.CancelledError:
            cancel_requested = True
            if not worker_alive():
                raise

            async def cancel_and_wait():
                nonlocal cleanup_started
                cleanup_started = True
                if running_task is not None:
                    running_task.cancel()
                    await asyncio.gather(running_task, return_exceptions=True)

            cleanup = asyncio.wrap_future(event_loop_thread.run_coroutine(cancel_and_wait()))
            deadline = time.monotonic() + WORKER_CANCEL_START_TIMEOUT_SECONDS
            # Await a started cleanup in full. Stop waiting only when the worker thread
            # stopped or its blocked loop has not started the cancellation in time.
            while not cleanup.done() and worker_alive() and (
                cleanup_started or time.monotonic() < deadline
            ):
                try:
                    await asyncio.wait({cleanup}, timeout=WORKER_LIVENESS_POLL_SECONDS)
                except asyncio.CancelledError:
                    pass
            if cleanup.done():
                await asyncio.gather(result, return_exceptions=True)
            elif worker_alive():
                PrintStyle.warning(
                    f"Browser {method!r} cancellation was not confirmed; the worker loop "
                    f"did not respond within {WORKER_CANCEL_START_TIMEOUT_SECONDS:g} seconds."
                )
            raise
        if result.cancelled():
            # This caller was not cancelled; the worker cancelled the call, e.g. on close.
            raise RuntimeError(f"Browser worker cancelled {method!r} before it finished.")
        return result.result()

    async def close(self, delete_profile: bool = False) -> None:
        if self._closed:
            return
        try:
            await self.call("close", delete_profile=delete_profile)
        finally:
            self._closed = True
            try:
                self._worker.kill(terminate_thread=True)
            finally:
                self._core.interactive_view.close()


class BrowserRuntimeSession:
    def __init__(self, context_id: str, runtime: BrowserRuntime):
        self.context_id = str(context_id)
        self._runtime = runtime

    async def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        return await self._runtime.call_for(self.context_id, method, *args, **kwargs)


class _BrowserRuntimeCore:
    _VALID_MODIFIERS = {"Control", "Shift", "Alt", "Meta"}
    _KEY_ALIASES = {
        "cmd": "Meta",
        "command": "Meta",
        "control": "Control",
        "ctrl": "Control",
        "escape": "Escape",
        "esc": "Escape",
        "meta": "Meta",
        "option": "Alt",
        "return": "Enter",
        "space": "Space",
    }
    _POPUP_WAIT_SECONDS = 2.0

    def __init__(self, context_id: str):
        self.context_id = context_id
        self.safe_context_id = _safe_context_id(context_id)
        self.request_context_id: contextvars.ContextVar[str] = contextvars.ContextVar(
            f"browser_context_{id(self)}",
            default=context_id,
        )
        self.playwright = None
        self.context = None
        self.pages: dict[int, BrowserPage] = {}
        self.screencasts: dict[str, _BrowserScreencast] = {}
        self.next_browser_id = 1
        self._last_interacted_browser_ids: dict[str, int] = {}
        self._dom_helper_source: str | None = None
        self._content_helper_source: str | None = None
        self._start_lock: asyncio.Lock | None = None
        self._registry_lock: asyncio.Lock | None = None
        self._closing = False
        self._pending_popups: list[asyncio.Future[int]] = []
        self._pending_popup_contexts: dict[asyncio.Future[int], str] = {}
        self._background_popup_pages: set[int] = set()
        self._bootstrap_page: Any | None = None
        self._restore_state_exists = False
        self._restore_state_loaded = False
        self._restore_entries: list[dict[str, Any]] = []
        self._restored_context_ids: set[str] = set()
        self._restored_all = False
        self._restoring_tabs = False
        self._browser_chrome_height: int | None = None
        self._browser_window_page: Any | None = None
        self._browser_window_session: Any | None = None
        self._browser_window_id: int | None = None
        self.interactive_view = BrowserInteractiveView(context_id)

    @property
    def current_context_id(self) -> str:
        return str(self.request_context_id.get() or self.context_id)

    @property
    def last_interacted_browser_id(self) -> int | None:
        return self._last_interacted_browser_ids.get(self.current_context_id)

    @last_interacted_browser_id.setter
    def last_interacted_browser_id(self, browser_id: int | None) -> None:
        self._set_last_interacted(self.current_context_id, browser_id)

    def _set_last_interacted(self, context_id: str, browser_id: int | None) -> None:
        context_id = str(context_id or self.context_id)
        if browser_id is None:
            self._last_interacted_browser_ids.pop(context_id, None)
        else:
            self._last_interacted_browser_ids[context_id] = int(browser_id)

    def _load_restore_state(self) -> None:
        self._restore_state_exists, self._restore_entries = _load_browser_tabs()
        self._restore_state_loaded = True
        self._restored_context_ids.clear()
        self._restored_all = False
        self._restoring_tabs = False

    def _tab_scope(self) -> str:
        return str(
            get_browser_config().get(TAB_SCOPE_KEY, DEFAULT_BROWSER_TAB_SCOPE)
            or DEFAULT_BROWSER_TAB_SCOPE
        )

    def _persist_browser_tabs(self) -> None:
        if not self._restore_state_loaded or self._restoring_tabs:
            return

        replaced_contexts = set(self._restored_context_ids)
        live_tabs: list[dict[str, Any]] = []
        for browser_id in sorted(self.pages):
            browser_page = self.pages[browser_id]
            context_id = self._page_context_id(browser_page)
            replaced_contexts.add(context_id)
            try:
                url = str(browser_page.page.url or "about:blank").strip()
            except Exception:
                continue
            if not url:
                url = "about:blank"
            live_tabs.append(
                {
                    "context_id": context_id,
                    "url": url,
                    "active": (
                        self._last_interacted_browser_ids.get(context_id) == browser_id
                    ),
                }
            )

        preserved_tabs = (
            []
            if self._restored_all
            else [
                entry
                for entry in self._restore_entries
                if entry["context_id"] not in replaced_contexts
            ]
        )
        tabs = preserved_tabs + live_tabs
        try:
            _save_browser_tabs(tabs)
        except Exception as exc:
            PrintStyle.warning(f"Browser tab recovery state could not be saved: {exc}")
            return
        self._restore_state_exists = True
        self._restore_entries = tabs

    async def _restore_tabs_for_scope(self) -> None:
        if not self._restore_state_loaded or self._restoring_tabs or not self.context:
            return

        tab_scope = self._tab_scope()
        if tab_scope == "shared":
            if self._restored_all:
                return
            entries = [
                entry
                for entry in self._restore_entries
                if entry["context_id"] not in self._restored_context_ids
            ]
        else:
            context_id = self.current_context_id
            if self._restored_all or context_id in self._restored_context_ids:
                return
            entries = [
                entry for entry in self._restore_entries if entry["context_id"] == context_id
            ]

        restored_ids: dict[str, list[int]] = {}
        active_ids: dict[str, int] = {}
        navigations: list[tuple[Any, str]] = []
        self._restoring_tabs = True
        try:
            for entry in entries:
                context_id = entry["context_id"]
                if len(self._context_browser_ids(context_id)) >= self._max_open_tabs():
                    continue
                page = self._bootstrap_page
                self._bootstrap_page = None
                if not page or page.is_closed():
                    page = await self.context.new_page()
                browser_page = await self._register_page(page, context_id)
                navigations.append((page, normalize_url(entry["url"])))
                restored_ids.setdefault(context_id, []).append(browser_page.id)
                if entry["active"]:
                    active_ids[context_id] = browser_page.id
            await asyncio.gather(
                *(
                    self._goto(page, url, wait_until="commit")
                    for page, url in navigations
                )
            )
        finally:
            self._restoring_tabs = False

        for context_id, browser_ids in restored_ids.items():
            self._set_last_interacted(
                context_id,
                active_ids.get(context_id, browser_ids[0]),
            )
        if tab_scope == "shared":
            self._restored_all = True
            self._restored_context_ids.update(entry["context_id"] for entry in entries)
        else:
            self._restored_context_ids.add(self.current_context_id)
        self._persist_browser_tabs()

    def _page_context_id(self, browser_page: BrowserPage) -> str:
        return str(browser_page.context_id or self.context_id)

    def _context_browser_ids(self, context_id: str | None = None) -> list[int]:
        target = str(context_id or self.current_context_id)
        return sorted(
            browser_id
            for browser_id, browser_page in self.pages.items()
            if self._page_context_id(browser_page) == target
        )

    def _ensure_registry_lock(self) -> asyncio.Lock:
        if self._registry_lock is None:
            self._registry_lock = asyncio.Lock()
        return self._registry_lock

    def _maybe_promote(self, resolved_id: int) -> None:
        # Promote only if the target IS the current active tab or no tab is
        # active yet. Cross-tab work on a backgrounded tab does not steal
        # viewer focus.
        current = self.last_interacted_browser_id
        if current is None or current == resolved_id:
            self.last_interacted_browser_id = int(resolved_id)

    def _background_focus_target(
        self,
        previous_focus: int | None,
        fallback_id: int,
    ) -> int | None:
        browser_ids = self._context_browser_ids()
        if previous_focus in browser_ids:
            return int(previous_focus)
        if fallback_id in browser_ids:
            return int(fallback_id)
        return next(iter(browser_ids), None)

    def _normalize_modifiers(self, modifiers: list[str] | str | None) -> list[str] | None:
        if modifiers is None:
            return None
        if isinstance(modifiers, str):
            raw = [modifiers]
        elif isinstance(modifiers, list):
            raw = modifiers
        else:
            raise ValueError("modifiers must be a string or list")
        normalized = [str(modifier).strip() for modifier in raw if str(modifier).strip()]
        if not normalized:
            return None
        bad = set(normalized) - self._VALID_MODIFIERS
        if bad:
            raise ValueError(
                f"unsupported modifiers: {sorted(bad)}; allowed: {sorted(self._VALID_MODIFIERS)}"
            )
        return normalized

    @classmethod
    def _normalize_keys(cls, keys: list[str] | str | None) -> list[str]:
        if keys is None:
            return []
        if isinstance(keys, str):
            raw = re.split(r"\s*\+\s*|\s*,\s*", keys.strip())
        elif isinstance(keys, list):
            raw = keys
        else:
            raw = [str(keys)]
        normalized: list[str] = []
        for key in raw:
            value = str(key or "").strip()
            if not value:
                continue
            normalized.append(
                cls._KEY_ALIASES.get(
                    value.lower(),
                    value.upper() if len(value) == 1 and value.isalpha() else value,
                )
            )
        return normalized

    @staticmethod
    def _has_reference(reference_id: int | str | None) -> bool:
        return reference_id is not None and str(reference_id).strip() != ""

    def _screenshot_output_path(self, browser_id: int, path: str = "") -> tuple[Path, str, str]:
        raw_path = str(path or "").strip()
        if raw_path:
            output_path = Path(files.fix_dev_path(raw_path) if raw_path.startswith("/a0/") else raw_path)
            if not output_path.is_absolute():
                output_path = Path(files.get_abs_path(str(output_path)))
            suffix = output_path.suffix.lower()
            if suffix == ".png":
                return output_path, "png", "image/png"
            if suffix not in {".jpg", ".jpeg"}:
                output_path = output_path.with_suffix(".jpg") if not suffix else output_path.with_name(f"{output_path.name}.jpg")
            return output_path, "jpeg", "image/jpeg"

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        millis = int((time.time() % 1) * 1000)
        output_path = self.screenshots_dir / f"browser-{int(browser_id)}-{timestamp}-{millis:03d}.jpg"
        return output_path, "jpeg", "image/jpeg"

    @staticmethod
    def _normalize_upload_paths(path: str = "", paths: list[str] | None = None) -> list[str]:
        raw_paths: list[str] = []
        if paths:
            if not isinstance(paths, list):
                raise ValueError("paths must be a list of file paths")
            raw_paths.extend(str(item or "").strip() for item in paths)
        if str(path or "").strip():
            raw_paths.append(str(path or "").strip())

        normalized_paths: list[str] = []
        for raw_path in raw_paths:
            if not raw_path:
                continue
            candidate = Path(files.fix_dev_path(raw_path) if raw_path.startswith("/a0/") else raw_path)
            if not candidate.is_absolute():
                candidate = Path(files.get_abs_path(str(candidate)))
            candidate = candidate.expanduser().resolve()
            if not candidate.is_file():
                raise FileNotFoundError(f"Upload file does not exist: {candidate}")
            normalized_paths.append(str(candidate))

        if not normalized_paths:
            raise ValueError("upload_file requires path or non-empty paths")
        return normalized_paths

    @staticmethod
    def _multi_group_key(call: dict[str, Any]) -> Any:
        value = call.get("browser_id")
        if value is None or str(value).strip() == "":
            return None
        raw = str(value).strip()
        if raw.startswith("browser-"):
            raw = raw.split("-", 1)[1]
        try:
            return int(raw)
        except ValueError:
            return raw

    @property
    def profile_dir(self) -> Path:
        return Path(files.get_abs_path("tmp/browser/sessions", self.safe_context_id))

    @property
    def downloads_dir(self) -> Path:
        return Path(files.get_abs_path("usr/downloads/browser"))

    @property
    def screenshots_dir(self) -> Path:
        return Path(files.get_abs_path("tmp/browser/screenshots", self.safe_context_id))

    async def ensure_started(self) -> None:
        if self._context_is_alive():
            await self._restore_tabs_for_scope()
            return
        if self.context:
            await self._discard_stale_context("Browser context is stale; restarting.")

        if self._start_lock is None:
            self._start_lock = asyncio.Lock()

        async with self._start_lock:
            if self._context_is_alive():
                await self._restore_tabs_for_scope()
                return
            if self.context:
                await self._discard_stale_context("Browser context is stale; restarting.")
            elif self.playwright and not self._closing:
                await self._stop_playwright("Browser context closed; restarting Playwright.")
            await self._start()
            await self._restore_tabs_for_scope()

    def _context_is_alive(self) -> bool:
        if not self.context:
            return False
        try:
            pages = getattr(self.context, "pages")
            len(pages() if callable(pages) else pages)
            return True
        except AttributeError:
            # Lightweight test doubles may not model Playwright's pages property.
            return True
        except Exception:
            return False

    async def _discard_stale_context(self, message: str) -> None:
        PrintStyle.warning(message)
        self._discard_context_state()
        await self._stop_playwright("Playwright stop after Browser context loss failed")

    def _discard_context_state(self) -> None:
        for waiter in self._pending_popups:
            if not waiter.done():
                waiter.set_exception(RuntimeError("Browser context closed."))
        self._pending_popups.clear()
        self._pending_popup_contexts.clear()
        self._background_popup_pages.clear()
        self._bootstrap_page = None
        self._browser_chrome_height = None
        self._browser_window_page = None
        self._browser_window_session = None
        self._browser_window_id = None
        self.pages.clear()
        self._last_interacted_browser_ids.clear()
        for screencast in self.screencasts.values():
            screencast.stopped = True
            screencast._drop_queued_frames()
            with contextlib.suppress(asyncio.QueueFull):
                screencast.queue.put_nowait(None)
            for task in list(screencast._ack_tasks):
                task.cancel()
            screencast._ack_tasks.clear()
        self.screencasts.clear()
        self.context = None

    async def _stop_playwright(self, warning: str) -> None:
        if not self.playwright:
            return
        try:
            await self.playwright.stop()
        except Exception as exc:
            PrintStyle.warning(f"{warning}: {exc}")
        finally:
            self.playwright = None

    async def _start(self) -> None:
        from plugins._browser import hooks

        self._load_restore_state()
        preparation = hooks.prepare_playwright_cache()
        if preparation.get("errors") or not preparation.get("binary"):
            problem = preparation.get("errors") or "missing binary"
            raise RuntimeError(f"Browser setup failed: {problem}")
        from patchright.async_api import async_playwright

        self.profile_dir.parent.mkdir(parents=True, exist_ok=True)
        self._adopt_legacy_profile(self.current_context_id)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self._prepare_download_preferences()
        self._release_orphaned_profile_singleton()
        browser_config = get_browser_config()
        launch_config = build_browser_launch_config(browser_config)
        browser_binary = Path(preparation["binary"])
        browser_display = self.interactive_view.ensure_display()
        launch_args = list(launch_config["args"])
        if not self._restore_state_exists:
            launch_args.append("--restore-last-session")
        if browser_display:
            launch_args.extend(
                [
                    "--window-position=0,0",
                    f"--window-size={self.interactive_view.width},{self.interactive_view.height}",
                ]
            )

        self.playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "user_data_dir": str(self.profile_dir),
            "headless": not bool(browser_display),
            "accept_downloads": True,
            "downloads_path": str(self.downloads_dir),
            "args": launch_args,
        }
        if browser_display:
            launch_kwargs["env"] = {**os.environ, "DISPLAY": browser_display}
            launch_kwargs["no_viewport"] = True
        else:
            launch_kwargs.update(
                viewport=DEFAULT_VIEWPORT,
                screen=DEFAULT_VIEWPORT,
                no_viewport=False,
            )
        if launch_config["channel"]:
            launch_kwargs["channel"] = launch_config["channel"]
        else:
            launch_kwargs["executable_path"] = str(browser_binary)
        if launch_config["proxy"]:
            launch_kwargs["proxy"] = launch_config["proxy"]
        try:
            self.context = await self.playwright.chromium.launch_persistent_context(
                **launch_kwargs
            )
        except Exception:
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception:
                    pass
                self.playwright = None
            raise
        self.context.set_default_timeout(30000)
        self.context.set_default_navigation_timeout(30000)
        self.context.on("close", self._on_context_closed)
        self.context.on("page", self._on_new_page_sync)

        existing_pages = list(self.context.pages)
        if existing_pages:
            session = await self.context.new_cdp_session(existing_pages[0])
            try:
                # Honor the folder and save-dialog preference from Chromium's settings.
                await session.send("Browser.setDownloadBehavior", {"behavior": "default"})
            finally:
                await session.detach()
        if self._restore_state_exists:
            for page in existing_pages:
                if self._bootstrap_page is None:
                    self._bootstrap_page = page
                    await self._fit_browser_window(page)
                    continue
                with contextlib.suppress(Exception):
                    await page.close()
            return

        for page in existing_pages:
            if page.url == "about:blank":
                if browser_display and self._bootstrap_page is None:
                    self._bootstrap_page = page
                    await self._fit_browser_window(page)
                    continue
                try:
                    await page.close()
                except Exception:
                    pass
                continue
            await self._register_page(page)

    def _prepare_download_preferences(self) -> None:
        path = self.profile_dir / "Default" / "Preferences"
        preferences = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        downloads = preferences.setdefault("download", {})
        if downloads.get("default_directory"):
            return
        downloads["default_directory"] = str(self.downloads_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".a0.tmp")
        temporary.write_text(json.dumps(preferences), encoding="utf-8")
        temporary.replace(path)

    def _adopt_legacy_profile(self, context_id: str) -> None:
        if self.safe_context_id != SHARED_RUNTIME_ID or self.profile_dir.exists():
            return
        legacy_profile = Path(
            files.get_abs_path("tmp/browser/sessions", _safe_context_id(context_id))
        )
        if legacy_profile == self.profile_dir or not legacy_profile.is_dir():
            return
        try:
            legacy_profile.rename(self.profile_dir)
            PrintStyle.info(
                f"Browser adopted the existing profile for context {context_id}."
            )
        except OSError as exc:
            PrintStyle.warning(f"Browser profile migration failed: {exc}")

    def _release_orphaned_profile_singleton(self) -> None:
        lock_path = self.profile_dir / "SingletonLock"
        owner_pid = self._profile_singleton_owner_pid(lock_path)
        if owner_pid and self._process_owns_profile(owner_pid):
            PrintStyle.warning(
                f"Stopping orphaned Chromium process {owner_pid} for Browser profile {self.safe_context_id}."
            )
            self._terminate_process(owner_pid)

        for name in CHROME_SINGLETON_FILES:
            singleton_path = self.profile_dir / name
            try:
                if singleton_path.exists() or singleton_path.is_symlink():
                    singleton_path.unlink()
            except OSError as exc:
                PrintStyle.warning(f"Could not remove stale Browser profile lock {singleton_path}: {exc}")

    @staticmethod
    def _profile_singleton_owner_pid(lock_path: Path) -> int | None:
        try:
            target = os.readlink(lock_path)
        except OSError:
            return None
        raw_pid = target.rsplit("-", 1)[-1]
        if not raw_pid.isdigit():
            return None
        return int(raw_pid)

    def _process_owns_profile(self, pid: int) -> bool:
        cmdline_path = Path("/proc") / str(pid) / "cmdline"
        try:
            raw = cmdline_path.read_bytes()
        except OSError:
            return False
        cmdline = raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore")
        return "chrome" in cmdline.lower() and str(self.profile_dir) in cmdline

    @staticmethod
    def _terminate_process(pid: int) -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except OSError as exc:
            PrintStyle.warning(f"Could not stop orphaned Chromium process {pid}: {exc}")
            return

        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if not Path("/proc", str(pid)).exists():
                return
            time.sleep(0.1)

        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as exc:
            PrintStyle.warning(f"Could not force-stop orphaned Chromium process {pid}: {exc}")

    async def open(
        self, url: str = "", *, wait_until: str = "domcontentloaded"
    ) -> dict[str, Any]:
        await self.ensure_started()
        self._ensure_can_open_page()
        context_id = self.current_context_id
        page = self._bootstrap_page
        self._bootstrap_page = None
        if not page or page.is_closed():
            page = await self.context.new_page()
        browser_page = await self._register_page(page, context_id)
        self.last_interacted_browser_id = browser_page.id
        target_url = self._initial_url(url)
        if target_url and target_url != "about:blank":
            await self._goto(page, normalize_url(target_url), wait_until=wait_until)
        self._persist_browser_tabs()
        return {"id": browser_page.id, "state": await self._state(browser_page.id)}

    def _initial_url(self, url: str = "") -> str:
        raw_url = str(url or "").strip()
        if raw_url:
            return raw_url
        return str(get_browser_config().get(DEFAULT_HOMEPAGE_KEY) or "about:blank").strip() or "about:blank"

    def _max_open_tabs(self) -> int:
        try:
            value = int(get_browser_config().get(MAX_OPEN_TABS_KEY, DEFAULT_MAX_OPEN_TABS))
        except (TypeError, ValueError):
            value = DEFAULT_MAX_OPEN_TABS
        return max(1, value)

    def _tab_limit_error(self, context_id: str | None = None) -> RepairableException:
        max_open_tabs = self._max_open_tabs()
        open_tabs = len(self._context_browser_ids(context_id))
        return RepairableException(
            f"Browser tab limit reached ({open_tabs}/{max_open_tabs}). "
            "Navigate an existing browser_id or close tabs with close/close_all before opening more."
        )

    def _ensure_can_open_page(self) -> None:
        if len(self._context_browser_ids()) >= self._max_open_tabs():
            raise self._tab_limit_error()

    async def list(self, include_content: bool = False) -> dict[str, Any]:
        if self.context or has_restorable_browser_tabs(self.current_context_id):
            await self.ensure_started()
        ids = self._context_browser_ids()
        if not ids:
            return {
                "browsers": [],
                "last_interacted_browser_id": self.last_interacted_browser_id,
            }
        states_task = asyncio.gather(*(self._state(bid) for bid in ids))
        if include_content:
            contents_task = asyncio.gather(
                *(self.content(bid) for bid in ids),
                return_exceptions=True,
            )
            states, contents = await asyncio.gather(states_task, contents_task)
            out: list[dict[str, Any]] = []
            for idx, bid in enumerate(ids):
                entry = states[idx]
                c = contents[idx]
                if isinstance(c, Exception):
                    entry["content_error"] = str(c)
                else:
                    entry["content"] = c
                out.append(entry)
        else:
            out = await states_task
        return {
            "browsers": out,
            "last_interacted_browser_id": self.last_interacted_browser_id,
        }

    async def list_all(self) -> dict[str, Any]:
        if self.context or has_restorable_browser_tabs(self.current_context_id):
            await self.ensure_started()
        browser_ids = sorted(self.pages)
        return {
            "browsers": await asyncio.gather(
                *(self._state(browser_id) for browser_id in browser_ids)
            ),
            "last_interacted_browser_ids": dict(self._last_interacted_browser_ids),
        }

    async def multi(self, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await run_browser_calls(calls, self._dispatch_call)

    async def _dispatch_call(self, call: dict[str, Any]) -> Any:
        action = str(call.get("action") or "").strip().lower().replace("-", "_")
        bid = call.get("browser_id")
        if action == "open":
            return await self.open(call.get("url") or "")
        if action == "screenshot":
            return await self.screenshot_file(
                bid,
                quality=int(call.get("quality") or 80),
                full_page=bool(call.get("full_page")),
                path=call.get("path") or "",
            )
        if action == "list":
            return await self.list(include_content=bool(call.get("include_content")))
        if action == "state":
            return await self.state(bid)
        if action in {"set_active", "setactive", "activate", "focus"}:
            return await self.set_active(bid)
        if action == "navigate":
            return await self.navigate(bid, call.get("url") or "")
        if action == "back":
            return await self.back(bid)
        if action == "forward":
            return await self.forward(bid)
        if action == "reload":
            return await self.reload(bid)
        if action == "content":
            payload = None
            sels = call.get("selectors")
            sel = call.get("selector")
            if sels:
                payload = {"selectors": sels}
            elif sel:
                payload = {"selector": sel}
            return await self.content(bid, payload)
        if action == "detail":
            ref = call.get("ref")
            if ref is None:
                raise ValueError("detail requires ref")
            return await self.detail(bid, ref)
        if action == "click":
            ref = call.get("ref")
            if ref is None and (call.get("x") or call.get("y")):
                return await self.mouse(
                    bid,
                    "click",
                    float(call.get("x") or 0),
                    float(call.get("y") or 0),
                    button=call.get("button") or "left",
                    modifiers=self._normalize_modifiers(call.get("modifiers")),
                )
            if ref is None:
                raise ValueError("click requires ref")
            return await self.click(
                bid, ref,
                modifiers=self._normalize_modifiers(call.get("modifiers")),
                focus_popup=call.get("focus_popup"),
            )
        if action == "type":
            ref = call.get("ref")
            if ref is None:
                return await self.keyboard(
                    bid,
                    key="",
                    text=str(call.get("text") or ""),
                )
            return await self.type(bid, ref, call.get("text") or "")
        if action == "submit":
            ref = call.get("ref")
            if ref is None:
                raise ValueError("submit requires ref")
            return await self.submit(bid, ref)
        if action in {"type_submit", "typesubmit"}:
            ref = call.get("ref")
            if ref is None:
                raise ValueError("type_submit requires ref")
            return await self.type_submit(bid, ref, call.get("text") or "")
        if action == "scroll":
            ref = call.get("ref")
            if ref is None:
                raise ValueError("scroll requires ref")
            return await self.scroll(bid, ref)
        if action == "evaluate":
            return await self.evaluate(bid, call.get("script") or "")
        if action in {"key_chord", "keychord"}:
            keys = self._normalize_keys(call.get("keys"))
            if not keys:
                raise ValueError("key_chord requires non-empty keys")
            return await self.key_chord(bid, keys)
        if action == "mouse":
            return await self.mouse(
                bid, call.get("event_type") or "click",
                float(call.get("x") or 0), float(call.get("y") or 0),
                button=call.get("button") or "left",
                modifiers=self._normalize_modifiers(call.get("modifiers")),
            )
        if action == "hover":
            return await self.hover(
                bid,
                ref=call.get("ref"),
                x=float(call.get("x") or 0),
                y=float(call.get("y") or 0),
                offset_x=float(call.get("offset_x") or 0),
                offset_y=float(call.get("offset_y") or 0),
            )
        if action == "double_click":
            return await self.double_click(
                bid,
                ref=call.get("ref"),
                x=float(call.get("x") or 0),
                y=float(call.get("y") or 0),
                button=call.get("button") or "left",
                modifiers=self._normalize_modifiers(call.get("modifiers")),
                offset_x=float(call.get("offset_x") or 0),
                offset_y=float(call.get("offset_y") or 0),
            )
        if action == "right_click":
            return await self.right_click(
                bid,
                ref=call.get("ref"),
                x=float(call.get("x") or 0),
                y=float(call.get("y") or 0),
                modifiers=self._normalize_modifiers(call.get("modifiers")),
                offset_x=float(call.get("offset_x") or 0),
                offset_y=float(call.get("offset_y") or 0),
            )
        if action == "drag":
            return await self.drag(
                bid,
                ref=call.get("ref"),
                target_ref=call.get("target_ref"),
                x=float(call.get("x") or 0),
                y=float(call.get("y") or 0),
                to_x=float(call.get("to_x") or 0),
                to_y=float(call.get("to_y") or 0),
                offset_x=float(call.get("offset_x") or 0),
                offset_y=float(call.get("offset_y") or 0),
                target_offset_x=float(call.get("target_offset_x") or 0),
                target_offset_y=float(call.get("target_offset_y") or 0),
            )
        if action == "wheel":
            return await self.wheel(
                bid,
                float(call.get("x") or 0),
                float(call.get("y") or 0),
                float(call.get("delta_x") or 0),
                float(call.get("delta_y") or 0),
            )
        if action == "keyboard":
            return await self.keyboard(
                bid,
                key=str(call.get("key") or ""),
                text=str(call.get("text") or ""),
            )
        if action == "clipboard":
            clipboard_action = str(
                call.get("clipboard_action")
                or call.get("operation")
                or call.get("event_type")
                or ""
            ).strip().lower()
            return await self.clipboard(
                bid,
                action=clipboard_action,
                text=str(call.get("text") or ""),
            )
        if action in {"copy", "cut", "paste"}:
            return await self.clipboard(
                bid,
                action=action,
                text=str(call.get("text") or ""),
            )
        if action == "set_viewport":
            return await self.set_viewport(
                bid,
                int(call.get("width") or 0),
                int(call.get("height") or 0),
            )
        if action == "select_option":
            ref = call.get("ref")
            if ref is None:
                raise ValueError("select_option requires ref")
            return await self.select_option(
                bid,
                ref,
                value=str(call.get("value") or ""),
                values=call.get("values"),
            )
        if action == "set_checked":
            ref = call.get("ref")
            if ref is None:
                raise ValueError("set_checked requires ref")
            checked = call.get("checked")
            return await self.set_checked(
                bid,
                ref,
                checked=True if checked is None else bool(checked),
            )
        if action == "upload_file":
            ref = call.get("ref")
            if ref is None:
                raise ValueError("upload_file requires ref")
            return await self.upload_file(
                bid,
                ref,
                path=call.get("path") or "",
                paths=call.get("paths"),
            )
        if action == "close":
            return await self.close_browser(bid)
        if action == "close_all":
            return await self.close_all_browsers()
        raise ValueError(f"unknown action: {action}")

    async def set_active(self, browser_id: int | str | None) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        # Explicit focus change — bypass _maybe_promote.
        self.last_interacted_browser_id = int(resolved_id)
        with contextlib.suppress(Exception):
            await page.bring_to_front()
        await self._fit_browser_window(page)
        self._persist_browser_tabs()
        return await self._state(resolved_id)

    async def state(self, browser_id: int | str | None = None) -> dict[str, Any]:
        await self.ensure_started()
        return await self._state(self._resolve_browser_id(browser_id))

    async def zoom(self, browser_id: int | str | None, direction: str) -> dict[str, Any]:
        shortcuts = {"in": "ctrl+plus", "out": "ctrl+minus", "reset": "ctrl+0"}
        if direction not in shortcuts:
            raise ValueError("Zoom direction must be in, out, or reset.")
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        display = self.interactive_view.display_name
        xdotool = shutil.which("xdotool")
        if not display or not xdotool:
            raise RuntimeError("Page zoom requires the interactive container browser.")
        await self._page(resolved_id).bring_to_front()
        await asyncio.to_thread(
            subprocess.run,
            [xdotool, "key", "--clearmodifiers", shortcuts[direction]],
            env={**os.environ, "DISPLAY": display},
            check=True, timeout=3, capture_output=True,
        )
        self._maybe_promote(resolved_id)
        return await self._state(resolved_id)

    async def navigate(
        self,
        browser_id: int | str | None,
        url: str,
        *,
        wait_until: str = "domcontentloaded",
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await self._goto(page, normalize_url(url), wait_until=wait_until)
        self._maybe_promote(resolved_id)
        self._persist_browser_tabs()
        return await self._state(resolved_id)

    async def back(
        self,
        browser_id: int | str | None = None,
        *,
        wait_until: str = "domcontentloaded",
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await page.go_back(wait_until=wait_until, timeout=10000)
        self._maybe_promote(resolved_id)
        self._persist_browser_tabs()
        return await self._state(resolved_id)

    async def forward(
        self,
        browser_id: int | str | None = None,
        *,
        wait_until: str = "domcontentloaded",
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await page.go_forward(wait_until=wait_until, timeout=10000)
        self._maybe_promote(resolved_id)
        self._persist_browser_tabs()
        return await self._state(resolved_id)

    async def reload(
        self,
        browser_id: int | str | None = None,
        *,
        wait_until: str = "domcontentloaded",
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await page.reload(wait_until=wait_until, timeout=15000)
        self._maybe_promote(resolved_id)
        self._persist_browser_tabs()
        return await self._state(resolved_id)

    async def content(
        self,
        browser_id: int | str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await self._ensure_content_helper(page)
        result = await page.evaluate(
            "(payload) => globalThis.__spaceBrowserPageContent__.capture(payload || null)",
            payload or None,
            isolated_context=True,
        )
        self._maybe_promote(resolved_id)
        return result or {}

    async def detail(self, browser_id: int | str | None, reference_id: int | str) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await self._ensure_content_helper(page)
        result = await page.evaluate(
            "(ref) => globalThis.__spaceBrowserPageContent__.detail(ref)",
            reference_id,
            isolated_context=True,
        )
        self._maybe_promote(resolved_id)
        return result or {}

    async def annotation_target(
        self,
        browser_id: int | str | None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await self._ensure_content_helper(page)
        result = await page.evaluate(
            "(payload) => globalThis.__spaceBrowserPageContent__.annotate(payload || null)",
            payload or None,
            isolated_context=True,
        )
        self._maybe_promote(resolved_id)
        return result or {}

    async def evaluate(self, browser_id: int | str | None, script: str) -> dict[str, Any]:
        if not isinstance(script, str) or not script.strip():
            raise ValueError("evaluate requires a non-empty 'script' string")
        from agent import AgentContext

        context = AgentContext.get(self.current_context_id)
        config = get_browser_config(agent=context.agent0 if context else None)
        timeout = normalize_evaluate_timeout(
            config.get(EVALUATE_TIMEOUT_KEY, DEFAULT_EVALUATE_TIMEOUT_SECONDS)
        )
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        browser_page = self.pages[resolved_id]
        async with browser_page.evaluate_lock:
            return await self._evaluate_page(browser_page, script, timeout)

    async def _evaluate_page(
        self, browser_page: BrowserPage, script: str, timeout: float
    ) -> dict[str, Any]:
        page = browser_page.page
        session = await asyncio.wait_for(
            page.context.new_cdp_session(page), EVALUATE_RECOVERY_TIMEOUT_SECONDS
        )

        async def run():
            result = await page.evaluate(script, isolated_context=False)
            self._maybe_promote(browser_page.id)
            return {"result": result, "state": await self._state(browser_page.id)}

        operation = asyncio.create_task(run())
        aborted = False
        timeout_error = f"evaluate timed out after {timeout:g} seconds"
        timed_out = False
        try:
            return await asyncio.wait_for(asyncio.shield(operation), timeout)
        except asyncio.TimeoutError:
            aborted = timed_out = True
            raise TimeoutError(timeout_error) from None
        except asyncio.CancelledError:
            aborted = True
            raise
        finally:
            cleanup = asyncio.create_task(
                self._finish_evaluate(browser_page, session, operation, aborted)
            )
            cancelled = False
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    cancelled = True
                except Exception:
                    break
            try:
                recovery_notice = cleanup.result()
            except Exception as exc:
                if timed_out:
                    raise TimeoutError(f"{timeout_error}; {exc}") from None
                raise
            if timed_out and recovery_notice:
                raise TimeoutError(f"{timeout_error}; {recovery_notice}") from None
            if cancelled:
                raise asyncio.CancelledError

    async def _finish_evaluate(
        self, browser_page: BrowserPage, session: Any, operation: asyncio.Task, aborted: bool
    ) -> str:
        page = browser_page.page
        recovery_notice = ""

        async def recover():
            if operation.done() and not operation.cancelled() and operation.exception() is None:
                return ""
            await session.send("Runtime.terminateExecution")
            done, _ = await asyncio.wait({operation}, timeout=EVALUATE_TERMINATION_GRACE_SECONDS)
            if done and not operation.cancelled() and not isinstance(
                operation.exception(), (TimeoutError, asyncio.TimeoutError)
            ):
                return ""
            # An awaited Promise may survive termination. Only that unresolved
            # execution needs a new document; synchronous scripts keep the page.
            await page.reload(wait_until="commit", timeout=EVALUATE_RECOVERY_TIMEOUT_SECONDS * 1000)
            await asyncio.gather(asyncio.shield(operation), return_exceptions=True)
            return "affected tab reloaded to cancel pending JavaScript"

        try:
            if aborted and not page.is_closed():
                try:
                    recovery_notice = await asyncio.wait_for(recover(), EVALUATE_RECOVERY_TIMEOUT_SECONDS)
                except Exception:
                    if not page.is_closed():
                        try:
                            await asyncio.wait_for(
                                page.close(run_before_unload=False), EVALUATE_RECOVERY_TIMEOUT_SECONDS
                            )
                        except Exception:
                            raise RuntimeError(
                                "Browser evaluate recovery failed; the affected tab could not be closed"
                            ) from None
                    await self._unregister_page_async(browser_page.id)
                    self._persist_browser_tabs()
                    recovery_notice = "affected tab closed after unsuccessful recovery"
        finally:
            if not operation.done():
                operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
            try:
                await asyncio.wait_for(session.detach(), EVALUATE_RECOVERY_TIMEOUT_SECONDS)
            except Exception:
                if not page.is_closed():
                    raise RuntimeError("Browser evaluate protocol session cleanup failed") from None
        return recovery_notice

    async def click(
        self,
        browser_id: int | str | None,
        reference_id: int | str,
        modifiers: list[str] | str | None = None,
        focus_popup: bool | None = None,
    ) -> dict[str, Any]:
        modifiers = self._normalize_modifiers(modifiers)
        if modifiers:
            return await self._modifier_click(browser_id, reference_id, modifiers, focus_popup)
        return await self._reference_action("click", browser_id, reference_id)

    async def _modifier_click(
        self,
        browser_id: int | str | None,
        reference_id: int | str,
        modifiers: list[str],
        focus_popup: bool | None,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        previous_focus = self.last_interacted_browser_id
        page = self._page(resolved_id)
        await self._ensure_content_helper(page)

        box = await page.evaluate(
            "(ref) => globalThis.__spaceBrowserPageContent__.boundingBoxFor(ref)",
            reference_id,
            isolated_context=True,
        )

        background = focus_popup is False or (
            focus_popup is None and bool({"Control", "Meta"} & set(modifiers))
        )

        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[int] = loop.create_future()
        self._pending_popups.append(waiter)
        self._pending_popup_contexts[waiter] = self.current_context_id

        warning: str | None = None
        opened_id: int | None = None
        try:
            box_has_geometry = bool(box and box.get("width") and box.get("height"))
            box_selector = box.get("selector") if box else None
            if box_has_geometry:
                cx = box["x"] + box["width"] / 2
                cy = box["y"] + box["height"] / 2
                # Mouse.click does not accept modifiers; hold them via keyboard.
                pressed: list[str] = []
                try:
                    for mod in modifiers:
                        await page.keyboard.down(mod)
                        pressed.append(mod)
                    await page.mouse.click(cx, cy)
                finally:
                    for mod in reversed(pressed):
                        with contextlib.suppress(Exception):
                            await page.keyboard.up(mod)
                await self._settle(page, short=False)
            elif box_selector:
                try:
                    await page.locator(box_selector).click(
                        modifiers=list(modifiers), force=True, timeout=5000
                    )
                    await self._settle(page, short=False)
                except Exception as exc:
                    await self._reference_action("click", browser_id, reference_id)
                    warning = f"modifiers ignored: locator click failed ({exc})"
            else:
                await self._reference_action("click", browser_id, reference_id)
                warning = "modifiers ignored: target geometry unavailable"

            try:
                opened_id = await asyncio.wait_for(
                    asyncio.shield(waiter), timeout=self._POPUP_WAIT_SECONDS
                )
            except asyncio.TimeoutError:
                opened_id = None
            finally:
                if waiter in self._pending_popups:
                    self._pending_popups.remove(waiter)
                self._pending_popup_contexts.pop(waiter, None)
                if not waiter.done():
                    waiter.cancel()

            if opened_id is not None and background:
                if self.last_interacted_browser_id == opened_id:
                    # Force focus back to the tab that was active before the
                    # background click; the popup hook may have promoted.
                    self.last_interacted_browser_id = self._background_focus_target(
                        previous_focus,
                        resolved_id,
                    )
        finally:
            if waiter in self._pending_popups:
                self._pending_popups.remove(waiter)
            self._pending_popup_contexts.pop(waiter, None)

        if background:
            # Background-mode click: preserve the pre-click focus even when
            # the clicked tab itself was not active.
            self.last_interacted_browser_id = self._background_focus_target(
                previous_focus,
                resolved_id,
            )
        return {
            "action": {
                "ref": reference_id,
                "modifiers": list(modifiers),
                "opened_browser_ids": [opened_id] if opened_id is not None else [],
                **({"warning": warning} if warning else {}),
            },
            "state": await self._state(resolved_id),
        }

    async def key_chord(
        self,
        browser_id: int | str | None,
        keys: list[str],
    ) -> dict[str, Any]:
        if not keys:
            raise ValueError("key_chord requires at least one key")
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        pressed: list[str] = []
        try:
            for k in keys:
                await page.keyboard.down(k)
                pressed.append(k)
        finally:
            for k in reversed(pressed):
                with contextlib.suppress(Exception):
                    await page.keyboard.up(k)
        await self._settle(page, short=True)
        self._maybe_promote(resolved_id)
        return await self._state(resolved_id)

    async def submit(self, browser_id: int | str | None, reference_id: int | str) -> dict[str, Any]:
        return await self._reference_action("submit", browser_id, reference_id)

    async def scroll(self, browser_id: int | str | None, reference_id: int | str) -> dict[str, Any]:
        return await self._reference_action("scroll", browser_id, reference_id)

    async def type(
        self,
        browser_id: int | str | None,
        reference_id: int | str,
        text: str,
    ) -> dict[str, Any]:
        return await self._reference_action("type", browser_id, reference_id, text)

    async def type_submit(
        self,
        browser_id: int | str | None,
        reference_id: int | str,
        text: str,
    ) -> dict[str, Any]:
        return await self._reference_action("typeSubmit", browser_id, reference_id, text)

    async def clipboard(
        self,
        browser_id: int | str | None,
        *,
        action: str,
        text: str = "",
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        normalized_action = str(action or "").strip().lower()
        if normalized_action not in {"copy", "cut", "paste"}:
            raise ValueError(f"Unsupported clipboard action: {normalized_action}")

        clipboard_result: dict[str, Any]
        try:
            clipboard_result = await page.evaluate(
                CLIPBOARD_BRIDGE_SCRIPT,
                {
                    "action": normalized_action,
                    "text": str(text or ""),
                },
                isolated_context=False,
            ) or {}
        except Exception as exc:
            clipboard_result = {
                "action": normalized_action,
                "text": "",
                "changed": False,
                "default_prevented": False,
                "handled": False,
                "error": str(exc),
            }

        if (
            normalized_action == "paste"
            and text
            and not clipboard_result.get("changed")
            and not clipboard_result.get("default_prevented")
        ):
            if await self._insert_clipboard_text(page, str(text)):
                clipboard_result["changed"] = True
                clipboard_result["method"] = "keyboard.insert_text"
        elif normalized_action in {"copy", "cut"} and not clipboard_result.get("text"):
            with contextlib.suppress(Exception):
                shortcut = "Control+C" if normalized_action == "copy" else "Control+X"
                await page.keyboard.press(shortcut)
                clipboard_result["keyboard_shortcut"] = True

        await self._settle(page, short=True)
        self._maybe_promote(resolved_id)
        return {
            "state": await self._state(resolved_id),
            "clipboard": clipboard_result,
        }

    async def close_browser(self, browser_id: int | str | None = None) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        await self._stop_screencasts_for_browser(resolved_id)
        page = self._page(resolved_id)
        await page.close()
        self.pages.pop(resolved_id, None)
        if self.last_interacted_browser_id == resolved_id:
            self.last_interacted_browser_id = next(iter(self._context_browser_ids()), None)
        self._persist_browser_tabs()
        return await self.list()

    async def close_all_browsers(self) -> dict[str, Any]:
        await self.ensure_started()
        await self.close_context()
        return {"browsers": [], "last_interacted_browser_id": None}

    async def close_context(self) -> None:
        for browser_id in self._context_browser_ids():
            await self._stop_screencasts_for_browser(browser_id)
            try:
                await self.pages[browser_id].page.close()
            except Exception:
                pass
            self.pages.pop(browser_id, None)
        self.last_interacted_browser_id = None
        self._restored_context_ids.add(self.current_context_id)
        self._persist_browser_tabs()

    async def screenshot(
        self,
        browser_id: int | str | None = None,
        *,
        quality: int = 70,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        image = await page.screenshot(type="jpeg", quality=max(20, min(95, int(quality))))
        return {
            "browser_id": resolved_id,
            "mime": "image/jpeg",
            "image": base64.b64encode(image).decode("ascii"),
            "state": await self._state(resolved_id),
        }

    async def screenshot_file(
        self,
        browser_id: int | str | None = None,
        *,
        quality: int = 80,
        full_page: bool = False,
        path: str = "",
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        page_context_id = self._page_context_id(self.pages[resolved_id])
        raw_path = str(path or "").strip()
        if not raw_path:
            image = await page.screenshot(
                type="jpeg",
                quality=max(20, min(95, int(quality))),
                full_page=bool(full_page),
            )
            saved = chat_media.save_image_bytes(
                context_id=page_context_id,
                payload=image,
                mime_type="image/jpeg",
                category="screenshots",
                source="browser",
                preferred_name=f"browser-{resolved_id}.jpg",
            )
            return {
                "browser_id": resolved_id,
                "context_id": page_context_id,
                "path": saved.path,
                "a0_path": saved.a0_path,
                "mime": "image/jpeg",
                "ephemeral": False,
                "chat_scoped": True,
                "state": await self._state(resolved_id),
                "vision_load": {
                    "tool_name": "vision_load",
                    "tool_args": {
                        "paths": [saved.a0_path],
                    },
                },
            }

        output_path, image_type, mime = self._screenshot_output_path(resolved_id, path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        clamped_quality = max(20, min(95, int(quality)))
        screenshot_kwargs: dict[str, Any] = {
            "path": str(output_path),
            "type": image_type,
            "full_page": bool(full_page),
        }
        if image_type == "jpeg":
            screenshot_kwargs["quality"] = clamped_quality
        await page.screenshot(**screenshot_kwargs)
        local_path = str(output_path)
        return {
            "browser_id": resolved_id,
            "context_id": page_context_id,
            "path": local_path,
            "a0_path": files.normalize_a0_path(local_path),
            "mime": mime,
            "state": await self._state(resolved_id),
            "vision_load": {
                "tool_name": "vision_load",
                "tool_args": {
                    "paths": [local_path],
                },
            },
        }

    async def start_screencast(
        self,
        browser_id: int | str | None = None,
        *,
        quality: int = 78,
        every_nth_frame: int = 1,
        capture_scale: float = 1.0,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        stream_id = uuid.uuid4().hex
        session = await self.context.new_cdp_session(page)
        screencast = _BrowserScreencast(
            stream_id=stream_id,
            browser_id=resolved_id,
            session=session,
            mime="image/jpeg",
        )
        self.screencasts[stream_id] = screencast
        try:
            await screencast.start(
                quality=quality,
                every_nth_frame=every_nth_frame,
                viewport=await self._page_viewport(page),
                capture_scale=capture_scale,
            )
        except Exception:
            self.screencasts.pop(stream_id, None)
            await screencast.stop()
            raise
        self._maybe_promote(resolved_id)
        return {
            "stream_id": stream_id,
            "browser_id": resolved_id,
            "state": await self._state(resolved_id),
        }

    @staticmethod
    async def _page_viewport(page: Any) -> dict[str, int]:
        viewport = getattr(page, "viewport_size", None)
        if viewport:
            return {
                "width": int(viewport.get("width") or DEFAULT_VIEWPORT["width"]),
                "height": int(viewport.get("height") or DEFAULT_VIEWPORT["height"]),
            }
        try:
            measured = await page.evaluate(
                "() => ({ width: globalThis.innerWidth, height: globalThis.innerHeight })",
                isolated_context=False,
            )
            return {
                "width": int(measured.get("width") or DEFAULT_VIEWPORT["width"]),
                "height": int(measured.get("height") or DEFAULT_VIEWPORT["height"]),
            }
        except Exception:
            return dict(DEFAULT_VIEWPORT)

    async def interactive_viewer(
        self,
        browser_id: int | str | None = None,
        *,
        width: int = 0,
        height: int = 0,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        viewer = self.interactive_view.ensure_viewer(width, height)
        if not viewer.get("available"):
            return viewer

        await self._stop_screencasts_for_browser(resolved_id)
        with contextlib.suppress(Exception):
            await page.bring_to_front()
        viewport_result = await self.set_viewport(
            resolved_id,
            int(viewer.get("width") or width or DEFAULT_VIEWPORT["width"]),
            int(viewer.get("height") or height or DEFAULT_VIEWPORT["height"]),
            resize_interactive=True,
        )
        self.last_interacted_browser_id = int(resolved_id)
        return {
            **viewer,
            "browser_id": resolved_id,
            "state": viewport_result["state"],
            "viewport": viewport_result["viewport"],
        }

    async def read_screencast_frame(
        self,
        stream_id: str,
        *,
        timeout: float = 1.0,
    ) -> dict[str, Any]:
        screencast = self.screencasts.get(str(stream_id or ""))
        if not screencast:
            raise KeyError("Browser screencast is not active.")
        return await screencast.next_frame(timeout=timeout)

    async def pop_screencast_frame(self, stream_id: str) -> dict[str, Any] | None:
        screencast = self.screencasts.get(str(stream_id or ""))
        if not screencast:
            raise KeyError("Browser screencast is not active.")
        return await screencast.pop_frame()

    async def attach_screencast_consumer(
        self,
        stream_id: str,
        frame_consumer: Any,
        stop_callback: Any | None = None,
    ) -> None:
        screencast = self.screencasts.get(str(stream_id or ""))
        if not screencast:
            raise KeyError("Browser screencast is not active.")
        await screencast.attach_consumer(frame_consumer, stop_callback)

    async def stop_screencast(self, stream_id: str) -> None:
        screencast = self.screencasts.pop(str(stream_id or ""), None)
        if screencast:
            await screencast.stop()

    async def set_viewport(
        self,
        browser_id: int | str | None,
        width: int,
        height: int,
        restart_screencast: bool = False,
        resize_interactive: bool = False,
        include_state: bool = True,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        if resize_interactive:
            resized = self.interactive_view.resize(width, height)
            viewport = {
                "width": int(resized.get("width") or self.interactive_view.width),
                "height": int(resized.get("height") or self.interactive_view.height),
            }
            await self._fit_browser_window(page)
            self._maybe_promote(resolved_id)
            return {
                "state": await self._state(resolved_id) if include_state else None,
                "viewport": viewport,
            }

        viewport = {
            "width": max(320, min(4096, int(width or DEFAULT_VIEWPORT["width"]))),
            "height": max(200, min(4096, int(height or DEFAULT_VIEWPORT["height"]))),
        }
        current_viewport = await self._page_viewport(page)
        changed = (
            abs(int(current_viewport.get("width") or 0) - viewport["width"])
            > VIEWPORT_SIZE_TOLERANCE
            or abs(int(current_viewport.get("height") or 0) - viewport["height"])
            > VIEWPORT_SIZE_TOLERANCE
        )
        should_restart_screencast = changed or restart_screencast
        if should_restart_screencast:
            await self._stop_screencasts_for_browser(resolved_id)
        if changed:
            await page.set_viewport_size(viewport)
        if should_restart_screencast:
            await self._settle(page, short=True)
        self._maybe_promote(resolved_id)
        return {"state": await self._state(resolved_id), "viewport": viewport}

    async def _point_for(
        self,
        page: Any,
        reference_id: int | str,
        *,
        offset_x: float = 0,
        offset_y: float = 0,
    ) -> dict[str, Any]:
        await self._ensure_content_helper(page)
        point = await page.evaluate(
            "(args) => globalThis.__spaceBrowserPageContent__.pointFor(args.ref, args.offsets)",
            {
                "ref": reference_id,
                "offsets": {
                    "offset_x": float(offset_x),
                    "offset_y": float(offset_y),
                    "useOffsets": bool(offset_x or offset_y),
                },
            },
            isolated_context=True,
        )
        if not point or not isinstance(point, dict):
            raise ValueError(f"Could not resolve Browser ref {reference_id!r} to a viewport point")
        return point

    async def _input_point(
        self,
        page: Any,
        reference_id: int | str | None,
        *,
        x: float = 0,
        y: float = 0,
        offset_x: float = 0,
        offset_y: float = 0,
    ) -> dict[str, Any]:
        if self._has_reference(reference_id):
            return await self._point_for(
                page,
                reference_id,
                offset_x=offset_x,
                offset_y=offset_y,
            )
        return {
            "x": float(x),
            "y": float(y),
            "rect": None,
            "selector": None,
        }

    async def hover(
        self,
        browser_id: int | str | None,
        ref: int | str | None = None,
        x: float = 0,
        y: float = 0,
        offset_x: float = 0,
        offset_y: float = 0,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        point = await self._input_point(
            page,
            ref,
            x=x,
            y=y,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        await page.mouse.move(float(point["x"]), float(point["y"]))
        self._maybe_promote(resolved_id)
        return {
            "action": {
                "point": point,
                "ref": ref if self._has_reference(ref) else None,
            },
            "state": await self._state(resolved_id),
        }

    async def double_click(
        self,
        browser_id: int | str | None,
        ref: int | str | None = None,
        x: float = 0,
        y: float = 0,
        button: str = "left",
        modifiers: list[str] | str | None = None,
        offset_x: float = 0,
        offset_y: float = 0,
    ) -> dict[str, Any]:
        modifiers = self._normalize_modifiers(modifiers)
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        point = await self._input_point(
            page,
            ref,
            x=x,
            y=y,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        pressed: list[str] = []
        try:
            if modifiers:
                for mod in modifiers:
                    await page.keyboard.down(mod)
                    pressed.append(mod)
            await page.mouse.dblclick(float(point["x"]), float(point["y"]), button=button or "left")
        finally:
            for mod in reversed(pressed):
                with contextlib.suppress(Exception):
                    await page.keyboard.up(mod)
        await self._settle(page, short=True)
        self._maybe_promote(resolved_id)
        return {
            "action": {
                "button": button or "left",
                "modifiers": modifiers or [],
                "point": point,
                "ref": ref if self._has_reference(ref) else None,
            },
            "state": await self._state(resolved_id),
        }

    async def right_click(
        self,
        browser_id: int | str | None,
        ref: int | str | None = None,
        x: float = 0,
        y: float = 0,
        modifiers: list[str] | str | None = None,
        offset_x: float = 0,
        offset_y: float = 0,
    ) -> dict[str, Any]:
        modifiers = self._normalize_modifiers(modifiers)
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        point = await self._input_point(
            page,
            ref,
            x=x,
            y=y,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        pressed: list[str] = []
        try:
            if modifiers:
                for mod in modifiers:
                    await page.keyboard.down(mod)
                    pressed.append(mod)
            await page.mouse.click(float(point["x"]), float(point["y"]), button="right")
        finally:
            for mod in reversed(pressed):
                with contextlib.suppress(Exception):
                    await page.keyboard.up(mod)
        await self._settle(page, short=True)
        self._maybe_promote(resolved_id)
        return {
            "action": {
                "button": "right",
                "modifiers": modifiers or [],
                "point": point,
                "ref": ref if self._has_reference(ref) else None,
            },
            "state": await self._state(resolved_id),
        }

    async def drag(
        self,
        browser_id: int | str | None,
        ref: int | str | None = None,
        target_ref: int | str | None = None,
        x: float = 0,
        y: float = 0,
        to_x: float = 0,
        to_y: float = 0,
        offset_x: float = 0,
        offset_y: float = 0,
        target_offset_x: float = 0,
        target_offset_y: float = 0,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        start_point = await self._input_point(
            page,
            ref,
            x=x,
            y=y,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        end_point = await self._input_point(
            page,
            target_ref,
            x=to_x,
            y=to_y,
            offset_x=target_offset_x,
            offset_y=target_offset_y,
        )
        await page.mouse.move(float(start_point["x"]), float(start_point["y"]))
        await page.mouse.down()
        await page.mouse.move(float(end_point["x"]), float(end_point["y"]), steps=12)
        await page.mouse.up()
        await self._settle(page, short=True)
        self._maybe_promote(resolved_id)
        return {
            "action": {
                "from": start_point,
                "ref": ref if self._has_reference(ref) else None,
                "target_ref": target_ref if self._has_reference(target_ref) else None,
                "to": end_point,
            },
            "state": await self._state(resolved_id),
        }

    async def select_option(
        self,
        browser_id: int | str | None,
        ref: int | str,
        value: str = "",
        values: list[str] | None = None,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await self._ensure_content_helper(page)
        action = await page.evaluate(
            "(args) => globalThis.__spaceBrowserPageContent__.select(args.ref, args.values)",
            {
                "ref": ref,
                "values": values if values is not None else value,
            },
            isolated_context=True,
        )
        await self._settle(page, short=True)
        self._maybe_promote(resolved_id)
        return {"action": action or {}, "state": await self._state(resolved_id)}

    async def set_checked(
        self,
        browser_id: int | str | None,
        ref: int | str,
        checked: bool = True,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await self._ensure_content_helper(page)
        action = await page.evaluate(
            "(args) => globalThis.__spaceBrowserPageContent__.setChecked(args.ref, args.checked)",
            {
                "ref": ref,
                "checked": bool(checked),
            },
            isolated_context=True,
        )
        await self._settle(page, short=True)
        self._maybe_promote(resolved_id)
        return {"action": action or {}, "state": await self._state(resolved_id)}

    async def upload_file(
        self,
        browser_id: int | str | None,
        ref: int | str,
        path: str = "",
        paths: list[str] | None = None,
    ) -> dict[str, Any]:
        upload_paths = self._normalize_upload_paths(path=path, paths=paths)
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await self._ensure_content_helper(page)
        metadata = await page.evaluate(
            "(ref) => globalThis.__spaceBrowserPageContent__.fileInputFor(ref)",
            ref,
            isolated_context=True,
        )
        handle = None
        try:
            handle = await page.evaluate_handle(
                "(ref) => globalThis.__spaceBrowserPageContent__.fileInputElementFor(ref)",
                ref,
                isolated_context=True,
            )
            element = handle.as_element() if handle else None
            if element:
                await element.set_input_files(upload_paths)
            elif metadata and metadata.get("selector"):
                await page.set_input_files(metadata["selector"], upload_paths)
            else:
                raise ValueError(f"Browser ref {ref!r} does not resolve to a file input")
        finally:
            if handle:
                with contextlib.suppress(Exception):
                    await handle.dispose()
        await self._settle(page, short=True)
        self._maybe_promote(resolved_id)
        return {
            "action": {
                "files": upload_paths,
                "input": metadata or {},
                "ref": ref,
            },
            "state": await self._state(resolved_id),
        }

    async def mouse(
        self,
        browser_id: int | str | None,
        event_type: str,
        x: float,
        y: float,
        button: str = "left",
        modifiers: list[str] | str | None = None,
    ) -> dict[str, Any]:
        event_type_lower = str(event_type or "click").lower()
        modifiers = self._normalize_modifiers(modifiers)
        if modifiers:
            if event_type_lower != "click":
                raise ValueError("modifiers are only valid for event_type='click'")
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        if event_type_lower == "move":
            await page.mouse.move(float(x), float(y))
        elif event_type_lower == "down":
            await page.mouse.down(button=button)
        elif event_type_lower == "up":
            await page.mouse.up(button=button)
        else:
            pressed: list[str] = []
            try:
                if modifiers:
                    for mod in modifiers:
                        await page.keyboard.down(mod)
                        pressed.append(mod)
                await page.mouse.click(float(x), float(y), button=button)
            finally:
                for mod in reversed(pressed):
                    with contextlib.suppress(Exception):
                        await page.keyboard.up(mod)
            await self._settle(page, short=True)
        self._maybe_promote(resolved_id)
        return await self._state(resolved_id)

    async def wheel(
        self,
        browser_id: int | str | None,
        x: float,
        y: float,
        delta_x: float = 0,
        delta_y: float = 0,
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await page.mouse.move(float(x), float(y))
        await page.mouse.wheel(float(delta_x), float(delta_y))
        self._maybe_promote(resolved_id)
        return await self._state(resolved_id)

    async def keyboard(
        self,
        browser_id: int | str | None,
        *,
        key: str = "",
        text: str = "",
    ) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        if text:
            await page.keyboard.type(str(text))
        elif key:
            await page.keyboard.press(str(key))
        await self._settle(page, short=True)
        self._maybe_promote(resolved_id)
        return await self._state(resolved_id)

    async def _insert_clipboard_text(self, page: Any, text: str) -> bool:
        if not text:
            return False
        insert_text = getattr(page.keyboard, "insert_text", None)
        if callable(insert_text):
            await insert_text(str(text))
        else:
            await page.keyboard.type(str(text))
        return True

    async def close(self, delete_profile: bool = False) -> None:
        if delete_profile:
            with contextlib.suppress(Exception):
                kvp.remove_persistent(BROWSER_TABS_KEY)
            self._restore_entries.clear()
            self._restore_state_exists = False
        else:
            self._persist_browser_tabs()
        self._closing = True
        for waiter in self._pending_popups:
            if not waiter.done():
                waiter.set_exception(RuntimeError("Browser runtime is closing."))
        self._pending_popups.clear()
        self._pending_popup_contexts.clear()
        self._background_popup_pages.clear()
        await self._stop_all_screencasts()
        await self._reset_browser_window_session()
        for browser_id in list(self.pages):
            try:
                await self.pages[browser_id].page.close()
            except Exception:
                pass
        self.pages.clear()
        if self.context:
            try:
                await self.context.close()
            except Exception as exc:
                PrintStyle.warning(f"Browser context close failed: {exc}")
            self.context = None
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as exc:
                PrintStyle.warning(f"Playwright stop failed: {exc}")
            self.playwright = None
        self._last_interacted_browser_ids.clear()
        if delete_profile:
            shutil.rmtree(self.profile_dir, ignore_errors=True)

    def _on_context_closed(self) -> None:
        if self._closing or self.context is None:
            return
        PrintStyle.warning("Browser context closed unexpectedly; will restart on next use.")
        self._discard_context_state()

    async def _reference_action(
        self,
        helper_method: str,
        browser_id: int | str | None,
        reference_id: int | str,
        text: str | None = None,
    ) -> dict[str, Any]:
        resolved_id = self._resolve_browser_id(browser_id)
        page = self._page(resolved_id)
        await self._ensure_content_helper(page)
        if text is None:
            action = await page.evaluate(
                "(args) => globalThis.__spaceBrowserPageContent__[args.method](args.ref)",
                {"method": helper_method, "ref": reference_id},
                isolated_context=True,
            )
        else:
            action = await page.evaluate(
                "(args) => globalThis.__spaceBrowserPageContent__[args.method](args.ref, args.text)",
                {"method": helper_method, "ref": reference_id, "text": text},
                isolated_context=True,
            )
        await self._settle(page, short=False)
        self._maybe_promote(resolved_id)
        return {"action": action or {}, "state": await self._state(resolved_id)}

    async def _goto(
        self,
        page: Any,
        url: str,
        *,
        wait_until: str = "domcontentloaded",
    ) -> None:
        from patchright.async_api import Error as PlaywrightError
        from patchright.async_api import TimeoutError as PlaywrightTimeoutError

        try:
            await page.goto(url, wait_until=wait_until, timeout=30000)
        except PlaywrightTimeoutError:
            PrintStyle.warning(f"Browser navigation timed out waiting for {wait_until}: {url}")
        except PlaywrightError as exc:
            PrintStyle.warning(f"Browser navigation showed a native error page for {url}: {exc}")

    async def _settle(self, page: Any, short: bool = False) -> None:
        from patchright.async_api import Error as PlaywrightError
        from patchright.async_api import TimeoutError as PlaywrightTimeoutError

        try:
            await page.wait_for_load_state(
                "domcontentloaded",
                timeout=1000 if short else 5000,
            )
        except (PlaywrightError, PlaywrightTimeoutError):
            pass
        await asyncio.sleep(0.1 if short else 0.35)

    async def _state(self, browser_id: int) -> dict[str, Any]:
        browser_page = self.pages.get(int(browser_id))
        if not browser_page:
            raise KeyError(f"Browser {browser_id} is not open.")
        page = browser_page.page
        try:
            state = await page.evaluate(
                "() => ({title: document.title, canGoBack: history.length > 1, "
                "loading: document.readyState !== 'complete', zoom: Math.round(devicePixelRatio * 100)})",
                isolated_context=False,
            )
        except Exception:
            state = {}
        return {
            "id": browser_page.id,
            "context_id": self._page_context_id(browser_page),
            "currentUrl": page.url,
            "title": state.get("title", ""),
            "canGoBack": bool(state.get("canGoBack")),
            "canGoForward": False,
            "loading": bool(state.get("loading")),
            "zoom": state.get("zoom", 100),
            "zoom_available": bool(self.interactive_view.display_name and shutil.which("xdotool")),
        }

    def _register_page_locked(
        self,
        page: Any,
        context_id: str | None = None,
    ) -> BrowserPage:
        requested_context_id = str(context_id or self.current_context_id)
        existing = self._browser_id_for_page(page)
        if existing is not None:
            browser_page = self.pages[existing]
            if (
                context_id is not None
                and self._page_context_id(browser_page) != requested_context_id
            ):
                previous_context_id = self._page_context_id(browser_page)
                browser_page.context_id = requested_context_id
                if self._last_interacted_browser_ids.get(previous_context_id) == existing:
                    self._set_last_interacted(previous_context_id, None)
            return browser_page
        browser_id = self.next_browser_id
        self.next_browser_id += 1
        browser_page = BrowserPage(
            id=browser_id,
            page=page,
            context_id=requested_context_id,
        )
        self.pages[browser_id] = browser_page

        def on_close() -> None:
            try:
                asyncio.create_task(self._unregister_page_async(browser_id))
            except RuntimeError:
                # No running loop (e.g., during shutdown). Best-effort sync pop.
                self.pages.pop(browser_id, None)

        page.on("close", on_close)

        def on_navigated(frame: Any) -> None:
            main_frame = getattr(page, "main_frame", None)
            if main_frame is not None and frame is not main_frame:
                return
            try:
                asyncio.create_task(self._persist_page_change_async(browser_id))
            except RuntimeError:
                return

        page.on("framenavigated", on_navigated)
        return browser_page

    async def _register_page(
        self,
        page: Any,
        context_id: str | None = None,
    ) -> BrowserPage:
        lock = self._ensure_registry_lock()
        async with lock:
            browser_page = self._register_page_locked(page, context_id)
        await self._fit_browser_window(page)
        return browser_page

    async def _fit_browser_window(self, page: Any) -> None:
        if getattr(self.interactive_view, "display", None) is None or not self.context:
            return
        try:
            if self._browser_window_session is None or self._browser_window_page is not page:
                await self._reset_browser_window_session()
                self._browser_window_page = page
                self._browser_window_session = await self.context.new_cdp_session(page)
                target = await self._browser_window_session.send("Browser.getWindowForTarget")
                self._browser_window_id = target.get("windowId")
                if self._browser_window_id is None:
                    await self._reset_browser_window_session()
                    return
                current = await self._browser_window_session.send(
                    "Browser.getWindowBounds",
                    {"windowId": self._browser_window_id},
                )
                if current.get("bounds", {}).get("windowState") != "normal":
                    await self._browser_window_session.send(
                        "Browser.setWindowBounds",
                        {
                            "windowId": self._browser_window_id,
                            "bounds": {"windowState": "normal"},
                        },
                    )
            if self._browser_chrome_height is None:
                chrome_height = await page.evaluate(
                    "() => Math.max(0, globalThis.outerHeight - globalThis.innerHeight)",
                    isolated_context=False,
                )
                self._browser_chrome_height = max(0, min(256, int(chrome_height or 0)))
            chrome_height = self._browser_chrome_height
            await self._browser_window_session.send(
                "Browser.setWindowBounds",
                {
                    "windowId": self._browser_window_id,
                    "bounds": {
                        "windowState": "normal",
                        "left": 0,
                        "top": -chrome_height,
                        "width": self.interactive_view.width,
                        "height": self.interactive_view.height + chrome_height,
                    },
                },
            )
        except Exception as exc:
            await self._reset_browser_window_session()
            PrintStyle.warning(f"Interactive Browser window fit failed: {exc}")

    async def _reset_browser_window_session(self) -> None:
        session = self._browser_window_session
        self._browser_window_page = None
        self._browser_window_session = None
        self._browser_window_id = None
        if session:
            with contextlib.suppress(Exception):
                await session.detach()

    async def _unregister_page_async(self, browser_id: int) -> None:
        try:
            lock = self._ensure_registry_lock()
            async with lock:
                browser_page = self.pages.pop(browser_id, None)
                if browser_page:
                    context_id = self._page_context_id(browser_page)
                    if self._last_interacted_browser_ids.get(context_id) == browser_id:
                        remaining = self._context_browser_ids(context_id)
                        self._set_last_interacted(
                            context_id,
                            next(iter(remaining), None),
                        )
                self._background_popup_pages.discard(browser_id)
        except Exception as exc:
            PrintStyle.warning(f"Page unregister failed: {exc}")

    async def _persist_page_change_async(self, browser_id: int) -> None:
        await asyncio.sleep(0)
        if self._closing or self._restoring_tabs or browser_id not in self.pages:
            return
        self._persist_browser_tabs()

    def _on_new_page_sync(self, page: Any) -> None:
        if self._closing or self.context is None:
            return
        try:
            asyncio.create_task(self._on_new_page_async(page))
        except RuntimeError:
            return

    async def _on_new_page_async(self, page: Any) -> None:
        try:
            with contextlib.suppress(Exception):
                await page.wait_for_load_state("domcontentloaded", timeout=2000)
            if self._closing or page.is_closed():
                return
            lock = self._ensure_registry_lock()
            close_over_limit = False
            context_id = await self._new_page_context_id(page)
            async with lock:
                if self._closing:
                    return
                if self._browser_id_for_page(page) is not None:
                    return
                if len(self._context_browser_ids(context_id)) >= self._max_open_tabs():
                    limit_error = self._tab_limit_error(context_id)
                    waiter = self._pop_pending_popup(context_id)
                    if waiter:
                        waiter.set_exception(limit_error)
                    close_over_limit = True
                else:
                    browser_page = self._register_page_locked(page, context_id)
                    new_id = browser_page.id
                    waiter = self._pop_pending_popup(context_id)
                    if waiter:
                        waiter.set_result(new_id)
                    if new_id not in self._background_popup_pages:
                        self._set_last_interacted(context_id, new_id)
                    else:
                        self._background_popup_pages.discard(new_id)
            if close_over_limit:
                with contextlib.suppress(Exception):
                    await page.close()
            else:
                await self._fit_browser_window(page)
                self._persist_browser_tabs()
        except Exception as exc:
            PrintStyle.warning(f"Popup registration failed: {exc}")

    async def _new_page_context_id(self, page: Any) -> str:
        opener_fn = getattr(page, "opener", None)
        if callable(opener_fn):
            with contextlib.suppress(Exception):
                opener = await opener_fn()
                opener_id = self._browser_id_for_page(opener)
                if opener_id is not None:
                    return self._page_context_id(self.pages[opener_id])
        for waiter in self._pending_popups:
            context_id = self._pending_popup_contexts.get(waiter)
            if context_id and not waiter.done():
                return context_id
        return self.current_context_id

    def _pop_pending_popup(self, context_id: str) -> asyncio.Future[int] | None:
        for waiter in list(self._pending_popups):
            if waiter.done():
                self._pending_popups.remove(waiter)
                self._pending_popup_contexts.pop(waiter, None)
                continue
            if self._pending_popup_contexts.get(waiter) != context_id:
                continue
            self._pending_popups.remove(waiter)
            self._pending_popup_contexts.pop(waiter, None)
            return waiter
        return None

    def _browser_id_for_page(self, page: Any) -> int | None:
        for browser_id, browser_page in self.pages.items():
            if browser_page.page == page:
                return browser_id
        return None

    def _resolve_browser_id(self, browser_id: int | str | None = None) -> int:
        browser_ids = self._context_browser_ids()
        if browser_id is None or str(browser_id).strip() == "":
            if self.last_interacted_browser_id in browser_ids:
                return int(self.last_interacted_browser_id)
            if browser_ids:
                return browser_ids[0]
            raise KeyError("No browser is open. Use action=open first.")
        value = str(browser_id).strip()
        if value.startswith("browser-"):
            value = value.split("-", 1)[1]
        resolved = int(value)
        if resolved not in browser_ids:
            raise KeyError(f"Browser {resolved} is not open.")
        return resolved

    def _page(self, browser_id: int) -> Any:
        return self.pages[int(browser_id)].page

    async def _stop_screencasts_for_browser(self, browser_id: int) -> None:
        stream_ids = [
            stream_id
            for stream_id, screencast in self.screencasts.items()
            if screencast.browser_id == int(browser_id)
        ]
        for stream_id in stream_ids:
            await self.stop_screencast(stream_id)

    async def _stop_all_screencasts(self) -> None:
        for stream_id in list(self.screencasts):
            await self.stop_screencast(stream_id)

    async def _ensure_content_helper(self, page: Any) -> None:
        await self._ensure_dom_helper(page)
        has_helper = await page.evaluate(
            "() => Boolean(globalThis.__spaceBrowserPageContent__?.ready?.())",
            isolated_context=True,
        )
        if has_helper:
            return
        if self._content_helper_source is None:
            self._content_helper_source = CONTENT_HELPER_PATH.read_text(encoding="utf-8")
        await page.evaluate(self._content_helper_source, isolated_context=True)

    async def _ensure_dom_helper(self, page: Any) -> None:
        if self._dom_helper_source is None:
            self._dom_helper_source = DOM_HELPER_PATH.read_text(encoding="utf-8")
        await self._ensure_helper_source(
            page,
            self._dom_helper_source,
            "() => Boolean(globalThis.__spaceBrowserDomHelper__?.captureDocument)",
        )

    async def _ensure_helper_source(self, page: Any, source: str, ready_script: str) -> None:
        targets = [page]
        frames = getattr(page, "frames", None)
        if isinstance(frames, list) and frames:
            targets = frames
        for target in targets:
            try:
                has_helper = await target.evaluate(ready_script, isolated_context=True)
            except Exception:
                continue
            if has_helper:
                continue
            with contextlib.suppress(Exception):
                await target.evaluate(source, isolated_context=True)

_runtimes: dict[str, BrowserRuntimeSession] = {}
_shared_runtime: BrowserRuntime | None = None
_runtime_lock = threading.RLock()


async def get_runtime(
    context_id: str,
    *,
    create: bool = True,
) -> BrowserRuntimeSession | None:
    global _shared_runtime
    context_id = str(context_id or "").strip()
    if not context_id:
        raise ValueError("context_id is required")
    with _runtime_lock:
        runtime = _runtimes.get(context_id)
        if runtime is None and _shared_runtime is not None:
            runtime = BrowserRuntimeSession(context_id, _shared_runtime)
            if create:
                _runtimes[context_id] = runtime
        elif runtime is None and create:
            if _shared_runtime is None:
                _shared_runtime = BrowserRuntime(SHARED_RUNTIME_ID)
            runtime = BrowserRuntimeSession(context_id, _shared_runtime)
            _runtimes[context_id] = runtime
        return runtime


async def close_runtime(context_id: str, *, delete_profile: bool = True) -> None:
    context_id = str(context_id or "").strip()
    if not context_id:
        return
    _forget_browser_context(context_id)
    with _runtime_lock:
        runtime = _runtimes.pop(context_id, None)
        shared_runtime = _shared_runtime
    try:
        if runtime:
            await runtime.call("close_context")
        elif shared_runtime:
            await shared_runtime.call_for(context_id, "close_context")
    except BrowserWorkerStoppedError as exc:
        # A stopped worker cannot reach the context's tabs; do not block chat reset/removal.
        PrintStyle.warning(f"Browser cleanup skipped for context {context_id}: {exc}")


def close_runtime_sync(context_id: str, *, delete_profile: bool = True) -> None:
    task = DeferredTask(thread_name="BrowserCleanup")
    task.start_task(close_runtime, context_id, delete_profile=delete_profile)
    try:
        task.result_sync(timeout=30)
    finally:
        task.kill()


async def close_all_runtimes(*, delete_profiles: bool = False) -> None:
    global _shared_runtime
    with _runtime_lock:
        _runtimes.clear()
        runtime = _shared_runtime
        _shared_runtime = None
    if delete_profiles:
        with contextlib.suppress(Exception):
            kvp.remove_persistent(BROWSER_TABS_KEY)
    if runtime:
        try:
            await runtime.close(delete_profile=delete_profiles)
        except Exception as exc:
            PrintStyle.warning(f"Browser runtime cleanup failed: {exc}")


def close_all_runtimes_sync() -> None:
    task = DeferredTask(thread_name="BrowserCleanupAll")
    task.start_task(close_all_runtimes, delete_profiles=False)
    try:
        task.result_sync(timeout=30)
    finally:
        task.kill(terminate_thread=True)


def known_context_ids() -> list[str]:
    with _runtime_lock:
        return sorted(_runtimes)


async def list_runtime_sessions() -> list[dict[str, Any]]:
    with _runtime_lock:
        runtimes = list(_runtimes.items())
        shared_runtime = _shared_runtime

    if shared_runtime and str(
        get_browser_config().get(TAB_SCOPE_KEY, DEFAULT_BROWSER_TAB_SCOPE)
        or DEFAULT_BROWSER_TAB_SCOPE
    ) == "shared":
        request_context_id = runtimes[0][0] if runtimes else SHARED_RUNTIME_ID
        try:
            listing = await shared_runtime.call_for(request_context_id, "list_all")
        except Exception as exc:
            PrintStyle.warning(f"Shared Browser runtime list failed: {exc}")
            return []
        grouped: dict[str, list[dict[str, Any]]] = {}
        for browser in listing.get("browsers") or []:
            context_id = str(browser.get("context_id") or SHARED_RUNTIME_ID)
            grouped.setdefault(context_id, []).append(browser)
        active_ids = listing.get("last_interacted_browser_ids") or {}
        return [
            {
                "context_id": context_id,
                "browsers": browsers,
                "last_interacted_browser_id": active_ids.get(context_id),
            }
            for context_id, browsers in grouped.items()
        ]

    sessions: list[dict[str, Any]] = []
    for context_id, runtime in runtimes:
        try:
            listing = await runtime.call("list")
        except Exception as exc:
            PrintStyle.warning(f"Browser runtime list failed for context {context_id}: {exc}")
            continue
        sessions.append(
            {
                "context_id": context_id,
                "browsers": listing.get("browsers") or [],
                "last_interacted_browser_id": listing.get("last_interacted_browser_id"),
            }
        )
    return sessions


atexit.register(close_all_runtimes_sync)
