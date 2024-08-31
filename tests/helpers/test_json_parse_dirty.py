import unittest
from python.helpers.extract_tools import extract_json_object_string
from python.helpers.dirty_json import DirtyJson
from typing import Any


def json_parse_dirty(json: str) -> dict[str, Any] | None:
    ext_json = extract_json_object_string(json)
    if ext_json:
        data = DirtyJson.parse_string(ext_json)
        if isinstance(data, dict):
            return data
    return None


class TestJsonParseDirty(unittest.TestCase):
    def test_valid_json(self):
        json_string = '{"key": "value"}'
        expected_output = {"key": "value"}
        self.assertEqual(json_parse_dirty(json_string), expected_output)

    def test_invalid_json(self):
        json_string = 'invalid json'
        self.assertIsNone(json_parse_dirty(json_string))

    def test_partial_json(self):
        json_string = 'some text before {"key": "value"} some text after'
        expected_output = {"key": "value"}
        self.assertEqual(json_parse_dirty(json_string), expected_output)

    def test_no_closing_brace(self):
        json_string = '{"key": "value"'
        expected_output = {"key": "value"}
        self.assertEqual(json_parse_dirty(json_string), expected_output)

    def test_no_opening_brace(self):
        json_string = '"key": "value"}'
        self.assertIsNone(json_parse_dirty(json_string))

    def test_agent_response(self):
        json_string = ('{"thoughts": ["The user wants to save the source code of their Hello, World! application to a '
                       'file.", "I can use the code_execution_tool with terminal runtime to achieve this."], '
                       '"tool_name": "code_execution_tool", "tool_args": {"runtime": "terminal", "code": "echo '
                       '\'print(\'Hello, World!\')\' > hello_world.py"}}')
        expected_result = {
            "thoughts": [
                "The user wants to save the source code of their Hello, World! application to a file.",
                "I can use the code_execution_tool with terminal runtime to achieve this."
            ],
            "tool_name": "code_execution_tool",
            "tool_args": {
                "runtime": "terminal",
                "code": "echo \'print(\'Hello, World!\')\' > hello_world.py"
            }
        }
        self.assertEqual(json_parse_dirty(json_string), expected_result)


if __name__ == '__main__':
    unittest.main()