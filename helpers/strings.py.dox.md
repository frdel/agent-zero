# strings.py DOX

## Purpose

- Own the `strings.py` helper module.
- This module sanitizes, formats, truncates, and expands framework string content.
- Keep this file-level DOX profile synchronized with `strings.py` because this directory is intentionally flat.

## Ownership

- `strings.py` owns the runtime implementation.
- `strings.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Top-level functions:
- `sanitize_string(s: str, encoding: str=...) -> str`
- `calculate_valid_match_lengths(first: bytes | str, second: bytes | str, deviation_threshold: int=..., deviation_reset: int=..., ignore_patterns: list[bytes | str]=..., debug: bool=...) -> tuple[int, int]`
- `format_key(key: str) -> str`: Format a key string to be more readable.
- `dict_to_text(d: dict) -> str`
- `truncate_text(text: str, length: int, at_end: bool=..., replacement: str=...) -> str`
- `truncate_text_by_ratio(text: str, threshold: int, replacement: str=..., ratio: float=...) -> str`: Truncate text with replacement at a specified ratio position.
- `replace_file_includes(text: str, placeholder_pattern: str=...) -> str`

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem reads, filesystem deletion.
- Imported dependency areas include: `helpers`, `re`, `sys`, `time`.

## Key Concepts

- `helpers.files` is imported inside `replace_file_includes`, its only consumer, because `helpers.files` imports `sanitize_string` back from this module mid-file; keeping the import deferred avoids a startup import cycle.
- Important called helpers/classes observed in the source: `s.encode.decode`, `join`, `join.rstrip`, `re.sub`, `skip_ignored_patterns`, `match.group`, `s.encode`, `sys.stdout.write`, `sys.stdout.flush`, `time.sleep`, `c.isupper`, `result.islower`, `word.capitalize`, `files.fix_dev_path`, `files.read_file`, `re.match`, `formatted.split`, `c.isalnum`, `format_key`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_model_search.py`
  - `tests/test_whatsapp_number_utils.py`

## Child DOX Index

No child DOX files.
