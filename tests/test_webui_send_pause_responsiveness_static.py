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
