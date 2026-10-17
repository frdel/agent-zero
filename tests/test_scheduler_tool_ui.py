from types import SimpleNamespace

from plugins._scheduler.tools.scheduler import SchedulerTool


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())


def _make_tool(args: dict) -> SchedulerTool:
    return SchedulerTool(
        agent=_FakeAgent(), name="scheduler", method="execute", args=args, message="", loop_data=None
    )


def test_log_object_passes_action_through():
    tool = _make_tool({"action": "find-task", "name": "backup"})

    entry = tool.get_log_object()

    assert entry["type"] == "scheduler"
    assert entry["heading"] == "icon://calendar_month Schedule: Find Task"
    assert entry["kvps"]["action"] == "find-task"
    assert entry["kvps"]["name"] == "backup"


def test_get_heading_falls_back_without_action():
    tool = _make_tool({})

    assert tool.get_heading() == "icon://calendar_month Schedule"
