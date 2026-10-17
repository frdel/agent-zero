from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers.dirty_json import DirtyJson


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            '{"tool_name":"x","tool_args":{}}',
            {"tool_name": "x", "tool_args": {}},
        ),
        ("[1, 2, 3]", [1, 2, 3]),
    ],
)
def test_completed_true_when_root_is_explicitly_closed(payload, expected) -> None:
    parser = DirtyJson()

    assert parser.parse(payload) == expected
    assert parser.completed is True


def test_completed_false_when_root_hits_eof_before_closing() -> None:
    parser = DirtyJson()

    assert parser.parse('{"tool_name":"x","tool_args":{}') == {
        "tool_name": "x",
        "tool_args": {},
    }
    assert parser.completed is False


def test_completed_remains_true_after_trailing_content() -> None:
    parser = DirtyJson()

    assert parser.feed('{"tool_name":"x","tool_args":{}}') == {
        "tool_name": "x",
        "tool_args": {},
    }
    assert parser.completed is True

    assert parser.feed(" trailing noise") == {
        "tool_name": "x",
        "tool_args": {},
    }

    assert parser.completed is True


def test_value_keeps_unescaped_markdown_quotes_until_structural_delimiter() -> None:
    payload = (
        "{\n"
        '    "tool_name": "response",\n'
        '    "tool_args": {\n'
        '        "text": "The rule:\\n\\n> *"'
        'Create a child AGENTS.md when a folder becomes a boundary."'
        '*\\n\\nAdding `css/AGENTS.md` that says *"'
        'this folder contains CSS"'
        '* is duplication."\n'
        "    }\n"
        "}"
    )

    parsed = DirtyJson.parse_string(payload)

    assert parsed["tool_args"] == {
        "text": (
            "The rule:\n\n"
            '> *"Create a child AGENTS.md when a folder becomes a boundary."*\n\n'
            'Adding `css/AGENTS.md` that says *"this folder contains CSS"* is duplication.'
        )
    }


def test_value_keeps_unescaped_quotes_on_single_line() -> None:
    parsed = DirtyJson.parse_string(
        '{"text":"He said "hello" before closing","ok":true}'
    )

    assert parsed == {"text": 'He said "hello" before closing', "ok": True}


def test_value_can_still_end_before_quoted_key_when_comma_is_missing() -> None:
    parsed = DirtyJson.parse_string('{"first":"one" "second":"two"}')

    assert parsed == {"first": "one", "second": "two"}


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("[foo, bar, baz]", ["foo", "bar", "baz"]),
        ('[foo, "bar"]', ["foo", "bar"]),
        ('["foo", bar]', ["foo", "bar"]),
        ("[foo]", ["foo"]),
    ],
)
def test_unquoted_array_elements_are_all_kept(payload, expected) -> None:
    # A bareword element must not consume its own trailing delimiter, which
    # previously truncated the array after the first unquoted value.
    assert DirtyJson.parse_string(payload) == expected
