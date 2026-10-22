from __future__ import annotations

import asyncio
import ipaddress
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers import network as network_helper
from plugins._document_query import hooks as document_query_hooks
from plugins._document_query.helpers.fetch import FetchedDocument, fetch_public_resource
import plugins._document_query.helpers.document_query as document_query_module
from plugins._document_query.helpers.document_query import (
    DocumentQueryHelper,
    DocumentQueryStore,
)
from plugins._document_query.helpers.parsers.base import BaseParser
from plugins._document_query.helpers.parsers import get_parsers_for_mimetype
from plugins._document_query.helpers.parsers import liteparse as liteparse_module
from plugins._document_query.helpers.parsers.liteparse import LiteParseParser
from plugins._document_query.helpers.parsers.text import TextParser


def run_async(coro):
    with asyncio.Runner() as runner:
        return runner.run(coro)


class ParserNameShouldNotLeak(BaseParser):
    mimetypes = ["text/plain"]

    def _parse_sync(self, document: FetchedDocument, config: dict) -> str:
        return "parsed"


class CountingAsyncParser(BaseParser):
    mimetypes = ["text/plain"]
    active = 0
    max_active = 0

    async def _parse_async(self, document: FetchedDocument, config: dict) -> str:
        type(self).active += 1
        type(self).max_active = max(type(self).max_active, type(self).active)
        try:
            await asyncio.sleep(0.02)
            return document.uri
        finally:
            type(self).active -= 1

    def _parse_sync(self, document: FetchedDocument, config: dict) -> str:
        return document.uri


class _StoreContext:
    def __init__(self, context_id: str):
        self.id = context_id
        self.data = {}

    def get_data(self, key: str, recursive: bool = True):
        return self.data.get(key)

    def set_data(self, key: str, value, recursive: bool = True):
        self.data[key] = value


class _StoreAgent:
    def __init__(self, context_id: str):
        self.config = object()
        self.context = _StoreContext(context_id)


class _FakeVectorDB:
    def __init__(self):
        self.docs = []

    async def insert_documents(self, docs):
        ids = []
        for doc in docs:
            doc_id = f"doc-{len(self.docs)}"
            doc.metadata["id"] = doc_id
            ids.append(doc_id)
            self.docs.append(doc)
        return ids

    async def search_by_metadata(self, filter: str, limit: int = 0):
        document_uri = filter.split("'", 2)[1]
        docs = [
            doc
            for doc in self.docs
            if doc.metadata.get("document_uri") == document_uri
        ]
        return docs[:limit] if limit > 0 else docs

    async def delete_documents_by_ids(self, ids: list[str]):
        removed = [doc for doc in self.docs if doc.metadata.get("id") in ids]
        self.docs = [doc for doc in self.docs if doc.metadata.get("id") not in ids]
        return removed


def test_fetch_file_detects_mimetype_and_reads_once(tmp_path):
    document = tmp_path / "notes.txt"
    document.write_text("hello\nworld\n", encoding="utf-8")

    fetched = run_async(fetch_public_resource(str(document), {}))

    assert fetched.scheme == "file"
    assert fetched.mimetype == "text/plain"
    assert fetched.local_path == str(document)
    assert fetched.text() == "hello\nworld\n"


def test_fetch_http_blocks_non_public_destinations():
    with pytest.raises(ValueError, match="Blocked non-public address"):
        run_async(
            fetch_public_resource(
                "http://127.0.0.1/internal.txt",
                {"fetch_retries": 1},
            )
        )


def test_fetch_http_blocks_redirects_to_non_public_destinations(monkeypatch):
    source = "https://public.example/start"
    calls = []

    class RedirectResponse:
        status_code = 302
        headers = {"Location": "http://127.0.0.1/internal.txt"}
        encoding = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class FakeSession:
        trust_env = True

        def get(self, url, **kwargs):
            calls.append((url, kwargs, self.trust_env))
            return RedirectResponse()

    def resolve_host_ips(hostname):
        address = "127.0.0.1" if hostname == "127.0.0.1" else "93.184.216.34"
        return (ipaddress.ip_address(address),)

    monkeypatch.setattr(network_helper, "resolve_host_ips", resolve_host_ips)
    monkeypatch.setattr(network_helper.requests, "Session", FakeSession)

    with pytest.raises(ValueError, match="Blocked non-public address"):
        run_async(fetch_public_resource(source, {"fetch_retries": 1}))

    assert [url for url, _kwargs, _trust_env in calls] == [source]


