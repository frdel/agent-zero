import base64
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import models
from agent import Agent, LoopData
from helpers import extension, extract_tools, litellm_transport
from helpers.log import Log
from plugins._context_window.helpers import output_speed, usage


def _timing(first=100.0, last=110.0, deltas=50, reasoning_chars=0, paused=False, answer=None):
    answer_first, answer_last, answer_deltas = answer or (first, last, deltas)
    return {
        "first": first,
        "last": last,
        "deltas": deltas,
        "answer_first": answer_first,
        "answer_last": answer_last,
        "answer_deltas": answer_deltas,
        "reasoning_chars": reasoning_chars,
        "paused": paused,
    }


def test_speed_counts_tokens_after_the_first_per_streamed_second():
    speed = output_speed.measure_output_speed({"completion_tokens": 501}, _timing())

    assert speed == {"tokens_per_second": 50.0, "output_tokens": 501, "seconds": 10.0}


@pytest.mark.parametrize(
    ("provider_usage", "timing"),
    [
        ({"completion_tokens": 501}, None),
        ({"completion_tokens": 501}, _timing(paused=True)),
        ({"completion_tokens": 501}, _timing(deltas=1)),
        ({"completion_tokens": 501}, _timing(last=100.9)),
        ({"completion_tokens": 501}, _timing(first=None)),
        ({}, _timing()),
        (None, _timing()),
        ({"completion_tokens": 1}, _timing()),
        (
            {"completion_tokens": 900, "completion_tokens_details": {"reasoning_tokens": 899}},
            _timing(reasoning_chars=0),
        ),
        (
            {"output_tokens": 900, "output_tokens_details": {"reasoning_tokens": 800}},
            _timing(reasoning_chars=0, answer=(100.0, 100.5, 20)),
        ),
    ],
    ids=[
        "no timing",
        "paused",
        "one delta",
        "short window",
        "no first delta",
        "no output tokens",
        "no usage",
        "one output token",
        "hidden reasoning, one answer token",
        "hidden reasoning, short answer window",
    ],
)
def test_speed_is_omitted_instead_of_guessed(provider_usage, timing):
    assert output_speed.measure_output_speed(provider_usage, timing) is None


@pytest.mark.parametrize(
    ("provider_usage", "reasoning_chars"),
    [
        ({"completion_tokens": 901, "completion_tokens_details": {"reasoning_tokens": 400}}, 0),
        ({"output_tokens": 901, "output_tokens_details": {"reasoning_tokens": 400}}, 150),
    ],
    ids=["hidden reasoning", "summarized reasoning"],
)
def test_unstreamed_reasoning_counts_only_the_answer(provider_usage, reasoning_chars):
    # Reasoning ran before the answer, outside the stream: 501 answer tokens in 10 s.
    timing = _timing(first=90.0, last=110.0, deltas=80, reasoning_chars=reasoning_chars, answer=(100.0, 110.0, 50))

    speed = output_speed.measure_output_speed(provider_usage, timing)

    assert speed == {"tokens_per_second": 50.0, "output_tokens": 501, "seconds": 10.0}


def test_streamed_reasoning_stays_inside_the_window():
    speed = output_speed.measure_output_speed(
        {"completion_tokens": 901, "completion_tokens_details": {"reasoning_tokens": 800}},
        _timing(reasoning_chars=3000),
    )

    assert speed and speed["tokens_per_second"] == 90.0


