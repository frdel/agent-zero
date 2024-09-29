import glob
import os
import hashlib
import json
from typing import Any, Dict, Literal, TypedDict
from langchain_community.document_loaders import (
    CSVLoader,
    JSONLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
)
from python.helpers import files
from python.helpers.log import LogItem

text_loader_kwargs = {"autodetect_encoding": True}


class KnowledgeImport(TypedDict):
    file: str
    checksum: str
    ids: list[str]
    state: Literal["changed", "original", "removed"]
    documents: list[Any]


def calculate_checksum(file_path: str) -> str:
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()


def load_knowledge(
    log_item: LogItem | None, knowledge_dir: str, index: Dict[str, KnowledgeImport]
) -> Dict[str, KnowledgeImport]:
    knowledge_dir = files.get_abs_path("knowledge",knowledge_dir)

    from python.helpers.memory import Memory

    # Mapping file extensions to corresponding loader classes
    file_types_loaders = {
        "txt": TextLoader,
        "pdf": PyPDFLoader,
        "csv": CSVLoader,
        "html": UnstructuredHTMLLoader,
        "json": JSONLoader,
        "md": UnstructuredMarkdownLoader,
    }

    cnt_files = 0
    cnt_docs = 0

    for area in Memory.Area:
        subdir = files.get_abs_path(knowledge_dir, area.value)

        if not os.path.exists(subdir):
            os.makedirs(subdir)
            continue

        # Fetch all files in the directory with specified extensions
        kn_files = glob.glob(subdir + "/**/*", recursive=True)
        if kn_files:
            print(f"Found {len(kn_files)} knowledge files in {subdir}, processing...")
            if log_item:
                log_item.stream(
                    progress=f"\nFound {len(kn_files)} knowledge files in {subdir}, processing...",
                )

        for file_path in kn_files:
            ext = file_path.split(".")[-1].lower()
            if ext in file_types_loaders:
                checksum = calculate_checksum(file_path)
                file_key = file_path  # os.path.relpath(file_path, knowledge_dir)

                # Load existing data from the index or create a new entry
                file_data = index.get(file_key, {})

                if file_data.get("checksum") == checksum:
                    file_data["state"] = "original"
                else:
                    file_data["state"] = "changed"

                if file_data["state"] == "changed":
                    file_data["checksum"] = checksum
                    loader_cls = file_types_loaders[ext]
                    loader = loader_cls(
                        file_path,
                        **(
                            text_loader_kwargs
                            if ext in ["txt", "csv", "html", "md"]
                            else {}
                        ),
                    )
                    file_data["documents"] = loader.load_and_split()
                    for doc in file_data["documents"]:
                        doc.metadata["area"] = area.value
                    cnt_files += 1
                    cnt_docs += len(file_data["documents"])
                    # print(f"Imported {len(file_data['documents'])} documents from {file_path}")

                # Update the index
                index[file_key] = file_data  # type: ignore

    # loop index where state is not set and mark it as removed
    for file_key, file_data in index.items():
        if not file_data.get("state", ""):
            index[file_key]["state"] = "removed"

    print(f"Processed {cnt_docs} documents from {cnt_files} files.")
    if log_item:
        log_item.stream(
            progress=f"\nProcessed {cnt_docs} documents from {cnt_files} files."
        )
    return index
