from types import SimpleNamespace

from tools.skills_tool import SkillsTool


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())


def _make_tool(args: dict) -> SkillsTool:
    return SkillsTool(
        agent=_FakeAgent(), name="skills_tool", method="execute", args=args, message="", loop_data=None
    )


def test_log_object_uses_dedicated_type_and_passthrough():
    tool = _make_tool({"action": "load", "skill_name": "ponytail"})

    entry = tool.get_log_object()

    assert entry["type"] == "skills_tool"
    assert entry["heading"] == "icon://school Loading skill: ponytail"
    assert entry["kvps"] == {"action": "load", "skill_name": "ponytail"}


def test_get_headings_follow_actions():
    assert _make_tool({}).get_heading() == "icon://school Listing skills"
    assert _make_tool({"action": "search", "query": "browser"}).get_heading() == "icon://school Searching skills: browser"
    assert _make_tool({"action": "search"}).get_heading() == "icon://school Searching skills"
    assert _make_tool({"action": "read_file", "skill_name": "ponytail", "file_path": "SKILL.md"}).get_heading() == "icon://school Reading skill: ponytail/SKILL.md"
    assert _make_tool({"action": "read_file", "file_path": "docs/usage.md"}).get_heading() == "icon://school Reading skill: docs/usage.md"
    assert _make_tool({"action": "load"}).get_heading() == "icon://school Loading skill"
