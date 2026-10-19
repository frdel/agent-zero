from types import SimpleNamespace

from plugins._office.tools.office_artifact import OfficeArtifact


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())


def _make(args: dict) -> OfficeArtifact:
    return OfficeArtifact(
        agent=_FakeAgent(), name="office_artifact", method="execute", args=args, message="", loop_data=None
    )


def test_log_object_drops_agent_prefix_and_internal_kvp():
    entry = _make({"action": "status", "_tool_name": "office_artifact"}).get_log_object()

    assert entry["heading"] == "icon://description Office: Checking status"
    assert entry["kvps"] == {"action": "status"}


def test_get_headings_name_action_and_document():
    assert _make({"action": "read", "path": "/tmp/report.odt"}).get_heading() == "icon://description Office: Reading report.odt"
    assert _make({"action": "create", "title": "Notes"}).get_heading() == "icon://description Office: Creating Notes"
    assert _make({}).get_heading() == "icon://description Office"