def test_fetch_http_preserves_public_redirects_and_request_compatibility(monkeypatch):
    source = "https://public.example/start"
    destination = "https://public.example/report.txt"
    calls = []

    class FakeResponse:
        def __init__(self, status_code, headers, body=b""):
            self.status_code = status_code
            self.headers = headers
            self.encoding = "utf-8"
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def iter_content(self, chunk_size):
            assert chunk_size == 64 * 1024
            yield self.body

    class FakeSession:
        trust_env = True

        def get(self, url, **kwargs):
            calls.append((url, kwargs, self.trust_env))
            if url == source:
                return FakeResponse(302, {"Location": "/report.txt"})
            return FakeResponse(
                200,
                {
                    "Content-Length": "9",
                    "Content-Type": "text/plain; charset=utf-8",
                },
                b"public ok",
            )

    monkeypatch.setattr(
        network_helper,
        "resolve_host_ips",
        lambda _hostname: (ipaddress.ip_address("93.184.216.34"),),
    )
    monkeypatch.setattr(network_helper.requests, "Session", FakeSession)
    monkeypatch.setenv("USER_AGENT", "AgentZeroTest")

    fetched = run_async(
        fetch_public_resource(
            source,
            {
                "fetch_retries": 1,
                "fetch_timeout": 2,
                "max_remote_bytes": 1024,
            },
        )
    )

    assert fetched.uri == destination
    assert fetched.mimetype == "text/plain"
    assert fetched.text() == "public ok"
    assert [url for url, _kwargs, _trust_env in calls] == [source, destination]
    assert all(not trust_env for _url, _kwargs, trust_env in calls)
    assert all(
        kwargs["allow_redirects"] is False
        for _url, kwargs, _trust_env in calls
    )
    assert all(kwargs["timeout"] == (2.0, 2.0) for _url, kwargs, _trust_env in calls)
    assert all(
        kwargs["headers"] == {"User-Agent": "AgentZeroTest"}
        for _url, kwargs, _trust_env in calls
    )


def test_parser_registry_prefers_liteparse_for_pdf():
    parsers = get_parsers_for_mimetype("application/pdf", {"liteparse_enabled": True})

    assert [parser.__class__.__name__ for parser in parsers[:2]] == [
        "LiteParseParser",
        "PdfParser",
    ]


def test_parser_registry_can_disable_liteparse():
    parsers = get_parsers_for_mimetype("application/pdf", {"liteparse_enabled": False})

    assert parsers
    assert parsers[0].__class__.__name__ == "PdfParser"


def test_text_parser_uses_prefetched_content():
    fetched = FetchedDocument(
        uri="/tmp/example.json",
        source_uri="/tmp/example.json",
        scheme="file",
        mimetype="application/json",
        content=b'{"ok": true}',
        local_path=None,
    )

    text = run_async(TextParser().parse(fetched, {}, timeout=1))

    assert text == '{"ok": true}'


def test_compatibility_imports_point_to_plugin_classes():
    pytest.importorskip("langchain_core")

    from helpers.document_query import DocumentQueryHelper as CompatHelper
    from plugins._document_query.helpers.document_query import DocumentQueryHelper
    from plugins._document_query.tools.document_query import DocumentQueryTool
    from tools.document_query import DocumentQueryTool as CompatTool

    assert CompatHelper is DocumentQueryHelper
    assert CompatTool is DocumentQueryTool


def test_liteparse_is_installed_by_docker_and_plugin_hook_requirements():
    root_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    hooks_source = (
        ROOT / "plugins" / "_document_query" / "hooks.py"
    ).read_text(encoding="utf-8")

    assert "liteparse==2.0.3" in root_requirements
    assert "_ROOT_REQUIREMENTS_FILE" in hooks_source
    assert document_query_hooks._liteparse_requirement() == "liteparse==2.0.3"
    assert not (ROOT / "plugins" / "_document_query" / "requirements.txt").exists()