@pytest.mark.asyncio
async def test_timing_wrappers_stamp_deltas_and_pass_results_through(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(output_speed, "clock", lambda: now[0])
    seen = []

    async def response_callback(chunk, full):
        seen.append(("response", chunk, full))
        return "accepted tool request"

    async def reasoning_callback(chunk, full):
        seen.append(("reasoning", chunk, full))

    data = {
        "args": (),
        "kwargs": {
            "messages": [],
            "response_callback": response_callback,
            "reasoning_callback": reasoning_callback,
        },
    }
    output_speed.start_output_timing(SimpleNamespace(context=None), data)
    kwargs = data["kwargs"]

    now[0] = 5.0
    assert await kwargs["reasoning_callback"]("think", "think") is None
    now[0] = 6.5
    assert await kwargs["response_callback"]("{", "{") == "accepted tool request"

    timing = data[output_speed.OUTPUT_TIMING_KEY]
    assert seen == [("reasoning", "think", "think"), ("response", "{", "{")]
    assert timing == {
        "first": 5.0,
        "last": 6.5,
        "deltas": 2,
        "answer_first": 6.5,
        "answer_last": 6.5,
        "answer_deltas": 1,
        "reasoning_chars": 5,
        "paused": False,
    }


class _Context:
    def __init__(self):
        self.paused = False

    def get_data(self, _key):
        return None


def _framework_agent():
    agent = object.__new__(Agent)
    agent.loop_data = LoopData()
    agent.context = _Context()
    agent.config = SimpleNamespace(profile="default")
    agent.data = {}
    return agent


@pytest.mark.asyncio
async def test_a_pause_inside_a_callback_is_flagged_where_the_agent_waits(monkeypatch):
    monkeypatch.setattr(output_speed, "clock", lambda: 1.0)
    agent = _framework_agent()

    async def agent_callback(chunk, full):
        # The pause lands after the callback started, before its later
        # handle_intervention wait, as when extensions run for the delta.
        agent.context.paused = True
        await extension.call_extensions_async(
            "_functions/agent/Agent/handle_intervention/start",
            agent,
            data={"args": (agent,), "kwargs": {}},
        )
        agent.context.paused = False

    data = {"args": (agent,), "kwargs": {"response_callback": agent_callback}}
    await extension.call_extensions_async(
        "_functions/agent/Agent/call_chat_model_turn/start", agent, data=data
    )
    await data["kwargs"]["response_callback"]("a", "a")
    await data["kwargs"]["response_callback"]("b", "ab")

    assert data[output_speed.OUTPUT_TIMING_KEY]["paused"] is True
    assert agent.loop_data.params_temporary[output_speed.OUTPUT_TIMING_KEY]["paused"] is True


@pytest.mark.asyncio
async def test_hooks_run_through_the_extension_dispatcher():
    agent = _framework_agent()

    async def agent_callback(chunk, full):
        return None

    data = {"args": (agent,), "kwargs": {"response_callback": agent_callback}}
    await extension.call_extensions_async(
        "_functions/agent/Agent/call_chat_model_turn/start", agent, data=data
    )
    assert data["kwargs"]["response_callback"] is not agent_callback
    assert output_speed.OUTPUT_TIMING_KEY in agent.loop_data.params_temporary

    data.update(
        result=SimpleNamespace(usage={"completion_tokens": 3}),
        exception=None,
    )
    await extension.call_extensions_async(
        "_functions/agent/Agent/call_chat_model_turn/end", agent, data=data
    )
    assert output_speed.OUTPUT_TIMING_KEY not in data
    assert output_speed.OUTPUT_TIMING_KEY not in agent.loop_data.params_temporary

    item = Log().log(type="agent", heading="A0: Generating")
    speed = {"tokens_per_second": 50.0, "output_tokens": 501, "seconds": 10.0}
    agent.loop_data.params_temporary.update(
        {"log_item_generating": item, output_speed.OUTPUT_SPEED_KEY: speed}
    )
    # Same keyword arguments as agent.py passes to message_loop_result.
    log_speed = next(
        cls
        for cls in extension._get_extension_classes("message_loop_result")  # type: ignore[attr-defined]
        if cls.__name__ == "LogOutputSpeed"
    )
    log_speed(agent=agent).execute(loop_data=agent.loop_data, result_data={"llm_result": None})
    assert item.kvps["output_speed"] == speed


def test_missing_callbacks_stay_missing():
    data = {"args": (), "kwargs": {"messages": [], "reasoning_callback": None}}

    output_speed.start_output_timing(SimpleNamespace(context=None), data)

    assert data["kwargs"] == {"messages": [], "reasoning_callback": None}
    assert data[output_speed.OUTPUT_TIMING_KEY]["deltas"] == 0


@pytest.mark.asyncio
async def test_drained_tail_is_timed_and_the_accepted_response_is_kept(monkeypatch):
    response = '{"tool_name":"response","tool_args":{"text":"done"}}'
    now = [0.0]
    chunks = [
        (100.0, {"choices": [{"delta": {"content": response}, "message": {}}]}),
        (101.5, {"choices": [{"delta": {"content": " tail"}, "message": {}}]}),
        (103.0, {"choices": [], "usage": {"prompt_tokens": 900, "completion_tokens": 80}}),
    ]

    async def stream():
        for at, chunk in chunks:
            now[0] = at
            yield chunk

    async def fake_acompletion(*args, **kwargs):
        return stream()

    async def fake_rate_limiter(*args, **kwargs):
        return None

    async def response_callback(chunk, full):
        return full if extract_tools.extract_tool_request(full) else None

    monkeypatch.setattr(output_speed, "clock", lambda: now[0])
    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)
    wrapper = models.LiteLLMChatWrapper(
        model="test-model",
        provider="openrouter",
        model_config=None,
        api_base="https://openrouter.ai/api/v1",
    )
    data = {"args": (), "kwargs": {"response_callback": response_callback}}
    output_speed.start_output_timing(SimpleNamespace(context=None), data)

    result = await wrapper.unified_turn(
        messages=[HumanMessage(content="question")],
        response_callback=data["kwargs"]["response_callback"],
    )

    timing = data[output_speed.OUTPUT_TIMING_KEY]
    assert result.response == response
    assert (timing["first"], timing["last"], timing["deltas"]) == (100.0, 101.5, 2)
    assert output_speed.measure_output_speed(result.usage, timing)["tokens_per_second"] == 52.7


