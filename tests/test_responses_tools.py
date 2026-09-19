import sys
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers import responses_tools, tool_policy


class FakeAgent:
    def __init__(self, prompt_root: Path, data=None):
        self.prompt_root = prompt_root
        self.data = data or {}
        self.config = SimpleNamespace(profile="default")
        self.context = SimpleNamespace(get_data=lambda *args, **kwargs: None)

    def read_prompt(self, file: str, **kwargs) -> str:
        prompt = (self.prompt_root / file).read_text(encoding="utf-8")
        for key, value in kwargs.items():
            prompt = prompt.replace("{{" + key + "}}", str(value))
        return prompt

    def get_data(self, key: str):
        return self.data.get(key)


def _write_prompt(prompt_root: Path, basename: str, content: str) -> None:
    (prompt_root / basename).write_text(content.strip() + "\n", encoding="utf-8")


def test_responses_function_tools_use_prompt_declared_names(monkeypatch, tmp_path):
    prompt_root = tmp_path / "prompts"
    prompt_root.mkdir()
    _write_prompt(
        prompt_root,
        "agent.system.tool.code_exe.md",
        """
        ### code_execution_tool
        run terminal commands
        ```json
        {"tool_name": "code_execution_tool", "tool_args": {"runtime": "terminal"}}
        ```
        """,
    )
    _write_prompt(
        prompt_root,
        "agent.system.tool.memory.md",
        """
        ## memory tools
        durable memory operations
        - `memory_load`: args `query`, optional `threshold`, `limit`, `filter`
        - `memory_save`: args `text`, optional `area`
        - `memory_delete`: arg `ids`
        - `memory_forget`: args `query`, optional `threshold`, `filter`
        ```json
        {"tool_name": "memory_load", "tool_args": {"query": "responses naming"}}
        ```
        """,
    )
    _write_prompt(
        prompt_root,
        "agent.system.tool.call_sub.md",
        """
        ### call_subordinate
        delegate a subtask
        ```json
        {"tool_name": "call_subordinate", "tool_args": {"message": "inspect"}}
        ```
        """,
    )
    _write_prompt(
        prompt_root,
        "agent.system.tool.behaviour.md",
        """
        ### behaviour_adjustment
        update persistent behavioral rules
        """,
    )
    _write_prompt(
        prompt_root,
        "agent.system.tool.filename_only.md",
        "plain prompt with no declared callable name",
    )

    monkeypatch.setattr(
        responses_tools.subagents,
        "get_paths",
        lambda *args, **kwargs: [str(prompt_root)],
    )
    monkeypatch.setattr(
        responses_tools,
        "_include_local_tool_prompt",
        lambda agent, tool_name: True,
    )
    monkeypatch.setattr(responses_tools, "_mcp_tools", lambda agent: [])

    tools, name_map = responses_tools.build_responses_function_tools(
        FakeAgent(prompt_root)
    )

    names = {tool["name"] for tool in tools}
    assert {
        "code_execution_tool",
        "memory_load",
        "memory_save",
        "memory_delete",
        "memory_forget",
        "call_subordinate",
        "behaviour_adjustment",
        "filename_only",
    } <= names
    assert not {"code_exe", "memory", "call_sub", "behaviour"} & names
    assert name_map["code_execution_tool"] == "code_execution_tool"
    assert name_map["memory_load"] == "memory_load"
    assert name_map["memory_save"] == "memory_save"
    assert name_map["memory_delete"] == "memory_delete"
    assert name_map["memory_forget"] == "memory_forget"
    assert name_map["call_subordinate"] == "call_subordinate"
    assert name_map["behaviour_adjustment"] == "behaviour_adjustment"
    assert name_map["filename_only"] == "filename_only"
    assert all(isinstance(tool["parameters"].get("properties"), dict) for tool in tools)


def test_responses_function_tools_add_empty_properties_to_mcp_schemas(
    monkeypatch,
    tmp_path,
):
    prompt_root = tmp_path / "prompts"
    prompt_root.mkdir()

    monkeypatch.setattr(
        responses_tools.subagents,
        "get_paths",
        lambda *args, **kwargs: [str(prompt_root)],
    )
    monkeypatch.setattr(
        responses_tools,
        "_mcp_tools",
        lambda agent: [
            (
                "remote_noop",
                {
                    "description": "Remote noop",
                    "input_schema": {"type": "object"},
                },
            )
        ],
    )

    tools, _name_map = responses_tools.build_responses_function_tools(
        FakeAgent(prompt_root)
    )

    assert tools == [
        {
            "type": "function",
            "name": "remote_noop",
            "strict": False,
            "description": "Remote noop",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": True,
            },
        }
    ]