def test_default_config_bounds_liteparse_runtime_concurrency():
    default_config = (
        ROOT / "plugins" / "_document_query" / "default_config.yaml"
    ).read_text(encoding="utf-8")

    assert "parser_concurrency: 1" in default_config
    assert "context_intro_chunks: 2" in default_config
    assert "max_index_chunks: 1200" in default_config
    assert "liteparse_num_workers: 2" in default_config
    assert "liteparse_ocr_auto_disable_pages: 30" in default_config
    assert "liteparse_subprocess" not in default_config


def test_config_panel_exposes_document_query_settings():
    config_html = (
        ROOT / "plugins" / "_document_query" / "webui" / "config.html"
    ).read_text(encoding="utf-8")

    assert "Max parser concurrency" in config_html
    for setting in [
        "parser_concurrency",
        "per_document_timeout",
        "gather_timeout",
        "chunk_size",
        "chunk_overlap",
        "max_index_chunks",
        "search_threshold",
        "search_limit",
        "context_intro_chunks",
        "fetch_timeout",
        "fetch_retries",
        "fetch_retry_backoff",
        "max_remote_bytes",
        "liteparse_enabled",
        "liteparse_ocr_enabled",
        "liteparse_ocr_language",
        "liteparse_ocr_server_url",
        "liteparse_tessdata_path",
        "liteparse_max_pages",
        "liteparse_target_pages",
        "liteparse_dpi",
        "liteparse_preserve_very_small_text",
        "liteparse_output_format",
        "liteparse_num_workers",
        "pdf_ocr_fallback",
        "thread_offload",
    ]:
        assert f"config.{setting}" in config_html
    assert "liteparse_subprocess" not in config_html


def test_document_query_adapts_chunk_size_for_large_documents():
    store = object.__new__(DocumentQueryStore)
    store.config = {
        "chunk_size": 100,
        "chunk_overlap": 10,
        "max_index_chunks": 10,
    }

    chunks = store._split_text_for_index(("alpha beta gamma delta " * 400).strip())

    assert 1 < len(chunks) <= 10


def test_document_query_allows_uncapped_index_chunks():
    store = object.__new__(DocumentQueryStore)
    store.config = {
        "chunk_size": 100,
        "chunk_overlap": 10,
        "max_index_chunks": 0,
    }

    chunks = store._split_text_for_index(("alpha beta gamma delta " * 400).strip())

    assert len(chunks) > 10


def test_document_query_store_reuses_vector_db_per_context(monkeypatch):
    monkeypatch.setattr(
        document_query_module,
        "_load_config",
        lambda _agent: {
            "chunk_size": 100,
            "chunk_overlap": 10,
            "max_index_chunks": 20,
        },
    )
    monkeypatch.setattr(
        DocumentQueryStore,
        "init_vector_db",
        lambda _self: _FakeVectorDB(),
    )

    agent = _StoreAgent("ctx-one")
    store = DocumentQueryStore.get(agent)

    success, ids = run_async(
        store.add_document("alpha beta gamma " * 20, "/tmp/book.txt")
    )
    second_store = DocumentQueryStore.get(agent)

    assert success is True
    assert ids
    assert second_store is store
    assert second_store.vector_db is store.vector_db
    assert run_async(second_store.document_exists("/tmp/book.txt")) is True

    isolated_store = DocumentQueryStore.get(_StoreAgent("ctx-two"))
    assert isolated_store is not store
    assert run_async(isolated_store.document_exists("/tmp/book.txt")) is False


def test_document_query_thumbnail_matches_plugin_hub_limits():
    thumbnail = ROOT / "plugins" / "_document_query" / "webui" / "thumbnail.jpg"

    assert thumbnail.exists()
    assert thumbnail.stat().st_size <= 20 * 1024
    with Image.open(thumbnail) as image:
        assert image.format == "JPEG"
        assert image.size == (256, 256)


def test_liteparse_parser_caps_workers_by_default():
    parser = LiteParseParser()

    assert parser._liteparse_kwargs({})["num_workers"] == 2
    assert parser._liteparse_kwargs({"liteparse_num_workers": "3"})["num_workers"] == 3
    assert parser._liteparse_kwargs({"liteparse_num_workers": ""})["num_workers"] == 2


