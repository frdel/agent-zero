from dataclasses import dataclass, field
import json
from typing import Any, Literal, Optional, Dict
import uuid
from collections import OrderedDict  # Import OrderedDict
from python.helpers.strings import truncate_text_by_ratio
import copy

Type = Literal[
    "agent",
    "browser",
    "code_exe",
    "error",
    "hint",
    "info",
    "progress",
    "response",
    "tool",
    "input",
    "user",
    "util",
    "warning",
]

ProgressUpdate = Literal["persistent", "temporary", "none"]


HEADING_MAX_LEN: int = 120
CONTENT_MAX_LEN: int = 10000
KEY_MAX_LEN: int = 60
VALUE_MAX_LEN: int = 3000
PROGRESS_MAX_LEN: int = 120


def _truncate_heading(text: str | None) -> str:
    if text is None:
        return ""
    return truncate_text_by_ratio(str(text), HEADING_MAX_LEN, "...", ratio=1.0)

def _truncate_progress(text: str | None) -> str:
    if text is None:
        return ""
    return truncate_text_by_ratio(str(text), PROGRESS_MAX_LEN, "...", ratio=1.0)

def _truncate_key(text: str) -> str:
    return truncate_text_by_ratio(str(text), KEY_MAX_LEN, "...", ratio=1.0)

def _truncate_value(val: Any) -> Any:
    # If dict, recursively truncate each value
    if isinstance(val, dict):
        for k in list(val.keys()):
            val[k] = _truncate_value(val[k])
        return val
    # If list or tuple, recursively truncate each item
    if isinstance(val, list):
        for i in range(len(val)):
            val[i] = _truncate_value(val[i])
        return val
    if isinstance(val, tuple):
        return tuple(_truncate_value(x) for x in val)

    # Convert non-str values to json for consistent length measurement
    if isinstance(val, str):
        raw = val
    else:
        try:
            raw = json.dumps(val, ensure_ascii=False)
        except Exception:
            raw = str(val)

    if len(raw) <= VALUE_MAX_LEN:
        return val  # No truncation needed, preserve original type

    # Do a single truncation calculation
    removed = len(raw) - VALUE_MAX_LEN
    replacement = f"\n\n<< {removed} Characters hidden >>\n\n"
    truncated = truncate_text_by_ratio(raw, VALUE_MAX_LEN, replacement, ratio=0.3)
    return truncated

def _truncate_content(text: str | None) -> str:
    if text is None:
        return ""
    raw = str(text)
    if len(raw) <= CONTENT_MAX_LEN:
        return raw

    # Same dynamic replacement logic as value truncation
    removed = len(raw) - CONTENT_MAX_LEN
    while True:
        replacement = f"\n\n<< {removed} Characters hidden >>\n\n"
        truncated = truncate_text_by_ratio(raw, CONTENT_MAX_LEN, replacement, ratio=0.3)
        new_removed = len(raw) - (len(truncated) - len(replacement))
        if new_removed == removed:
            break
        removed = new_removed
    return truncated

@dataclass
class LogItem:
    log: "Log"
    no: int
    type: str
    heading: str
    content: str
    temp: bool
    update_progress: Optional[ProgressUpdate] = "persistent"
    kvps: Optional[OrderedDict] = None  # Use OrderedDict for kvps
    id: Optional[str] = None  # Add id field
    guid: str = ""

    def __post_init__(self):
        self.guid = self.log.guid

    def update(
        self,
        type: Type | None = None,
        heading: str | None = None,
        content: str | None = None,
        kvps: dict | None = None,
        temp: bool | None = None,
        update_progress: ProgressUpdate | None = None,
        **kwargs,
    ):
        if self.guid == self.log.guid:
            self.log._update_item(
                self.no,
                type=type,
                heading=heading,
                content=content,
                kvps=kvps,
                temp=temp,
                update_progress=update_progress,
                **kwargs,
            )

    def stream(
        self,
        heading: str | None = None,
        content: str | None = None,
        **kwargs,
    ):
        if heading is not None:
            self.update(heading=self.heading + heading)
        if content is not None:
            self.update(content=self.content + content)

        for k, v in kwargs.items():
            prev = self.kvps.get(k, "") if self.kvps else ""
            self.update(**{k: prev + v})

    def output(self):
        return {
            "no": self.no,
            "id": self.id,  # Include id in output
            "type": self.type,
            "heading": self.heading,
            "content": self.content,
            "temp": self.temp,
            "kvps": self.kvps,
        }


