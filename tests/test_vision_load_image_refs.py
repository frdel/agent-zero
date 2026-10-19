import asyncio
import types
from types import SimpleNamespace
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers import images


class _TestResponse(SimpleNamespace):
    def __init__(self, message="", break_loop=False, additional=None, **kwargs):
        super().__init__(
            message=message,
            break_loop=break_loop,
            additional=additional,
            **kwargs,
        )


class _TestTool:
    def __init__(
        self,
        agent=None,
        name="",
        method=None,
        args=None,
        message="",
        loop_data=None,
        **kwargs,
    ):
        self.agent = agent
        self.name = name
        self.method = method
        self.args = args or {}
        self.message = message
        self.loop_data = loop_data

    async def after_execution(self, response, **kwargs):
        self.agent.hist_add_tool_result(
            self.name,
            response.message.strip(),
            id=self.log.id,
            **(response.additional or {}),
        )
        self.log.update(content=response.message.strip())


def _install_tool_stub(monkeypatch):
    tool_stub = types.ModuleType("helpers.tool")
    tool_stub.Response = _TestResponse
    tool_stub.Tool = _TestTool
    history_stub = types.ModuleType("helpers.history")

    class _RawMessage(dict):
        def __init__(self, raw_content, preview):
            super().__init__(raw_content=raw_content, preview=preview)

    history_stub.RawMessage = _RawMessage
    monkeypatch.setitem(sys.modules, "helpers.tool", tool_stub)
    monkeypatch.setitem(sys.modules, "helpers.history", history_stub)
    monkeypatch.delitem(sys.modules, "tools.vision_load", raising=False)


def test_prepare_content_keeps_missing_local_image_refs_strict():
    missing_path = "/tmp/a0-missing-desktop-screenshot.png"

    with pytest.raises(FileNotFoundError):
        images.prepare_content(
            [{"type": "image_url", "image_url": {"url": missing_path}}]
        )


