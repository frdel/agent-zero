import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers import chat_media, files as files_helper
from helpers.log import Log
from helpers.tool import Response
from tools.response import ResponseTool
from extensions.python._functions.agent.Agent.hist_add_ai_response.end._10_log_plain_responses import (
    LogPlainResponses,
)


def _patch_chat_media_paths(monkeypatch, tmp_path: Path) -> None:
    def fake_get_abs_path(*parts):
        joined = Path(*parts) if parts else Path()
        if joined.is_absolute():
            raw = str(joined)
            if raw.startswith("/a0/"):
                return str(tmp_path.joinpath(raw[4:]))
            try:
                return str(tmp_path.joinpath(joined.relative_to("/a0")))
            except ValueError:
                return raw
        return str(tmp_path.joinpath(*parts))

    def fake_normalize_a0_path(path):
        resolved = Path(path)
        try:
            relative = resolved.relative_to(tmp_path)
        except ValueError:
            relative = resolved
        return "/a0/" + str(relative).replace("\\", "/")

    def fake_fix_dev_path(path):
        raw = str(path)
        if raw.startswith("/a0/"):
            raw = raw[4:]
        return str(tmp_path.joinpath(raw))

    monkeypatch.setattr(files_helper, "get_abs_path", fake_get_abs_path)
    monkeypatch.setattr(files_helper, "normalize_a0_path", fake_normalize_a0_path)
    monkeypatch.setattr(files_helper, "fix_dev_path", fake_fix_dev_path)
    monkeypatch.setattr(chat_media.files, "get_abs_path", fake_get_abs_path)
    monkeypatch.setattr(chat_media.files, "normalize_a0_path", fake_normalize_a0_path)
    monkeypatch.setattr(chat_media.files, "fix_dev_path", fake_fix_dev_path)


def test_snapshot_image_refs_copies_reused_workdir_file(tmp_path, monkeypatch):
    _patch_chat_media_paths(monkeypatch, tmp_path)
    live = tmp_path / "usr" / "workdir" / "logo.png"
    live.parent.mkdir(parents=True)
    live.write_bytes(b"first-version")

    markdown = "![logo](img:///a0/usr/workdir/logo.png)"
    rewritten = chat_media.snapshot_image_refs(markdown, context_id="chat-1")

    assert rewritten != markdown
    assert rewritten.startswith("![logo](img:///a0/usr/chats/chat-1/images/response/logo-")
    stored = tmp_path / rewritten[len("![logo](img://"):-1].removeprefix("/a0/")
    assert stored.read_bytes() == b"first-version"

    live.write_bytes(b"second-version")
    second = chat_media.snapshot_image_refs(markdown, context_id="chat-1")
    second_stored = tmp_path / second[len("![logo](img://"):-1].removeprefix("/a0/")
    assert second_stored.read_bytes() == b"second-version"
    assert stored.read_bytes() == b"first-version"
    assert stored != second_stored


def test_snapshot_image_refs_keeps_chat_scoped_paths(tmp_path, monkeypatch):
    _patch_chat_media_paths(monkeypatch, tmp_path)
    existing = (
        tmp_path
        / "usr"
        / "chats"
        / "chat-1"
        / "images"
        / "vision-load"
        / "logo-already.png"
    )
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"vision-copy")
    markdown = f"![logo](img://{chat_media.files.normalize_a0_path(str(existing))})"

    rewritten = chat_media.snapshot_image_refs(markdown, context_id="chat-1")

    assert rewritten == markdown
    copies = list((tmp_path / "usr" / "chats" / "chat-1" / "images" / "response").glob("*"))
    assert copies == []


def test_snapshot_image_refs_leaves_missing_files_unchanged(tmp_path, monkeypatch):
    _patch_chat_media_paths(monkeypatch, tmp_path)
    markdown = "![gone](img:///a0/usr/workdir/missing.png)"

    assert chat_media.snapshot_image_refs(markdown, context_id="chat-1") == markdown


def test_response_tool_snapshots_finished_log_content(tmp_path, monkeypatch):
    _patch_chat_media_paths(monkeypatch, tmp_path)
    live = tmp_path / "usr" / "workdir" / "board_submit.png"
    live.parent.mkdir(parents=True)
    live.write_bytes(b"board-v1")

    log = Log()
    item = log.log(
        type="response",
        content="![board](img:///a0/usr/workdir/board_submit.png)",
    )
    agent = SimpleNamespace(context=SimpleNamespace(id="chat-logo", get_data=lambda *_a, **_k: None))
    tool = ResponseTool(
        agent,
        "response",
        None,
        {"text": item.content},
        "",
        SimpleNamespace(params_temporary={"log_item_response": item}),
    )

    asyncio.run(tool.after_execution(Response(message=item.content, break_loop=True)))

    assert item.kvps["finished"] is True
    assert "usr/chats/chat-logo/images/response/board_submit-" in item.content
    live.write_bytes(b"board-v2")
    stored = tmp_path / item.content.split("img://", 1)[1][:-1].removeprefix("/a0/")
    assert stored.read_bytes() == b"board-v1"


def test_plain_response_logging_snapshots_image_markdown(tmp_path, monkeypatch):
    _patch_chat_media_paths(monkeypatch, tmp_path)
    live = tmp_path / "usr" / "workdir" / "logo.png"
    live.parent.mkdir(parents=True)
    live.write_bytes(b"plain-v1")

    log = Log()
    item = log.log(type="agent", heading="A0: Calling LLM...", id="msg-1")
    agent = SimpleNamespace(
        loop_data=SimpleNamespace(params_temporary={"log_item_generating": item}),
        context=SimpleNamespace(id="chat-plain", get_data=lambda *_a, **_k: None),
    )
    data = {
        "args": (agent, "![logo](img:///a0/usr/workdir/logo.png)"),
        "kwargs": {"id": "msg-1", "llm_result": SimpleNamespace(mode="responses")},
    }

    LogPlainResponses(agent=agent).execute(data=data)

    assert item.type == "response"
    assert "usr/chats/chat-plain/images/response/logo-" in item.content
    live.write_bytes(b"plain-v2")
    stored = tmp_path / item.content.split("img://", 1)[1][:-1].removeprefix("/a0/")
    assert stored.read_bytes() == b"plain-v1"