def test_liteparse_parser_always_uses_subprocess(monkeypatch):
    fetched = FetchedDocument(
        uri="/tmp/report.pdf",
        source_uri="/tmp/report.pdf",
        scheme="file",
        mimetype="application/pdf",
        content=b"",
        local_path="/tmp/report.pdf",
    )
    parser = LiteParseParser()

    monkeypatch.setattr(parser, "_parse_subprocess", lambda _document, _config: "ok")

    def fail_in_process(_document, _config):
        raise AssertionError("LiteParse must stay isolated from the Web UI process")

    monkeypatch.setattr(parser, "_parse_in_process", fail_in_process)

    assert parser._parse_sync(fetched, {"liteparse_subprocess": False}) == "ok"


def test_liteparse_auto_disables_ocr_for_large_text_pdf(monkeypatch):
    parser = LiteParseParser()
    fetched = FetchedDocument(
        uri="/tmp/report.pdf",
        source_uri="/tmp/report.pdf",
        scheme="file",
        mimetype="application/pdf",
        content=b"",
        local_path="/tmp/report.pdf",
    )
    monkeypatch.setattr(
        liteparse_module,
        "_pdf_text_profile",
        lambda _file_path, _config: liteparse_module._PdfTextProfile(
            page_count=277,
            sampled_pages=5,
            text_chars=2500,
        ),
    )

    kwargs = parser._liteparse_kwargs({}, fetched, "/tmp/report.pdf")

    assert kwargs["ocr_enabled"] is False


def test_liteparse_keeps_ocr_for_small_pdf(monkeypatch):
    parser = LiteParseParser()
    fetched = FetchedDocument(
        uri="/tmp/bill.pdf",
        source_uri="/tmp/bill.pdf",
        scheme="file",
        mimetype="application/pdf",
        content=b"",
        local_path="/tmp/bill.pdf",
    )
    monkeypatch.setattr(
        liteparse_module,
        "_pdf_text_profile",
        lambda _file_path, _config: liteparse_module._PdfTextProfile(
            page_count=10,
            sampled_pages=5,
            text_chars=2500,
        ),
    )

    kwargs = parser._liteparse_kwargs({}, fetched, "/tmp/bill.pdf")

    assert kwargs["ocr_enabled"] is True


def test_liteparse_disables_ocr_for_large_text_sparse_pdf(monkeypatch):
    parser = LiteParseParser()
    fetched = FetchedDocument(
        uri="/tmp/scan.pdf",
        source_uri="/tmp/scan.pdf",
        scheme="file",
        mimetype="application/pdf",
        content=b"",
        local_path="/tmp/scan.pdf",
    )
    monkeypatch.setattr(
        liteparse_module,
        "_pdf_text_profile",
        lambda _file_path, _config: liteparse_module._PdfTextProfile(
            page_count=277,
            sampled_pages=5,
            text_chars=20,
        ),
    )

    kwargs = parser._liteparse_kwargs({}, fetched, "/tmp/scan.pdf")

    assert kwargs["ocr_enabled"] is False


def test_liteparse_respects_explicit_ocr_disabled(monkeypatch):
    parser = LiteParseParser()
    fetched = FetchedDocument(
        uri="/tmp/bill.pdf",
        source_uri="/tmp/bill.pdf",
        scheme="file",
        mimetype="application/pdf",
        content=b"",
        local_path="/tmp/bill.pdf",
    )
    monkeypatch.setattr(
        liteparse_module,
        "_pdf_text_profile",
        lambda _file_path, _config: liteparse_module._PdfTextProfile(
            page_count=10,
            sampled_pages=5,
            text_chars=0,
        ),
    )

    kwargs = parser._liteparse_kwargs(
        {"liteparse_ocr_enabled": False},
        fetched,
        "/tmp/bill.pdf",
    )

    assert kwargs["ocr_enabled"] is False


def test_liteparse_target_pages_can_keep_ocr_enabled_for_large_pdf(monkeypatch):
    parser = LiteParseParser()
    fetched = FetchedDocument(
        uri="/tmp/report.pdf",
        source_uri="/tmp/report.pdf",
        scheme="file",
        mimetype="application/pdf",
        content=b"",
        local_path="/tmp/report.pdf",
    )
    monkeypatch.setattr(
        liteparse_module,
        "_pdf_text_profile",
        lambda _file_path, _config: liteparse_module._PdfTextProfile(
            page_count=277,
            sampled_pages=5,
            text_chars=2500,
        ),
    )

    small_range = parser._liteparse_kwargs(
        {"liteparse_target_pages": "1-10"},
        fetched,
        "/tmp/report.pdf",
    )
    large_range = parser._liteparse_kwargs(
        {"liteparse_target_pages": "1-40"},
        fetched,
        "/tmp/report.pdf",
    )

    assert small_range["ocr_enabled"] is True
    assert large_range["ocr_enabled"] is False


