from types import SimpleNamespace

from plugins._a0_connector.tools.computer_use_remote import ComputerUseRemote


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())


def _make(args: dict) -> ComputerUseRemote:
    return ComputerUseRemote(
        agent=_FakeAgent(), name="computer_use_remote", method="execute", args=args, message="", loop_data=None
    )


def test_log_object_uses_dedicated_type_and_passthrough():
    entry = _make({"action": "capture"}).get_log_object()

    assert entry["type"] == "computer_use_remote"
    assert entry["heading"] == "icon://desktop_windows Computer use: Capturing screen"
    assert entry["kvps"] == {"action": "capture"}


def test_get_headings_follow_actions():
    assert _make({"action": "click"}).get_heading() == "icon://desktop_windows Computer use: Clicking"
    assert _make({"action": "get_window_state"}).get_heading() == "icon://desktop_windows Computer use: Reading window state"
    assert _make({}).get_heading() == "icon://desktop_windows Computer use"