def _agent():
    return SimpleNamespace(data={}, loop_data=LoopData(), set_data=None)


def _recording_agent():
    agent = _agent()
    agent.set_data = lambda key, value: agent.data.__setitem__(key, value)
    return agent


def test_recorded_usage_carries_speed_and_never_keeps_a_stale_one():
    classes = extension._get_extension_classes(  # type: ignore[attr-defined]
        "_functions/agent/Agent/call_chat_model_turn/end"
    )
    record = next(cls for cls in classes if cls.__name__ == "RecordProviderUsage")
    agent = _recording_agent()
    params = agent.loop_data.params_temporary

    data = {
        "result": SimpleNamespace(usage={"prompt_tokens": 900, "completion_tokens": 501}),
        "exception": None,
        output_speed.OUTPUT_TIMING_KEY: _timing(),
    }
    record(agent=agent).execute(data=data)

    assert output_speed.OUTPUT_TIMING_KEY not in data
    assert agent.data[usage.PROVIDER_USAGE_KEY] == {
        "input_tokens": 900,
        "output_tokens": 501,
        "output_tokens_per_second": 50.0,
    }
    assert params[output_speed.OUTPUT_SPEED_KEY]["tokens_per_second"] == 50.0
    assert usage.latest_provider_usage(agent)["output_tokens_per_second"] == 50.0

    data = {
        "result": SimpleNamespace(usage={"prompt_tokens": 900, "completion_tokens": 3}),
        "exception": None,
        output_speed.OUTPUT_TIMING_KEY: _timing(last=100.2),
    }
    record(agent=agent).execute(data=data)

    assert "output_tokens_per_second" not in agent.data[usage.PROVIDER_USAGE_KEY]
    assert output_speed.OUTPUT_SPEED_KEY not in params
    assert "output_tokens_per_second" not in usage.latest_provider_usage(agent)

    data = {"result": None, "exception": RuntimeError("stream failed"), output_speed.OUTPUT_TIMING_KEY: _timing()}
    record(agent=agent).execute(data=data)
    assert output_speed.OUTPUT_TIMING_KEY not in data


@pytest.mark.parametrize("stored", [-5, "fast", float("nan"), None])
def test_stored_speed_must_be_a_positive_number(stored):
    agent = _agent()
    agent.data[usage.PROVIDER_USAGE_KEY] = {"output_tokens": 10, "output_tokens_per_second": stored}

    assert "output_tokens_per_second" not in usage.latest_provider_usage(agent)


def test_speed_joins_the_generation_log_after_core_rewrites():
    log = Log()
    item = log.log(type="agent", heading="A0: Generating", kvps={"step": "Thinking"})
    loop_data = LoopData()
    loop_data.params_temporary["log_item_generating"] = item
    speed = {"tokens_per_second": 50.0, "output_tokens": 501, "seconds": 10.0}
    loop_data.params_temporary[output_speed.OUTPUT_SPEED_KEY] = speed

    # The core stream extension replaces kvps on every tick before this point.
    item.update(kvps={"thoughts": ["done"], "tool_name": "response"})
    output_speed.log_output_speed(loop_data)

    assert item.kvps["thoughts"] == ["done"]
    assert item.kvps["tool_name"] == "response"
    assert item.kvps["output_speed"] == speed
    assert item.output()["kvps"]["output_speed"] == speed
    assert output_speed.OUTPUT_SPEED_KEY not in loop_data.params_temporary


def test_speed_extensions_are_registered_after_log_rewrites():
    start = extension._get_extension_classes(  # type: ignore[attr-defined]
        "_functions/agent/Agent/call_chat_model_turn/start"
    )
    assert any(cls.__name__ == "TimeOutputStream" for cls in start)
    pause = extension._get_extension_classes(  # type: ignore[attr-defined]
        "_functions/agent/Agent/handle_intervention/start"
    )
    assert any(cls.__name__ == "FlagOutputPause" for cls in pause)

    result_names = [
        cls.__name__
        for cls in extension._get_extension_classes("message_loop_result")  # type: ignore[attr-defined]
    ]
    assert result_names[-1] == "LogOutputSpeed"
    assert result_names.index("NativeThoughts") < result_names.index("LogOutputSpeed")


