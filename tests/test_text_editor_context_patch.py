import asyncio
import importlib
import inspect
import os
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins._text_editor.helpers.context_patch import ContextPatchError
from plugins._text_editor.helpers import file_ops
from plugins._text_editor.helpers.file_ops import (
    apply_context_patch_file,
    apply_exact_replace_file,
)
from plugins._text_editor.helpers.patch_request import (
    exact_replace_to_patch_text,
    parse_patch_request,
)
from plugins._text_editor.helpers.patch_state import (
    LOCAL_FRESHNESS_KEY,
    REMOTE_FRESHNESS_KEY,
    apply_patch_post_state,
    check_patch_freshness,
    mark_file_state_stale,
    record_file_state,
)


@pytest.mark.parametrize("method", ["line", "context", "exact"])
@pytest.mark.parametrize("mode", [0o600, 0o640, 0o644, 0o755])
def test_patch_preserves_file_access(tmp_path: Path, method: str, mode: int) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("before\n", encoding="utf-8")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        os.chown(target, 12345, 23456)
    target.chmod(mode)
    before = target.stat()

    _patch_sample(target, method)

    after = target.stat()
    assert (after.st_mode, after.st_uid, after.st_gid) == (
        before.st_mode, before.st_uid, before.st_gid
    )
    assert target.read_text(encoding="utf-8") == "after\n"


@pytest.mark.parametrize("method", ["line", "context", "exact"])
def test_patch_metadata_failure_keeps_original(
    tmp_path: Path, monkeypatch, method: str
) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("before\n", encoding="utf-8")
    before = target.stat()

    def fail(*args, **kwargs):
        raise PermissionError("metadata denied")

    monkeypatch.setattr(file_ops.os, "chmod", fail)
    with pytest.raises(PermissionError, match="metadata denied"):
        _patch_sample(target, method)

    after = target.stat()
    assert (after.st_ino, after.st_mode, after.st_uid, after.st_gid) == (
        before.st_ino, before.st_mode, before.st_uid, before.st_gid
    )
    assert target.read_text(encoding="utf-8") == "before\n"
    assert list(tmp_path.iterdir()) == [target]


def _patch_sample(target: Path, method: str) -> None:
    if method == "line":
        file_ops.apply_patch(str(target), [
            {"from": 1, "to": 1, "content": "after\n", "insert": False}
        ])
    elif method == "context":
        apply_context_patch_file(str(target), "@@\n-before\n+after\n")
    else:
        apply_exact_replace_file(str(target), "before", "after")


@pytest.mark.parametrize(
    "original",
    ["alpha\nbeta", "alpha\nbeta\n"],
    ids=["unterminated", "terminated"],
)
def test_line_patch_appends_after_last_line_without_merging(
    tmp_path: Path, original: str
) -> None:
    target = tmp_path / "sample.txt"
    target.write_text(original, encoding="utf-8")
    edits, err = file_ops.validate_edits([{"from": 3, "content": "gamma\n"}])
    assert err == ""

    total = file_ops.apply_patch(str(target), edits)

    assert target.read_text(encoding="utf-8") == "alpha\nbeta\ngamma\n"
    assert total == 3


