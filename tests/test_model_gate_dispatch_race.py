import re
from pathlib import Path

STORE = Path("webui/components/chat/model-gate-store.js").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    start = STORE.index(f"  async {name}(")
    end = STORE.index("\n  },", start)
    return STORE[start:end]


def test_dispatch_captures_pending_before_await():
    body = _function_source("dispatchPendingIfConfigured")
    capture_at = body.index("const pending = this.pending;")
    latch_at = body.index("this.dispatching = true;")
    await_at = body.index("await this.canSendToModel();")
    assert capture_at < await_at
    assert latch_at < await_at


def test_dispatch_rechecks_pending_identity_after_await():
    body = _function_source("dispatchPendingIfConfigured")
    await_at = body.index("await this.canSendToModel();")
    recheck_at = body.index("this.pending !== pending")
    assert await_at < recheck_at


def test_dispatch_never_reads_message_without_pending_guard():
    body = _function_source("dispatchPendingIfConfigured")
    assert "!pending" in body
    # message is only read from the captured local, never from this.pending
    assert "pending.message" in body
    assert not re.search(r"this\.pending\.message", body)


def test_open_advanced_catch_reports_readable_message():
    body = _function_source("openAdvancedModelConfiguration")
    assert "error?.message" in body
