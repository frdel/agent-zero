from types import SimpleNamespace

from tools.vision_load import VisionLoad


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())


def _make_tool(args: dict) -> VisionLoad:
    return VisionLoad(
        agent=_FakeAgent(), name="vision_load", method="execute", args=args, message="", loop_data=None
    )


def test_log_object_uses_dedicated_type_and_passthrough():
    tool = _make_tool({"paths": ["/tmp/report.png"], "query": "charts"})

    entry = tool.get_log_object()

    assert entry["type"] == "vision_load"
    assert entry["heading"] == "icon://imagesmode Loading images: report.png"
    assert entry["kvps"] == {"paths": ["/tmp/report.png"], "query": "charts"}


def test_get_headings_count_extra_images():
    assert _make_tool({}).get_heading() == "icon://imagesmode Loading images"
    assert _make_tool({"paths": ["/tmp/report.png"]}).get_heading() == "icon://imagesmode Loading images: report.png"
    assert _make_tool({"paths": ["/tmp/a.png", "/tmp/b.png", "/tmp/c.png"]}).get_heading() == "icon://imagesmode Loading images: a.png + 2 more"
