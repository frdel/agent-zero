import tiktoken

APPROX_BUFFER = 1.1

def count_tokens(text: str, encoding_name="cl100k_base") -> int:
        if not text:
            return 0
    
        # Get the encoding
        encoding = tiktoken.get_encoding(encoding_name)

        # Encode the text and count the tokens
        tokens = encoding.encode(text)
        token_count = len(tokens)

        return token_count

def approximate_tokens(text: str, ) -> int:
    return int(count_tokens(text) * APPROX_BUFFER)