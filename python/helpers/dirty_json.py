import json
from python.helpers.print_style import PrintStyle


def try_parse(json_string: str):
    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        return DirtyJson.parse_string(json_string)


def parse(json_string: str):
    return DirtyJson.parse_string(json_string)


def stringify(obj, **kwargs):
    return json.dumps(obj, ensure_ascii=False, **kwargs)


class DirtyJson:

    DEBUG = False

    def __init__(self):
        self._reset()

    def _reset(self):
        self.json_string = ""
        self.index = 0
        self.current_char = None
        self.result = None
        self.stack = []
        self.is_complete = False
        self.required_properties = []

    @staticmethod
    def parse_string_checked(json_string, required_properties=None):
        parser = DirtyJson()
        result, is_complete = parser.parse(json_string, required_properties)
        return (is_complete, result)

    @staticmethod
    def parse_string(json_string, required_properties=None):
        parser = DirtyJson()
        result, _ = parser.parse(json_string, required_properties)
        return result

    def parse(self, json_string, required_properties=None):
        self._reset()
        self.json_string = json_string
        if not self.json_string:
            return None, False
        self.required_properties = required_properties or []
        self.index = self.get_start_pos(self.json_string)  # skip any text up to the first brace
        if self.index >= len(self.json_string):
            return None, False
        self.current_char = self.json_string[self.index]
        self._parse()
        self._check_completeness()
        return self.result, self.is_complete

    def feed(self, chunk, required_properties=None):
        if required_properties is not None:
            self.required_properties = required_properties
        self.json_string += chunk
        if not self.current_char and self.json_string:
            self.current_char = self.json_string[0]
        try:
            self._parse()
            self._check_completeness()
        except Exception as e:
            if DirtyJson.DEBUG:
                PrintStyle(font_color="red", background_color="black", bold=True, padding=True).print(
                    f"DIRTY_JSON: Error in feed: {str(e)}"
                )
            # Don't update is_complete on error
        return self.result, self.is_complete

    def _advance(self, count=1):
        self.index += count
        if self.index < len(self.json_string):
            self.current_char = self.json_string[self.index]
        else:
            self.current_char = None

    def _skip_whitespace(self):
        while self.current_char is not None:
            if self.current_char.isspace():
                self._advance()
            elif (
                self.current_char == "/" and self._peek(1) == "/"
            ):  # Single-line comment
                self._skip_single_line_comment()
            elif (
                self.current_char == "/" and self._peek(1) == "*"
            ):  # Multi-line comment
                self._skip_multi_line_comment()
            else:
                break

    def _skip_single_line_comment(self):
        while self.current_char is not None and self.current_char != "\n":
            self._advance()
        if self.current_char == "\n":
            self._advance()

    def _skip_multi_line_comment(self):
        self._advance(2)  # Skip /*
        while self.current_char is not None:
            if self.current_char == "*" and self._peek(1) == "/":
                self._advance(2)  # Skip */
                break
            self._advance()

    def _parse(self):
        if self.result is None:
            self.result = self._parse_value()
        else:
            self._continue_parsing()
        # Ensure we have a result even if parsing fails partially
        if self.result is None and self.stack and isinstance(self.stack[0], dict):
            self.result = self.stack[0]

    def _continue_parsing(self):
        while self.current_char is not None:
            if isinstance(self.result, dict):
                self._parse_object_content()
            elif isinstance(self.result, list):
                self._parse_array_content()
            elif isinstance(self.result, str):
                self.result = self._parse_string()
            else:
                break

    def _parse_value(self):
        self._skip_whitespace()
        if self.current_char == "{":
            if self._peek(1) == "{":  # Handle {{
                self._advance(2)
            return self._parse_object()
        elif self.current_char == "[":
            return self._parse_array()
        elif self.current_char in ['"', "'", "`"]:
            if self._peek(2) == self.current_char * 2:  # type: ignore
                return self._parse_multiline_string()
            return self._parse_string()
        elif self.current_char and (
            self.current_char.isdigit() or self.current_char in ["-", "+"]
        ):
            return self._parse_number()
        elif self._match("true"):
            return True
        elif self._match("false"):
            return False
        elif self._match("null") or self._match("undefined"):
            return None
        elif self.current_char:
            return self._parse_unquoted_string()
        return None

    def _match(self, text: str) -> bool:
        # first char should match current char
        if not self.current_char or self.current_char.lower() != text[0].lower():
            return False

        # peek remaining chars
        remaining = len(text) - 1
        if self._peek(remaining).lower() == text[1:].lower():
            self._advance(len(text))
            return True
        return False

    def _parse_object(self):
        obj = {}
        self._advance()  # Skip opening brace
        self.stack.append(obj)
        self._parse_object_content()
        return obj

    def _parse_object_content(self):
        while self.current_char is not None:
            self._skip_whitespace()
            if self.current_char == "}":
                if self._peek(1) == "}":  # Handle }}
                    self._advance(2)
                else:
                    self._advance()
                self.stack.pop()
                return
            if self.current_char is None:
                # Don't pop the stack here, as the object is incomplete
                return  # End of input reached while parsing object

            key = self._parse_key()
            value = None
            self._skip_whitespace()

            if self.current_char == ":":
                self._advance()
                value = self._parse_value()
            elif self.current_char is None:
                value = None  # End of input reached after key
            else:
                value = self._parse_value()

            self.stack[-1][key] = value

            self._skip_whitespace()
            if self.current_char == ",":
                self._advance()
                continue
            elif self.current_char != "}":
                if self.current_char is None:
                    # Don't pop the stack here, as the object is incomplete
                    return  # End of input reached after value
                continue

    def _parse_key(self):
        self._skip_whitespace()
        if self.current_char in ['"', "'"]:
            return self._parse_string()
        else:
            return self._parse_unquoted_key()

    def _parse_unquoted_key(self):
        result = ""
        while (
            self.current_char is not None
            and not self.current_char.isspace()
            and self.current_char not in [":", ",", "}", "]"]
        ):
            result += self.current_char
            self._advance()
        return result

    def _parse_array(self):
        arr = []
        self._advance()  # Skip opening bracket
        self.stack.append(arr)
        self._parse_array_content()
        return arr

    def _parse_array_content(self):
        while self.current_char is not None:
            self._skip_whitespace()
            if self.current_char == "]":
                self._advance()
                self.stack.pop()
                return
            value = self._parse_value()
            self.stack[-1].append(value)
            self._skip_whitespace()
            if self.current_char == ",":
                self._advance()
                # handle trailing commas, end of array
                self._skip_whitespace()
                if self.current_char is None or self.current_char == "]":
                    if self.current_char == "]":
                        self._advance()
                    self.stack.pop()
                    return
            elif self.current_char != "]":
                self.stack.pop()
                return

    def _parse_string(self):
        result = ""
        quote_char = self.current_char
        self._advance()  # Skip opening quote
        while self.current_char is not None and self.current_char != quote_char:
            if self.current_char == "\\":
                self._advance()
                if self.current_char in ['"', "'", "\\", "/", "b", "f", "n", "r", "t"]:
                    result += {
                        "b": "\b",
                        "f": "\f",
                        "n": "\n",
                        "r": "\r",
                        "t": "\t",
                    }.get(self.current_char, self.current_char)
                elif self.current_char == "u":
                    self._advance()  # Skip 'u'
                    unicode_char = ""
                    # Try to collect exactly 4 hex digits
                    for _ in range(4):
                        if self.current_char is None or not self.current_char.isalnum():
                            # If we can't get 4 hex digits, treat it as a literal '\u' followed by whatever we got
                            return result + "\\u" + unicode_char
                        unicode_char += self.current_char
                        self._advance()
                    try:
                        result += chr(int(unicode_char, 16))
                    except ValueError:
                        # If invalid hex value, treat as literal
                        result += "\\u" + unicode_char
                    continue
            else:
                result += self.current_char
            self._advance()
        if self.current_char == quote_char:
            self._advance()  # Skip closing quote
        return result

    def _parse_multiline_string(self):
        result = ""
        quote_char = self.current_char
        self._advance(3)  # Skip first quote
        while self.current_char is not None:
            if self.current_char == quote_char and self._peek(2) == quote_char * 2:  # type: ignore
                self._advance(3)  # Skip first quote
                break
            result += self.current_char
            self._advance()
        return result.strip()

    def _parse_number(self):
        number_str = ""
        while self.current_char is not None and (
            self.current_char.isdigit()
            or self.current_char in ["-", "+", ".", "e", "E"]
        ):
            number_str += self.current_char
            self._advance()
        try:
            return int(number_str)
        except ValueError:
            return float(number_str)

    def _parse_unquoted_string(self):
        result = ""
        while self.current_char is not None and self.current_char not in [
            ":",
            ",",
            "}",
            "]",
        ]:
            result += self.current_char
            self._advance()
        self._advance()
        return result.strip()

    def _peek(self, n):
        peek_index = self.index + 1
        result = ""
        for _ in range(n):
            if peek_index < len(self.json_string):
                result += self.json_string[peek_index]
                peek_index += 1
            else:
                break
        return result

    def get_start_pos(self, input_str: str) -> int:
        chars = ["{", "[", '"']
        indices = [input_str.find(char) for char in chars if input_str.find(char) != -1]
        return min(indices) if indices else 0

    def _check_completeness(self):
        """Check if the parsed object is complete according to the specified rules."""
        # Make sure we have a result first
        if self.result is None:
            self.is_complete = False
            return

        # If stack is empty, everything was properly closed by the parser
        if not self.stack:
            self.is_complete = True
            return

        # Non-empty stack means we have unclosed structures
        self.is_complete = False

        # If we have objects or arrays that haven't been closed, we're definitely incomplete
        if len(self.stack) > 1:
            return

        # Special case: if we have exactly one object in the stack (top-level object)
        if len(self.stack) == 1 and isinstance(self.stack[0], dict):
            # First check if required properties are complete
            if not self._check_required_properties():
                return

            # Then check if the string ends with an unclosed structure
            self._check_for_truncated_ending()

    def _check_required_properties(self):
        """Check if all required properties are fully present and complete."""
        if not self.required_properties:
            return True

        top_obj = self.stack[0]

        # Check if all required properties are present
        for prop in self.required_properties:
            # Property is missing
            if prop not in top_obj:
                if DirtyJson.DEBUG:
                    PrintStyle(font_color="red", background_color="black", bold=True, padding=True).print(
                        f"DIRTY_JSON: Required property {prop} is missing"
                    )
                return False

            # Property is present but needs to be checked for completeness
            value = top_obj[prop]
            if self._is_property_incomplete(prop, value):
                if DirtyJson.DEBUG:
                    PrintStyle(font_color="red", background_color="black", bold=True, padding=True).print(
                        f"DIRTY_JSON: Required property {prop} is incomplete"
                    )
                return False

        return True

    def _is_property_incomplete(self, prop_name, value):
        """Check if a specific property is incomplete."""
        try:
            # Simple values are always complete
            if not isinstance(value, (dict, list)):
                return False

            # For collections, we need to check if they're properly closed
            # First find the property in the JSON string
            prop_pattern = f'"{prop_name}"'
            # Also try with single quotes
            if prop_pattern not in self.json_string:
                prop_pattern = f"'{prop_name}'"
                if prop_pattern not in self.json_string:
                    # Can't find the property - shouldn't happen if it's in top_obj
                    return False

            # Find the last occurrence of the property in the string (in case of duplicates)
            prop_pos = self.json_string.rfind(prop_pattern)
            if prop_pos == -1:
                return False

            # Specifically for tool_args, add detailed diagnostics
            if prop_name == "tool_args":
                if DirtyJson.DEBUG:
                    PrintStyle(font_color="red", background_color="black", bold=True, padding=True).print(
                        f"DIRTY_JSON: Checking 'tool_args' at position {prop_pos}"
                    )
                    PrintStyle(font_color="red", background_color="black", bold=True, padding=True).print(
                        f"DIRTY_JSON: Value type: {type(value)}"
                    )
                # Show context around the property
                context_start = max(0, prop_pos - 10)
                context_end = min(len(self.json_string), prop_pos + 50)
                if DirtyJson.DEBUG:
                    PrintStyle(font_color="red", background_color="black", bold=True, padding=True).print(
                        f"DIRTY_JSON: Context: {self.json_string[context_start:context_end]}"
                    )

            # Find the value part after the property
            colon_pos = self.json_string.find(':', prop_pos)
            if colon_pos == -1:
                return True  # Incomplete - no colon

            # Extract the value part
            value_start = colon_pos + 1
            # Skip whitespace
            while value_start < len(self.json_string) and self.json_string[value_start].isspace():
                value_start += 1

            if value_start >= len(self.json_string):
                return True  # Incomplete - no value after colon

            # Special handling for empty objects and arrays
            char = self.json_string[value_start]

            # Check for an empty object or array
            if char == '{' and isinstance(value, dict) and not value:
                # If we have an opening brace but no closing one, it's incomplete
                if not self._find_matching_close(value_start, '{', '}'):
                    if prop_name == "tool_args":
                        if DirtyJson.DEBUG:
                            PrintStyle(font_color="red", background_color="black", bold=True, padding=True).print(
                                "Empty tool_args object is incomplete!"
                            )
                    return True

            if char == '[' and isinstance(value, list) and not value:
                # If we have an opening bracket but no closing one, it's incomplete
                if not self._find_matching_close(value_start, '[', ']'):
                    return True

            # Handle different value types
            if char == '{':  # Object
                if isinstance(value, dict):
                    # Check if all required properties in this nested object are complete
                    for k, v in value.items():
                        nested_prop = f"{prop_name}.{k}"
                        if self._is_property_incomplete(nested_prop, v):
                            return True
                # Also check for matching braces to detect truncation
                is_complete = self._find_matching_close(value_start, '{', '}')
                if not is_complete and prop_name == "tool_args":
                    if DirtyJson.DEBUG:
                        PrintStyle(font_color="red", background_color="black", bold=True, padding=True).print(
                            "Tool args object has no matching close!"
                        )
                return not is_complete
            elif char == '[':  # Array
                is_complete = self._find_matching_close(value_start, '[', ']')
                return not is_complete
            elif char in ['"', "'"]:  # String
                is_complete = self._find_matching_quote(value_start, char)
                return not is_complete

            # For primitives, ensure we have a complete value (comma or closing brace after)
            return self._is_primitive_incomplete(value_start)
        except Exception as e:
            if DirtyJson.DEBUG:
                PrintStyle(font_color="red", background_color="black", bold=True, padding=True).print(
                    f"DIRTY_JSON: Error checking property {prop_name}: {str(e)}"
                )
            # If there's an error, assume incomplete
            return True

    def _is_primitive_incomplete(self, start_pos):
        """Check if a primitive value is incomplete."""
        pos = start_pos
        # Skip the value itself
        while pos < len(self.json_string) and self.json_string[pos] not in [',', '}', ']']:
            pos += 1

        # If we reached the end, it's incomplete
        if pos >= len(self.json_string):
            return True

        # We should find a comma or closing brace/bracket
        return self.json_string[pos] not in [',', '}', ']']

    def _find_matching_close(self, start_pos, open_char, close_char):
        """Find the matching closing character for a given opening character."""
        count = 1  # Start with 1 for the opening char we've already found
        pos = start_pos + 1

        while pos < len(self.json_string) and count > 0:
            current = self.json_string[pos]
            if current == open_char:
                count += 1
                pos += 1
            elif current == close_char:
                count -= 1
                pos += 1
            elif current in ['"', "'"]:
                # Skip string contents to avoid counting braces inside strings
                quote_char = current
                pos += 1
                # Find the end of this string
                while pos < len(self.json_string):
                    if pos < len(self.json_string) and self.json_string[pos] == '\\':
                        # Skip escaped character
                        pos += 2
                        continue
                    if pos < len(self.json_string) and self.json_string[pos] == quote_char:
                        pos += 1
                        break
                    pos += 1
            else:
                pos += 1

        return count == 0  # True if we found the matching close

    def _find_matching_quote(self, start_pos, quote_char):
        """Find the matching closing quote for a string."""
        pos = start_pos + 1

        while pos < len(self.json_string):
            if pos < len(self.json_string) and self.json_string[pos] == '\\':
                # Skip escaped character
                pos += 2
                continue

            if pos < len(self.json_string) and self.json_string[pos] == quote_char:
                return True

            pos += 1

        return False  # No matching quote found

    def _check_for_truncated_ending(self):
        """Check specifically for truncated JSON endings like 'property': { or 'property': ["""
        # Get the end of the string (ignoring whitespace)
        cleaned_json = self.json_string.rstrip()
        if not cleaned_json:
            return

        # Direct check for ending with opening braces or colons
        if cleaned_json[-1] in ['{', '[', ':', ',']:
            return

        # Check for property name followed by unclosed structure
        # This detects patterns like "tool_args": {
        last_50_chars = cleaned_json[-50:] if len(cleaned_json) >= 50 else cleaned_json

        # Look for common truncation patterns
        truncation_patterns = [
            '": {',      # property followed by unclosed object
            '": [',      # property followed by unclosed array
            '": "',      # property followed by unclosed string
            '":{',       # property followed by unclosed object (no space)
            '":[',       # property followed by unclosed array (no space)
            '":"',       # property followed by unclosed string (no space)
            ': {',       # property followed by unclosed object
            ': [',       # property followed by unclosed array
            ': "'        # property followed by unclosed string
        ]

        for pattern in truncation_patterns:
            if pattern in last_50_chars:
                pattern_pos = last_50_chars.rfind(pattern)
                # Check if there's a closing structure after this pattern
                if pattern[-1] == '{' and '}' not in last_50_chars[pattern_pos + len(pattern) - 1:]:
                    return
                elif pattern[-1] == '[' and ']' not in last_50_chars[pattern_pos + len(pattern) - 1:]:
                    return
                elif pattern[-1] in ['"', "'"] and pattern[-1] not in last_50_chars[pattern_pos + len(pattern):]:
                    return

        # Count braces to ensure balance
        open_braces = cleaned_json.count('{')
        close_braces = cleaned_json.count('}')
        open_brackets = cleaned_json.count('[')
        close_brackets = cleaned_json.count(']')

        if open_braces != close_braces or open_brackets != close_brackets:
            return

        # One additional check: check for an unclosed quote at the end
        # This is tricky because we need to account for escaped quotes
        if self._has_unclosed_quote_at_end(cleaned_json):
            return

        # If we've passed all these checks, we can consider the object complete
        # except for a possibly missing closing brace at the top level
        self.is_complete = True

    def _has_unclosed_quote_at_end(self, text):
        """Check if the text ends with an unclosed quote."""
        # Look at the last part of the string
        last_part = text[-30:] if len(text) >= 30 else text

        # Count quotes backward from the end to see if we have an unclosed one
        quote_chars = ['"', "'"]
        for quote_char in quote_chars:
            if quote_char in last_part:
                # Find last occurrence
                last_quote = last_part.rfind(quote_char)

                # Count backslashes before this quote to check if it's escaped
                i = last_quote - 1
                backslash_count = 0
                while i >= 0 and last_part[i] == '\\':
                    backslash_count += 1
                    i -= 1

                # If even number of backslashes, quote is not escaped
                if backslash_count % 2 == 0:
                    # Check if we have a closing quote after this
                    return last_quote == len(last_part) - 1

        return False

    def _has_unclosed_braces(self):
        """Check if there are any unclosed braces or brackets in the recent input."""
        # Count all opening and closing braces in the entire input
        # This is a simplistic check but effective for detecting obvious issues
        open_braces = self.json_string.count('{')
        close_braces = self.json_string.count('}')
        open_brackets = self.json_string.count('[')
        close_brackets = self.json_string.count(']')

        # If we have more opening braces/brackets than closing ones,
        # we definitely have unclosed structures
        if open_braces > close_braces or open_brackets > close_brackets:
            return True

        # Check specifically for unclosed objects at the end
        last_part = self.json_string[-50:] if len(self.json_string) > 50 else self.json_string
        # Strip trailing whitespace for more accurate detection
        last_part_stripped = last_part.rstrip()

        # Check if the last non-whitespace character is an opening brace or bracket
        if last_part_stripped and last_part_stripped[-1] in ['{', '[']:
            return True

        # Check for recently opened structures that haven't been closed
        if '{' in last_part_stripped:
            last_open = last_part_stripped.rindex('{')
            if '}' not in last_part_stripped[last_open:]:
                return True

        # Check specifically for unclosed arrays at the end
        if '[' in last_part_stripped:
            last_open = last_part_stripped.rindex('[')
            if ']' not in last_part_stripped[last_open:]:
                return True

        return False

    def _has_incomplete_last_property(self):
        """Check if the last property in the object is incomplete."""
        if not self.stack or not isinstance(self.stack[0], dict) or not self.stack[0]:
            return False

        # Get the last 50 characters to analyze
        last_part = self.json_string[-50:] if len(self.json_string) > 50 else self.json_string
        # Strip trailing whitespace for analysis
        last_part_stripped = last_part.rstrip()

        # If the last non-whitespace character is a colon, it's definitely incomplete
        if last_part_stripped and last_part_stripped[-1] == ':':
            return True

        # Check for property definitions that look incomplete
        for char in [':', '{', '[']:
            if char in last_part_stripped:
                pos = last_part_stripped.rindex(char)
                after_char = last_part_stripped[pos + 1:].strip()
                # If there's barely anything meaningful after these chars, likely incomplete
                if not after_char or after_char in [',', '{', '[']:
                    return True

        return False

    def _is_in_property_parsing(self):
        """Check if we're in the middle of parsing a property value."""
        # Check if the last key in the dictionary has an incomplete value
        if not self.stack or not isinstance(self.stack[0], dict):
            return False

        # Look at the last characters in the string for clues
        last_part = self.json_string[max(0, self.index - 50):self.index]
        # Strip trailing whitespace
        last_part_stripped = last_part.rstrip()

        # If the last non-whitespace character is a colon, we're definitely in property parsing
        if last_part_stripped and last_part_stripped[-1] == ':':
            return True

        # If we have a colon without a following complete value, we're in property parsing
        if ':' in last_part_stripped:
            colon_idx = last_part_stripped.rindex(':')
            after_colon = last_part_stripped[colon_idx + 1:].strip()
            # If there's barely anything after the colon, we're likely in property parsing
            if not after_colon or (len(after_colon) < 2 and not after_colon.endswith((',', '}'))):
                return True

        # Check for an open brace/bracket without matching close
        if '{' in last_part_stripped:
            open_idx = last_part_stripped.rindex('{')
            if '}' not in last_part_stripped[open_idx:]:
                return True

        if '[' in last_part_stripped:
            open_idx = last_part_stripped.rindex('[')
            if ']' not in last_part_stripped[open_idx:]:
                return True

        return False

    def _is_incomplete_value(self, value):
        """Check if a value is potentially incomplete."""
        # All simple primitive values are considered complete
        if not isinstance(value, (dict, list)):
            return False

        # Empty dict/list is incomplete if it appears at the end of input and was just opened
        if not value:
            return self._has_unclosed_braces()

        # For non-empty collections, check if they contain incomplete values
        if isinstance(value, dict):
            for k, v in value.items():
                if self._is_incomplete_value(v):
                    return True

        if isinstance(value, list):
            # Check last element of list for incompleteness
            if value and self._is_incomplete_value(value[-1]):
                return True

        return False

    def _has_empty_object_marker(self):
        """Check if there's an empty object marker in the recent input."""
        # Look for a '{' without a matching '}'
        last_part = self.json_string[max(0, self.index - 20):self.index]
        return '{' in last_part and '}' not in last_part[last_part.rfind('{'):]

    def _has_empty_array_marker(self):
        """Check if there's an empty array marker in the recent input."""
        # Look for a '[' without a matching ']'
        last_part = self.json_string[max(0, self.index - 20):self.index]
        return '[' in last_part and ']' not in last_part[last_part.rfind('['):]
