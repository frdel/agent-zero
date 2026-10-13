from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return PROJECT_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_pause_snapshots_respect_in_flight_clicks() -> None:
    store = read("webui", "components", "chat", "input", "input-store.js")
    index_js = read("webui", "index.js")

    assert "_pendingPause" in store
    assert "applyPausedSnapshot(paused)" in store
    assert "if ((this._pendingPause || 0) > 0) return;" in store
    assert "inputStore.paused = snapshot.paused;" not in index_js
    assert "inputStore.applyPausedSnapshot(snapshot.paused);" in index_js


def test_send_message_guards_against_in_flight_duplicates() -> None:
    index_js = read("webui", "index.js")

    assert "if (sendMessage.inFlight) return false;" in index_js
    assert "sendMessage.inFlight = true;" in index_js
    fn = index_js[index_js.index("export async function sendMessage") : index_js.index("globalThis.sendMessage = sendMessage;")]
    assert fn.index("if (sendMessage.inFlight) return false;") < fn.index("callJsExtensions")
    assert "finally {" in fn
    assert "sendMessage.inFlight = false;" in fn.split("finally {", 1)[1].split("}", 1)[0]
