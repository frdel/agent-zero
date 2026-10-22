from types import SimpleNamespace

from plugins._browser.tools.browser import Browser


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())


def _make(args: dict) -> Browser:
    return Browser(
        agent=_FakeAgent(), name="browser", method="execute", args=args, message="", loop_data=None
    )


def test_log_object_names_action_without_agent_prefix():
    entry = _make({"action": "list"}).get_log_object()

    assert entry["heading"] == "icon://captive_portal Browser: Listing tabs"
    assert entry["kvps"] == {"action": "list"}


def test_get_headings_name_action_and_target():
    assert _make({"action": "open", "url": "https://example.com"}).get_heading() == "icon://captive_portal Browser: Opening https://example.com"
    assert _make({"action": "type_submit", "ref": 5, "text": "hi"}).get_heading() == "icon://captive_portal Browser: Typing"
    assert _make({"action": "screenshot"}).get_heading() == "icon://captive_portal Browser: Taking screenshot"
    assert _make({"action": "setactive"}).get_heading() == "icon://captive_portal Browser: Selecting tab"
    assert _make({}).get_heading() == "icon://captive_portal Browser"
