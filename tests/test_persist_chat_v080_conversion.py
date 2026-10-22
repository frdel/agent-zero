from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers import persist_chat


@pytest.mark.parametrize("ctxid", ["Ab3dE7gn", "x9Kq2Zos", "R2d2C3po", "Tk4mW8qa"])
def test_v080_chat_moves_into_a_folder_named_after_its_full_id(
    monkeypatch, tmp_path, ctxid
) -> None:
    monkeypatch.setattr(persist_chat.files, "_base_dir", str(tmp_path))
    chats = tmp_path / persist_chat.CHATS_FOLDER
    chats.mkdir(parents=True)
    (chats / f"{ctxid}.json").write_text("{}")

    persist_chat._convert_v080_chats()

    assert sorted(p.name for p in chats.iterdir()) == [ctxid]
    assert (chats / ctxid / persist_chat.CHAT_FILE_NAME).read_text() == "{}"
