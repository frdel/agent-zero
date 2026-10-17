from types import SimpleNamespace

from plugins._goal.tools.goal import GoalTool


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())


def _make_tool(args: dict) -> GoalTool:
    return GoalTool(
        agent=_FakeAgent(), name="goal", method="execute", args=args, message="", loop_data=None
    )


def test_log_object_passes_action_through():
    tool = _make_tool({"action": "create", "objective": "Ship the release"})

    entry = tool.get_log_object()

    assert entry["type"] == "goal"
    assert entry["heading"] == "icon://flag Setting goal"
    assert entry["kvps"]["action"] == "create"
    assert entry["kvps"]["objective"] == "Ship the release"


def test_get_headings_follow_action_verbs_without_arg_text():
    assert _make_tool({}).get_heading() == "icon://flag Checking goal"
    assert _make_tool({"action": "show"}).get_heading() == "icon://flag Checking goal"
    assert _make_tool({"action": "update", "objective": "Ship it"}).get_heading() == "icon://flag Updating goal"
    assert _make_tool({"action": "complete", "objective": "Ship it"}).get_heading() == "icon://flag Completing goal"
    assert _make_tool({"action": "update", "status": "blocked"}).get_heading() == "icon://flag Blocking goal"