class Log:

    def __init__(self):
        self.guid: str = str(uuid.uuid4())
        self.updates: list[int] = []
        self.logs: list[LogItem] = []
        self.set_initial_progress()

    def log(
        self,
        type: Type,
        heading: str | None = None,
        content: str | None = None,
        kvps: dict | None = None,
        temp: bool | None = None,
        update_progress: ProgressUpdate | None = None,
        id: Optional[str] = None,  # Add id parameter
        **kwargs,
    ) -> LogItem:
        # Truncate heading and content
        heading = _truncate_heading(heading)
        content = _truncate_content(content)

        # Truncate kvps
        if kvps is not None:
            kvps = copy.deepcopy(kvps) # deep copy to avoid modifying the original kvps
            kvps = OrderedDict({
                _truncate_key(k): _truncate_value(v) for k, v in kvps.items()
            })
        # Apply truncation to kwargs merged into kvps later
        if kwargs is not None:
            kwargs = copy.deepcopy(kwargs) # deep copy to avoid modifying the original kwargs
        kwargs = { _truncate_key(k): _truncate_value(v) for k, v in (kwargs or {}).items() }

        # Ensure kvps is OrderedDict even if None
        if kvps is None:
            kvps = OrderedDict()

        item = LogItem(
            log=self,
            no=len(self.logs),
            type=type,
            heading=heading or "",
            content=content or "",
            kvps=OrderedDict({**(kvps or {}), **(kwargs or {})}),
            update_progress=(
                update_progress if update_progress is not None else "persistent"
            ),
            temp=temp if temp is not None else False,
            id=id,  # Pass id to LogItem
        )
        self.logs.append(item)
        self.updates += [item.no]
        self._update_progress_from_item(item)
        return item

    def _update_item(
        self,
        no: int,
        type: str | None = None,
        heading: str | None = None,
        content: str | None = None,
        kvps: dict | None = None,
        temp: bool | None = None,
        update_progress: ProgressUpdate | None = None,
        **kwargs,
    ):
        item = self.logs[no]
        # Apply truncation where necessary
        if type is not None:
            item.type = type

        if update_progress is not None:
            item.update_progress = update_progress

        if heading is not None:
            item.heading = _truncate_heading(heading)

        if content is not None:
            item.content = _truncate_content(content)

        if kvps is not None:
            kvps = copy.deepcopy(kvps) # deep copy to avoid modifying the original kvps
            item.kvps = OrderedDict({
                _truncate_key(k): _truncate_value(v) for k, v in kvps.items()
            })  # Ensure order

        if temp is not None:
            item.temp = temp

        if kwargs:
            kwargs = copy.deepcopy(kwargs) # deep copy to avoid modifying the original kwargs
            if item.kvps is None:
                item.kvps = OrderedDict()  # Ensure kvps is an OrderedDict
            for k, v in kwargs.items():
                item.kvps[_truncate_key(k)] = _truncate_value(v)


        self.updates += [item.no]
        self._update_progress_from_item(item)

    def set_progress(self, progress: str, no: int = 0, active: bool = True):
        self.progress = _truncate_progress(progress)
        if not no:
            no = len(self.logs)
        self.progress_no = no
        self.progress_active = active

    def set_initial_progress(self):
        self.set_progress("Waiting for input", 0, False)

    def output(self, start=None, end=None):
        if start is None:
            start = 0
        if end is None:
            end = len(self.updates)

        out = []
        seen = set()
        for update in self.updates[start:end]:
            if update not in seen:
                out.append(self.logs[update].output())
                seen.add(update)

        return out

    def reset(self):
        self.guid = str(uuid.uuid4())
        self.updates = []
        self.logs = []
        self.set_initial_progress()

    def _update_progress_from_item(self, item: LogItem):
        if item.heading and item.update_progress != "none":
            if item.no >= self.progress_no:
                self.set_progress(
                    item.heading,
                    (item.no if item.update_progress == "persistent" else -1),
                )
            