def test_query_optimize_prompt_filename_is_spelled_correctly():
    prompt_dir = ROOT / "plugins" / "_document_query" / "prompts"
    helper_source = (
        ROOT / "plugins" / "_document_query" / "helpers" / "document_query.py"
    ).read_text(encoding="utf-8")

    assert (prompt_dir / "fw.document_query.optimize_query.md").exists()
    assert "fw.document_query.optimize_query.md" in helper_source


def test_parser_progress_is_user_facing_and_generic():
    fetched = FetchedDocument(
        uri="/tmp/example.txt",
        source_uri="/tmp/example.txt",
        scheme="file",
        mimetype="text/plain",
        content=b"content",
        local_path=None,
    )
    progress = []
    helper = object.__new__(DocumentQueryHelper)
    helper.config = {}
    helper.progress_callback = progress.append

    content = run_async(
        helper._parse_document(
            document=fetched,
            parsers=[ParserNameShouldNotLeak()],
            timeout=1,
            thread_offload=False,
        )
    )

    assert content == "parsed"
    assert progress == ["Parsing document content"]


def test_parse_document_limits_parser_concurrency_across_helpers():
    CountingAsyncParser.active = 0
    CountingAsyncParser.max_active = 0
    fetched_a = FetchedDocument(
        uri="/tmp/a.txt",
        source_uri="/tmp/a.txt",
        scheme="file",
        mimetype="text/plain",
        content=b"a",
        local_path=None,
    )
    fetched_b = FetchedDocument(
        uri="/tmp/b.txt",
        source_uri="/tmp/b.txt",
        scheme="file",
        mimetype="text/plain",
        content=b"b",
        local_path=None,
    )
    helper_a = object.__new__(DocumentQueryHelper)
    helper_a.config = {"parser_concurrency": 1}
    helper_a.progress_callback = lambda _msg: None
    helper_b = object.__new__(DocumentQueryHelper)
    helper_b.config = {"parser_concurrency": 1}
    helper_b.progress_callback = lambda _msg: None

    async def parse_both():
        return await asyncio.gather(
            helper_a._parse_document(
                document=fetched_a,
                parsers=[CountingAsyncParser()],
                timeout=1,
                thread_offload=False,
            ),
            helper_b._parse_document(
                document=fetched_b,
                parsers=[CountingAsyncParser()],
                timeout=1,
                thread_offload=False,
            ),
        )

    assert sorted(run_async(parse_both())) == ["/tmp/a.txt", "/tmp/b.txt"]
    assert CountingAsyncParser.max_active == 1


def test_document_query_prompt_uses_progressive_skill_disclosure():
    from helpers.skills import find_skill

    prompt = (
        ROOT
        / "plugins"
        / "_document_query"
        / "prompts"
        / "agent.system.tool.document_query.md"
    ).read_text(encoding="utf-8")
    main_prompt = (ROOT / "prompts" / "agent.system.main.tips.md").read_text(
        encoding="utf-8"
    )
    skill = find_skill("document-query", include_content=True)

    assert skill is not None
    assert "document_query" not in main_prompt
    assert "vision_load" not in main_prompt
    assert "skills_tool:load" in prompt
    assert "document-query" in prompt
    assert "document_query" in prompt
    assert "local/remote documents" in prompt
    assert "Use vision tools first" in prompt
    assert "fallback OCR" in prompt
    description = skill.description.casefold()
    # Discovery metadata stays concise; the loaded skill owns detailed routing.
    for capability in ("read", "extract", "compare", "pdf", "office", "url", "text", "ocr", "vision"):
        assert capability in description
    assert any(condition in description for condition in ("fails", "unavailable", "insufficient"))
    assert "### Answer Questions Over A Document" in skill.content
    assert "Use vision tools first" in skill.content
    assert "### Fallback OCR After Vision Cannot Read A Document Image" in skill.content
