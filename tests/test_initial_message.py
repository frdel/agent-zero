import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from extensions.python.agent_init._10_initial_message import InitialMessage
from helpers import history
from helpers.llm_result import result_from_metadata
from helpers.log import Log


@pytest.mark.parametrize("greeting", [
    json.dumps({"tool_name": "response", "tool_args": {"text": "Welcome."}}, indent=2),
    "Welcome to this profile.",
])
def test_initial_greeting_keeps_user_first_order_and_linked_log_after_reload(greeting):
    messages = []
    log = Log()

    def add_ai(content, llm_result):
        message = history.Message(True, content, metadata=llm_result.metadata())
        messages.append(message)
        return message

    agent = SimpleNamespace(
        number=0,
        context=SimpleNamespace(log=log),
        read_prompt=lambda name: "Hello!" if name == "fw.initial_user_message.md" else greeting,
        hist_add_user_message=lambda message: messages.append(history.Message(False, message.message)) or messages[-1],
        hist_add_ai_response=add_ai,
    )
    extension = InitialMessage(agent)
    extension.execute()
    extension.execute()
    assert len(messages) == 2
    assert len(log.logs) == 1
    assert log.logs[0].id == messages[1].id
    assert log.logs[0].id != messages[0].id

    reloaded = [history.Message.from_dict(message.to_dict(), history=None) for message in messages]
    rendered = history.output_langchain([item for message in reloaded for item in message.output()])
    assert [type(item) for item in rendered] == [HumanMessage, AIMessage]
    assert rendered[0].content == "Hello!"
    assert rendered[1].content == messages[1].content
    result = result_from_metadata(reloaded[1].metadata)
    assert result.mode == "" and result.state == "off" and not result.response_id
    if greeting.startswith("{"):
        assert "\n" not in rendered[1].content
        assert log.logs[0].content == "Welcome."
    else:
        assert log.logs[0].content == greeting
