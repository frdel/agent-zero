from python.helpers.dirty_json import DirtyJson


json_string = """
{"key1": "value1",
    "key2": "value2",
    "key3": "value3"
}
"""

json = DirtyJson.parse_string(json_string)
print(json)