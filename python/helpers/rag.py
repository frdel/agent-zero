from typing import List

from langchain_core.documents import Document
from python.helpers import files

from langchain_community.document_loaders import (
    CSVLoader,
    JSONLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
)

# def extract_file(path: str) -> List[Document]:
#     pass  # TODO finish implementing

def extract_text(content: bytes, chunk_size: int = 128) -> List[str]:
    result = []

    def is_binary_chunk(chunk: bytes) -> bool:
        # Check for high concentration of control chars
        try:
            text = chunk.decode("utf-8", errors="ignore")
            control_chars = sum(1 for c in text if ord(c) < 32 and c not in "\n\r\t")
            return control_chars / len(text) > 0.3
        except UnicodeDecodeError:
            return True

    # Process the content in overlapping chunks to handle boundaries
    pos = 0
    while pos < len(content):
        # Get current chunk with overlap
        chunk_end = min(pos + chunk_size, len(content))

        # Add overlap to catch word boundaries, unless at end of content
        if chunk_end < len(content):
            # Look ahead for next newline or space to avoid splitting words
            for i in range(chunk_end, min(chunk_end + 100, len(content))):
                if content[i : i + 1] in [b" ", b"\n", b"\r"]:
                    chunk_end = i + 1
                    break

        chunk = content[pos:chunk_end]

        if is_binary_chunk(chunk):
            if not result or result[-1] != "[BINARY]":
                result.append("[BINARY]")
        else:
            try:
                text = chunk.decode("utf-8", errors="ignore").strip()
                if text:  # Only add non-empty text chunks
                    result.append(text)
            except UnicodeDecodeError:
                if not result or result[-1] != "[BINARY]":
                    result.append("[BINARY]")

        pos = chunk_end

    return result
