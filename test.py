def extract_json_string(content):
    start = content.find('{')
    if start == -1:
        print("No JSON content found.")
        return ""

    # Find the first '{'
    end = content.rfind('}')
    if end == -1:
        # If there's no closing '}', return from start to the end
        return content[start:]
    else:
        # If there's a closing '}', return the substring from start to end
        return content[start:end+1]

# Test cases
test_cases = [
    'Some text before {"key1": "value1", "key2": 123, "key3": true, "key4": null} some text after',
    '{"key1": "value1", "key2": 123, "key3": true, "key4": null',  # Incomplete JSON
    '{"nested": {"key": "value"}, "list": [1, 2, 3], "bool": true}',
    'text without json',
]

# Run the test cases
results = [extract_json_string(tc) for tc in test_cases]
print(results)