def test_prepare_content_resolves_secret_masked_local_image_ref(monkeypatch, tmp_path):
    image_path = tmp_path / "private-image.png"
    image_path.write_bytes(b"png-data")

    class _SecretsManager:
        def replace_placeholders(self, value):
            return value.replace("§§secret(IMAGE_DIR)", str(tmp_path))

    monkeypatch.setattr(
        "helpers.secrets.get_secrets_manager",
        lambda: _SecretsManager(),
    )

    prepared = images.prepare_content(
        [{"type": "image_url", "image_url": {"url": "§§secret(IMAGE_DIR)/private-image.png"}}]
    )

    assert prepared[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_resolve_ref_keeps_unknown_secret_placeholder_masked(monkeypatch):
    class _SecretsManager:
        def replace_placeholders(self, value):
            raise RuntimeError("secret lookup failed")

    monkeypatch.setattr(
        "helpers.secrets.get_secrets_manager",
        lambda: _SecretsManager(),
    )

    masked_path = "/tmp/§§secret(UNKNOWN)/image.png"
    with pytest.raises(FileNotFoundError, match="§§secret\\(UNKNOWN\\)"):
        images.resolve_ref(masked_path)


@pytest.mark.anyio
async def test_vision_load_materializes_local_image_to_chat_artifact(monkeypatch, tmp_path):
    _install_tool_stub(monkeypatch)
    import tools.vision_load as vision_load_module

    def fake_get_abs_path(*parts):
        return str(tmp_path.joinpath(*parts))

    def fake_normalize_a0_path(path):
        return "/a0/" + str(Path(path).relative_to(tmp_path)).replace("\\", "/")

    monkeypatch.setattr(vision_load_module.chat_media.files, "get_abs_path", fake_get_abs_path)
    monkeypatch.setattr(vision_load_module.chat_media.files, "normalize_a0_path", fake_normalize_a0_path)
    monkeypatch.setattr(vision_load_module, "get_chat_model_config", lambda _agent: {"vision": True, "max_embeds": 10})
    monkeypatch.setattr(vision_load_module, "get_vision_model_config", lambda _agent: {})

    async def direct_call(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(
        vision_load_module.runtime,
        "call_development_function",
        direct_call,
    )

    image_path = tmp_path / "sample-image.png"
    image_path.write_bytes(b"png-data")

    tool_results = []
    messages = []
    updates = []
    agent = SimpleNamespace(
        context=SimpleNamespace(id="ctx-vision", get_data=lambda *_args, **_kwargs: None),
        agent_name="Agent 0",
        hist_add_tool_result=lambda *args, **kwargs: tool_results.append((args, kwargs)),
        hist_add_message=lambda *args, **kwargs: messages.append((args, kwargs)),
    )
    tool = vision_load_module.VisionLoad(
        agent=agent,
        name="vision_load",
        method=None,
        args={"paths": [str(image_path)]},
        message="",
        loop_data=None,
    )
    tool.log = SimpleNamespace(id="vision-log", update=lambda **kwargs: updates.append(kwargs))

    invalid = await tool.execute(paths=None)
    assert invalid.message == "vision_load error: `paths` must be a string or an array."

    response = await tool.execute(
        paths=str(image_path),
        query="Read the footer text.",
    )
    image_path.unlink()
    await tool.after_execution(response)

    raw_message = messages[0][1]["content"]
    assert [item["type"] for item in raw_message["raw_content"]] == ["image_url"]
    stored_ref = raw_message["raw_content"][0]["image_url"]["url"]
    assert stored_ref.startswith("/a0/usr/chats/ctx-vision/images/vision-load/sample-image-")
    stored_path = tmp_path / stored_ref.removeprefix("/a0/")
    assert stored_path.read_bytes() == b"png-data"
    assert updates[-1]["content"] == response.message


def test_active_vision_model_route_prefers_main_native_vision(monkeypatch):
    from plugins._model_config.helpers import model_config

    cases = [
        ({"vision": False}, {}, False),
        ({"vision": False}, {"provider": "p"}, False),
        ({"vision": False}, {"name": "v"}, False),
        ({"vision": True}, {"provider": "p", "name": "v"}, False),
        ({"vision": False}, {"provider": "p", "name": "v"}, True),
        (
            {"vision": True},
            {"provider": "p", "name": "v", "override_main": True},
            True,
        ),
    ]
    for chat, vision, expected in cases:
        monkeypatch.setattr(
            model_config,
            "get_effective_config",
            lambda _agent=None, chat=chat, vision=vision: {
                "chat_model": chat,
                "vision_model": vision,
            },
        )
        assert bool(model_config.get_vision_model_config()) is expected


def test_vision_summary_only_shows_skipped_section_when_needed(monkeypatch):
    _install_tool_stub(monkeypatch)
    import tools.vision_load as vision_load_module

    tool = vision_load_module.VisionLoad(agent=None)
    tool.vision_config = {"max_embeds": 10}
    tool.loaded_paths = ["loaded.png"]
    tool.skipped_paths = []

    assert tool._summary() == "Loaded images (1):\nloaded.png"

    tool.skipped_paths = ["skipped.png"]
    assert tool._summary() == (
        "Loaded images (1):\nloaded.png\n\n"
        "Skipped images (1, max 10):\nskipped.png"
    )


@pytest.mark.anyio
async def test_vision_model_sends_multiple_images_once_and_keeps_history_text_only(
    monkeypatch,
    tmp_path,
):
    _install_tool_stub(monkeypatch)
    import tools.vision_load as vision_load_module

    async def direct_call(func, *args, **kwargs):
        return func(*args, **kwargs)

    calls = []

    class FakeVisionModel:
        async def unified_call(self, **kwargs):
            calls.append(kwargs)
            return "The second screenshot fixes the red login error.", ""

    monkeypatch.setattr(vision_load_module.runtime, "call_development_function", direct_call)
    monkeypatch.setattr(vision_load_module, "build_vision_model", lambda _agent: FakeVisionModel())
    monkeypatch.setattr(
        vision_load_module,
        "get_chat_model_config",
        lambda _agent: {"vision": True, "max_embeds": 1},
    )
    monkeypatch.setattr(
        vision_load_module,
        "get_vision_model_config",
        lambda _agent: {"provider": "test", "name": "vision", "max_embeds": 5},
    )

    image_paths = [tmp_path / "before.png", tmp_path / "after.png"]
    for path in image_paths:
        path.write_bytes(b"png-data")

    tool_results = []
    raw_messages = []
    agent = SimpleNamespace(
        context=SimpleNamespace(id=""),
        agent_name="Agent 0",
        last_user_message=SimpleNamespace(
            output_text=lambda: "Review these UI screenshots."
        ),
        read_prompt=lambda _name, request, query: (
            f"Current request: {request}\n\nVisual query: {query}"
        ),
        hist_add_tool_result=lambda *args, **kwargs: tool_results.append((args, kwargs)),
        hist_add_message=lambda *args, **kwargs: raw_messages.append((args, kwargs)),
    )
    tool = vision_load_module.VisionLoad(
        agent=agent,
        name="vision_load",
        method=None,
        args={"paths": [str(path) for path in image_paths]},
        message="",
        loop_data=None,
    )
    tool.log = SimpleNamespace(id="vision-log", update=lambda **kwargs: None)

    response = await tool.execute(
        paths=[str(path) for path in image_paths],
        query="Compare the login error banners.",
    )
    response.additional = {"_responses_output_item": {"output": response.message}}
    await tool.after_execution(response)

    assert len(calls) == 1
    content = calls[0]["messages"][0].content
    assert content[0] == {
        "type": "text",
        "text": (
            "Current request: Review these UI screenshots.\n\n"
            "Visual query: Compare the login error banners."
        ),
    }
    assert [item["type"] for item in content].count("image_url") == 2
    assert "max_tokens" not in calls[0]
    assert "explicit_caching" not in calls[0]
    assert "fixes the red login error" in response.message
    assert response.message != "dummy"
    assert raw_messages == []
    assert tool.loaded_paths == [str(path) for path in image_paths]
    assert tool_results[0][1]["_responses_output_item"]["output"] == response.message


@pytest.mark.anyio
async def test_vision_model_empty_response_is_reported_as_error(monkeypatch):
    _install_tool_stub(monkeypatch)
    import tools.vision_load as vision_load_module

    class FakeVisionModel:
        async def unified_call(self, **kwargs):
            return "", ""

    monkeypatch.setattr(
        vision_load_module,
        "build_vision_model",
        lambda _agent: FakeVisionModel(),
    )
    monkeypatch.setattr(
        vision_load_module,
        "get_vision_model_config",
        lambda _agent: {"provider": "test", "name": "vision", "max_embeds": 10},
    )

    agent = SimpleNamespace(
        context=SimpleNamespace(id="", get_data=lambda _key: ""),
        last_user_message=SimpleNamespace(output_text=lambda: "Inspect the image."),
        read_prompt=lambda _name, request, query: f"{request}\n{query}",
    )
    tool = vision_load_module.VisionLoad(
        agent=agent,
        name="vision_load",
        method=None,
        args={"paths": ["data:image/png;base64,AA=="]},
        message="",
        loop_data=None,
    )

    response = await tool.execute(paths=["data:image/png;base64,AA=="])

    assert response.message == (
        "Image analysis error: Vision Model returned an empty response."
    )


@pytest.mark.anyio
async def test_parallel_worker_consumes_parent_ephemeral_image(monkeypatch, tmp_path):
    _install_tool_stub(monkeypatch)
    import tools.vision_load as vision_load_module

    def fake_get_abs_path(*parts):
        return str(tmp_path.joinpath(*parts))

    def fake_normalize_a0_path(path):
        return "/a0/" + str(Path(path).relative_to(tmp_path)).replace("\\", "/")

    monkeypatch.setattr(vision_load_module.chat_media.files, "get_abs_path", fake_get_abs_path)
    monkeypatch.setattr(vision_load_module.chat_media.files, "normalize_a0_path", fake_normalize_a0_path)
    parent_id = "parent-vision"
    monkeypatch.setattr(
        vision_load_module,
        "get_chat_model_config",
        lambda _agent: {"vision": True, "max_embeds": 10},
    )
    monkeypatch.setattr(vision_load_module, "get_vision_model_config", lambda _agent: {})
    queued = []
    monkeypatch.setattr(
        vision_load_module.parallel_tools,
        "queue_parallel_parent_history",
        lambda _agent, **message: queued.append(message) or True,
    )

    ref = vision_load_module.ephemeral_images.put_image_bytes(
        context_id=parent_id,
        mime="image/png",
        payload=b"png-data",
        name="shot.png",
    )
    context = SimpleNamespace(
        id="parallel-worker",
        get_data=lambda key: parent_id
        if key == vision_load_module.parallel_tools.PARALLEL_WORKER_PARENT_CONTEXT_KEY
        else None,
    )
    tool_results = []
    local_messages = []
    agent = SimpleNamespace(
        context=context,
        agent_name="Agent 0",
        hist_add_tool_result=lambda *args, **kwargs: tool_results.append((args, kwargs)),
        hist_add_message=lambda *args, **kwargs: local_messages.append((args, kwargs)),
    )
    tool = vision_load_module.VisionLoad(
        agent=agent,
        name="vision_load",
        method=None,
        args={"paths": [ref]},
        message="",
        loop_data=None,
    )
    tool.log = SimpleNamespace(id="vision-log", update=lambda **kwargs: None)

    response = await tool.execute(paths=[ref])
    await tool.after_execution(response)

    assert tool._context_id() == parent_id
    assert tool.loaded_paths == ["shot.png"]
    assert vision_load_module.ephemeral_images.get_image(ref, context_id=parent_id) is None
    stored_ref = tool.images_dict["shot.png"]
    assert stored_ref.startswith("/a0/usr/chats/parent-vision/images/vision-load/shot-")
    assert local_messages == []
    assert queued[0]["tokens"] == vision_load_module.TOKENS_ESTIMATE
    raw_content = queued[0]["content"]["raw_content"]
    assert raw_content == [
        {"type": "image_url", "image_url": {"url": stored_ref}}
    ]


@pytest.mark.anyio
async def test_independent_vision_model_calls_can_run_concurrently(monkeypatch, tmp_path):
    _install_tool_stub(monkeypatch)
    import tools.vision_load as vision_load_module

    active = 0
    max_active = 0
    call_count = 0

    class FakeVisionModel:
        async def unified_call(self, **kwargs):
            nonlocal active, max_active, call_count
            active += 1
            call_count += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1
            return "done", ""

    async def direct_call(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(vision_load_module.runtime, "call_development_function", direct_call)
    monkeypatch.setattr(vision_load_module, "build_vision_model", lambda _agent: FakeVisionModel())
    monkeypatch.setattr(vision_load_module, "get_chat_model_config", lambda _agent: {"vision": False})
    monkeypatch.setattr(
        vision_load_module,
        "get_vision_model_config",
        lambda _agent: {"provider": "test", "name": "vision", "max_embeds": 10},
    )

    image_paths = [tmp_path / "one.png", tmp_path / "two.png"]
    for path in image_paths:
        path.write_bytes(b"png-data")

    def make_tool(index):
        agent = SimpleNamespace(
            context=SimpleNamespace(id=""),
            agent_name=f"Agent {index}",
            last_user_message=SimpleNamespace(
                output_text=lambda: f"inspection {index}"
            ),
            read_prompt=lambda _name, request, query: f"{request}\n{query}",
        )
        return vision_load_module.VisionLoad(
            agent=agent,
            name="vision_load",
            method=None,
            args={"paths": [str(path) for path in image_paths]},
            message="",
            loop_data=None,
        )

    responses = await asyncio.gather(
        *(
            make_tool(index).execute(paths=[str(path) for path in image_paths])
            for index in range(4)
        )
    )

    assert call_count == 4
    assert max_active == 4
    assert all("done" in response.message for response in responses)
