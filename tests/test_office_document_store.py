from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import types
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers import system_packages
from plugins._office import hooks
from plugins._desktop import hooks as desktop_hooks
from plugins._desktop.helpers import desktop_session
from plugins._editor.helpers import (
    markdown_sessions as editor_markdown_sessions,
    open_files_context,
)
from plugins._editor.api.editor_session import EditorSession
from plugins._office.helpers import (
    artifact_editor,
    canvas_context,
    document_store,
    libreoffice,
)


@pytest.fixture(autouse=True)
def runtime_package_os(monkeypatch):
    monkeypatch.setattr(system_packages.platform, "freedesktop_os_release", lambda: {"ID": "debian"})


@pytest.fixture
def office_state(tmp_path, monkeypatch):
    from helpers import settings
    monkeypatch.setattr(settings, "get_settings", lambda: {"file_browser_max_text_size_mb": 10, "file_browser_max_transfer_size_mb": 100, "file_browser_max_extract_size_mb": 100, "file_browser_max_archive_entries": 1000})
    state = tmp_path / "state"
    backups = state / "backups"
    workdir = tmp_path / "workdir"
    documents = workdir / "documents"
    projects_parent = tmp_path / "projects"

    monkeypatch.setattr(document_store, "STATE_DIR", state)
    monkeypatch.setattr(document_store, "DB_PATH", state / "documents.sqlite3")
    monkeypatch.setattr(document_store, "BACKUP_DIR", backups)
    monkeypatch.setattr(document_store, "WORKDIR", workdir)
    monkeypatch.setattr(document_store, "DOCUMENTS_DIR", documents)
    settings_helpers = types.SimpleNamespace(get_settings=lambda: {"workdir_path": str(workdir)})
    project_helpers = types.SimpleNamespace(
        get_context_project_name=lambda context: None,
        get_project_folder=lambda name: str(projects_parent / name),
        get_projects_parent_folder=lambda: str(projects_parent),
    )
    monkeypatch.setattr(document_store, "_settings", lambda: settings_helpers)
    monkeypatch.setattr(document_store, "_projects", lambda: project_helpers)
    monkeypatch.setattr(
        editor_markdown_sessions,
        "_manager",
        editor_markdown_sessions.MarkdownSessionManager(),
        raising=False,
    )

    workdir.mkdir(parents=True, exist_ok=True)
    documents.mkdir(parents=True, exist_ok=True)
    projects_parent.mkdir(parents=True, exist_ok=True)
    document_store.ensure_dirs()
    return types.SimpleNamespace(
        state=state,
        backups=backups,
        workdir=workdir,
        documents=documents,
        projects_parent=projects_parent,
        project_helpers=project_helpers,
    )


def test_document_store_create_defaults_to_markdown(office_state):
    doc = document_store.create_document("document", "Research Note", content="A precise note.")

    assert doc["extension"] == "md"
    assert Path(doc["path"]).parent == office_state.workdir
    assert Path(doc["path"]).read_text(encoding="utf-8").startswith("# Research Note")


def test_text_files_register_as_editor_documents(office_state):
    path = office_state.workdir / "plain-note.txt"
    path.write_text("Plain text belongs in the Editor surface.\n", encoding="utf-8")

    doc = document_store.register_document(path)

    assert doc["extension"] == "txt"
    assert "txt" in document_store.EDITOR_TEXT_EXTENSIONS
    assert "txt" not in desktop_session.OFFICIAL_EXTENSIONS


def test_file_browser_can_register_runtime_root_markdown(office_state, monkeypatch):
    runtime_root = office_state.state.parent / "runtime-root"
    runtime_root.mkdir()
    path = runtime_root / "AGENTS.md"
    path.write_text("# Runtime Instructions\n", encoding="utf-8")
    monkeypatch.setattr(document_store.files, "get_base_dir", lambda: str(runtime_root))

    with pytest.raises(PermissionError, match="active project or workdir"):
        document_store.register_document(path)

    doc = document_store.register_document(path, allow_base_dir=True)

    assert doc["basename"] == "AGENTS.md"
    assert doc["path"] == str(path)


def test_editor_http_input_accepts_large_text_and_rejects_over_limit(office_state):
    path = office_state.workdir / "large.txt"
    text = "a" * (2 * 1024 * 1024)
    path.write_text(text, encoding="utf-8")
    handler = EditorSession(app=None, thread_lock=None)
    request = types.SimpleNamespace(headers={}, host_url="http://localhost/")
    opened = asyncio.run(handler.process({"action": "open", "path": str(path)}, request))
    assert opened["ok"] and opened["text"] == text
    payload = {"action": "input", "session_id": opened["session_id"], "text": text + "b"}
    assert asyncio.run(handler.process(payload, request))["ok"]
    with pytest.raises(ValueError, match="10 MiB"):
        asyncio.run(handler.process({**payload, "text": "a" * (10 * 1024 * 1024 + 1)}, request))
    assert asyncio.run(handler.process({"action": "save", "session_id": opened["session_id"]}, request))["ok"]
    assert path.read_text(encoding="utf-8") == text + "b"


def test_editor_file_browser_source_opens_runtime_root_markdown(office_state, monkeypatch):
    runtime_root = office_state.state.parent / "runtime-root"
    runtime_root.mkdir()
    path = runtime_root / "AGENTS.md"
    path.write_text("# Runtime Instructions\n", encoding="utf-8")
    monkeypatch.setattr(document_store.files, "get_base_dir", lambda: str(runtime_root))
    handler = EditorSession(app=None, thread_lock=None)
    request = types.SimpleNamespace(headers={}, host_url="http://localhost/")

    blocked = asyncio.run(handler.process({"action": "open", "path": str(path)}, request))
    opened = asyncio.run(handler.process({
        "action": "open",
        "path": str(path),
        "source": "file-browser",
    }, request))

    assert blocked["ok"] is False
    assert "active project or workdir" in blocked["error"]
    assert opened["ok"] is True
    assert opened["title"] == "AGENTS.md"
    assert opened["text"] == "# Runtime Instructions\n"


@pytest.mark.parametrize(
    ("kind", "title", "fmt", "expected_name"),
    [
        ("document", "real-chat-canvas-smoke.md", "md", "real-chat-canvas-smoke.md"),
        ("document", "Board Memo.ODT", "odt", "Board Memo.odt"),
        ("spreadsheet", "Budget.ods", "ods", "Budget.ods"),
        ("presentation", "Roadmap.odp", "odp", "Roadmap.odp"),
    ],
)
def test_create_document_does_not_duplicate_matching_extension(office_state, kind, title, fmt, expected_name):
    doc = document_store.create_document(kind, title, fmt, content="Smoke")

    assert Path(doc["path"]).name == expected_name


def test_explicit_docx_creates_valid_word_package(office_state):
    doc = document_store.create_document("document", "Board Memo", "docx", "A careful memo.")

    assert doc["extension"] == "docx"
    assert Path(doc["path"]).parent == office_state.documents
    assert libreoffice.validate_docx(doc["path"])["ok"] is True
    with zipfile.ZipFile(doc["path"]) as archive:
        assert "word/document.xml" in archive.namelist()


def test_odf_formats_create_valid_libreoffice_packages(office_state):
    writer = document_store.create_document("document", "Board Memo", "odt", "A careful memo.")
    sheet = document_store.create_document("spreadsheet", "Budget", "ods", "Name,Amount\nPlatform,1000")
    deck = document_store.create_document("presentation", "Roadmap", "odp", "Roadmap\nLaunch sequence")

    assert writer["extension"] == "odt"
    assert sheet["extension"] == "ods"
    assert deck["extension"] == "odp"
    assert Path(writer["path"]).parent == office_state.documents
    assert libreoffice.validate_odf(writer["path"])["ok"] is True
    assert libreoffice.validate_odf(sheet["path"])["ok"] is True
    assert libreoffice.validate_odf(deck["path"])["ok"] is True
    assert artifact_editor.read_artifact(writer)["text"].startswith("Board Memo")
    assert artifact_editor.read_artifact(sheet)["sheets"][0]["preview_rows"][1][1] == 1000
    assert artifact_editor.read_artifact(deck)["slides"][0]["title"] == "Roadmap"


def test_blank_docx_includes_editable_body_paragraph(office_state):
    doc = document_store.create_document("document", "Blank Memo", "docx", "")
    with zipfile.ZipFile(doc["path"]) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
        root = ET.fromstring(xml)

    word_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    assert len(list(root.iter(f"{{{word_ns}}}p"))) >= 2
    assert 'xml:space="preserve">&#160;</w:t>' in xml


def test_odf_and_ooxml_creation_and_direct_edits_still_work(office_state):
    odt = document_store.create_document("document", "Writer Memo", "odt", "Old phrase")
    updated_odt, odt_payload = artifact_editor.edit_artifact(
        odt,
        operation="replace_text",
        find="Old phrase",
        replace="New phrase",
    )
    odt_read = artifact_editor.read_artifact(updated_odt)

    assert odt_payload["changed"] is True
    assert "New phrase" in odt_read["text"]

    ods = document_store.create_document(
        "spreadsheet",
        "Budget ODS",
        "ods",
        "Name,Amount\nPlatform,1000",
    )
    updated_ods, ods_payload = artifact_editor.edit_artifact(
        ods,
        operation="set_cells",
        cells={"Sheet1!B2": 12500, "Sheet1!A3": "Research", "Sheet1!B3": 4700},
    )
    ods_read = artifact_editor.read_artifact(updated_ods)
    ods_rows = ods_read["sheets"][0]["preview_rows"]

    assert ods_payload["changed"] is True
    assert ods_rows[1][1] == 12500
    assert ods_rows[2][0] == "Research"


def test_office_artifact_helpers_reject_markdown_inputs(office_state):
    doc = document_store.create_document("document", "Append Shapes", "md", "# Title\n\nBase")

    with pytest.raises(ValueError, match="use text_editor"):
        artifact_editor.read_artifact(doc)
    with pytest.raises(ValueError, match="use text_editor"):
        artifact_editor.edit_artifact(doc, operation="set_text", content="# Updated")


def test_office_artifact_direct_edits_cover_presentations_spreadsheets_and_decks(office_state):

    odp = document_store.create_document(
        "presentation",
        "Roadmap ODP",
        "odp",
        "Roadmap\nLaunch sequence\n\n---\n\nNext\nPolish rollout",
    )
    updated_odp, odp_payload = artifact_editor.edit_artifact(
        odp,
        operation="set_slides",
        slides=[
            {"title": "Now", "bullets": ["Stabilize"]},
            {"title": "Next", "bullets": ["Polish"]},
        ],
    )
    odp_read = artifact_editor.read_artifact(updated_odp)

    assert odp_payload["changed"] is True
    assert odp_read["slide_count"] == 2
    assert odp_read["slides"][1]["title"] == "Next"

    sheet = document_store.create_document(
        "spreadsheet",
        "Budget",
        "xlsx",
        "Name,Amount\nPlatform,1000",
    )
    updated_sheet, sheet_payload = artifact_editor.edit_artifact(
        sheet,
        operation="set_cells",
        cells={"Sheet1!B2": 12500, "Sheet1!A3": "Research", "Sheet1!B3": 4700},
    )
    sheet_read = artifact_editor.read_artifact(updated_sheet)
    rows = sheet_read["sheets"][0]["preview_rows"]

    assert sheet_payload["changed"] is True
    assert rows[1][1] == 12500
    assert rows[2][0] == "Research"

    deck = document_store.create_document(
        "presentation",
        "Roadmap",
        "pptx",
        "Roadmap\nLaunch sequence\n\n---\n\nNext\nPolish rollout",
    )
    created_deck_read = artifact_editor.read_artifact(deck)
    with zipfile.ZipFile(deck["path"]) as archive:
        created_slide_names = [name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]

    assert created_deck_read["slide_count"] == 2
    assert created_deck_read["slides"][0]["title"] == "Roadmap"
    assert created_deck_read["slides"][1]["title"] == "Next"
    assert len(created_slide_names) == 2

    updated_deck, deck_payload = artifact_editor.edit_artifact(
        deck,
        operation="set_slides",
        slides=[
            {"title": "Now", "bullets": ["Stabilize"]},
            {"title": "Next", "bullets": ["Polish"]},
        ],
    )
    deck_read = artifact_editor.read_artifact(updated_deck)

    assert deck_payload["changed"] is True
    assert deck_read["slide_count"] == 2
    assert deck_read["slides"][1]["title"] == "Next"