def test_webui_shows_speed_on_generation_steps_and_in_the_popover():
    plugin = ROOT / "plugins/_context_window"
    component = (
        plugin / "extensions/webui/model-context-strip-end/context-window.html"
    ).read_text(encoding="utf-8")
    store = (plugin / "webui/context-window-store.js").read_text(encoding="utf-8")
    page_head = (plugin / "extensions/webui/page-head/output-speed.html").read_text(
        encoding="utf-8"
    )
    css = (plugin / "webui/output-speed.css").read_text(encoding="utf-8")

    assert ">Output speed<" in component
    assert "usage.provider.speed" in component
    assert 'formatOutputSpeed(optionalNumber(value, "output_tokens_per_second"))' in store
    assert 'href="/plugins/_context_window/webui/output-speed.css"' in page_head
    assert ".process-step-header .step-output-speed" in css
    assert ".hide-output-speed .process-step-header .step-output-speed" in css
    assert 'x-effect="$store.contextWindow?.applyOutputSpeedVisibility()"' in component
    assert '"hide-output-speed",\n      !preferencesStore.isUiControlVisible("contextWindowUsage")' in store
    assert "var(--font-family-code)" in css


def _module_url(source):
    return "data:text/javascript;base64," + base64.b64encode(source.encode("utf-8")).decode(
        "ascii"
    )


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js is required")
def test_step_labels_are_formatted_updated_and_removed():
    plugin = ROOT / "plugins/_context_window"
    formatter = (plugin / "webui/output-speed.js").read_text(encoding="utf-8")
    hook = (plugin / "extensions/webui/set_messages_after_loop/output-speed.js").read_text(
        encoding="utf-8"
    )
    hook = hook.replace(
        'import { outputSpeedLabel } from "/plugins/_context_window/webui/output-speed.js";',
        f"import {{ outputSpeedLabel }} from {_module_url(formatter)!r};",
    )
    script = f"""
const {{ formatOutputSpeed }} = await import({_module_url(formatter)!r});
const {{ default: showOutputSpeed }} = await import({_module_url(hook)!r});
const expect = (actual, expected) => {{
  if (actual !== expected) throw new Error(`expected ${{JSON.stringify(expected)}}, got ${{JSON.stringify(actual)}}`);
}};

expect(formatOutputSpeed(48.24), "48.2 tok/s");
expect(formatOutputSpeed(153.4), "153 tok/s");
expect(formatOutputSpeed(0), "");
expect(formatOutputSpeed(null), "");
expect(formatOutputSpeed("fast"), "");

class Node {{
  constructor(className = "") {{ this.className = className; this.children = []; this.parent = null; this.textContent = ""; this.title = ""; }}
  querySelector(selector) {{
    const name = selector.replace(":scope > .", "");
    return this.children.find(child => child.className === name) || null;
  }}
  append(child) {{ this.children.push(child); child.parent = this; }}
  after(child) {{ const siblings = this.parent.children; siblings.splice(siblings.indexOf(this) + 1, 0, child); child.parent = this.parent; }}
  remove() {{ const siblings = this.parent.children; siblings.splice(siblings.indexOf(this), 1); this.parent = null; }}
}}
globalThis.document = {{ createElement: () => new Node() }};

const step = new Node("process-step");
const header = new Node("process-step-header");
step.append(header);
for (const name of ["step-expand-icon", "step-badge", "step-title", "step-extra"]) header.append(new Node(name));
const run = (kvps, type = "agent", target = step) => showOutputSpeed({{
  results: [{{ args: {{ type, kvps }}, result: {{ step: target }} }}],
}});
const labels = () => header.children.filter(child => child.className === "step-output-speed");

await run({{ step: "Thinking" }});
expect(labels().length, 0);
await run({{ output_speed: {{ tokens_per_second: 48.24, output_tokens: 511, seconds: 10.6 }} }});
await run({{ output_speed: {{ tokens_per_second: 48.24, output_tokens: 511, seconds: 10.6 }} }});
expect(labels().length, 1);
expect(header.children.indexOf(labels()[0]), 3);
expect(labels()[0].textContent, "48.2 tok/s");
expect(labels()[0].title, "511 output tokens in 10.6 s");
await run({{ output_speed: {{ tokens_per_second: 120, output_tokens: 1201, seconds: 10 }} }});
expect(labels()[0].textContent, "120 tok/s");
await run({{ output_speed: {{ tokens_per_second: 99 }} }}, "agent", null);
expect(labels()[0].textContent, "120 tok/s");
await run({{ output_speed: {{ tokens_per_second: 99 }} }}, "response");
expect(labels()[0].textContent, "99.0 tok/s");
expect(labels()[0].title, "99.0 tok/s");
await run({{ step: "Thinking" }});
expect(labels().length, 0);
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True)
