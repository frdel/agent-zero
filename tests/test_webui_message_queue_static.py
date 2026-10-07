from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return (PROJECT_ROOT / Path(*parts)).read_text(encoding="utf-8")


def test_pending_queue_thumbnails_use_local_blob_urls():
    store_js = read("webui", "components", "chat", "message-queue", "message-queue-store.js")
    queue_html = read("webui", "components", "chat", "message-queue", "message-queue.html")

    assert "_pendingAttachmentUrls" in store_js
    assert "getAttachmentUrl(item, filename)" in store_js
    assert "attachmentUrls?.[filename]" in store_js
    assert "getAttachmentUrl(item, att)" in queue_html


def test_failed_queue_adds_drop_pending_entries():
    store_js = read("webui", "components", "chat", "message-queue", "message-queue-store.js")

    assert store_js.count("_dropPendingItem(tempId)") >= 3