def test_ods_direct_edit_preserves_rows_beyond_preview_window_and_blank_separators(office_state):
    rows = [["Row", "Value"], ["alpha", 1], [], ["separator-survives", 2]]
    rows.extend([[f"item-{index}", index] for index in range(4, 96)])
    doc = document_store.create_document("spreadsheet", "Long ODS", "ods", "")
    updated, payload = artifact_editor.edit_artifact(
        doc,
        operation="set_rows",
        rows=rows,
    )
    updated, payload = artifact_editor.edit_artifact(
        updated,
        operation="set_cells",
        cells={"Sheet1!B90": 9000},
    )
    parsed = artifact_editor._ods_sheets_from_bytes(Path(updated["path"]).read_bytes(), max_rows=120, max_cols=10)

    assert payload["changed"] is True
    assert parsed[0]["rows"][2] == []
    assert parsed[0]["rows"][3][0] == "separator-survives"
    assert parsed[0]["rows"][89][1] == 9000


def test_office_artifact_creates_ods_with_action_contract(office_state, monkeypatch):
    tool_module = types.ModuleType("helpers.tool")

    class Response:
        def __init__(self, message, break_loop, additional=None):
            self.message = message
            self.break_loop = break_loop
            self.additional = additional

    class Tool:
        def __init__(self, agent, name, method, args, message, loop_data, **kwargs):
            self.agent = agent
            self.name = name
            self.method = method
            self.args = args
            self.message = message
            self.loop_data = loop_data

    tool_module.Response = Response
    tool_module.Tool = Tool
    monkeypatch.setitem(sys.modules, "helpers.tool", tool_module)
    spec = importlib.util.spec_from_file_location(
        "test_office_artifact_tool",
        PROJECT_ROOT / "plugins" / "_office" / "tools" / "office_artifact.py",
    )
    office_artifact_module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(office_artifact_module)
    OfficeArtifact = office_artifact_module.OfficeArtifact

    tool = OfficeArtifact(
        agent=None,
        name="office_artifact",
        method=None,
        args={},
        message="",
        loop_data=None,
    )

    response = asyncio.run(
        tool.execute(
            action="create",
            kind="document",
            title="New Calc Workbook",
            format="ods",
            content="Sheet1\n",
        )
    )
    payload = json.loads(response.message)

    assert payload["action"] == "create"
    assert payload["document"]["extension"] == "ods"
    assert Path(payload["document"]["path"]).name == "New Calc Workbook.ods"
    assert Path(document_store._path_from_a0(payload["document"]["path"])).exists()


def test_odf_is_advertised_and_docx_remains_explicit_compatibility(office_state):
    prompt = (PROJECT_ROOT / "plugins" / "_office" / "prompts" / "agent.system.tool.office_artifact.md").read_text(
        encoding="utf-8",
    )

    assert "formats: odt ods odp docx xlsx pptx" in prompt
    assert "use `text_editor` for Markdown and plain text files" in prompt
    assert "ODF is first-class for LibreOffice" in prompt
    assert "DOCX/XLSX/PPTX are compatibility formats" in prompt
    assert "`method` is accepted as an alias for action" not in prompt
    assert "they do not open a surface automatically" in prompt
    assert "do not write faux UI action labels" in prompt
    assert '"Open document" or "Download file"' in prompt
    assert "explicit Download, Open Document, or Desktop edit message actions" not in prompt
    doc = document_store.create_document("document", "Use ODT", "odt", "")
    assert doc["extension"] == "odt"


def test_project_scoped_creation_uses_active_project_root(office_state, monkeypatch):
    project_root = office_state.projects_parent / "apollo"
    project_root.mkdir(parents=True, exist_ok=True)
    context = object()
    agent_module = types.SimpleNamespace(
        AgentContext=types.SimpleNamespace(get=staticmethod(lambda context_id: context))
    )

    monkeypatch.setitem(sys.modules, "agent", agent_module)
    monkeypatch.setattr(office_state.project_helpers, "get_context_project_name", lambda active_context: "apollo")
    monkeypatch.setattr(office_state.project_helpers, "get_project_folder", lambda name: str(project_root))

    markdown = document_store.create_document("document", "Project Note", "md", "Scoped.", context_id="ctx-project")
    odt = document_store.create_document("document", "Project Memo", "odt", "Scoped.", context_id="ctx-project")

    assert Path(markdown["path"]).parent == project_root
    assert Path(odt["path"]).parent == project_root / "documents"


def test_non_project_creation_uses_configured_workdir(office_state):
    markdown = document_store.create_document("document", "Workdir Note", content="Plain.")
    spreadsheet = document_store.create_document("spreadsheet", "Workdir Sheet", "ods", "Name,Value")

    assert markdown["extension"] == "md"
    assert Path(markdown["path"]).parent == office_state.workdir
    assert Path(spreadsheet["path"]).parent == office_state.documents


def test_sessions_and_canvas_context_are_neutral(office_state):
    doc = document_store.create_document("document", "Canvas Context", "odt", "Private body text.")
    session = document_store.create_session(doc["file_id"], "user-a", "write", "http://localhost:32080")

    open_docs = document_store.get_open_documents()
    context = canvas_context.build_context()

    assert open_docs[0]["file_id"] == doc["file_id"]
    assert "Office artifacts" in context
    assert "Private body text" not in context
    assert document_store.close_session(session_id=session["session_id"]) == 1
    assert document_store.get_open_documents() == []


def test_editor_open_files_are_scoped_to_active_context(office_state):
    first = document_store.create_document("document", "First Editor Note", "md", "First private body.")
    second = document_store.create_document("document", "Second Editor Note", "md", "Second private body.")
    manager = editor_markdown_sessions.get_manager()

    first_session = manager.open(first, context_id="ctx-a")
    second_session = manager.open(second, context_id="ctx-b")
    manager.input(first_session["session_id"], text="Unsaved ctx-a text")
    reopened_first = manager.open(first, context_id="ctx-a")

    ctx_a_files = manager.list_open("ctx-a")
    ctx_b_files = manager.list_open("ctx-b")
    prompt_context = open_files_context.build_context("ctx-a")

    assert reopened_first["session_id"] == first_session["session_id"]
    assert reopened_first["text"] == "Unsaved ctx-a text"
    assert [item["file_id"] for item in ctx_a_files] == [first["file_id"]]
    assert [item["file_id"] for item in ctx_b_files] == [second["file_id"]]
    assert ctx_a_files[0]["dirty"] is True
    assert ctx_a_files[0]["active"] is True
    assert ctx_a_files[0]["open_sessions"] == 1
    assert "First Editor Note.md" in prompt_context
    assert "Second Editor Note.md" not in prompt_context
    assert "First private body" not in prompt_context
    assert "Unsaved ctx-a text" not in prompt_context


def test_markdown_save_tracks_version_history(office_state):
    doc = document_store.create_document("document", "Versioned", "md", "First")
    updated = document_store.write_markdown(doc["file_id"], "# Versioned\n\nSecond\n")
    history = document_store.version_history(doc["file_id"])

    assert updated["version"] == 2
    assert history
    assert Path(updated["path"]).read_text(encoding="utf-8").endswith("Second\n")


def test_document_path_update_preserves_file_id_after_rename(office_state):
    doc = document_store.create_document("document", "Rename Me", "md", "Body")
    original = Path(doc["path"])
    renamed = original.with_name("Renamed.md")
    original.rename(renamed)

    updated = document_store.update_document_path(doc["file_id"], renamed)

    assert updated["file_id"] == doc["file_id"]
    assert updated["basename"] == "Renamed.md"
    assert updated["path"] == str(renamed)
    assert document_store.get_document(doc["file_id"])["path"] == str(renamed)


def test_document_rename_materializes_missing_markdown_with_editor_text(office_state):
    doc = document_store.create_document("document", "Unsaved Draft", "md", "Seed")
    original = Path(doc["path"])
    original.unlink()
    renamed = original.with_name("Renamed Draft.md")

    updated = document_store.rename_document(
        doc["file_id"],
        renamed,
        content="# Renamed Draft\n\nCanvas text",
    )

    assert updated["file_id"] == doc["file_id"]
    assert updated["basename"] == "Renamed Draft.md"
    assert updated["path"] == str(renamed)
    assert renamed.read_text(encoding="utf-8") == "# Renamed Draft\n\nCanvas text"


def test_document_rename_saves_dirty_markdown_and_removes_original(office_state):
    doc = document_store.create_document("document", "Dirty Rename", "md", "Old")
    original = Path(doc["path"])
    renamed = original.with_name("Clean Rename.md")

    updated = document_store.rename_document(
        doc["file_id"],
        renamed,
        content="# Clean Rename\n\nFresh text",
    )

    assert updated["version"] == 2
    assert not original.exists()
    assert renamed.read_text(encoding="utf-8") == "# Clean Rename\n\nFresh text"


def test_native_office_rename_preserves_unsaved_content_and_metadata(office_state):
    import stat

    doc = document_store.create_document("document", "Native Rename", "odt", "Saved text")
    source = Path(doc["path"])
    source.chmod(0o640)
    original = source.read_bytes()
    metadata = source.stat()
    target = source.with_name("Renamed.odt")
    dirty = document_store.odt_bytes("Native Rename", "Unsaved Writer text")

    def native_rename(old, new):
        assert old == source and new == target
        assert old.read_bytes() == original and not new.exists()
        new.write_bytes(dirty)
        return True

    updated = document_store.rename_document(doc["file_id"], target, rename_open_document=native_rename)

    assert not source.exists()
    assert target.read_bytes() == dirty
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert (target.stat().st_uid, target.stat().st_gid) == (metadata.st_uid, metadata.st_gid)
    assert updated["file_id"] == doc["file_id"]
    assert updated["version"] == doc["version"] + 1
    assert updated["sha256"] == document_store.sha256_bytes(dirty)


def test_native_office_rename_rejects_collisions_and_keeps_source_on_failure(office_state):
    doc = document_store.create_document("document", "Failed Rename", "odt", "Original")
    source = Path(doc["path"])
    original = source.read_bytes()
    target = source.with_name("Taken.odt")
    target.write_bytes(b"collision sentinel")

    def fail_rename(old, new):
        raise RuntimeError("Native rename failed")

    with pytest.raises(FileExistsError):
        document_store.rename_document(doc["file_id"], target, rename_open_document=fail_rename)
    assert target.read_bytes() == b"collision sentinel"
    target.unlink()
    with pytest.raises(RuntimeError, match="Native rename failed"):
        document_store.rename_document(doc["file_id"], target, rename_open_document=fail_rename)
    assert source.read_bytes() == original
    assert not target.exists()
    assert document_store.get_document(doc["file_id"])["path"] == str(source)

    updated = document_store.rename_document(doc["file_id"], target, rename_open_document=lambda *_: False)
    assert updated["path"] == str(target)
    assert target.read_bytes() == original
    assert not source.exists()