def test_response_tool_native_contract_stays_provider_neutral(monkeypatch):
    prompt_root = PROJECT_ROOT / "agents" / "agent0" / "prompts"
    prompt = (prompt_root / "agent.system.tool.response.md").read_text(encoding="utf-8")

    description = tool_policy.tool_prompt_description(
        prompt,
        "response",
        fallback="response",
    )
    monkeypatch.setattr(
        responses_tools.subagents,
        "get_paths",
        lambda *args, **kwargs: [str(prompt_root)],
    )
    monkeypatch.setattr(
        responses_tools,
        "_include_local_tool_prompt",
        lambda agent, tool_name: True,
    )
    monkeypatch.setattr(responses_tools, "_vision_tool_prompt", lambda agent: "")
    monkeypatch.setattr(responses_tools, "_mcp_tools", lambda agent: [])
    tools, _name_map = responses_tools.build_responses_function_tools(
        FakeAgent(prompt_root)
    )
    response_tool = next(tool for tool in tools if tool["name"] == "response")

    assert description == "final answer to user"
    assert response_tool["parameters"] == responses_tools._schema_from_prompt(prompt)
    assert response_tool["strict"] is False


def test_complex_prompt_args_are_not_guessed_as_string_schemas():
    for path in (
        PROJECT_ROOT / "plugins" / "_scheduler" / "prompts" / "agent.system.tool.scheduler.md",
        PROJECT_ROOT / "prompts" / "agent.system.tool.parallel.md",
    ):
        schema = responses_tools._schema_from_prompt(path.read_text(encoding="utf-8"))

        assert schema == {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        }


def test_remote_execution_schemas_match_local_runtime_and_input_contracts():
    params = responses_tools.BUNDLED_TOOL_PARAMETERS
    local = params["plugins/_code_execution/tools/code_execution_tool.py"]
    remote = params["plugins/_a0_connector/tools/code_execution_remote.py"]
    assert remote["runtime"] == local["runtime"]
    assert "input" not in remote["runtime"]["enum"]
    assert "allow_running" not in remote
    assert params["plugins/_a0_connector/tools/input_remote.py"] == params["plugins/_code_execution/tools/input.py"]


def test_bundled_schema_follows_implementation_and_explicit_overrides(monkeypatch, tmp_path):
    tool_path = PROJECT_ROOT / "plugins/_code_execution/tools/code_execution_tool.py"
    custom_path = tmp_path / "code_execution_tool.py"
    monkeypatch.setattr(
        responses_tools.subagents, "get_paths",
        lambda *args: [str(custom_path), str(tool_path)],
    )
    schema = responses_tools._schema_for_tool(None, "code_execution_tool", "")
    assert schema["properties"]["session"] == {"type": "integer"}
    assert schema["properties"]["reset"] == {"type": "boolean"}
    assert "output" in schema["properties"]["runtime"]["enum"]
    assert "code" not in schema.get("required", [])  # Output polling needs no code.
    schema["properties"]["runtime"]["enum"].clear()
    assert responses_tools._schema_for_tool(None, "code_execution_tool", "")["properties"]["runtime"]["enum"]

    custom_path.write_text("class CustomTool: pass\n")
    assert responses_tools._schema_for_tool(None, "code_execution_tool", "") == responses_tools._permissive_schema()
    explicit = 'Input schema for tool_args: {"type":"object","properties":{"custom":{"type":"boolean"}},"required":["custom"],"additionalProperties":false}'
    assert responses_tools._schema_for_tool(None, "code_execution_tool", explicit) == {
        "type": "object", "properties": {"custom": {"type": "boolean"}},
        "required": ["custom"], "additionalProperties": False,
    }


def test_responses_function_tools_include_vision_prompt(monkeypatch, tmp_path):
    prompt_root = tmp_path / "prompts"
    prompt_root.mkdir()
    _write_prompt(
        prompt_root,
        "agent.system.tools_vision.md",
        """
        ## multimodal vision tools
        ### vision_load
        load images into the model for visual reasoning
        args: `paths` list of absolute image paths
        """,
    )
    agent = FakeAgent(prompt_root)

    monkeypatch.setattr(responses_tools.subagents, "get_paths", lambda *args: [])
    monkeypatch.setattr(
        responses_tools,
        "_vision_tool_prompt",
        lambda _agent: agent.read_prompt("agent.system.tools_vision.md"),
    )
    monkeypatch.setattr(responses_tools, "_mcp_tools", lambda _agent: [])

    tools, name_map = responses_tools.build_responses_function_tools(agent)

    assert [tool["name"] for tool in tools] == ["vision_load"]
    assert "load images into the model for visual reasoning" in tools[0]["description"]
    assert "args: `paths` list of absolute image paths" in tools[0]["description"]
    assert tools[0]["parameters"]["properties"] == {}
    assert name_map == {"vision_load": "vision_load"}


