class DirtyJson:
    def __init__(self):
        self._reset()

    def _reset(self):
        self.json_string = ""
        self.index = 0
        self.current_char = None
        self.result = None
        self.stack = []

    @staticmethod
    def parse_string(json_string):
        parser = DirtyJson()
        return parser.parse(json_string)
    
    def parse(self, json_string):
        self._reset()
        self.json_string = json_string
        self.index = self.index_of_first_brace(self.json_string)
        if self.index == -1:
            raise ValueError("No opening brace found in input string.")
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
        while self.current_char is not None and self.current_char.isspace():
            self._advance()

    def _parse(self):
        if self.result is None:
            self.result = self._parse_value()
        else:
            self._continue_parsing()

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
        if self.current_char == '{':
            return self._parse_object()
        elif self.current_char == '[':
            return self._parse_array()
        elif self.current_char in ['"', "'", "`"]:
            return self._parse_string()
        elif self.current_char and (self.current_char.isdigit() or self.current_char in ['-', '+']):
            return self._parse_number()
        elif self._match("true"):
            return True
        elif self._match('false'):
            return False
        elif self._match('null'):
            return None
        else:
            raise ValueError(f"Unexpected character {self.current_char} at position {self.index}")

    def _match(self, text: str) -> bool:
        cnt = len(text)
        if self._peek(cnt).lower() == text.lower():
            self._advance(cnt)
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
            if self.current_char == '}':
                self._advance()
                self.stack.pop()
                return
            key = self._parse_key()
            self._skip_whitespace()

            if self.current_char != ':':
                raise ValueError(f"Expected ':' after key at position {self.index}, got '{self.current_char}'")
            self._advance()  # Skip colon
            value = self._parse_value()
            self.stack[-1][key] = value
            self._skip_whitespace()
            if self.current_char == ',':
                self._advance()
            elif self.current_char == '}':
                continue
            else:
                raise ValueError(f"Expected ',' or '}}' after value at position {self.index}, got '{self.current_char}'")

    def _parse_key(self):
        self._skip_whitespace()
        if self.current_char in ['"', "'"]:
            return self._parse_string()
        else:
            return self._parse_unquoted_key()

    def _parse_unquoted_key(self):
        self._skip_whitespace()
        result = ""
        if not (self.current_char.isalpha() or self.current_char == '_'): # type: ignore
            raise ValueError(f"Invalid start of unquoted key at position {self.index}, got '{self.current_char}'")
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'):
            result += self.current_char
            self._advance()
        if not result:
            raise ValueError(f"Expected key at position {self.index}")
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
            if self.current_char == ']':
                self._advance()
                self.stack.pop()
                return
            value = self._parse_value()
            self.stack[-1].append(value)
            self._skip_whitespace()
            if self.current_char == ',':
                self._advance()
            elif self.current_char == ']':
                continue
            else:
                raise ValueError(f"Expected ',' or ']' after value at position {self.index}, got '{self.current_char}'")

    def _parse_string(self):
        result = ""
        quote_char = self.current_char
        self._advance()  # Skip opening quote
        while self.current_char is not None and self.current_char != quote_char:
            if self.current_char == '\\':
                self._advance()
                if self.current_char in ['"', "'", '\\', '/', 'b', 'f', 'n', 'r', 't']:
                    escaped_char = {
                        '"': '"',
                        "'": "'",
                        '\\': '\\',
                        '/': '/',
                        'b': '\b',
                        'f': '\f',
                        'n': '\n',
                        'r': '\r',
                        't': '\t'
                    }[self.current_char]
                    result += escaped_char
                    self._advance()
                elif self.current_char == 'u':
                    unicode_char = ""
                    self._advance()  # Skip 'u'
                    for _ in range(4):
                        if self.current_char is None:
                            raise ValueError("Unterminated Unicode escape sequence in string")
                        unicode_char += self.current_char
                        self._advance()
                    try:
                        result += chr(int(unicode_char, 16))
                    except ValueError:
                        raise ValueError(f"Invalid Unicode escape sequence '\\u{unicode_char}'")
                else:
                    raise ValueError(f"Invalid escape character '\\{self.current_char}' at position {self.index}")
            else:
                result += self.current_char
                self._advance()
        if self.current_char == quote_char:
            self._advance()  # Skip closing quote
            return result
        else:
            raise ValueError(f"Unterminated string starting at position {self.index}")

    def _parse_multiline_string(self):
        result = ""
        quote_char = self.current_char
        self._advance(3)  # Skip the starting triple quotes
        while self.current_char is not None:
            if self.current_char == quote_char and self._peek(2) == quote_char * 2: # type: ignore
                self._advance(3)  # Skip the ending triple quotes
                break
            result += self.current_char
            self._advance()
        else:
            raise ValueError("Unterminated multiline string")
        return result

    def _parse_number(self):
        number_str = ""
        start_index = self.index
        while self.current_char is not None and (self.current_char.isdigit() or self.current_char in ['-', '+', '.', 'e', 'E']):
            number_str += self.current_char
            self._advance()
        try:
            if '.' in number_str or 'e' in number_str or 'E' in number_str:
                return float(number_str)
            else:
                return int(number_str)
        except ValueError:
            raise ValueError(f"Invalid number '{number_str}' at position {start_index}")

    def _parse_unquoted_string(self):
        self._skip_whitespace()
        result = ""
        while self.current_char is not None and not self.current_char.isspace() and self.current_char not in [',', '}', ']', ':']:
            result += self.current_char
            self._advance()
        if not result:
            raise ValueError(f"Expected value at position {self.index}")
        return result

    def _peek(self, n):
        peek_index = self.index
        result = ''
        for _ in range(n):
            if peek_index < len(self.json_string):
                result += self.json_string[peek_index]
                peek_index += 1
            else:
                break
        return result

    def index_of_first_brace(self, input_str: str) -> int:
        return input_str.find("{")