def test_native_office_bridge_matches_full_url_and_disallows_overwrite(tmp_path, monkeypatch):
    from plugins._desktop.helpers import rename_office_document

    source = tmp_path / "source" / "Same name.odt"
    target = source.with_name("Renamed.odt")
    calls = []
    other = types.SimpleNamespace(
        getURL=lambda: (tmp_path / "other" / source.name).as_uri(),
        storeAsURL=lambda *_: pytest.fail("Renamed a different document with the same basename"),
    )
    document = types.SimpleNamespace(
        getURL=lambda: source.as_uri(),
        getArgs=lambda: (types.SimpleNamespace(Name="FilterName", Value="Office Open XML Text"),
                         types.SimpleNamespace(Name="URL", Value=source.as_uri())),
        storeAsURL=lambda url, properties: calls.append((url, [(p.Name, p.Value) for p in properties])),
    )
    items = [other, document]
    enumeration = types.SimpleNamespace(hasMoreElements=lambda: bool(items), nextElement=lambda: items.pop(0))
    desktop = types.SimpleNamespace(getComponents=lambda: types.SimpleNamespace(createEnumeration=lambda: enumeration))
    context = types.SimpleNamespace()
    resolver = types.SimpleNamespace(resolve=lambda url: context)
    context.ServiceManager = types.SimpleNamespace(createInstanceWithContext=lambda name, _: resolver if name.endswith("UnoUrlResolver") else desktop)
    monkeypatch.setitem(sys.modules, "uno", types.SimpleNamespace(
        getComponentContext=lambda: context,
        createUnoStruct=lambda _: types.SimpleNamespace(),
    ))
    commands = []

    def launch(command, **kwargs):
        commands.append(command)
        return types.SimpleNamespace(poll=lambda: 0, wait=lambda timeout: 0)

    monkeypatch.setattr(rename_office_document.subprocess, "Popen", launch)
    assert rename_office_document.rename_document("soffice", tmp_path / "profile", source, target)
    assert calls == [(target.as_uri(), [("FilterName", "Office Open XML Text"), ("Overwrite", False)])]
    assert any(arg.startswith("--accept=pipe,name=") for arg in commands[0])

    items[:] = [other]
    assert not rename_office_document.rename_document("soffice", tmp_path / "profile", source, target)
    assert len(calls) == 1


def test_text_session_save_as_creates_new_file_without_mutating_original(office_state):
    manager = editor_markdown_sessions.MarkdownSessionManager()
    doc = document_store.create_document("document", "Original Note", "md", "# Original Note\n")
    original = Path(doc["path"])
    session = manager.open(doc, context_id="ctx-a")
    target = office_state.workdir / "notes" / "Saved Copy.txt"

    result = manager.save_as(
        session["session_id"],
        str(target),
        text="Saved Copy\n\nExact body\n",
    )

    saved_session = manager._sessions[session["session_id"]]
    assert result["ok"] is True
    assert result["document"]["file_id"] != doc["file_id"]
    assert result["previous_file_id"] == doc["file_id"]
    assert saved_session.file_id == result["document"]["file_id"]
    assert saved_session.path == str(target)
    assert saved_session.extension == "txt"
    assert saved_session.dirty is False
    assert original.read_text(encoding="utf-8") == "# Original Note"
    assert target.read_text(encoding="utf-8") == "Saved Copy\n\nExact body\n"


def test_editor_session_opens_and_saves_txt_documents(office_state):
    manager = editor_markdown_sessions.MarkdownSessionManager()
    doc = document_store.create_document("document", "Plain Note", "txt", "First line")
    session = manager.open(doc, context_id="ctx-a")

    assert session["extension"] == "txt"
    assert session["text"] == "First line"

    result = manager.save(session["session_id"], text="Second line\n")

    assert result["ok"] is True
    assert result["document"]["extension"] == "txt"
    assert Path(result["document"]["path"]).read_text(encoding="utf-8") == "Second line\n"


def test_refresh_open_markdown_session_reloads_external_file_edits(office_state):
    manager = editor_markdown_sessions.MarkdownSessionManager()
    doc = document_store.create_document("document", "External Refresh", "md", "First")
    session = manager.open(doc, context_id="ctx-a")

    Path(doc["path"]).write_text("# External Refresh\n\nSecond\n", encoding="utf-8")
    refreshed = manager.open(doc, context_id="ctx-a", refresh=True)

    assert refreshed["session_id"] == session["session_id"]
    assert refreshed["text"] == "# External Refresh\n\nSecond\n"
    assert manager._sessions[session["session_id"]].dirty is False


def test_refresh_open_markdown_session_preserves_dirty_editor_text(office_state):
    manager = editor_markdown_sessions.MarkdownSessionManager()
    doc = document_store.create_document("document", "Dirty External Refresh", "md", "First")
    session = manager.open(doc, context_id="ctx-a")
    manager.input(session["session_id"], text="Unsaved editor text")

    Path(doc["path"]).write_text("External disk text\n", encoding="utf-8")
    refreshed = manager.open(doc, context_id="ctx-a", refresh=True)

    assert refreshed["text"] == "Unsaved editor text"
    assert manager._sessions[session["session_id"]].dirty is True


def test_external_text_editor_mutation_refreshes_clean_open_markdown_session(office_state):
    manager = editor_markdown_sessions.MarkdownSessionManager()
    doc = document_store.create_document("document", "Synced External Edit", "md", "First")
    session = manager.open(doc, context_id="ctx-a")

    Path(doc["path"]).write_text("# Synced External Edit\n\nSecond\n", encoding="utf-8")
    result = manager.sync_external_file_mutations([doc["path"]])

    assert result["matched"] == 1
    assert manager._sessions[session["session_id"]].text == "# Synced External Edit\n\nSecond\n"
    assert manager._sessions[session["session_id"]].dirty is False
    assert manager._sessions[session["session_id"]].external_modified is False


def test_external_text_editor_mutation_marks_dirty_markdown_session_pending(office_state):
    manager = editor_markdown_sessions.MarkdownSessionManager()
    doc = document_store.create_document("document", "Dirty Synced External Edit", "md", "First")
    session = manager.open(doc, context_id="ctx-a")
    manager.input(session["session_id"], text="Unsaved editor text")

    Path(doc["path"]).write_text("External disk text\n", encoding="utf-8")
    result = manager.sync_external_file_mutations([doc["path"]])

    dirty_session = manager._sessions[session["session_id"]]
    assert result["matched"] == 1
    assert dirty_session.text == "Unsaved editor text"
    assert dirty_session.dirty is True
    assert dirty_session.external_modified is True


def test_markdown_editor_save_rejects_stale_canvas_overwrite(office_state):
    manager = editor_markdown_sessions.MarkdownSessionManager()
    doc = document_store.create_document("document", "Stale Save Guard", "md", "First")
    session = manager.open(doc, context_id="ctx-a")

    Path(doc["path"]).write_text("# Stale Save Guard\n\nExternal newer text\n", encoding="utf-8")
    result = manager.save(session["session_id"], text="# Stale Save Guard\n\nOlder canvas text\n")

    assert result["ok"] is False
    assert result["code"] == "external_change_conflict"
    assert "External newer text" in Path(doc["path"]).read_text(encoding="utf-8")
    assert "Older canvas text" not in Path(doc["path"]).read_text(encoding="utf-8")


def test_markdown_session_rejects_office_binaries(office_state):
    manager = editor_markdown_sessions.MarkdownSessionManager()
    doc = document_store.create_document("document", "Desktop Only", "odt", "Native text")

    with pytest.raises(ValueError, match="Open .odt files in the Desktop"):
        manager.open(doc)


def test_thunar_defaults_preserve_existing_profile_settings(tmp_path):
    thunar_xml = tmp_path / "thunar.xml"
    thunar_xml.write_text(
        """<?xml version="1.1" encoding="UTF-8"?>
<channel name="thunar" version="1.0">
  <property name="last-view" type="string" value="ThunarDetailsView"/>
  <property name="last-window-width" type="int" value="900"/>
  <property name="last-show-hidden" type="bool" value="false"/>
</channel>
""",
        encoding="utf-8",
    )

    desktop_session._write_thunar_defaults(thunar_xml)

    root = ET.parse(thunar_xml).getroot()
    values = {child.get("name"): child.get("value") for child in root.findall("property")}
    assert values["last-view"] == "ThunarDetailsView"
    assert values["last-window-width"] == "900"
    assert values["last-show-hidden"] == "true"


