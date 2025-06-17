from dataclasses import dataclass, field
import json
from typing import Any, Literal, Optional, Dict
import uuid
from collections import OrderedDict  # Import OrderedDict
from datetime import datetime, timezone

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
        print(f"DEBUG: LogItem __post_init__ CALLED for item.no: {self.no}. Initial self.kvps: {self.kvps}")
        self.guid = self.log.guid
        if self.kvps is None: # Should be initialized by Log.log before __post_init__
            self.kvps = OrderedDict()
            print(f"DEBUG: LogItem __post_init__ self.kvps was None, initialized for item.no: {self.no}")

        if 'timestamp' not in self.kvps:
            # new_timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z') # Disabled timestamp generation
            # self.kvps['timestamp'] = new_timestamp # Disabled timestamp generation
            # print(f"DEBUG: LogItem __post_init__ 'timestamp' key NOT FOUND. ADDED timestamp for item.no: {self.no} with {new_timestamp}. self.kvps is now: {self.kvps}") # Disabled
            print(f"DEBUG: LogItem __post_init__ 'timestamp' key NOT FOUND. Timestamp generation DISABLED. item.no: {self.no}")
        else:
            print(f"DEBUG: LogItem __post_init__ 'timestamp' key FOUND for item.no: {self.no}. Value: {self.kvps.get('timestamp')}. self.kvps: {self.kvps}")

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
        # Use OrderedDict if kvps is provided
        if kvps is not None:
            kvps = OrderedDict(kvps)
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
        print(f"DEBUG: _update_item START for no: {no}. Original item.kvps: {item.kvps}")
        print(f"DEBUG: _update_item incoming args - type: {type}, heading: {heading}, content: {content}, kvps: {kvps}, temp: {temp}, update_progress: {update_progress}, kwargs: {kwargs}")

        if type is not None:
            item.type = type
        if update_progress is not None:
            item.update_progress = update_progress
        if heading is not None:
            item.heading = heading
        if content is not None:
            item.content = content

        # Check if incoming kvps will overwrite an existing timestamp
        if kvps is not None:
            print(f"DEBUG: _update_item item.no {no}: item.kvps BEFORE OrderedDict(kvps) update: {item.kvps.get('timestamp') if item.kvps else 'N/A'}")
            item.kvps = OrderedDict(kvps)  # Use OrderedDict to keep the order
            print(f"DEBUG: _update_item item.no {no}: item.kvps AFTER OrderedDict(kvps) update: {item.kvps.get('timestamp')}. Incoming kvps was: {kvps}")
        else:
            print(f"DEBUG: _update_item item.no {no}: incoming kvps is None. item.kvps.timestamp remains: {item.kvps.get('timestamp') if item.kvps else 'N/A'}")

        if temp is not None:
            item.temp = temp

        if kwargs:
            if item.kvps is None: # Should be initialized by __post_init__ if Log.log passes None
                item.kvps = OrderedDict()
                print(f"DEBUG: _update_item item.no {no}: item.kvps was None, initialized before adding kwargs.")
            
            if 'timestamp' in kwargs:
                print(f"DEBUG: _update_item item.no {no}: 'timestamp' found in kwargs: {kwargs['timestamp']}. Current item.kvps.timestamp: {item.kvps.get('timestamp') if item.kvps else 'N/A'}")
            
            for k, v in kwargs.items():
                item.kvps[k] = v
            print(f"DEBUG: _update_item item.no {no}: item.kvps AFTER kwargs update: {item.kvps.get('timestamp') if item.kvps else 'N/A'}. kwargs were: {kwargs}")
        
        print(f"DEBUG: _update_item END for item.no: {no}. Final item.kvps.timestamp: {item.kvps.get('timestamp') if item.kvps else 'N/A'}")
        self.updates += [item.no]
        self._update_progress_from_item(item)

    def set_progress(self, progress: str, no: int = 0, active: bool = True):
        self.progress = progress
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
            
