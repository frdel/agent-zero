"""
Pure file operations for the text_editor plugin.

No agent/tool dependencies — only stdlib + tokens helper.
"""

import os
import stat
import tempfile
from typing import TypedDict

from helpers import tokens
from plugins._text_editor.helpers.context_patch import (
    apply_context_patch_with_metadata,
)

_BINARY_PEEK = 8192


# ------------------------------------------------------------------
# Binary detection
# ------------------------------------------------------------------

def is_binary(path: str) -> bool:
    """Detect binary file by checking for null bytes."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(_BINARY_PEEK)
        return b"\x00" in chunk
    except OSError:
        return False


# ------------------------------------------------------------------
# File metadata
# ------------------------------------------------------------------

class FileInfo(TypedDict):
    exists: bool
    is_file: bool
    realpath: str
    expanded: str
    mtime: float | None


def file_info(path: str) -> FileInfo:
    """Return file metadata for mtime tracking and path resolution."""
    path = os.path.expanduser(path)
    rp = os.path.realpath(path)
    exists = os.path.exists(path)
    is_file = os.path.isfile(path)
    mtime = None
    if exists:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            pass
    return FileInfo(
        exists=exists,
        is_file=is_file,
        realpath=rp,
        expanded=path,
        mtime=mtime,
    )


# ------------------------------------------------------------------
# Read
# ------------------------------------------------------------------

class ReadResult(TypedDict):
    content: str
    total_lines: int
    warnings: str
    error: str


def read_file(
    path: str,
    line_from: int = 1,
    line_to: int | None = None,
    max_line_tokens: int = 500,
    default_line_count: int = 100,
    max_total_read_tokens: int = 4000,
) -> ReadResult:
    """
    Read a text file and return numbered lines with token budgeting.

    Line numbers are 1-based (matching grep, sed, editors).
    line_from and line_to are both inclusive.
    None line_to defaults to line_from + default_line_count - 1.
    """
    path = os.path.expanduser(path)

    if not os.path.isfile(path):
        return ReadResult(
            content="", total_lines=0, warnings="",
            error="file not found",
        )

    if is_binary(path):
        return ReadResult(
            content="", total_lines=0, warnings="",
            error="file appears binary, use terminal instead",
        )

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except OSError as exc:
        return ReadResult(
            content="", total_lines=0, warnings="",
            error=str(exc),
        )

    total_lines = len(all_lines)
    line_from = max(line_from, 1)
    if line_to is None:
        line_to = line_from + default_line_count - 1
    line_to = min(line_to, total_lines)

    # Convert 1-based inclusive range to 0-based slice
    idx_from = line_from - 1
    idx_to = line_to  # slice is exclusive, line_to is inclusive 1-based
    selected = all_lines[idx_from:idx_to]
    num_width = len(str(line_to))

    warn_parts: list[str] = []
    cropped_lines: list[int] = []
    output_lines: list[str] = []
    running_tokens = 0
    trimmed_by_total = False

    for i, raw_line in enumerate(selected):
        line_no = line_from + i  # 1-based
        stripped = raw_line.rstrip("\n").rstrip("\r")
        line_tok = tokens.count_tokens(stripped)

        if line_tok > max_line_tokens:
            chars_per_tok = max(len(stripped) / line_tok, 1)
            keep_chars = int(max_line_tokens * chars_per_tok * tokens.TRIM_BUFFER)
            stripped = stripped[:keep_chars] + "..."
            cropped_lines.append(line_no)
            line_tok = max_line_tokens

        if running_tokens + line_tok > max_total_read_tokens:
            trimmed_by_total = True
            break

        running_tokens += line_tok
        output_lines.append(f"{line_no:>{num_width}} {stripped}")

    if cropped_lines:
        nums = " ".join(str(n) for n in cropped_lines)
        warn_parts.append(
            f"long lines {nums} cropped - use terminal for precise manipulation"
        )
    if trimmed_by_total:
        actual_end = line_from + len(output_lines)
        warn_parts.append(
            f"output trimmed at line {actual_end} due to token limit"
            " - use line_from/line_to for remaining"
        )

    warn_str = ""
    if warn_parts:
        warn_str = "\nwarning: " + "; ".join(warn_parts)

    return ReadResult(
        content="\n".join(output_lines),
        total_lines=total_lines,
        warnings=warn_str,
        error="",
    )


# ------------------------------------------------------------------
# Write
# ------------------------------------------------------------------

class WriteResult(TypedDict):
    total_lines: int
    error: str


def write_file(path: str, content: str | None) -> WriteResult:
    """Create or overwrite a file."""
    if content is None:
        content = ""
    path = os.path.expanduser(path)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        return WriteResult(total_lines=0, error=str(exc))

    total = content.count("\n") + (
        1 if content and not content.endswith("\n") else 0
    )
    return WriteResult(total_lines=total, error="")


# ------------------------------------------------------------------
# Patch
# ------------------------------------------------------------------

class PatchResult(TypedDict):
    total_lines: int
    edit_count: int
    error: str


class ContextPatchFileResult(TypedDict):
    total_lines: int
    hunk_count: int
    line_from: int
    line_to: int


class ExactReplaceFileResult(TypedDict):
    total_lines: int
    replacement_count: int
    line_from: int
    line_to: int


def validate_edits(edits: list | None) -> tuple[list[dict], str]:
    """
    Normalise and validate an edits array.

    Line numbers are 1-based (matching grep, sed, editors).
    Semantics (to is inclusive):
      {from:2, to:2, content:"x\\n"} - replace line 2
      {from:1, to:3, content:"x\\n"} - replace lines 1-3
      {from:2, to:2}                 - delete line 2
      {from:5}  or {from:5, to:-1}   - insert before line 5 (no deletion)

    Returns (parsed_edits, error_string). error_string is empty on success.
    """
    if not edits or not isinstance(edits, list):
        return [], "edits array is required"

    parsed: list[dict] = []
    for e in edits:
        if not isinstance(e, dict):
            return [], f"invalid edit entry: {e}"
        frm = int(e.get("from", 0))
        if frm < 1:
            return [], f"edit missing or invalid from (must be >= 1): {e}"
        # to == -1 or absent means pure insert (no lines removed)
        to = int(e.get("to", -1))
        is_insert = to < 0 or to < frm
        if is_insert:
            to = frm - 1  # normalise: marks zero-width range
        parsed.append({
            "from": frm,
            "to": to,
            "content": e.get("content", ""),
            "insert": is_insert,
        })

    parsed.sort(key=lambda x: (x["from"], 0 if x["insert"] else 1))
    for i in range(1, len(parsed)):
        prev, cur = parsed[i - 1], parsed[i]
        # Inserts at the same line don't overlap with each other or
        # with a replace that starts at the same line.
        if prev["insert"]:
            continue
        # prev is a replace/delete: its range is [from..to] inclusive
        if cur["from"] <= prev["to"]:
            return [], (
                f"overlapping edits: edit at {prev['from']}"
                f" (to {prev['to']}) and {cur['from']}"
                f" (to {cur['to']})"
            )

    return parsed, ""


def apply_patch(path: str, edits: list[dict]) -> int:
    """
    Apply sorted, validated edits by streaming to a temp file.

    Line numbers are 1-based. Edits use inclusive 'to'.
    Inserts have 'insert': True.
    Returns total line count after patching.
    """
    # Ensure content always ends with newline to prevent line merging
    for e in edits:
        if e["content"] and not e["content"].endswith("\n"):
            e["content"] += "\n"

    dir_name = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with (
            open(path, "r", encoding="utf-8", errors="replace") as src,
            os.fdopen(fd, "w", encoding="utf-8") as dst,
        ):
            edit_idx = 0
            line_no = 1  # 1-based
            total_written = 0
            last_line_unterminated = False

            for raw_line in src:
                # Process all inserts targeting this line first
                while (
                    edit_idx < len(edits)
                    and edits[edit_idx]["insert"]
                    and edits[edit_idx]["from"] == line_no
                ):
                    edit = edits[edit_idx]
                    if edit["content"]:
                        dst.write(edit["content"])
                        total_written += _count_content_lines(edit["content"])
                    edit_idx += 1

                # Check if current line falls in a replace/delete range
                if edit_idx < len(edits) and not edits[edit_idx]["insert"]:
                    edit = edits[edit_idx]
                    if edit["from"] <= line_no <= edit["to"]:
                        # Write replacement content once at range start
                        if line_no == edit["from"] and edit["content"]:
                            dst.write(edit["content"])
                            total_written += _count_content_lines(
                                edit["content"]
                            )
                        # Skip original line; advance edit at range end
                        if line_no == edit["to"]:
                            edit_idx += 1
                        line_no += 1
                        continue

                dst.write(raw_line)
                total_written += 1
                line_no += 1
                last_line_unterminated = not raw_line.endswith("\n")

            # Remaining edits past end of file
            while edit_idx < len(edits):
                edit = edits[edit_idx]
                if edit["content"]:
                    # Terminate an unterminated last line so appended
                    # content starts on its own line instead of merging.
                    if last_line_unterminated:
                        dst.write("\n")
                        last_line_unterminated = False
                    dst.write(edit["content"])
                    total_written += _count_content_lines(edit["content"])
                edit_idx += 1

        _replace_file(tmp_path, path)
        return total_written
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def patch_file(path: str, edits: list | None) -> PatchResult:
    """Validate and apply edits to a file."""
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        return PatchResult(total_lines=0, edit_count=0, error="file not found")

    parsed, err = validate_edits(edits)
    if err:
        return PatchResult(total_lines=0, edit_count=0, error=err)

    try:
        total = apply_patch(path, parsed)
    except Exception as exc:
        return PatchResult(total_lines=0, edit_count=0, error=str(exc))

    return PatchResult(total_lines=total, edit_count=len(parsed), error="")


def apply_context_patch_file(path: str, patch_text: str) -> ContextPatchFileResult:
    """Apply a context patch to an existing text file."""
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        raise FileNotFoundError("file not found")

    with open(path, "r", encoding="utf-8", errors="replace") as src:
        content = src.read()

    result = apply_context_patch_with_metadata(content, patch_text)
    dir_name = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as dst:
            dst.write(result.content)
        _replace_file(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return ContextPatchFileResult(
        total_lines=_count_content_lines(result.content),
        hunk_count=result.hunk_count,
        line_from=result.line_from,
        line_to=result.line_to,
    )


def apply_exact_replace_file(
    path: str, old_text: str, new_text: str
) -> ExactReplaceFileResult:
    """Replace exactly one text span in an existing text file."""
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        raise FileNotFoundError("file not found")
    if not old_text:
        raise ValueError("old_text is required for exact replace")

    with open(path, "r", encoding="utf-8", errors="replace") as src:
        content = src.read()

    match_count = content.count(old_text)
    if match_count == 0:
        raise ValueError("old_text not found")
    if match_count > 1:
        raise ValueError(
            f"old_text matched {match_count} times; provide a longer exact span"
        )
    if old_text == new_text:
        raise ValueError("old_text and new_text are identical")

    start = content.index(old_text)
    line_from = content[:start].count("\n") + 1
    line_to = line_from + max(_count_content_lines(old_text) - 1, 0)
    new_content = content.replace(old_text, new_text, 1)

    dir_name = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as dst:
            dst.write(new_content)
        _replace_file(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return ExactReplaceFileResult(
        total_lines=_count_content_lines(new_content),
        replacement_count=1,
        line_from=line_from,
        line_to=line_to,
    )


# ------------------------------------------------------------------
# Internal
# ------------------------------------------------------------------

def _replace_file(tmp_path: str, path: str) -> None:
    """Keep the existing file's access when publishing a patched version."""
    original = os.stat(path)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        os.chown(tmp_path, original.st_uid, original.st_gid)
    os.chmod(tmp_path, stat.S_IMODE(original.st_mode))
    os.replace(tmp_path, path)


def _count_content_lines(content: str) -> int:
    return content.count("\n") + (
        1 if content and not content.endswith("\n") else 0
    )
