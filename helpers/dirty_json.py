import json

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
    def __init__(self):
        self._reset()

    def _reset(self):
        self.json_string = ""
        self.index = 0
        self.current_char = None
        self.result = None
        self.stack = []
        self.completed = False
        self._parsing_started = False

    def _pop_stack(self, root_closed: bool = False):
        """Pop from the parsing stack and mark completed only on an explicit root close."""
        self.stack.pop()
        if root_closed and self._parsing_started and not self.stack:
            self.completed = True

    @staticmethod
    def parse_string(json_string):
        parser = DirtyJson()
        return parser.parse(json_string)

    def parse(self, json_string):
        self._reset()
        self.json_string = json_string

        # Add bounds checking to prevent IndexError
        if not json_string:
            # Return None for empty strings
            return None

        self.index = self.get_start_pos(self.json_string)

        # Ensure index is within bounds
        if self.index >= len(self.json_string):
            # If start position is beyond string length, return None
            return None

        self.current_char = self.json_string[self.index]
        self._parse()
        return self.result

    def feed(self, chunk):
        self.json_string += chunk
        if not self.current_char and self.json_string:
            self.current_char = self.json_string[0]
        self._parse()
        return self.result

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
        if self.completed and not self.stack:
            return
        if self.result is None:
            self.result = self._parse_value()
        else:
            self._continue_parsing()

    def _continue_parsing(self):
        while self.current_char is not None:
            if self.completed and not self.stack:
                return
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
            # Only treat doubled braces as a wrapper at the root; nested objects
            # must keep their closing braces paired correctly.
            if not self.stack and self._peek(1) == "{":  # Handle {{
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
        self._parsing_started = True
        self._parse_object_content()
        return obj

    def _parse_object_content(self):
        while self.current_char is not None:
            self._skip_whitespace()
            if self.current_char == "}":
                # Root-level wrapper outputs may end in "}}"; nested objects must
                # still close one brace at a time.
                if len(self.stack) == 1 and self._peek(1) == "}":  # Handle }}
                    self._advance(2)
                else:
                    self._advance()
                self._pop_stack(root_closed=True)
                return
            if self.current_char is None:
                self._pop_stack()
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
                    self._pop_stack()
                    return  # End of input reached after value
                continue

    def _parse_key(self):
        self._skip_whitespace()
        if self.current_char in ['"', "'"]:
            return self._parse_string(is_key=True)
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
        self._parsing_started = True
        self._parse_array_content()
        return arr

    def _parse_array_content(self):
        while self.current_char is not None:
            self._skip_whitespace()
            if self.current_char == "]":
                self._advance()
                self._pop_stack(root_closed=True)
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
                    self._pop_stack(root_closed=True)
                    return
            elif self.current_char != "]":
                self._pop_stack()
                return

    def _parse_string(self, is_key: bool = False):
        result = ""
        quote_char = self.current_char
        self._advance()  # Skip opening quote
        while self.current_char is not None:
            if self.current_char == quote_char:
                if self._is_closing_quote(is_key):
                    break
                result += self.current_char
                self._advance()
                continue

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

    def _is_closing_quote(self, is_key: bool) -> bool:
        next_index = self._skip_padding_from(self.index + 1)
        if next_index >= len(self.json_string):
            return True

        next_char = self.json_string[next_index]
        if is_key:
            return next_char in [":", ",", "}", "]"]

        if next_char in [",", "}", "]"]:
            return True

        return self._looks_like_missing_comma_before_key(next_index)

    def _looks_like_missing_comma_before_key(self, index: int) -> bool:
        if not self.stack or not isinstance(self.stack[-1], dict):
            return False
        if index >= len(self.json_string) or self.json_string[index] not in ['"', "'"]:
            return False

        quote_char = self.json_string[index]
        index += 1
        while index < len(self.json_string):
            char = self.json_string[index]
            if char == "\\":
                index += 2
                continue
            if char == quote_char:
                next_index = self._skip_padding_from(index + 1)
                return (
                    next_index < len(self.json_string)
                    and self.json_string[next_index] == ":"
                )
            if char in ["\n", "\r", "{", "}", "[", "]", ","]:
                return False
            index += 1

        return False

    def _skip_padding_from(self, index: int) -> int:
        while index < len(self.json_string):
            char = self.json_string[index]
            if char.isspace():
                index += 1
            elif char == "/" and index + 1 < len(self.json_string):
                next_char = self.json_string[index + 1]
                if next_char == "/":
                    index += 2
                    while index < len(self.json_string) and self.json_string[index] != "\n":
                        index += 1
                elif next_char == "*":
                    end = self.json_string.find("*/", index + 2)
                    if end == -1:
                        return len(self.json_string)
                    index = end + 2
                else:
                    break
            else:
                break
        return index

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
