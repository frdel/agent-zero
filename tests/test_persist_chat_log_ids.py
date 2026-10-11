from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_deserialize_log_preserves_item_id() -> None:
    from helpers.log import Log
    from helpers.persist_chat import _deserialize_log, _serialize_log

    log = Log()
    log.log(type="user", heading="User message", content="hello", id="msg-123")
    log.log(type="assistant", heading="Assistant", content="hi")

    serialized = _serialize_log(log)
    restored = _deserialize_log(serialized)

    assert restored.logs[0].type == "user"
    assert restored.logs[0].id == "msg-123"
    assert restored.logs[1].type == "assistant"
    assert restored.logs[1].id is None


def test_load_tmp_chats_skips_directories_without_chat_json(monkeypatch, capsys) -> None:
    from helpers import persist_chat

    monkeypatch.setattr(persist_chat, "_convert_v080_chats", lambda: None)
    monkeypatch.setattr(
        persist_chat.files,
        "get_abs_path",
        lambda *parts: "/" + "/".join(str(part).strip("/") for part in parts if part),
    )
    monkeypatch.setattr(
        persist_chat.files,
        "list_files",
        lambda folder, pattern="*": ["orphan", "valid"],
    )
    monkeypatch.setattr(
        persist_chat.files,
        "exists",
        lambda path: str(path).endswith("/valid/chat.json"),
    )
    monkeypatch.setattr(
        persist_chat.files,
        "read_file",
        lambda path: json.dumps({"id": "valid"}),
    )
    monkeypatch.setattr(
        persist_chat,
        "_deserialize_context",
        lambda data: SimpleNamespace(id=data["id"], data={}),
    )

    assert persist_chat.load_tmp_chats() == ["valid"]
    assert "Error loading chat" not in capsys.readouterr().out


def test_load_tmp_chats_reuses_only_version_and_isolates_bad_files(
    monkeypatch, tmp_path, capsys
) -> None:
    from helpers import persist_chat, settings

    configured = settings.get_default_settings()
    version_reads = []
    sensitive_reads = []
    versions = []

    def get_version():
        version_reads.append(len(version_reads))
        return str(len(version_reads))

    def deserialize(data):
        versions.append(settings.get_settings()["version"])
        return SimpleNamespace(id=data["id"], data={})

    monkeypatch.setattr(settings, "_settings", configured)
    monkeypatch.setattr(settings.git, "get_version", get_version)
    monkeypatch.setattr(settings, "_load_sensitive_settings", sensitive_reads.append)
    monkeypatch.setattr(persist_chat, "CHATS_FOLDER", str(tmp_path))
    monkeypatch.setattr(persist_chat, "_deserialize_context", deserialize)
    monkeypatch.setattr(persist_chat.files, "list_files", lambda *_: ["first", "bad", "last"])
    monkeypatch.setattr(persist_chat, "_convert_v080_chats", lambda: None)
    for name in ("first", "bad", "last"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "chat.json").write_text("{broken" if name == "bad" else json.dumps({"id": name}))

    assert persist_chat.load_tmp_chats() == ["first", "last"]
    assert versions == ["1", "1"]
    assert len(sensitive_reads) == 2
    assert "Error loading chat" in capsys.readouterr().out
    assert settings._get_version() == "2"

    assert persist_chat.load_tmp_chats() == ["first", "last"]
    assert versions == ["1", "1", "3", "3"]
    assert len(sensitive_reads) == 4
    assert settings._get_version() == "4"


def test_save_tmp_chat_preserves_existing_file_until_atomic_replace(
    monkeypatch, tmp_path
) -> None:
    from agent import AgentContextType
    from helpers import persist_chat

    path = tmp_path / "chat.json"
    path.write_text("previous", encoding="utf-8")
    context = SimpleNamespace(id="chat", type=AgentContextType.USER, data={})

    monkeypatch.setattr(persist_chat, "_get_chat_file_path", lambda _ctxid: str(path))
    monkeypatch.setattr(persist_chat, "_serialize_context", lambda _context: {"new": True})
    real_replace = persist_chat.os.replace

    def interrupted_replace(_source: str, destination: str) -> None:
        assert Path(destination).read_text(encoding="utf-8") == "previous"
        raise OSError("simulated interruption")

    monkeypatch.setattr(persist_chat.os, "replace", interrupted_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        persist_chat.save_tmp_chat(context)

    assert path.read_text(encoding="utf-8") == "previous"
    assert list(tmp_path.glob("*.tmp")) == []

    monkeypatch.setattr(persist_chat.os, "replace", real_replace)
    persist_chat.save_tmp_chat(context)

    assert json.loads(path.read_text(encoding="utf-8")) == {"new": True}
    assert context.data[persist_chat.SAVED_CHAT_CONTEXT_DATA_KEY] is True
