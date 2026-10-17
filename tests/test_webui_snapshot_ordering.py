"""Regression tests for the Web UI snapshot-application ordering.

Root cause (2026-08-02): after a WebSocket reconnect mid-turn, the frontend
receives a snapshot whose log version advanced while disconnected. In
``applySnapshot`` the cheap agent-state fields (progress indicator, paused
flag, notifications) were applied only AFTER ``await setMessages(...)``.
For large chats the message re-render can take a very long time, so a stale
"A0: Reasoning..." indicator stayed on screen — making an idle, finished
agent look like it was still working — until the render backlog drained.

The fix sequences the cheap state updates before the render await. These
tests pin that ordering in ``webui/index.js``.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_apply_snapshot_body() -> str:
    js = (PROJECT_ROOT / "webui" / "index.js").read_text(encoding="utf-8")
    start = js.find("export async function applySnapshot(")
    assert start != -1, "applySnapshot function not found in webui/index.js"
    # Skip the parameter list first (its `options = {}` default would fool a
    # naive brace counter), then brace-count the body to its matching close.
    paren_open = js.find("(", start)
    depth = 0
    pos = paren_open
    while pos < len(js):
        char = js[pos]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
        pos += 1
    body_start = js.find("{", pos)
    assert body_start != -1, "applySnapshot body opening brace not found"
    depth = 0
    for pos in range(body_start, len(js)):
        char = js[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return js[start : pos + 1]
    raise AssertionError("applySnapshot body is unbalanced in webui/index.js")


def test_apply_snapshot_updates_progress_before_render():
    body = _load_apply_snapshot_body()
    progress_pos = body.find("updateProgress(snapshot.log_progress")
    render_pos = body.find("await setMessages(modelGateStore")
    assert progress_pos != -1, "updateProgress call not found in applySnapshot"
    assert render_pos != -1, "setMessages render call not found in applySnapshot"
    assert progress_pos < render_pos, (
        "updateProgress must run before `await setMessages(...)` so the "
        "progress indicator cannot go stale behind a slow re-render"
    )


def test_apply_snapshot_updates_paused_before_render():
    body = _load_apply_snapshot_body()
    paused_pos = body.find("inputStore.paused = snapshot.paused")
    render_pos = body.find("await setMessages(modelGateStore")
    assert paused_pos != -1, "paused assignment not found in applySnapshot"
    assert render_pos != -1, "setMessages render call not found in applySnapshot"
    assert paused_pos < render_pos, (
        "inputStore.paused must run before `await setMessages(...)` so the "
        "paused state cannot go stale behind a slow re-render"
    )


def test_apply_snapshot_updates_notifications_before_render():
    body = _load_apply_snapshot_body()
    notif_pos = body.find("notificationStore.updateFromPoll(snapshot)")
    render_pos = body.find("await setMessages(modelGateStore")
    assert notif_pos != -1, "notification update not found in applySnapshot"
    assert render_pos != -1, "setMessages render call not found in applySnapshot"
    assert notif_pos < render_pos, (
        "notifications must update before `await setMessages(...)` so they "
        "cannot be delayed by a slow re-render"
    )


def test_apply_snapshot_keeps_log_cursors_after_render():
    """Cursor updates must stay after the render block: if the render throws,
    the next poll must retry the same log version instead of skipping it."""
    body = _load_apply_snapshot_body()
    render_pos = body.find("await setMessages(modelGateStore")
    cursor_pos = body.find("lastLogVersion = snapshot.log_version")
    assert render_pos != -1 and cursor_pos != -1
    assert cursor_pos > render_pos, (
        "lastLogVersion must only advance after setMessages succeeds"
    )