def test_local_tool_prompts_use_registered_render_kwargs(monkeypatch, tmp_path):
    prompt_root = tmp_path / "prompts"
    prompt_root.mkdir()
    basename = "agent.system.tool.text_editor.md"
    _write_prompt(
        prompt_root,
        basename,
        """
        ### text_editor
        read {{default_line_count}} lines by default
        """,
    )
    agent = FakeAgent(
        prompt_root,
        data={
            responses_tools.TOOL_PROMPT_KWARGS_KEY: {
                basename: {"default_line_count": 200}
            }
        },
    )

    monkeypatch.setattr(
        responses_tools.subagents,
        "get_paths",
        lambda *args, **kwargs: [str(prompt_root)],
    )
    monkeypatch.setattr(responses_tools, "_vision_tool_prompt", lambda _agent: "")
    monkeypatch.setattr(
        responses_tools,
        "_include_local_tool_prompt",
        lambda _agent, _tool_name: True,
    )

    prompts = dict(responses_tools._local_tool_prompts(agent))

    assert "{{default_line_count}}" not in prompts["text_editor"]
    assert "read 200 lines by default" in prompts["text_editor"]


def test_explicit_tool_name_precedes_a_generic_heading():
    prompt = """## memory tools
durable memory operations
{"tool_name": "memory_load", "tool_args": {}}
"""

    assert responses_tools._tool_names_from_prompt(
        prompt, fallback="memory"
    ) == ["memory_load"]


def test_bundled_memory_prompt_exposes_every_memory_tool():
    prompt = (
        PROJECT_ROOT / "plugins/_memory/prompts/agent.system.tool.memory.md"
    ).read_text(encoding="utf-8")

    assert responses_tools._tool_names_from_prompt(prompt, fallback="memory") == [
        "memory_load",
        "memory_save",
        "memory_delete",
        "memory_forget",
    ]


def test_native_description_preserves_guidance_and_projects_only_tool_examples():
    prompt = '''### example
Keep every operational rule.
~~~json
{"thoughts":["think"],"headline":"execute","tool_name":"example","tool_args":{"text":"héllo","nested":{"value":true}},}
~~~
{"tool_name":"other","tool_args":{"query":"lookup"}}
```python
payload = {"tool_name":"example","tool_args":{"text":"literal code"}}
```
```json
{"ordinary":"data"}
```
'''
    description = responses_tools._native_tool_description(prompt, 'example')
    assert 'Keep every operational rule.' in description
    assert 'Arguments example:\n```json\n{"text": "héllo", "nested": {"value": true}}' in description
    assert 'Call other with arguments:' in description
    assert '"thoughts"' not in description and '"headline"' not in description
    assert 'payload = {"tool_name":"example","tool_args":{"text":"literal code"}}' in description
    assert '```json\n{"ordinary":"data"}\n```' in description
    assert responses_tools._native_tool_description('rule\n' * 300, 'example').endswith('rule')
    assert len(responses_tools._native_tool_description('rule\n' * 300, 'example')) > 1024


def test_native_system_projection_is_scoped_and_does_not_mutate_inputs():
    from copy import deepcopy
    from helpers import files, litellm_transport

    legacy = 'Legacy format\n~~~json\n{"tool_name":"example"}\n~~~'
    rendered = files.remove_code_fences(legacy, language='json')
    items = [
        {'role':'system','content':f'Custom role\n{rendered}\nTOOLS\nCustom rule'},
        {'role':'developer','content':[{'type':'input_text','text':rendered}]},
        {'role':'user','content':[{'type':'input_text','text':rendered}, {'type':'input_image','image_url':'image-ref'}]},
        {'role':'assistant','content':'Summary stays visible'},
    ]
    original = deepcopy(items)
    kwargs = {
        'responses_state':'local', 'responses_local_input_items':items,
        'responses_prompt_replacements':{legacy:'Native format','TOOLS':'','   ':'Never insert this'},
        'a0_responses_function_tools':[{'type':'function','name':'example','parameters':{'type':'object'}}],
    }
    for build in (
        lambda: litellm_transport.ResponsesTransport.from_chat([], kwargs),
        lambda: litellm_transport.ResponsesTransport.from_input(items, kwargs),
    ):
        request = build()
        assert request['input'][0]['content'] == 'Custom role\nNative format\n\nCustom rule'
        assert request['input'][1]['content'][0]['text'] == 'Native format'
        assert request['input'][2:] == original[2:]
        assert 'responses_prompt_replacements' not in request
        assert items == original
    kwargs['a0_responses_function_tools'] = []
    assert litellm_transport.ResponsesTransport.from_chat([], kwargs)['input'] == original
