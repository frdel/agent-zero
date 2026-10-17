from types import SimpleNamespace

from plugins._behavior_adjustment.tools.behavior_adjustment import UpdateBehavior


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())


def _make_tool(args: dict) -> UpdateBehavior:
    return UpdateBehavior(
        agent=_FakeAgent(), name="behavior_adjustment", method="execute", args=args, message="", loop_data=None
    )


def test_log_object_uses_behavior_type_and_static_heading():
    tool = _make_tool({"adjustments": "always answer in Russian"})

    entry = tool.get_log_object()

    assert entry["type"] == "behavior_adjustment"
    assert entry["heading"] == "icon://psychology Adjusting behavior"
    assert entry["kvps"]["adjustments"] == "always answer in Russian"
