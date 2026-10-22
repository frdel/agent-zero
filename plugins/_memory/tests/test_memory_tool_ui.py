from types import SimpleNamespace

from plugins._memory.tools.memory import MemoryTool


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())


def _tool(args: dict) -> MemoryTool:
    return MemoryTool(
        agent=_FakeAgent(), name="memory", method="execute", args=args, message="", loop_data=None
    )


def test_memory_save_logs_dedicated_type():
    entry = _tool({"action": "save", "text": "Remember the demo", "area": "main"}).get_log_object()
    assert entry["type"] == "memory"
    assert entry["heading"] == "icon://bookmark_add Saving memory: Remember the demo"
    assert entry["kvps"] == {"action": "save", "text": "Remember the demo", "area": "main"}


def test_memory_load_headline_uses_query():
    entry = _tool({"action": "load", "query": "demo facts"}).get_log_object()

    assert entry["heading"] == "icon://saved_search Searching memories: demo facts"


def test_memory_delete_headline_uses_ids():
    entry = _tool({"action": "delete", "ids": "123"}).get_log_object()

    assert entry["heading"] == "icon://delete Deleting memories: 123"


def test_memory_forget_headline_uses_query():
    entry = _tool({"action": "forget", "query": "stale"}).get_log_object()

    assert entry["heading"] == "icon://auto_delete Forgetting memories: stale"


def test_headlines_fall_back_without_args():
    assert _tool({"action": "save"}).get_heading() == "icon://bookmark_add Saving memory"
    assert _tool({"action": "load"}).get_heading() == "icon://saved_search Searching memories"
    assert _tool({"action": "missing"}).get_heading() == "icon://psychology Using memory"