def test_official_desktop_session_status_and_url_contract(tmp_path, monkeypatch):
    xpra_html = tmp_path / "xpra" / "www"
    xpra_html.mkdir(parents=True)
    (xpra_html / "index.html").write_text("xpra", encoding="utf-8")

    monkeypatch.setattr(desktop_session.libreoffice, "find_soffice", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(
        desktop_session.shutil,
        "which",
        lambda name: f"/usr/bin/{name}"
        if name
        in {
            "xpra",
            "Xvfb",
            "xfce4-session",
            "dbus-launch",
            "xrandr",
            "xdotool",
            "thunar",
            "xfce4-terminal",
            "xfce4-settings-manager",
            "gio",
        }
        else "",
    )
    monkeypatch.setattr(desktop_session.virtual_desktop, "XPRA_HTML_ROOT_CANDIDATES", (xpra_html,))
    monkeypatch.setattr(desktop_session.virtual_desktop, "_package_installed", lambda package: True)

    status = desktop_session.collect_desktop_status()
    url = desktop_session._xpra_url("abc123")

    assert status["healthy"] is True
    assert status["xpra_html_root"] == str(xpra_html)
    assert url.startswith("/desktop/session/abc123/index.html?")
    assert "path=%2Fdesktop%2Fsession%2Fabc123%2F" in url
    assert "xpramenu=false" in url
    assert "floating_menu=false" in url
    assert "file_transfer=true" in url
    assert "sound=false" in url
    assert "encoding=jpeg" in url
    assert "quality=85" in url
    assert "speed=80" in url
    assert "printing=true" in url


def test_desktop_status_reports_installing_during_runtime_preparation(monkeypatch):
    monkeypatch.setattr(
        desktop_session.virtual_desktop,
        "collect_status",
        lambda: {
            "binaries": {},
            "packages": {},
            "xpra_html_root": "",
        },
    )
    monkeypatch.setattr(desktop_session.libreoffice, "find_soffice", lambda: "")
    monkeypatch.setattr(desktop_session.shutil, "which", lambda _name: "")
    monkeypatch.setattr(
        desktop_session,
        "_runtime_preparation_status",
        lambda: {"preparing": True, "active_count": 1, "started_at": 123.0},
    )

    status = desktop_session.collect_desktop_status()

    assert status["healthy"] is False
    assert status["installing"] is True
    assert status["state"] == "installing"
    assert status["message"].startswith("Installing Agent Zero Desktop runtime dependencies")
    assert "soffice" in status["missing"]


def test_desktop_gateway_patches_xpra_menu_script():
    source = (PROJECT_ROOT / "helpers" / "virtual_desktop_routes.py").read_text(encoding="utf-8")

    assert "XPRA_MENU_CUSTOM_PATCH" in source
    assert 'upstream_path.endswith("/js/MenuCustom.js")' in source
    assert "window.noWindowList" in source
    assert "__a0SafeWindowList" in source
    assert "XPRA_WINDOW_OFFSET_WARNING_PATCH" in source
    assert "XPRA_WINDOW_SCRIPT_PATCH" in source
    assert "a0_desktop_patch=20260506" in source
    assert 'upstream_path.endswith("/index.html")' in source
    assert 'upstream_path.endswith("/js/Window.js")' in source
    assert "window does not fit in canvas, offsets:" in source


def test_office_binary_open_requires_explicit_desktop_without_cold_session(office_state, monkeypatch):
    api_module = types.ModuleType("helpers.api")

    class ApiHandler:
        def __init__(self, app=None, thread_lock=None):
            self.app = app
            self.thread_lock = thread_lock

    api_module.ApiHandler = ApiHandler
    api_module.Request = object
    monkeypatch.setitem(sys.modules, "helpers.api", api_module)
    monkeypatch.delitem(sys.modules, "plugins._office.api.office_session", raising=False)

    from plugins._office.api import office_session

    doc = document_store.create_document("document", "Cold Memo", "odt", "No surprise Desktop.")

    def forbidden_session(*_args, **_kwargs):
        raise AssertionError("cold binary open must not create a store session")

    class ForbiddenManager:
        def open(self, *_args, **_kwargs):
            raise AssertionError("cold binary open must not open Desktop")

    monkeypatch.setattr(office_session.document_store, "create_session", forbidden_session)
    monkeypatch.setattr(office_session.desktop_session, "get_manager", lambda: ForbiddenManager())

    handler = office_session.OfficeSession(app=None, thread_lock=None)
    request = types.SimpleNamespace(headers={}, host_url="http://localhost:32080")
    result = asyncio.run(handler.process({"action": "open", "file_id": doc["file_id"]}, request))

    assert result["ok"] is True
    assert result["requires_desktop"] is True
    assert result["file_id"] == doc["file_id"]
    assert "session_id" not in result
    assert "store_session_id" not in result

    monkeypatch.delitem(sys.modules, "plugins._office.api.office_session", raising=False)
    api_package = sys.modules.get("plugins._office.api")
    if api_package is not None:
        monkeypatch.delattr(api_package, "office_session", raising=False)


def test_official_desktop_session_manager_opens_binary_session(office_state, tmp_path, monkeypatch):
    class FakeProcess:
        pid = 4242

        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    monkeypatch.setattr(desktop_session, "STATE_DIR", tmp_path / "desktop")
    monkeypatch.setattr(desktop_session, "SESSION_DIR", tmp_path / "desktop" / "sessions")
    monkeypatch.setattr(desktop_session, "PROFILE_DIR", tmp_path / "desktop" / "profiles")
    monkeypatch.setattr(desktop_session, "collect_desktop_status", lambda: {"healthy": True, "message": "ok"})
    monkeypatch.setattr(desktop_session.libreoffice, "find_soffice", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(desktop_session, "_port_is_free", lambda port: True)
    monkeypatch.setattr(desktop_session.virtual_desktop, "has_window", lambda **kwargs: True)
    real_get_abs_path = desktop_session.files.get_abs_path

    def fake_get_abs_path(*parts):
        if parts and parts[0] == "usr":
            return str(tmp_path.joinpath(*parts))
        return real_get_abs_path(*parts)

    monkeypatch.setattr(desktop_session.files, "get_abs_path", fake_get_abs_path)

    def fake_spawn(self, session):
        session.profile_dir.mkdir(parents=True, exist_ok=True)
        session.processes["xpra"] = FakeProcess()

    def fake_open_document(self, session, doc):
        session.processes[f"soffice-{doc['file_id']}"] = FakeProcess()

    monkeypatch.setattr(desktop_session.DesktopSessionManager, "_spawn_desktop_locked", fake_spawn)
    monkeypatch.setattr(desktop_session.DesktopSessionManager, "_open_document_locked", fake_open_document)

    doc = document_store.create_document("spreadsheet", "Official Sheet", "ods", "Name,Value\nA,1")
    manager = desktop_session.DesktopSessionManager()
    payload = manager.open(doc)

    assert payload["available"] is True
    assert payload["extension"] == "ods"
    assert payload["url"].startswith("/desktop/session/")
    registry = tmp_path / "desktop" / "profiles" / payload["session_id"] / "user" / "registrymodifications.xcu"
    registry_text = registry.read_text(encoding="utf-8")
    assert "ooSetupInstCompleted" in registry_text
    assert "FirstRun" in registry_text
    assert "Office.Paths/Variables" in registry_text
    assert "Office.Paths:NamedPath['Work']" in registry_text
    assert office_state.workdir.as_uri() in registry_text
    writer_launcher = tmp_path / "desktop" / "profiles" / payload["session_id"] / "Desktop" / "LibreOffice Writer.desktop"
    writer_text = writer_launcher.read_text(encoding="utf-8")
    assert "--writer" in writer_text
    assert f"Path={office_state.workdir}" in writer_text
    assert "X-XFCE-Trusted=true" in writer_text
    terminal_launcher = tmp_path / "desktop" / "profiles" / payload["session_id"] / "Desktop" / "Terminal.desktop"
    files_launcher = tmp_path / "desktop" / "profiles" / payload["session_id"] / "Desktop" / "Files.desktop"
    settings_launcher = tmp_path / "desktop" / "profiles" / payload["session_id"] / "Desktop" / "Settings.desktop"
    terminal_text = terminal_launcher.read_text(encoding="utf-8")
    settings_text = settings_launcher.read_text(encoding="utf-8")
    browser_launcher = tmp_path / "desktop" / "profiles" / payload["session_id"] / "Desktop" / "Browser.desktop"
    browser_text = browser_launcher.read_text(encoding="utf-8")
    assert "xfce4-terminal" in terminal_text
    assert "org.xfce.terminal" in terminal_text
    assert not files_launcher.exists()
    assert "open-url" in browser_text
    assert "firefox" not in browser_text.lower()
    assert "xfce4-settings-manager" in settings_text
    assert "org.xfce.settings.manager" in settings_text
    link_targets = {
        "Projects": "usr/projects",
        "Skills": "usr/skills",
        "Agents": "usr/agents",
        "Downloads": "usr/downloads",
    }
    workdir_link = tmp_path / "desktop" / "profiles" / payload["session_id"] / "Desktop" / "Workdir"
    assert workdir_link.is_symlink()
    assert workdir_link.resolve() == office_state.workdir
    for link_name, target in link_targets.items():
        link = tmp_path / "desktop" / "profiles" / payload["session_id"] / "Desktop" / link_name
        assert link.is_symlink()
        assert str(link.resolve()).endswith(target)
    xpra_override = (
        tmp_path
        / "desktop"
        / "profiles"
        / payload["session_id"]
        / ".local"
        / "share"
        / "applications"
        / "xpra-gui.desktop"
    )
    assert "Hidden=true" in xpra_override.read_text(encoding="utf-8")
    desktop_profile = (
        tmp_path
        / "desktop"
        / "profiles"
        / payload["session_id"]
        / ".config"
        / "xfce4"
        / "xfconf"
        / "xfce-perchannel-xml"
        / "xfce4-desktop.xml"
    )
    desktop_profile_text = desktop_profile.read_text(encoding="utf-8")
    assert "desktop-icons" in desktop_profile_text
    assert "image-path" in desktop_profile_text
    assert "usr/downloads" in desktop_profile_text
    thunar_profile = (
        tmp_path
        / "desktop"
        / "profiles"
        / payload["session_id"]
        / ".config"
        / "xfce4"
        / "xfconf"
        / "xfce-perchannel-xml"
        / "thunar.xml"
    ).read_text(encoding="utf-8")
    assert 'name="last-show-hidden" type="bool" value="true"' in thunar_profile
    user_dirs = (
        tmp_path
        / "desktop"
        / "profiles"
        / payload["session_id"]
        / ".config"
        / "user-dirs.dirs"
    ).read_text(encoding="utf-8")
    assert 'XDG_PICTURES_DIR="' in user_dirs
    assert "usr/downloads" in user_dirs
    assert f'XDG_DOCUMENTS_DIR="{office_state.workdir}"' in user_dirs
    panel_profile = (
        tmp_path
        / "desktop"
        / "profiles"
        / payload["session_id"]
        / ".config"
        / "xfce4"
        / "xfconf"
        / "xfce-perchannel-xml"
        / "xfce4-panel.xml"
    ).read_text(encoding="utf-8")
    assert "panel-1" in panel_profile
    assert "panel-2" not in panel_profile
    assert 'value="actions"' not in panel_profile
    assert 'value="launcher"' in panel_profile
    assert "agent-zero-shutdown.desktop" in panel_profile
    shutdown_app = (
        tmp_path
        / "desktop"
        / "profiles"
        / payload["session_id"]
        / ".local"
        / "share"
        / "applications"
        / "agent-zero-shutdown.desktop"
    ).read_text(encoding="utf-8")
    assert "Shutdown Desktop" in shutdown_app
    assert "shutdown-desktop" in shutdown_app
    shutdown_panel_launcher = (
        tmp_path
        / "desktop"
        / "profiles"
        / payload["session_id"]
        / ".config"
        / "xfce4"
        / "panel"
        / "launcher-9"
        / "agent-zero-shutdown.desktop"
    ).read_text(encoding="utf-8")
    assert "Shutdown Desktop" in shutdown_panel_launcher
    assert "shutdown-desktop" in shutdown_panel_launcher
    shutdown_script = (
        tmp_path
        / "desktop"
        / "profiles"
        / payload["session_id"]
        / ".agent-zero"
        / "shutdown-desktop"
    ).read_text(encoding="utf-8")
    assert "CONFIRM_SECONDS" in shutdown_script
    assert "ARM_PATH" in shutdown_script
    assert "Click Shutdown Desktop again" in shutdown_script
    assert "xmessage" in shutdown_script
    assert '"-buttons",' in shutdown_script
    desktop_helper = (
        PROJECT_ROOT / "plugins" / "_desktop" / "helpers" / "desktop_session.py"
    ).read_text(encoding="utf-8")
    assert "_refresh_xfce_desktop" in desktop_helper
    assert "DBUS_SESSION_BUS_ADDRESS" in desktop_helper
    autostart = (
        tmp_path
        / "desktop"
        / "profiles"
        / payload["session_id"]
        / ".config"
        / "autostart"
        / "agent-zero-desktop.desktop"
    )
    assert "prepare-xfce-profile.sh" in autostart.read_text(encoding="utf-8")
    profile_script = (
        tmp_path
        / "desktop"
        / "profiles"
        / payload["session_id"]
        / "prepare-xfce-profile.sh"
    ).read_text(encoding="utf-8")
    assert '"$HOME"/Desktop/*.desktop' in profile_script
    assert "agent-zero-settings.desktop" not in profile_script
    assert "metadata::xfce-exe-checksum" in profile_script
    assert "xfconf-query -c thunar -p /last-show-hidden" in profile_script
    assert "xfconf-query -c xfce4-panel" not in profile_script
    assert "launcher-*" not in profile_script
    for filename in (
        "exo-mail-reader.desktop",
        "exo-web-browser.desktop",
        "xfce4-mail-reader.desktop",
        "xfce4-web-browser.desktop",
        "xfce4-session-logout.desktop",
        "xfce4-lock-screen.desktop",
        "xflock4.desktop",
        "xfce4-switch-user.desktop",
    ):
        entry = (
            tmp_path
            / "desktop"
            / "profiles"
            / payload["session_id"]
            / ".local"
            / "share"
            / "applications"
            / filename
        ).read_text(encoding="utf-8")
        assert "NoDisplay=true" in entry
        assert "Hidden=true" in entry
    assert manager.proxy_for_token(payload["token"]) == ("127.0.0.1", desktop_session.XPRA_PORT_BASE)
    assert manager.close(payload["session_id"], save_first=False)["closed"] == 0
    assert manager.close(payload["session_id"], save_first=False)["persistent"] is True


def test_desktop_save_targets_requested_libreoffice_window(office_state, tmp_path, monkeypatch):
    doc = document_store.create_document("spreadsheet", "Targeted Save", "ods", "Name,Value\nA,1")
    session = desktop_session.DesktopSession(
        session_id=desktop_session.SYSTEM_SESSION_ID,
        file_id=doc["file_id"],
        extension=doc["extension"],
        path=doc["path"],
        title=doc["basename"],
        display=desktop_session.DISPLAY_BASE,
        xpra_port=desktop_session.XPRA_PORT_BASE,
        token=desktop_session.SYSTEM_SESSION_ID,
        url="/desktop/session/agent-zero-desktop/index.html",
        profile_dir=tmp_path / "profile",
        processes={"xpra": types.SimpleNamespace(poll=lambda: None)},
    )
    manager = desktop_session.DesktopSessionManager()
    manager._sessions[session.session_id] = session
    commands = []

    monkeypatch.setattr(desktop_session.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(desktop_session.time, "sleep", lambda _seconds: None)

    def fake_run(command, **_kwargs):
        commands.append(command)
        if command[1] == "search":
            assert command == ["/usr/bin/xdotool", "search", "--onlyvisible", "--class", "libreoffice"]
            return subprocess.CompletedProcess(command, 0, "222\n", "")
        if command[1] == "getwindowname":
            return subprocess.CompletedProcess(command, 0, f"{doc['basename']} — LibreOffice Calc\n", "")
        Path(doc["path"]).write_bytes(Path(doc["path"]).read_bytes() + b"changed")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(desktop_session.subprocess, "run", fake_run)

    result = manager.save(session.session_id, doc["file_id"])

    assert result["ok"] is True
    assert result["changed"] is True
    assert commands[-1] == [
        "/usr/bin/xdotool",
        "windowactivate",
        "--sync",
        "222",
        "key",
        "--clearmodifiers",
        "ctrl+s",
    ]

    session.file_id = desktop_session.SYSTEM_FILE_ID
    command_count = len(commands)
    assert manager.save(session.session_id)["changed"] is False
    assert len(commands) == command_count


def test_desktop_startup_waiters_probe_display_and_reject_dead_xfce(tmp_path, monkeypatch):
    session = desktop_session.DesktopSession(
        session_id=desktop_session.SYSTEM_SESSION_ID,
        file_id=desktop_session.SYSTEM_FILE_ID,
        extension="desktop",
        path=str(tmp_path),
        title=desktop_session.SYSTEM_TITLE,
        display=desktop_session.DISPLAY_BASE,
        xpra_port=desktop_session.XPRA_PORT_BASE,
        token=desktop_session.SYSTEM_SESSION_ID,
        url="/desktop/session/agent-zero-desktop/index.html",
        profile_dir=tmp_path / "profile",
        processes={"xvfb": types.SimpleNamespace(poll=lambda: None)},
    )
    manager = desktop_session.DesktopSessionManager()
    probes = iter((None, (1920, 1080)))
    monkeypatch.setattr(
        desktop_session.virtual_desktop,
        "current_display_size",
        lambda *_args, **_kwargs: next(probes),
    )
    monkeypatch.setattr(desktop_session.time, "sleep", lambda _seconds: None)

    manager._wait_for_display(session)

    session.processes = {"xfce": types.SimpleNamespace(poll=lambda: 1)}
    with pytest.raises(RuntimeError, match="XFCE desktop session exited"):
        manager._wait_for_xfce(session)


@pytest.mark.parametrize("overrides", [{}, {"XPRA_SYSTEM_DBUS_TIMEOUT": "7"}])
def test_desktop_xpra_uses_bounded_service_waits(tmp_path, monkeypatch, overrides):
    session = types.SimpleNamespace(
        profile_dir=tmp_path / "profile", processes={},
        display=120, xpra_port=14500, width=1440, height=900,
    )
    manager = desktop_session.DesktopSessionManager()
    environments = {}
    monkeypatch.setattr(desktop_session, "STATE_DIR", tmp_path)
    monkeypatch.setattr(desktop_session, "SESSION_DIR", tmp_path / "sessions")
    monkeypatch.setattr(desktop_session, "_require_binary", lambda name: name)
    monkeypatch.setattr(manager, "_prepare_xfce_launcher", lambda _: "xfce")
    monkeypatch.setattr(manager, "_session_env", lambda _: overrides)
    monkeypatch.setattr(manager, "_display_env", lambda _: overrides)
    for method in ("_wait_for_display", "_set_display_size", "_prepare_root_window",
                   "_wait_for_xfce", "_refresh_xfce_desktop"):
        monkeypatch.setattr(manager, method, lambda *_: None)
    monkeypatch.setattr(
        desktop_session, "_wait_for_port", lambda *_, **__: None,
    )

    def spawn(command, **kwargs):
        if command[0] == "xpra":
            assert "--mmap=no" in command
        environments[command[0]] = kwargs["env"]
        return types.SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr(desktop_session.subprocess, "Popen", spawn)
    manager._spawn_desktop_locked(session)

    assert environments["xpra"]["XPRA_SYSTEM_DBUS_TIMEOUT"] == overrides.get("XPRA_SYSTEM_DBUS_TIMEOUT", "1")
    assert environments["xpra"]["XPRA_SYSTEM_CUPS_TIMEOUT"] == "1"
    assert environments["xfce"] == overrides


def test_desktop_manifest_is_replaced_atomically(tmp_path, monkeypatch):
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    manifest = session_dir / f"{desktop_session.SYSTEM_SESSION_ID}.json"
    manifest.write_text('{"old": true}', encoding="utf-8")
    session = desktop_session.DesktopSession(
        session_id=desktop_session.SYSTEM_SESSION_ID,
        file_id=desktop_session.SYSTEM_FILE_ID,
        extension="desktop",
        path=str(tmp_path),
        title=desktop_session.SYSTEM_TITLE,
        display=desktop_session.DISPLAY_BASE,
        xpra_port=desktop_session.XPRA_PORT_BASE,
        token=desktop_session.SYSTEM_SESSION_ID,
        url="/desktop/session/agent-zero-desktop/index.html",
        profile_dir=tmp_path / "profile",
    )
    real_replace = os.replace

    def assert_atomic_replace(source, destination):
        assert json.loads(Path(destination).read_text(encoding="utf-8")) == {"old": True}
        assert json.loads(Path(source).read_text(encoding="utf-8"))["display"] == session.display
        real_replace(source, destination)

    monkeypatch.setattr(desktop_session, "SESSION_DIR", session_dir)
    monkeypatch.setattr(desktop_session.os, "replace", assert_atomic_replace)

    desktop_session.DesktopSessionManager()._write_manifest(session)

    assert json.loads(manifest.read_text(encoding="utf-8"))["session_id"] == session.session_id
    assert list(session_dir.glob(".*.tmp")) == []


def test_shutdown_panel_launcher_requires_second_click(tmp_path):
    profile_dir = tmp_path / "desktop" / "profiles" / desktop_session.SYSTEM_SESSION_ID
    profile_dir.mkdir(parents=True)
    desktop_path = tmp_path / "workdir"
    desktop_path.mkdir()
    session = desktop_session.DesktopSession(
        session_id=desktop_session.SYSTEM_SESSION_ID,
        file_id=desktop_session.SYSTEM_FILE_ID,
        extension="desktop",
        path=str(desktop_path),
        title=desktop_session.SYSTEM_TITLE,
        display=desktop_session.DISPLAY_BASE,
        xpra_port=desktop_session.XPRA_PORT_BASE,
        token=desktop_session.SYSTEM_SESSION_ID,
        url="/desktop/session/agent-zero-desktop/index.html",
        profile_dir=profile_dir,
    )
    script = desktop_session._write_shutdown_bridge_script(session)
    request = desktop_session._shutdown_request_path(session)
    arm = desktop_session._shutdown_arm_path(session)
    env = dict(os.environ)
    env.pop("DISPLAY", None)

    subprocess.run([sys.executable, str(script)], check=True, env=env)

    assert arm.exists()
    assert not request.exists()

    subprocess.run([sys.executable, str(script)], check=True, env=env)

    payload = json.loads(request.read_text(encoding="utf-8"))
    assert payload["source"] == "tray"
    assert payload["armed_at"] <= payload["created_at"]
    assert not arm.exists()


def test_desktop_session_sync_consumes_shutdown_marker(tmp_path, monkeypatch):
    class FakeProcess:
        pid = 5252
        terminated = False

        def poll(self):
            return None if not self.terminated else 0

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.terminated = True
            return 0

        def kill(self):
            self.terminated = True

    monkeypatch.setattr(desktop_session, "STATE_DIR", tmp_path / "desktop")
    monkeypatch.setattr(desktop_session, "SESSION_DIR", tmp_path / "desktop" / "sessions")
    monkeypatch.setattr(desktop_session, "PROFILE_DIR", tmp_path / "desktop" / "profiles")

    profile_dir = tmp_path / "desktop" / "profiles" / desktop_session.SYSTEM_SESSION_ID
    profile_dir.mkdir(parents=True)
    desktop_path = tmp_path / "workdir"
    desktop_path.mkdir()
    session = desktop_session.DesktopSession(
        session_id=desktop_session.SYSTEM_SESSION_ID,
        file_id=desktop_session.SYSTEM_FILE_ID,
        extension="desktop",
        path=str(desktop_path),
        title=desktop_session.SYSTEM_TITLE,
        display=desktop_session.DISPLAY_BASE,
        xpra_port=desktop_session.XPRA_PORT_BASE,
        token=desktop_session.SYSTEM_SESSION_ID,
        url="/desktop/session/agent-zero-desktop/index.html",
        profile_dir=profile_dir,
        processes={"xpra": FakeProcess()},
    )
    manager = desktop_session.DesktopSessionManager()
    manager._sessions[session.session_id] = session
    manager._write_manifest(session)
    desktop_session._write_url_bridge_script(session)
    shutdown_request = desktop_session._shutdown_request_path(session)
    shutdown_request.write_text('{"source": "tray", "created_at": 123.0}\n', encoding="utf-8")
    save_calls = []
    monkeypatch.setattr(
        manager,
        "save",
        lambda session_id, file_id="": save_calls.append((session_id, file_id)) or {"ok": True},
    )

    result = manager.sync(session_id=session.session_id)

    assert result["ok"] is True
    assert result["intentional_shutdown"] is True
    assert result["source"] == "tray"
    assert result["closed"] == 1
    assert save_calls == [(desktop_session.SYSTEM_SESSION_ID, "")]
    assert not shutdown_request.exists()
    assert not (desktop_session.SESSION_DIR / f"{session.session_id}.json").exists()
    assert manager.get(session.session_id) is None


def test_desktop_session_cleanup_preserves_live_owner_manifest(tmp_path, monkeypatch):
    session_dir = tmp_path / "sessions"
    legacy_session_dir = tmp_path / "legacy-sessions"
    session_dir.mkdir()
    legacy_session_dir.mkdir()
    manifest = session_dir / "live.json"
    manifest.write_text(
        json.dumps({"owner_pid": os.getpid(), "pids": {"xpra": 987654}}),
        encoding="utf-8",
    )
    legacy_manifest = legacy_session_dir / "stale.json"
    legacy_manifest.write_text(
        json.dumps({"owner_pid": 987650, "pids": {"xpra": 987651, "xfce": 987652}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(desktop_session, "SESSION_DIR", session_dir)
    monkeypatch.setattr(desktop_session, "LEGACY_SESSION_DIRS", (legacy_session_dir,))
    killed = []

    def fake_kill_pid(pid):
        killed.append(pid)
        return True

    monkeypatch.setattr(
        desktop_session,
        "_kill_pid",
        fake_kill_pid,
    )

    result = desktop_session.cleanup_stale_runtime_state()

    assert result["killed"] == [987651, 987652]
    assert killed == [987651, 987652]
    assert manifest.exists()
    assert not legacy_manifest.exists()


def test_desktop_session_removes_stale_lock_file(tmp_path):
    doc_path = tmp_path / "Deck.pptx"
    doc_path.write_text("pptx", encoding="utf-8")
    lock_path = tmp_path / ".~lock.Deck.pptx#"
    lock_path.write_text("stale", encoding="utf-8")
    session = desktop_session.DesktopSession(
        session_id="session",
        file_id="file",
        extension="pptx",
        path=str(doc_path),
        title=doc_path.name,
        display=desktop_session.DISPLAY_BASE,
        xpra_port=desktop_session.XPRA_PORT_BASE,
        token="token",
        url="/desktop/session/token/index.html",
        profile_dir=tmp_path / "profile",
    )

    desktop_session.DesktopSessionManager()._remove_stale_lock_file(session)

    assert not lock_path.exists()


def _isolate_office_cleanup_hook(monkeypatch, tmp_path):
    state_dir = tmp_path / "usr" / "plugins" / "_office"
    retired_state_dir = tmp_path / "usr" / "_office"
    monkeypatch.setattr(hooks, "RETIRED_WEB_APT_SOURCE_FILE", tmp_path / "missing.sources")
    monkeypatch.setattr(hooks, "RETIRED_WEB_APT_KEYRING_FILE", tmp_path / "missing.gpg")
    monkeypatch.setattr(hooks, "RETIRED_WEB_SUPERVISOR_FILE", tmp_path / "missing.conf")
    monkeypatch.setattr(hooks, "RETIRED_WEB_RUNTIME_DIRS", [])
    monkeypatch.setattr(hooks, "STATE_DIR", state_dir)
    monkeypatch.setattr(hooks, "RETIRED_STATE_DIR", retired_state_dir)
    monkeypatch.setattr(hooks, "DOCUMENT_STATE_DIR", state_dir / "documents")
    monkeypatch.setattr(hooks, "LEGACY_DOCUMENT_STATE_DIRS", [])
    monkeypatch.setattr(hooks, "CLEANUP_MARKER", state_dir / "cleanup.done")
    monkeypatch.setattr(hooks, "_installed_retired_web_packages", lambda: [])
    monkeypatch.setattr(hooks, "_installed_packages", lambda packages: [])
    monkeypatch.setattr(hooks, "_kill_old_processes", lambda errors: None)
    monkeypatch.setattr(hooks, "_ensure_runtime_dependencies", lambda installed, errors: None)
    monkeypatch.setattr(hooks, "_purge_packages", lambda removed, errors, **kwargs: None)
    monkeypatch.setattr(hooks.shutil, "which", lambda name: "")


def test_cleanup_hook_moves_retired_office_state_to_plugin_state(tmp_path, monkeypatch):
    _isolate_office_cleanup_hook(monkeypatch, tmp_path)
    retired_state = tmp_path / "usr" / "_office"
    plugin_state = tmp_path / "usr" / "plugins" / "_office"
    (retired_state / "documents" / "backups").mkdir(parents=True)
    (retired_state / "documents" / "documents.sqlite3").write_text("db\n", encoding="utf-8")
    (retired_state / "documents" / "backups" / "draft.md").write_text("backup\n", encoding="utf-8")
    (retired_state / "stale-cleanup-v3.done").write_text("ok\n", encoding="utf-8")
    plugin_state.mkdir(parents=True)

    result = hooks.cleanup_stale_runtime_state(force=True)

    assert result["ok"] is True
    assert (plugin_state / "documents" / "documents.sqlite3").read_text(encoding="utf-8") == "db\n"
    assert (plugin_state / "documents" / "backups" / "draft.md").read_text(encoding="utf-8") == "backup\n"
    assert (plugin_state / "stale-cleanup-v3.done").read_text(encoding="utf-8") == "ok\n"
    assert not retired_state.exists()


def test_cleanup_hook_migrates_legacy_document_state_without_removing_source(tmp_path, monkeypatch):
    _isolate_office_cleanup_hook(monkeypatch, tmp_path)
    legacy_documents = tmp_path / "usr" / "state" / "_office" / "documents"
    document_state = tmp_path / "usr" / "plugins" / "_office" / "documents"
    legacy_documents.mkdir(parents=True)
    (legacy_documents / "documents.sqlite3").write_text("legacy-db\n", encoding="utf-8")
    (legacy_documents / "backups").mkdir()
    (legacy_documents / "backups" / "draft.md").write_text("backup\n", encoding="utf-8")

    monkeypatch.setattr(hooks, "DOCUMENT_STATE_DIR", document_state)
    monkeypatch.setattr(hooks, "LEGACY_DOCUMENT_STATE_DIRS", [legacy_documents])
    result = hooks.cleanup_stale_runtime_state(force=True)

    assert result["ok"] is True
    assert result["migrated"] == [f"{legacy_documents} -> {document_state}"]
    assert (legacy_documents / "documents.sqlite3").exists()
    assert (document_state / "documents.sqlite3").read_text(encoding="utf-8") == "legacy-db\n"
    assert (document_state / "backups" / "draft.md").read_text(encoding="utf-8") == "backup\n"


def test_cleanup_hook_prefers_existing_new_document_state_without_merge(tmp_path, monkeypatch):
    _isolate_office_cleanup_hook(monkeypatch, tmp_path)
    legacy_documents = tmp_path / "legacy-documents"
    document_state = tmp_path / "usr" / "plugins" / "_office" / "documents"
    legacy_documents.mkdir(parents=True)
    document_state.mkdir(parents=True)
    (legacy_documents / "documents.sqlite3").write_text("legacy-db\n", encoding="utf-8")
    (document_state / "documents.sqlite3").write_text("new-db\n", encoding="utf-8")

    monkeypatch.setattr(hooks, "DOCUMENT_STATE_DIR", document_state)
    monkeypatch.setattr(hooks, "LEGACY_DOCUMENT_STATE_DIRS", [legacy_documents])
    result = hooks.cleanup_stale_runtime_state(force=True)

    assert result["ok"] is True
    assert result["migrated"] == []
    assert result["warnings"] == [
        f"Legacy Office document state left in place because {document_state} already exists: {legacy_documents}"
    ]
    assert (legacy_documents / "documents.sqlite3").read_text(encoding="utf-8") == "legacy-db\n"
    assert (document_state / "documents.sqlite3").read_text(encoding="utf-8") == "new-db\n"


def test_cleanup_hook_targets_legacy_collabora_runtime_artifacts():
    assert Path("/opt/cool") in hooks.RETIRED_WEB_RUNTIME_DIRS
    assert Path("/opt/collaboraoffice") in hooks.RETIRED_WEB_RUNTIME_DIRS
    assert {
        "collaboraoffice-ure",
        "collaboraofficebasis-core",
        "collaboraofficebasis-ooofonts",
    }.issubset(hooks.RETIRED_WEB_PACKAGES)


def test_installed_retired_web_packages_discovers_collabora_split_packages(monkeypatch):
    monkeypatch.setattr(
        hooks.shutil,
        "which",
        lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else "",
    )
    monkeypatch.setattr(
        hooks,
        "_package_installed",
        lambda package: package in {"coolwsd", "collaboraofficebasis-core"},
    )

    def fake_run(command, **kwargs):
        assert command == ["dpkg-query", "-W", "-f=${binary:Package}\t${Status}\n", "collaboraoffice*"]
        return types.SimpleNamespace(
            returncode=0,
            stdout=(
                "collaboraofficebasis-core\tinstall ok installed\n"
                "collaboraofficebasis-extra-future\tinstall ok installed\n"
                "collaboraofficebasis-config-files\tdeinstall ok config-files\n"
                "notcollaboraoffice\tinstall ok installed\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(hooks.subprocess, "run", fake_run)

    packages = hooks._installed_retired_web_packages()

    assert packages == [
        "coolwsd",
        "collaboraofficebasis-core",
        "collaboraofficebasis-extra-future",
    ]


def test_cleanup_hook_removes_stale_runtime_state_idempotently(tmp_path, monkeypatch):
    source = tmp_path / "sources.list.d" / "retired.sources"
    keyring = tmp_path / "keyrings" / "retired.gpg"
    supervisor = tmp_path / "supervisor" / "retired.conf"
    runtime_dir = tmp_path / "runtime"
    legacy_cool_dir = tmp_path / "opt" / "cool"
    legacy_collabora_dir = tmp_path / "opt" / "collaboraoffice"
    marker = tmp_path / "state" / "cleanup.done"

    for path in (source, keyring, supervisor):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("old\n", encoding="utf-8")
    (runtime_dir / "nested").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "nested" / "state.txt").write_text("old\n", encoding="utf-8")
    (legacy_cool_dir / "state").mkdir(parents=True, exist_ok=True)
    (legacy_cool_dir / "state" / "cool.txt").write_text("old\n", encoding="utf-8")
    (legacy_collabora_dir / "program").mkdir(parents=True, exist_ok=True)
    (legacy_collabora_dir / "program" / "office.txt").write_text("old\n", encoding="utf-8")

    monkeypatch.setattr(hooks, "RETIRED_WEB_APT_SOURCE_FILE", source)
    monkeypatch.setattr(hooks, "RETIRED_WEB_APT_KEYRING_FILE", keyring)
    monkeypatch.setattr(hooks, "RETIRED_WEB_SUPERVISOR_FILE", supervisor)
    monkeypatch.setattr(hooks, "RETIRED_WEB_RUNTIME_DIRS", [runtime_dir, legacy_cool_dir, legacy_collabora_dir])
    monkeypatch.setattr(hooks, "CLEANUP_MARKER", marker)
    monkeypatch.setattr(hooks, "DOCUMENT_STATE_DIR", tmp_path / "usr" / "plugins" / "_office" / "documents")
    monkeypatch.setattr(hooks, "LEGACY_DOCUMENT_STATE_DIRS", [])
    monkeypatch.setattr(hooks, "_installed_retired_web_packages", lambda: [])
    monkeypatch.setattr(hooks, "_installed_packages", lambda packages: [])
    monkeypatch.setattr(hooks, "_kill_old_processes", lambda errors: None)
    def fake_ensure(installed, errors):
        assert not source.exists()
        installed.append("libreoffice-core")

    def fake_purge(removed, errors, **kwargs):
        return None

    monkeypatch.setattr(hooks, "_ensure_runtime_dependencies", fake_ensure)
    monkeypatch.setattr(hooks, "_purge_packages", fake_purge)

    first = hooks.cleanup_stale_runtime_state(force=True)
    second = hooks.cleanup_stale_runtime_state(force=True)
    skipped = hooks.cleanup_stale_runtime_state()

    assert first["ok"] is True
    assert first["installed"] == ["libreoffice-core"]
    assert second["ok"] is True
    assert skipped["skipped"] is True
    assert not source.exists()
    assert not keyring.exists()
    assert not supervisor.exists()
    assert not runtime_dir.exists()
    assert not legacy_cool_dir.exists()
    assert not legacy_collabora_dir.exists()
    assert marker.exists()


def test_office_startup_defers_persistent_desktop_runtime(monkeypatch):
    cleanup_calls = []
    started_threads = []
    monkeypatch.delitem(
        sys.modules,
        "plugins._office.extensions.python.startup_migration._20_office_routes",
        raising=False,
    )

    from plugins._office.extensions.python.startup_migration import _20_office_routes as office_startup

    monkeypatch.setattr(
        office_startup.hooks,
        "cleanup_stale_runtime_state",
        lambda: cleanup_calls.append("cleanup") or {"ok": True, "errors": [], "installed": [], "removed": []},
    )

    class FakeThread:
        def __init__(self, *, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon

        def is_alive(self):
            return False

        def start(self):
            started_threads.append(self)

    monkeypatch.setattr(office_startup.threading, "Thread", FakeThread)

    office_startup.OfficeStartupCleanup(agent=None).execute()

    assert cleanup_calls == []
    assert len(started_threads) == 1
    assert started_threads[0].name == "a0-office-document-runtime-preparation"
    assert started_threads[0].daemon is True
    assert not hasattr(office_startup, "desktop_session")

    started_threads[0].target()
    assert cleanup_calls == ["cleanup"]


def test_cleanup_hook_reruns_when_stale_packages_exist_after_old_marker(tmp_path, monkeypatch):
    marker = tmp_path / "state" / "cleanup.done"
    marker.parent.mkdir(parents=True)
    marker.write_text("old\n", encoding="utf-8")

    monkeypatch.setattr(hooks, "RETIRED_WEB_APT_SOURCE_FILE", tmp_path / "missing.sources")
    monkeypatch.setattr(hooks, "RETIRED_WEB_APT_KEYRING_FILE", tmp_path / "missing.gpg")
    monkeypatch.setattr(hooks, "RETIRED_WEB_SUPERVISOR_FILE", tmp_path / "missing.conf")
    monkeypatch.setattr(hooks, "RETIRED_WEB_RUNTIME_DIRS", [])
    monkeypatch.setattr(hooks, "CLEANUP_MARKER", marker)
    monkeypatch.setattr(hooks, "DOCUMENT_STATE_DIR", tmp_path / "usr" / "plugins" / "_office" / "documents")
    monkeypatch.setattr(hooks, "LEGACY_DOCUMENT_STATE_DIRS", [])
    retired_web_packages = [
        "coolwsd",
        "collaboraoffice-ure",
        "collaboraofficebasis-core",
        "collaboraofficebasis-ooofonts",
    ]
    monkeypatch.setattr(hooks, "_installed_retired_web_packages", lambda: retired_web_packages)
    monkeypatch.setattr(hooks, "_installed_packages", lambda packages: [])
    monkeypatch.setattr(hooks, "_ensure_runtime_dependencies", lambda installed, errors: None)
    monkeypatch.setattr(hooks, "_kill_old_processes", lambda errors: None)
    def fake_purge(removed, errors, **kwargs):
        removed.extend(kwargs["installed_packages"])

    monkeypatch.setattr(hooks, "_purge_packages", fake_purge)

    result = hooks.cleanup_stale_runtime_state()

    assert result["skipped"] is False
    assert result["removed"] == retired_web_packages


def test_cleanup_hook_removes_retired_supervisor_program_after_marker(tmp_path, monkeypatch):
    marker = tmp_path / "state" / "cleanup.done"
    marker.parent.mkdir(parents=True)
    marker.write_text("ok\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(hooks, "RETIRED_WEB_APT_SOURCE_FILE", tmp_path / "missing.sources")
    monkeypatch.setattr(hooks, "RETIRED_WEB_APT_KEYRING_FILE", tmp_path / "missing.gpg")
    monkeypatch.setattr(hooks, "RETIRED_WEB_SUPERVISOR_FILE", tmp_path / "missing.conf")
    monkeypatch.setattr(hooks, "RETIRED_WEB_RUNTIME_DIRS", [])
    monkeypatch.setattr(hooks, "CLEANUP_MARKER", marker)
    monkeypatch.setattr(hooks, "DOCUMENT_STATE_DIR", tmp_path / "usr" / "plugins" / "_office" / "documents")
    monkeypatch.setattr(hooks, "LEGACY_DOCUMENT_STATE_DIRS", [])
    monkeypatch.setattr(hooks, "_installed_retired_web_packages", lambda: [])
    monkeypatch.setattr(hooks, "_installed_packages", lambda packages: [])
    monkeypatch.setattr(hooks, "_ensure_runtime_dependencies", lambda installed, errors: None)
    monkeypatch.setattr(hooks.shutil, "which", lambda name: "/usr/bin/supervisorctl" if name == "supervisorctl" else "")

    def fake_supervisorctl(*args):
        calls.append(args)
        if args == ("status", hooks.RETIRED_WEB_SUPERVISOR_PROGRAM):
            return types.SimpleNamespace(
                returncode=0,
                stdout="a0_office_collabora BACKOFF can't find command\n",
                stderr="",
            )
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(hooks, "_supervisorctl", fake_supervisorctl)

    result = hooks.cleanup_stale_runtime_state()

    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["errors"] == []
    assert calls == [
        ("status", hooks.RETIRED_WEB_SUPERVISOR_PROGRAM),
        ("stop", hooks.RETIRED_WEB_SUPERVISOR_PROGRAM),
        ("remove", hooks.RETIRED_WEB_SUPERVISOR_PROGRAM),
        ("reread",),
        ("update",),
    ]


def test_office_runtime_dependency_install_waits_out_apt_locks(monkeypatch):
    calls = []
    installed_state = {"libreoffice-core": False}
    update_attempts = {"count": 0}

    monkeypatch.setattr(hooks.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        hooks.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"apt-get", "dpkg-query"} else "",
    )
    monkeypatch.setattr(hooks, "RUNTIME_PACKAGES", ("libreoffice-core",))
    monkeypatch.setattr(hooks, "_package_installed", lambda package: installed_state.get(package, False))
    monkeypatch.setattr(system_packages.time, "sleep", lambda _seconds: None)

    def fake_run(command, **kwargs):
        calls.append(command)
        if command == ["apt-get", "update"]:
            update_attempts["count"] += 1
            if update_attempts["count"] == 1:
                return types.SimpleNamespace(
                    returncode=100,
                    stdout="",
                    stderr="E: Could not get lock /var/lib/apt/lists/lock. It is held by process 1829 (apt-get)",
                )
        if command[:2] == ["apt-get", "install"]:
            installed_state["libreoffice-core"] = True
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(hooks.subprocess, "run", fake_run)
    installed = []
    errors = []

    hooks._ensure_runtime_dependencies(installed, errors)

    assert errors == []
    assert installed == ["libreoffice-core"]
    assert calls[:2] == [["apt-get", "update"], ["apt-get", "update"]]
    assert calls[2][:4] == ["apt-get", "install", "-y", "--no-install-recommends"]


def test_desktop_runtime_packages_include_libreoffice_for_desktop_status():
    install_additional = (
        PROJECT_ROOT / "docker" / "run" / "fs" / "ins" / "install_additional.sh"
    ).read_text(encoding="utf-8")

    assert set(desktop_hooks.LIBREOFFICE_RUNTIME_PACKAGES).issubset(desktop_hooks.RUNTIME_PACKAGES)
    assert "libreoffice-writer" in desktop_hooks.RUNTIME_PACKAGES
    assert "libreoffice-calc" in desktop_hooks.RUNTIME_PACKAGES
    assert "libreoffice-impress" in desktop_hooks.RUNTIME_PACKAGES
    assert desktop_hooks.GTK_RUNTIME_PACKAGE in desktop_hooks.RUNTIME_PACKAGES
    assert "xpra-client" in desktop_hooks.RUNTIME_PACKAGES
    assert "xpra-client-gtk3" in desktop_hooks.RUNTIME_PACKAGES
    assert f'XPRA_VERSION="{desktop_hooks.XPRA_VERSION}"' in install_additional


def test_desktop_cleanup_moves_retired_state_to_plugin_state(tmp_path, monkeypatch):
    retired_state = tmp_path / "usr" / "_desktop"
    plugin_state = tmp_path / "usr" / "plugins" / "_desktop"
    (retired_state / "profiles" / "agent-zero-desktop").mkdir(parents=True)
    (retired_state / "profiles" / "agent-zero-desktop" / "profile.txt").write_text("profile\n", encoding="utf-8")
    (retired_state / "sessions").mkdir()
    (retired_state / "sessions" / "agent-zero-desktop.json").write_text("{}\n", encoding="utf-8")
    (retired_state / "screenshots").mkdir()
    (retired_state / "screenshots" / "desktop.png").write_bytes(b"png")
    plugin_state.mkdir(parents=True)

    monkeypatch.setattr(desktop_hooks, "STATE_DIR", plugin_state)
    monkeypatch.setattr(desktop_hooks, "RETIRED_STATE_DIR", retired_state)
    monkeypatch.setattr(desktop_hooks, "_installed_packages", lambda packages: [])
    monkeypatch.setattr(desktop_hooks, "_ensure_runtime_dependencies", lambda installed, errors: None)
    monkeypatch.setattr(desktop_hooks, "_cleanup_desktop_sessions", lambda errors: None)

    result = desktop_hooks.cleanup_stale_runtime_state(force=True)

    assert result["ok"] is True
    assert (plugin_state / "profiles" / "agent-zero-desktop" / "profile.txt").read_text(encoding="utf-8") == "profile\n"
    assert (plugin_state / "sessions" / "agent-zero-desktop.json").read_text(encoding="utf-8") == "{}\n"
    assert not (plugin_state / "screenshots").exists()
    assert any("Removed retired persistent Desktop screenshots" in warning for warning in result["warnings"])
    assert not retired_state.exists()


def test_cleanup_hook_installs_missing_desktop_session_dependencies(monkeypatch):
    calls = []
    installed_state = {"xpra": False}

    monkeypatch.setattr(desktop_hooks.os, "geteuid", lambda: 0)
    monkeypatch.setattr(desktop_hooks.shutil, "which", lambda name: f"/usr/bin/{name}" if name in {"apt-get", "dpkg-query"} else "")
    monkeypatch.setattr(desktop_hooks, "RUNTIME_PACKAGES", ("xpra",))
    monkeypatch.setattr(desktop_hooks, "_package_installed", lambda package: installed_state.get(package, False))

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["apt-get", "install"]:
            installed_state["xpra"] = True
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(desktop_hooks.subprocess, "run", fake_run)
    installed = []
    errors = []

    desktop_hooks._ensure_runtime_dependencies(installed, errors)

    assert installed == ["xpra"]
    assert errors == []
    assert calls[0] == ["apt-get", "update"]
    assert calls[1][:4] == ["apt-get", "install", "-y", "--no-install-recommends"]


def test_cleanup_hook_enables_official_xpra_repo_when_kali_lacks_candidate(tmp_path, monkeypatch):
    calls = []
    installed_state = {"xpra": False, "ca-certificates": True}
    keyring = tmp_path / "keyrings" / "xpra.asc"
    source = tmp_path / "sources.list.d" / "xpra.sources"

    monkeypatch.setattr(desktop_hooks.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        desktop_hooks.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"apt-get", "dpkg-query", "apt-cache"} else "",
    )
    monkeypatch.setattr(desktop_hooks, "RUNTIME_PACKAGES", ("xpra",))
    monkeypatch.setattr(desktop_hooks, "XPRA_KEYRING_FILE", keyring)
    monkeypatch.setattr(desktop_hooks, "XPRA_SOURCE_FILE", source)
    monkeypatch.setattr(desktop_hooks, "_download", lambda url: b"xpra-key")
    monkeypatch.setattr(desktop_hooks, "_read_os_release", lambda: {"ID": "kali", "VERSION_CODENAME": "kali-rolling"})
    monkeypatch.setattr(desktop_hooks, "_dpkg_architecture", lambda: "amd64")
    monkeypatch.setattr(desktop_hooks, "_package_installed", lambda package: installed_state.get(package, False))

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["apt-cache", "policy"]:
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        if command[:2] == ["apt-get", "install"]:
            installed_state["xpra"] = True
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(desktop_hooks.subprocess, "run", fake_run)
    installed = []
    errors = []

    desktop_hooks._ensure_runtime_dependencies(installed, errors)

    assert errors == []
    assert installed == ["xpra"]
    assert keyring.read_bytes() == b"xpra-key"
    assert "URIs: https://xpra.org\n" in source.read_text(encoding="utf-8")
    assert "Suites: trixie" in source.read_text(encoding="utf-8")
    assert calls.count(["apt-get", "update"]) == 1
    assert [
        "bash", str(PROJECT_ROOT / "plugins/_desktop/helpers/refresh_xpra_index.sh"), str(source),
    ] in calls
    assert calls[-1][:4] == ["apt-get", "install", "-y", "--no-install-recommends"]


def test_cleanup_hook_uses_trixie_xpra_components_for_kali_arm64(tmp_path, monkeypatch):
    calls = []
    installed_state = {"xpra-server": False, "xpra-x11": False, "xpra-html5": False, "ca-certificates": True}
    keyring = tmp_path / "keyrings" / "xpra.asc"
    source = tmp_path / "sources.list.d" / "xpra.sources"

    monkeypatch.setattr(desktop_hooks.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        desktop_hooks.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"apt-get", "dpkg-query", "apt-cache"} else "",
    )
    monkeypatch.setattr(desktop_hooks, "RUNTIME_PACKAGES", ("xpra-server", "xpra-x11", "xpra-html5"))
    monkeypatch.setattr(desktop_hooks, "XPRA_KEYRING_FILE", keyring)
    monkeypatch.setattr(desktop_hooks, "XPRA_SOURCE_FILE", source)
    monkeypatch.setattr(desktop_hooks, "_download", lambda url: b"xpra-key")
    monkeypatch.setattr(desktop_hooks, "_read_os_release", lambda: {"ID": "kali", "VERSION_CODENAME": "kali-rolling"})
    monkeypatch.setattr(desktop_hooks, "_dpkg_architecture", lambda: "arm64")
    monkeypatch.setattr(desktop_hooks, "_package_installed", lambda package: installed_state.get(package, False))

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["apt-cache", "policy"]:
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        if command[:2] == ["apt-get", "install"]:
            for package in command[4:]:
                installed_state[package] = True
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(desktop_hooks.subprocess, "run", fake_run)
    installed = []
    errors = []

    desktop_hooks._ensure_runtime_dependencies(installed, errors)

    assert errors == []
    assert installed == ["xpra-server", "xpra-x11", "xpra-html5"]
    source_text = source.read_text(encoding="utf-8")
    assert "URIs: https://xpra.org\n" in source_text
    assert "Suites: trixie" in source_text
    assert [
        "bash", str(PROJECT_ROOT / "plugins/_desktop/helpers/refresh_xpra_index.sh"), str(source),
    ] in calls
    assert "xpra" not in calls[-1]
    assert calls[-1][-3:] == [
        f"xpra-server={desktop_hooks.XPRA_VERSION}",
        f"xpra-x11={desktop_hooks.XPRA_VERSION}",
        "xpra-html5",
    ]


def test_cleanup_hook_stops_when_xpra_index_refresh_fails(monkeypatch):
    calls = []
    monkeypatch.setattr(desktop_hooks.os, "geteuid", lambda: 0)
    monkeypatch.setattr(desktop_hooks.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(desktop_hooks, "RUNTIME_PACKAGES", ("xpra-server",))
    monkeypatch.setattr(desktop_hooks, "_package_installed", lambda package: False)
    monkeypatch.setattr(desktop_hooks, "_package_candidates_available", lambda packages: False)
    monkeypatch.setattr(desktop_hooks, "_ensure_xpra_repository", lambda installed, errors: None)

    def run(command, **kwargs):
        calls.append(command)
        failed = command[0] == "bash"
        return types.SimpleNamespace(returncode=100 if failed else 0, stdout="", stderr="bad index signature" if failed else "")

    monkeypatch.setattr(desktop_hooks, "_run_apt_command", run)
    installed = []
    errors = []
    desktop_hooks._ensure_runtime_dependencies(installed, errors)
    assert installed == []
    assert errors == ["bad index signature"]
    assert len(calls) == 2
    assert calls[-1][0] == "bash"


def test_cleanup_hook_installs_matching_xpra_client_stack(monkeypatch):
    calls = []
    installed_state = {
        "xpra-client": False,
        "xpra-client-gtk3": False,
    }

    monkeypatch.setattr(desktop_hooks.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        desktop_hooks.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"apt-get", "dpkg-query", "apt-cache"} else "",
    )
    monkeypatch.setattr(
        desktop_hooks,
        "RUNTIME_PACKAGES",
        ("xpra-client", "xpra-client-gtk3"),
    )
    monkeypatch.setattr(desktop_hooks, "_package_installed", lambda package: installed_state.get(package, False))
    monkeypatch.setattr(desktop_hooks, "_package_version", lambda package: "6.5.2-r0-1")

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["apt-cache", "policy"]:
            return types.SimpleNamespace(returncode=0, stdout="Candidate: 6.5.3-r0-1\n", stderr="")
        if command[:2] == ["apt-get", "install"]:
            installed_state["xpra-client"] = True
            installed_state["xpra-client-gtk3"] = True
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(desktop_hooks.subprocess, "run", fake_run)
    installed = []
    errors = []

    desktop_hooks._ensure_runtime_dependencies(installed, errors)

    assert installed == ["xpra-client", "xpra-client-gtk3"]
    assert errors == []
    assert calls[-1][-2:] == ["xpra-client=6.5.2-r0-1", "xpra-client-gtk3=6.5.2-r0-1"]


@pytest.mark.parametrize("optional_installed", [False, True])
@pytest.mark.parametrize("install_fails", [False, True])
def test_cleanup_hook_repairs_kali_gtk_from_snapshot(tmp_path, monkeypatch, optional_installed, install_fails):
    calls = []
    installed_state = {package: optional_installed for package in desktop_hooks.ATK_OPTIONAL_PACKAGES}
    source = tmp_path / "sources.list"
    source.write_text("deb http://http.kali.org/kali kali-rolling main\n", encoding="utf-8")

    monkeypatch.setattr(system_packages, "KALI_SOURCE_FILES", (source,))
    monkeypatch.setattr(system_packages.platform, "freedesktop_os_release", lambda: {"ID": "kali"})
    monkeypatch.setattr(desktop_hooks.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        desktop_hooks.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"apt-get", "dpkg-query"} else "",
    )
    monkeypatch.setattr(desktop_hooks, "RUNTIME_PACKAGES", (desktop_hooks.GTK_RUNTIME_PACKAGE,))
    monkeypatch.setattr(desktop_hooks, "_read_os_release", lambda: {"ID": "kali"})
    monkeypatch.setattr(desktop_hooks, "_package_installed", lambda package: installed_state.get(package, False))

    def fake_run(command, **kwargs):
        calls.append(command)
        assert "kali-rolling" not in source.read_text(encoding="utf-8")
        assert not any(item.startswith("Dir::Etc::sourcelist=") for item in command)
        assert "download" not in command
        if "install" in command:
            assert "--allow-downgrades" in command
            for package in desktop_hooks.ATK_RUNTIME_PACKAGES:
                assert f"{package}={desktop_hooks.ATK_VERSION}" in command
            for package in desktop_hooks.ATK_OPTIONAL_PACKAGES:
                assert (f"{package}={desktop_hooks.ATK_VERSION}" in command) == optional_installed
            if install_fails:
                return types.SimpleNamespace(returncode=100, stdout="", stderr="GTK dependency conflict")
            installed_state[desktop_hooks.GTK_RUNTIME_PACKAGE] = True
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(desktop_hooks.subprocess, "run", fake_run)
    installed = []
    errors = []

    desktop_hooks._ensure_runtime_dependencies(installed, errors)

    if install_fails:
        assert installed == []
        assert errors == ["GTK dependency conflict"]
    else:
        assert installed == [desktop_hooks.GTK_RUNTIME_PACKAGE]
        assert errors == []
    assert calls[0] == ["apt-get", "update"]


def test_cleanup_hook_reports_required_xpra_codec_conflict(monkeypatch):
    codec_error = (
        "E: Unable to satisfy dependencies. Reached two conflicting assignments:\n"
        "   1. xpra-codecs:arm64=6.4.3-r0-1 is selected for install\n"
        "   2. xpra-codecs:arm64 Depends libvpx9 (>= 1.12.0)\n"
        "      but none of the choices are installable: [no choices]"
    )

    monkeypatch.setattr(desktop_hooks.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        desktop_hooks.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"apt-get", "dpkg-query", "apt-cache"} else "",
    )
    monkeypatch.setattr(desktop_hooks, "RUNTIME_PACKAGES", ("xpra-server",))
    monkeypatch.setattr(desktop_hooks, "_package_installed", lambda package: False)

    def fake_run(command, **kwargs):
        if command[:2] == ["apt-cache", "policy"]:
            return types.SimpleNamespace(returncode=0, stdout="Candidate: 6.4.3-r0-1\n", stderr="")
        if command[:2] == ["apt-get", "install"]:
            return types.SimpleNamespace(returncode=100, stdout="", stderr=codec_error)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(desktop_hooks.subprocess, "run", fake_run)
    installed = []
    errors = []

    desktop_hooks._ensure_runtime_dependencies(installed, errors)

    assert installed == []
    assert errors == [codec_error]


def test_self_update_launch_invokes_office_cleanup(monkeypatch, tmp_path):
    manager = load_self_update_manager()
    calls = []

    class Logger:
        def log(self, message=""):
            return None

    class Process:
        pass

    monkeypatch.setattr(manager, "run_office_cleanup_hook", lambda repo_dir, logger: calls.append(repo_dir))
    monkeypatch.setattr(manager, "run_command", lambda *args, **kwargs: None)
    monkeypatch.setattr(manager.subprocess, "Popen", lambda *args, **kwargs: Process())

    repo = tmp_path / "repo"
    repo.mkdir()
    process = manager.launch_ui_process(repo, Logger())

    assert isinstance(process, Process)
    assert calls == [repo]


def load_self_update_manager():
    manager_path = PROJECT_ROOT / "docker" / "run" / "fs" / "exe" / "self_update_manager.py"
    spec = importlib.util.spec_from_file_location("test_self_update_manager_office", manager_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["probe.jsonl", "module.py", "settings.yaml", "page.html", "Dockerfile", ".env", "custom.unknown"])
def test_editor_arbitrary_text_file_lifecycle(office_state, name):
    path = office_state.workdir / name
    original = b'first line\r\nsecond line\r\n'
    path.write_bytes(original)
    manager = editor_markdown_sessions.get_manager()
    doc = document_store.register_document(path)
    session = manager.open(doc)
    assert session["text"].encode() == original
    manager.input(session["session_id"], text="local edit\n")
    path.write_text("external edit\n")
    assert manager.save(session["session_id"])["code"] == "external_change_conflict"
    copy = path.with_name("copy-" + name)
    result = manager.save_as(session["session_id"], str(copy), text="saved copy\n")
    assert path.read_text() == "external edit\n"
    assert copy.read_text() == "saved copy\n"
    assert result["document"]["extension"] == copy.suffix.lstrip(".")
    with pytest.raises(FileExistsError):
        manager.save_as(session["session_id"], str(copy))
    renamed = copy.with_name("renamed-" + name)
    updated = document_store.rename_document(result["document"]["file_id"], renamed, content="renamed\n")
    manager.renamed(updated["file_id"], updated, text="renamed\n")
    assert not copy.exists()
    assert renamed.read_text() == "renamed\n"
    assert manager.save(session["session_id"], text="final\n")["ok"]
    assert renamed.read_text() == "final\n"
    manager.close(session["session_id"])


@pytest.mark.parametrize("content, message", [(b'a\x00b', "Binary"), (b'\xff\xfe', "UTF-8"), (b'x' * (10 * 1024 * 1024 + 1), "10 MiB")], ids=["binary", "encoding", "size"])
def test_editor_rejects_binary_invalid_encoding_and_large_files(office_state, content, message):
    path = office_state.workdir / "unsafe.jsonl"
    path.write_bytes(content)
    with pytest.raises(ValueError, match=message):
        document_store.register_document(path)
    assert path.read_bytes() == content


def test_editor_named_create_and_save_as_match_file_browser_scope(office_state, tmp_path):
    path = tmp_path / "outside-workdir.py"
    handler = EditorSession(app=None, thread_lock=None)
    request = types.SimpleNamespace(headers={}, host_url="http://localhost/")
    payload = {"action": "create", "path": str(path), "source": "file-browser", "content": "print(1)\n"}
    opened = asyncio.run(handler.process(payload, request))
    assert opened["ok"]
    assert opened["text"] == "print(1)\n"
    assert not asyncio.run(handler.process(payload, request))["ok"]
    assert path.read_text() == "print(1)\n"
    target = tmp_path / "Dockerfile"
    result = asyncio.run(handler.process({"action": "save_as", "session_id": opened["session_id"], "path": str(target), "text": "FROM scratch\n"}, request))
    assert result["ok"]
    assert result["document"]["extension"] == ""
    assert target.read_text() == "FROM scratch\n"
    with pytest.raises(PermissionError):
        document_store.register_document(target)


@pytest.mark.parametrize("mode", [0o755, 0o600])
def test_editor_preserves_file_permissions_and_private_backups(office_state, mode):
    import stat

    path = office_state.workdir / "script.sh"
    path.write_text("echo original\n")
    path.chmod(mode)
    original = path.stat()
    office_state.backups.chmod(0o775)
    manager = editor_markdown_sessions.get_manager()
    session = manager.open(document_store.register_document(path))
    assert manager.save(session["session_id"], text="echo saved\n")["ok"]
    copy = path.with_name("copy.sh")
    result = manager.save_as(session["session_id"], str(copy))
    renamed = path.with_name("renamed.sh")
    document_store.rename_document(result["document"]["file_id"], renamed, content="echo renamed\n")
    for target in (path, renamed):
        saved = target.stat()
        assert stat.S_IMODE(saved.st_mode) == mode
        assert (saved.st_uid, saved.st_gid) == (original.st_uid, original.st_gid)
    assert stat.S_IMODE(office_state.backups.stat().st_mode) == 0o700
    assert list(office_state.backups.iterdir())
    assert all(stat.S_IMODE(backup.stat().st_mode) == 0o600 for backup in office_state.backups.iterdir())


def test_editor_atomic_metadata_failure_keeps_original(office_state, monkeypatch):
    path = office_state.workdir / "private.sh"
    path.write_text("original\n")
    path.chmod(0o600)
    doc = document_store.register_document(path)

    def fail_chmod(*_args):
        raise PermissionError("metadata update failed")

    monkeypatch.setattr(document_store.os, "fchmod", fail_chmod)
    with pytest.raises(PermissionError, match="metadata update failed"):
        document_store.write_text_document(doc["file_id"], "replacement\n")
    assert path.read_text() == "original\n"
    assert not list(path.parent.glob(".private.sh.*.tmp"))
