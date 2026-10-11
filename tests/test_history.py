import pytest

from helpers import history
from helpers.history import output_langchain
from langchain_core.messages import AIMessage, HumanMessage


def test_output_langchain_omits_leading_assistant_messages():
    messages = output_langchain(
        [
            {"ai": True, "content": "Welcome"},
            {"ai": False, "content": "Hello"},
            {"ai": True, "content": "Hi"},
        ]
    )

    assert messages == [HumanMessage("Hello"), AIMessage("Hi")]


def test_restored_message_reuses_saved_tokens_and_summary(monkeypatch):
    data = {
        "_cls": "Message", "ai": False, "content": "original content",
        "id": "message", "sequence": 2, "metadata": {"custom": True},
        "summary": "saved summary", "tokens": 42,
    }

    def recount(_text):
        pytest.fail("Restoring a saved count must not tokenize the message again")

    monkeypatch.setattr(history.tokens, "approximate_tokens", recount)
    restored = history.Message.from_dict(data, history=None)

    assert restored.to_dict() == data
    assert restored.get_tokens() == 42
    assert restored.output()[0]["content"] == "saved summary"


@pytest.mark.parametrize("saved", [{}, {"tokens": 0}, {"tokens": None}])
def test_restored_message_without_token_count_recounts_using_summary(monkeypatch, saved):
    counted = []

    def count(text):
        counted.append(text)
        return 7

    monkeypatch.setattr(history.tokens, "approximate_tokens", count)
    restored = history.Message.from_dict(
        {"ai": False, "content": "original", "summary": "summary", **saved},
        history=None,
    )

    assert restored.tokens == saved.get("tokens", 0)
    assert restored.get_tokens() == 7
    assert counted == ["user: original", "user: summary"]
    assert restored.get_tokens() == 7
    assert len(counted) == 2
