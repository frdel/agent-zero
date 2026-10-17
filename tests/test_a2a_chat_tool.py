from types import SimpleNamespace

from plugins._a2a_chat.tools.a2a_chat import A2AChatTool


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())


def _make_tool(args: dict) -> A2AChatTool:
    return A2AChatTool(
        agent=_FakeAgent(), name="a2a_chat", method="execute", args=args, message="chat", loop_data=None
    )


def test_log_object_titles_headline_with_agent_url():
    tool = _make_tool({"agent_url": "http://peer.example.com/a2a", "message": "hello"})

    entry = tool.get_log_object()

    assert entry["type"] == "a2a_chat"
    assert entry["heading"] == "icon://hub Chatting: http://peer.example.com/a2a"
    assert entry["kvps"]["agent_url"] == "http://peer.example.com/a2a"
    assert entry["kvps"]["message"] == "hello"


def test_get_heading_falls_back_without_host():
    tool = _make_tool({})

    assert tool.get_heading() == "icon://hub Chatting"
