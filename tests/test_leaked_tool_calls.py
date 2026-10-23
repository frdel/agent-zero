import json

import pytest

from helpers.extract_tools import extract_leaked_tool_request, extract_tool_request


@pytest.mark.parametrize(
    "text",
    [
        '<tool_call>{"name":"x","arguments":{"a":1}}</tool_call>',
        '<tool_call>[{"name":"x","parameters":{"a":1}}]</tool_call>',
        '<tool_call>{"tool_name":"x","tool_args":{"a":1}}</tool_call>',
        "<function=x><parameter=a>1</parameter></function>",
        "<tool_call><function=x><parameter=a>1</parameter></function></tool_call>",
        '{"name":"x","arguments":{"a":1}}',
        '{"name":"x","arguments":"{\\"a\\":1}"}',
    ],
)
def test_recovers_one_complete_call(text):
    assert extract_tool_request(text) is None
    status, request = extract_leaked_tool_request(text)
    assert status == "call"
    assert request == {"tool_name": "x", "tool_args": {"a": 1}}


def test_keeps_provider_names_for_authorization_at_the_result_hook():
    status, request = extract_leaked_tool_request(
        '{"name":"native_x:read","arguments":{"path":"notes"}}'
    )
    assert status == "call"
    assert request == {"tool_name": "native_x:read", "tool_args": {"path": "notes"}}


@pytest.mark.parametrize(
    "text",
    [
        "<tool_call",
        "<tool_call>",
        "<function=x",
        "<function=x><parameter=path>/tmp/half",
        '<tool_call>{"name":"x","arguments":{}}',
        '<tool_call>{"name":"x","arguments":{}}</tool_call',
        '<tool_call>{"name":"x","arguments":{"path":"half',
        '{"name":"x","arguments":{"path":"half',
        '{"tool_name":"x","tool_args":{"path":"half',
    ],
)
def test_truncated_calls_never_produce_a_request(text):
    status, request = extract_leaked_tool_request(text)
    assert status == "truncated"
    assert request is None


@pytest.mark.parametrize(
    "text",
    [
        '<tool_call>{"name":"x","arguments":[]}</tool_call>',
        '<tool_call>{"name":"x","arguments":null}</tool_call>',
        '<tool_call>{"name":"x","arguments":{"a":1,}}</tool_call>',
        '<tool_call>{"name":"x","name":"response","arguments":{}}</tool_call>',
        '<tool_call>{"name":"x","arguments":{"a":1,"a":2}}</tool_call>',
        '<tool_call>{"name":"x","arguments":{"a":NaN}}</tool_call>',
        '<tool_call>{"name":"x","arguments":{"a":1e999}}</tool_call>',
        '{"name":"x","arguments":{},"parameters":{}}',
        '<tool_call>{"tool_name":"x","tool_args":{},"name":"response"}</tool_call>',
        "<function=x><parameter=a>one</parameter><parameter=a>two</parameter></function>",
        "<function=x><parameter=a>half</function>",
        "<function=x>unparsed<parameter=a>1</parameter></function>",
        "<function=x><parameter=a><function=x></parameter></function>",
        '<function_calls><invoke name="x"></invoke></function_calls>',
        "<minimax:tool_call>anything</minimax:tool_call>",
        "<|tool_calls_section_begin|>anything",
    ],
)
def test_rejects_malformed_ambiguous_and_unsupported_calls(text):
    status, request = extract_leaked_tool_request(text)
    assert status == "rejected"
    assert request is None


@pytest.mark.parametrize(
    "wrap",
    [
        lambda call: f"Example: {call}",
        lambda call: f"{call} and then explain it",
        lambda call: call + call,
        lambda call: call + "<function=x>",
        lambda call: f"```text\nexample\n```\n{call}",
    ],
)
def test_does_not_execute_a_call_amid_prose_or_other_calls(wrap):
    status, request = extract_leaked_tool_request(
        wrap('<tool_call>{"name":"x","arguments":{}}</tool_call>')
    )
    assert status == "rejected"
    assert request is None


@pytest.mark.parametrize(
    "wrap",
    [
        lambda call: f"Example:\n```xml\n{call}\n```",
        lambda call: f"~~~xml\n{call}\n~~~",
        lambda call: f"````xml\n{call}\n````",
        lambda call: f"Use `{call}` to call a tool.",
        lambda call: f"Use ``{call}`` to call a tool.",
        lambda call: f"```xml\n{call}",
    ],
)
def test_quoted_tool_examples_are_not_calls(wrap):
    status, request = extract_leaked_tool_request(
        wrap('<tool_call>{"name":"x","arguments":{}}</tool_call>')
    )
    assert status == "quoted"
    assert request is None


def test_preserves_json_string_payload_including_fences_and_markup():
    text = 'Example: ```json\n{"name":"x","arguments":{}}\n``` </tool_call> { \\"'
    status, request = extract_leaked_tool_request(
        "<tool_call>"
        + json.dumps({"name": "response", "arguments": {"text": text}})
        + "</tool_call>"
    )
    assert request["tool_args"]["text"] == text


def test_xml_parameters_preserve_whitespace_and_coerce_only_intact_tokens():
    status, request = extract_leaked_tool_request(
        '<function=x><parameter=data>{"a":1}</parameter>'
        "<parameter=text>  hello world\n</parameter><parameter=enabled>true</parameter>"
        "<parameter=content>```python\nprint(1)\n```</parameter></function>"
    )
    assert request["tool_args"] == {
        "data": {"a": 1},
        "text": "  hello world\n",
        "enabled": True,
        "content": "```python\nprint(1)\n```",
    }


@pytest.mark.parametrize(
    "text",
    [
        "Plain answer.",
        '{"name":"ordinary data"}',
        '{"text":"<tool_call>this is data</tool_call>"}',
        '{"thoughts":[],"tool_name":"response","tool_args":{"text":"<tool_call>example</tool_call>"}}',
        '{"type":"function","name":"x","parameters":{}}',
    ],
)
def test_clean_and_canonical_responses_keep_existing_behavior(text):
    assert extract_leaked_tool_request(text)[0] == "clean"


def test_multiple_native_calls_are_rejected_as_a_whole():
    status, request = extract_leaked_tool_request(
        '[{"name":"x","arguments":{}},{"name":"response","arguments":{}}]'
    )
    assert status == "rejected"
    assert request is None


@pytest.mark.parametrize(
    "text",
    [
        "{'tool_name':'x','tool_args':{}} {'tool_name':'response','tool_args':{}}",
        '{tool_name:"x",tool_args:{}} {tool_name:"response",tool_args:{}}',
    ],
)
def test_multiple_dirty_canonical_calls_cannot_reach_plugin_repair(text):
    assert extract_leaked_tool_request(text)[0] == "rejected"
