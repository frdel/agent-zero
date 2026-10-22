from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _FakeLogItem:
    def __init__(self, type_, heading="", content="", kvps=None, id=None, **kwargs):
        self.type = type_
        self.heading = heading
        self.content = content
        self.kvps = dict(kvps or {})
        self.kvps.update(kwargs)
        self.id = id


class _FakeLog:
    def __init__(self):
        self.items = []

    def log(self, type, heading="", content="", kvps=None, id=None, **kwargs):
        item = _FakeLogItem(type, heading, content, kvps, id, **kwargs)
        self.items.append(item)
        return item


class _FakeContext:
    def __init__(self):
        self.id = "ctx"
        self.log = _FakeLog()


class _FakeAgent:
    def __init__(self):
        self.context = _FakeContext()
        self.agent_name = "A0"


def _make_tool(cls, **args):
    return cls(_FakeAgent(), "text_editor", None, args, "", None)


@pytest.fixture(scope="module")
def text_editor_cls():
    from plugins._text_editor.tools.text_editor import TextEditor
    return TextEditor


@pytest.fixture(scope="module")
def text_editor_remote_cls():
    from plugins._a0_connector.tools.text_editor_remote import TextEditorRemote
    return TextEditorRemote


def test_text_editor_log_object_uses_custom_type(text_editor_cls):
    tool = _make_tool(text_editor_cls, action="read", path="/a0/file.txt")
    item = tool.get_log_object()
    assert item.type == "text_editor"
    assert item.kvps["_tool_name"] == "text_editor"
    assert item.kvps["action"] == "read"
    assert item.kvps["path"] == "/a0/file.txt"


def test_text_editor_log_object_heading_uses_action_and_path(text_editor_cls):
    cases = [
        ("read", "/a0/a.txt", "Reading /a0/a.txt"),
        ("write", "/a0/b.txt", "Writing /a0/b.txt"),
        ("patch", "/a0/c.txt", "Patching /a0/c.txt"),
    ]
    for action, path, expected in cases:
        tool = _make_tool(text_editor_cls, action=action, path=path)
        item = tool.get_log_object()
        assert item.heading == f"icon://construction {expected}", item.heading


def test_text_editor_log_object_falls_back_when_args_missing(text_editor_cls):
    tool = _make_tool(text_editor_cls)
    item = tool.get_log_object()
    assert item.type == "text_editor"
    assert item.heading == "icon://construction Using tool 'text_editor'"


def test_text_editor_log_object_id_is_uuid(text_editor_cls):
    tool = _make_tool(text_editor_cls, action="read", path="/x")
    item = tool.get_log_object()
    parsed = uuid.UUID(str(item.id))
    assert str(parsed) == str(item.id)


def test_text_editor_remote_log_object_has_remote_suffix(text_editor_remote_cls):
    tool = _make_tool(text_editor_remote_cls, action="read", path="/remote/file.txt")
    item = tool.get_log_object()
    assert item.type == "text_editor"
    assert item.heading == "icon://construction Reading /remote/file.txt (remote)"
    assert item.kvps["_tool_name"] == "text_editor"


def test_text_editor_remote_falls_back_with_remote_suffix(text_editor_remote_cls):
    tool = _make_tool(text_editor_remote_cls)
    item = tool.get_log_object()
    assert item.type == "text_editor"
    assert "(remote)" in item.heading

