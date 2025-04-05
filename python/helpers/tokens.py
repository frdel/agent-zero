from typing import Literal
import tiktoken

APPROX_BUFFER = 1.1
TRIM_BUFFER = 0.8


def count_tokens(text: str, encoding_name="cl100k_base") -> int:
    if not text:
        return 0

    # Get the encoding
    encoding = tiktoken.get_encoding(encoding_name)

    # Encode the text and count the tokens
    tokens = encoding.encode(text)
    token_count = len(tokens)

    return token_count


def approximate_tokens(
    text: str,
) -> int:
    return int(count_tokens(text) * APPROX_BUFFER)


def trim_to_tokens(
    text: str,
    max_tokens: int,
    direction: Literal["start", "end"],
    ellipsis: str = "...",
) -> str:
    chars = len(text)
    tokens = count_tokens(text)

    if tokens <= max_tokens:
        return text

    approx_chars = int(chars * (max_tokens / tokens) * TRIM_BUFFER)

    if direction == "start":
        return text[:approx_chars] + ellipsis
    return ellipsis + text[chars - approx_chars : chars]