def test_context_patch_chains_after_line_shift(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    first = apply_context_patch_file(
        str(target),
        (
            "*** Begin Patch\n"
            "*** Update File: sample.txt\n"
            "@@ alpha\n"
            "+inserted\n"
            "*** End Patch"
        ),
    )
    second = apply_context_patch_file(
        str(target),
        (
            "*** Begin Patch\n"
            "*** Update File: sample.txt\n"
            " beta\n"
            "-gamma\n"
            "+gamma-updated\n"
            "*** End Patch"
        ),
    )

    assert first["total_lines"] == 4
    assert first["hunk_count"] == 1
    assert second["total_lines"] == 4
    assert target.read_text(encoding="utf-8") == (
        "alpha\ninserted\nbeta\ngamma-updated\n"
    )


def test_context_patch_inserts_after_anchor(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")

    result = apply_context_patch_file(
        str(target),
        (
            "*** Begin Patch\n"
            "*** Update File: sample.txt\n"
            "@@ alpha\n"
            "+inserted\n"
            "*** End Patch"
        ),
    )

    assert result["line_from"] == 2
    assert result["line_to"] == 2
    assert target.read_text(encoding="utf-8") == "alpha\ninserted\nbeta\n"


def test_context_patch_replaces_matching_context(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    result = apply_context_patch_file(
        str(target),
        (
            "*** Begin Patch\n"
            "*** Update File: sample.txt\n"
            " beta\n"
            "-gamma\n"
            "+delta\n"
            "*** End Patch"
        ),
    )

    assert result["line_from"] == 2
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\ndelta\n"


def test_exact_replace_file_replaces_one_span(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nstatus = draft\ngamma\n", encoding="utf-8")

    result = apply_exact_replace_file(
        str(target), "status = draft", "status = ready"
    )

    assert result["replacement_count"] == 1
    assert result["line_from"] == 2
    assert target.read_text(encoding="utf-8") == "alpha\nstatus = ready\ngamma\n"


def test_exact_replace_file_rejects_ambiguous_match(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nalpha\n", encoding="utf-8")

    with pytest.raises(ValueError, match="matched 2 times"):
        apply_exact_replace_file(str(target), "alpha", "beta")

    assert target.read_text(encoding="utf-8") == "alpha\nalpha\n"


def test_exact_replace_to_patch_text_works_with_context_patch(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nstatus = draft\ngamma\n", encoding="utf-8")

    patch_text = exact_replace_to_patch_text(
        "sample.txt", "status = draft", "status = ready"
    )
    apply_context_patch_file(str(target), patch_text)

    assert target.read_text(encoding="utf-8") == "alpha\nstatus = ready\ngamma\n"


def test_context_patch_replaces_when_anchor_is_target_line(
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.py"
    target.write_text(
        (
            "def main():\n"
            "    print(greet(\"Agent Zero\"))\n"
            "\n"
            "\n"
            "if __name__ == \"__main__\":\n"
            "    main()\n"
        ),
        encoding="utf-8",
    )

    result = apply_context_patch_file(
        str(target),
        (
            "*** Begin Patch\n"
            "*** Update File: sample.py\n"
            "@@     print(greet(\"Agent Zero\"))\n"
            "-    print(greet(\"Agent Zero\"))\n"
            "+    print(greet(\"Agent Zero\").upper())\n"
            "*** End Patch"
        ),
    )

    assert result["line_from"] == 2
    assert target.read_text(encoding="utf-8") == (
        "def main():\n"
        "    print(greet(\"Agent Zero\").upper())\n"
        "\n"
        "\n"
        "if __name__ == \"__main__\":\n"
        "    main()\n"
    )


def test_context_patch_rejects_ambiguous_unanchored_context(
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("same\nold\nsame\nold\n", encoding="utf-8")

    with pytest.raises(ContextPatchError, match="matched multiple locations"):
        apply_context_patch_file(
            str(target),
            (
                "*** Begin Patch\n"
                "*** Update File: sample.txt\n"
                " same\n"
                "-old\n"
                "+new\n"
                "*** End Patch"
            ),
        )


@pytest.mark.parametrize(
    "patch_text, expected",
    [
        (
            "*** Begin Patch\n*** Add File: sample.txt\n+x\n*** End Patch",
            "supports update hunks only",
        ),
        (
            "*** Begin Patch\n*** Delete File: sample.txt\n*** End Patch",
            "supports update hunks only",
        ),
        (
            (
                "*** Begin Patch\n"
                "*** Update File: sample.txt\n"
                "*** Move to: other.txt\n"
                "*** End Patch"
            ),
            "does not support file moves",
        ),
        (
            (
                "*** Begin Patch\n"
                "*** Update File: sample.txt\n"
                "@@ alpha\n"
                "+one\n"
                "*** Update File: other.txt\n"
                "@@ beta\n"
                "+two\n"
                "*** End Patch"
            ),
            "may update only one file",
        ),
    ],
)
def test_context_patch_rejects_unsupported_file_operations(
    tmp_path: Path, patch_text: str, expected: str
) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")

    with pytest.raises(ContextPatchError, match=expected):
        apply_context_patch_file(str(target), patch_text)


def test_patch_request_rejects_edits_and_patch_text_together() -> None:
    request, err = parse_patch_request(
        [{"from": 1, "to": 1, "content": "x\n"}],
        "@@ alpha\n+beta",
    )

    assert request is None
    assert err == "provide exactly one patch form: edits, patch_text, or old_text/new_text"


def test_patch_request_rejects_empty_patch_text() -> None:
    request, err = parse_patch_request(None, "   \n")

    assert request is None
    assert err == "patch_text must not be empty"


def test_patch_request_accepts_exact_replace() -> None:
    request, err = parse_patch_request(
        None,
        None,
        old_text="status = draft",
        new_text="status = ready",
    )

    assert err == ""
    assert request is not None
    assert request.mode == "replace"
    assert request.old_text == "status = draft"
    assert request.new_text == "status = ready"


def test_patch_state_records_and_checks_fresh_file_state() -> None:
    agent = _FakeAgent()
    file_data = {"realpath": "/tmp/sample.txt", "mtime": 1.0, "total_lines": 3}

    record_file_state(agent, file_data, key=LOCAL_FRESHNESS_KEY)

    assert check_patch_freshness(agent, file_data, key=LOCAL_FRESHNESS_KEY) is None
    assert check_patch_freshness(
        agent,
        {"realpath": "/tmp/sample.txt", "mtime": 2.0, "total_lines": 3},
        key=LOCAL_FRESHNESS_KEY,
    ) == "patch_stale_read"


def test_patch_state_marks_context_patches_stale() -> None:
    agent = _FakeAgent()
    file_data = {"realpath": "/tmp/sample.txt", "mtime": 1.0, "total_lines": 3}

    record_file_state(agent, file_data, key=LOCAL_FRESHNESS_KEY)
    mark_file_state_stale(agent, file_data, key=LOCAL_FRESHNESS_KEY)

    assert agent.data[LOCAL_FRESHNESS_KEY]["/tmp/sample.txt"] == {
        "mtime": 0,
        "total_lines": 0,
    }


def test_patch_state_line_preserving_edits_can_chain() -> None:
    agent = _FakeAgent()
    initial = {"realpath": "/tmp/sample.txt", "mtime": 1.0, "total_lines": 3}
    patched = {"realpath": "/tmp/sample.txt", "mtime": 2.0, "total_lines": 3}
    edits = [{"from": 2, "to": 2, "content": "line-2a\n"}]

    record_file_state(agent, initial, key=LOCAL_FRESHNESS_KEY)
    apply_patch_post_state(agent, patched, edits, key=LOCAL_FRESHNESS_KEY)

    assert agent.data[LOCAL_FRESHNESS_KEY]["/tmp/sample.txt"] == {
        "mtime": 2.0,
        "total_lines": 3,
    }
    assert check_patch_freshness(agent, patched, key=LOCAL_FRESHNESS_KEY) is None


def test_patch_state_line_count_changes_force_reread() -> None:
    agent = _FakeAgent()
    initial = {"realpath": "/tmp/sample.txt", "mtime": 1.0, "total_lines": 3}
    patched = {"realpath": "/tmp/sample.txt", "mtime": 2.0, "total_lines": 4}
    edits = [{"from": 2, "content": "inserted\n"}]

    record_file_state(agent, initial, key=LOCAL_FRESHNESS_KEY)
    apply_patch_post_state(agent, patched, edits, key=LOCAL_FRESHNESS_KEY)

    assert agent.data[LOCAL_FRESHNESS_KEY]["/tmp/sample.txt"] == {
        "mtime": 0,
        "total_lines": 0,
    }


def test_patch_state_uses_separate_local_and_remote_keys() -> None:
    agent = _FakeAgent()
    file_data = {"realpath": "/tmp/sample.txt", "mtime": 1.0, "total_lines": 3}

    record_file_state(agent, file_data, key=LOCAL_FRESHNESS_KEY)
    mark_file_state_stale(agent, file_data, key=REMOTE_FRESHNESS_KEY)

    assert agent.data[LOCAL_FRESHNESS_KEY]["/tmp/sample.txt"] == {
        "mtime": 1.0,
        "total_lines": 3,
    }
    assert agent.data[REMOTE_FRESHNESS_KEY]["/tmp/sample.txt"] == {
        "mtime": 0,
        "total_lines": 0,
    }


@dataclass
class _FakeResponse:
    message: str
    break_loop: bool
    additional: dict | None = None


class _FakeTool:
    def __init__(
        self,
        agent,
        name: str = "text_editor",
        method: str = "patch",
        args: dict | None = None,
        message: str = "",
        loop_data=None,
        **kwargs,
    ) -> None:
        self.agent = agent
        self.name = name
        self.method = method
        self.args = args or {}
        self.message = message
        self.loop_data = loop_data


class _FakeAgent:
    def __init__(self, context_id: str = "") -> None:
        self.data = {}
        self.context = types.SimpleNamespace(id=context_id) if context_id else None

    def read_prompt(self, name: str, **kwargs) -> str:
        if name.endswith("read_ok.md"):
            return (
                f"{kwargs['path']} read {kwargs['total_lines']} lines\n"
                f">>>\n{kwargs['content']}\n<<<"
            )
        if name.endswith("patch_ok.md"):
            return (
                f"{kwargs['path']} patched {kwargs['edit_count']} edits applied "
                f"{kwargs['total_lines']} lines now\n>>>\n{kwargs['content']}\n<<<"
            )
        if name.endswith("patch_need_read.md"):
            return f"must read {kwargs['path']} first"
        if name.endswith("patch_stale_read.md"):
            return f"stale read for {kwargs['path']}"
        return f"error patching {kwargs.get('path')}: {kwargs.get('error')}"


def _load_text_editor_tool(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, dict | None]] = []
    import helpers

    tool_stub = types.ModuleType("helpers.tool")
    tool_stub.Tool = _FakeTool
    tool_stub.Response = _FakeResponse

    extension_stub = types.ModuleType("helpers.extension")

    async def call_extensions_async(name: str, *args, **kwargs):
        calls.append((name, kwargs.get("data")))

    extension_stub.call_extensions_async = call_extensions_async

    plugins_stub = types.ModuleType("helpers.plugins")
    plugins_stub.get_plugin_config = lambda *args, **kwargs: {}

    runtime_stub = types.ModuleType("helpers.runtime")

    async def call_development_function(func, *args, **kwargs):
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    runtime_stub.call_development_function = call_development_function

    monkeypatch.setitem(sys.modules, "helpers.tool", tool_stub)
    monkeypatch.setitem(sys.modules, "helpers.extension", extension_stub)
    monkeypatch.setitem(sys.modules, "helpers.plugins", plugins_stub)
    monkeypatch.setitem(sys.modules, "helpers.runtime", runtime_stub)
    monkeypatch.setattr(helpers, "extension", extension_stub, raising=False)
    monkeypatch.setattr(helpers, "plugins", plugins_stub, raising=False)
    monkeypatch.setattr(helpers, "runtime", runtime_stub, raising=False)
    sys.modules.pop("plugins._text_editor.tools.text_editor", None)
    module = importlib.import_module("plugins._text_editor.tools.text_editor")
    return module, calls


def test_text_editor_patch_text_does_not_require_prior_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, calls = _load_text_editor_tool(monkeypatch)
    target = tmp_path / "sample.txt"
    target.write_text("line-1\nline-2\nline-3\n", encoding="utf-8")
    agent = _FakeAgent()
    tool = module.TextEditor(agent, "text_editor", "patch", {}, "", None)

    response = asyncio.run(
        tool._patch(
            path=str(target),
            patch_text=(
                "*** Begin Patch\n"
                "*** Update File: sample.txt\n"
                "@@ line-1\n"
                "+inserted\n"
                "*** End Patch"
            ),
        )
    )

    assert "patched 1 edits applied 4 lines now" in response.message
    assert "inserted" in response.message
    assert target.read_text(encoding="utf-8") == (
        "line-1\ninserted\nline-2\nline-3\n"
    )
    realpath = os.path.realpath(target)
    assert agent.data[module._MTIME_KEY][realpath] == {
        "mtime": 0,
        "total_lines": 0,
    }
    assert calls[0] == (
        "text_editor_patch_before",
        {
            "path": str(target),
            "patch_text": (
                "*** Begin Patch\n"
                "*** Update File: sample.txt\n"
                "@@ line-1\n"
                "+inserted\n"
                "*** End Patch"
            ),
            "edits": [],
            "mode": "patch_text",
        },
    )
    assert calls[1][0] == "text_editor_patch_after"
    assert calls[1][1]["mode"] == "patch_text"


def test_text_editor_exact_replace_does_not_require_prior_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, calls = _load_text_editor_tool(monkeypatch)
    target = tmp_path / "sample.txt"
    target.write_text("line-1\nstatus = draft\nline-3\n", encoding="utf-8")
    agent = _FakeAgent()
    tool = module.TextEditor(agent, "text_editor", "patch", {}, "", None)

    response = asyncio.run(
        tool._patch(
            path=str(target),
            old_text="status = draft",
            new_text="status = ready",
        )
    )

    assert "patched 1 edits applied 3 lines now" in response.message
    assert "status = ready" in response.message
    assert target.read_text(encoding="utf-8") == "line-1\nstatus = ready\nline-3\n"
    realpath = os.path.realpath(target)
    assert agent.data[module._MTIME_KEY][realpath] == {
        "mtime": 0,
        "total_lines": 0,
    }
    assert calls[0] == (
        "text_editor_patch_before",
        {
            "path": str(target),
            "old_text": "status = draft",
            "new_text": "status = ready",
            "edits": [],
            "mode": "replace",
        },
    )
    assert calls[1][0] == "text_editor_patch_after"
    assert calls[1][1]["mode"] == "replace"


def test_text_editor_execute_accepts_action_alias_for_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, _calls = _load_text_editor_tool(monkeypatch)
    target = tmp_path / "sample.txt"
    target.write_text("line-1\nline-2\n", encoding="utf-8")
    tool = module.TextEditor(
        _FakeAgent(),
        "text_editor",
        None,
        {"action": "read", "path": str(target), "line_from": 1, "line_to": 1},
        "",
        None,
    )

    response = asyncio.run(tool.execute(**tool.args))

    assert "read 2 lines" in response.message
    assert "line-1" in response.message


def test_text_editor_write_result_carries_markdown_canvas_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, _calls = _load_text_editor_tool(monkeypatch)
    target = tmp_path / "note.md"
    tool = module.TextEditor(_FakeAgent("ctx-write-1"), "text_editor", "write", {}, "", None)

    response = asyncio.run(
        tool._write(
            path=str(target),
            content="# Note\n",
            open_in_canvas=True,
        )
    )

    assert target.read_text(encoding="utf-8") == "# Note\n"
    assert response.additional == {
        "_tool_name": "text_editor",
        "action": "write",
        "path": str(target),
        "format": "md",
        "extension": "md",
        "open_in_canvas": True,
        "context_id": "ctx-write-1",
        "ctxid": "ctx-write-1",
    }


def test_text_editor_patch_text_rejects_simultaneous_edits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, _calls = _load_text_editor_tool(monkeypatch)
    target = tmp_path / "sample.txt"
    target.write_text("line-1\n", encoding="utf-8")
    tool = module.TextEditor(_FakeAgent(), "text_editor", "patch", {}, "", None)

    response = asyncio.run(
        tool._patch(
            path=str(target),
            edits=[{"from": 1, "to": 1, "content": "updated\n"}],
            patch_text="@@ line-1\n+inserted",
        )
    )

    assert "provide exactly one patch form" in response.message
    assert target.read_text(encoding="utf-8") == "line-1\n"


def test_text_editor_patch_text_marks_existing_line_state_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, _calls = _load_text_editor_tool(monkeypatch)
    target = tmp_path / "sample.txt"
    target.write_text("line-1\nline-2\n", encoding="utf-8")
    realpath = os.path.realpath(target)
    agent = _FakeAgent()
    agent.data[module._MTIME_KEY] = {
        realpath: {"mtime": os.path.getmtime(target), "total_lines": 2}
    }
    tool = module.TextEditor(agent, "text_editor", "patch", {}, "", None)

    asyncio.run(
        tool._patch(
            path=str(target),
            patch_text=(
                "*** Begin Patch\n"
                "*** Update File: sample.txt\n"
                "@@ line-1\n"
                "+inserted\n"
                "*** End Patch"
            ),
        )
    )

    assert agent.data[module._MTIME_KEY][realpath] == {
        "mtime": 0,
        "total_lines": 0,
    }


def test_text_editor_line_edits_still_require_prior_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, calls = _load_text_editor_tool(monkeypatch)
    target = tmp_path / "sample.txt"
    target.write_text("line-1\n", encoding="utf-8")
    tool = module.TextEditor(_FakeAgent(), "text_editor", "patch", {}, "", None)

    response = asyncio.run(
        tool._patch(
            path=str(target),
            edits=[{"from": 1, "to": 1, "content": "updated\n"}],
        )
    )

    assert "must read" in response.message
    assert target.read_text(encoding="utf-8") == "line-1\n"
    assert calls == []
