from dataclasses import dataclass, field
import json
from typing import Any, Literal, Optional, Dict
import uuid
from collections import OrderedDict  # Import OrderedDict


Type = Literal[
    "agent",
    "code_exe",
    "error",
    "hint",
    "info",
    "progress",
    "response",
    "tool",
    "user",
    "util",
    "warning",
]


@dataclass
class LogItem:
    log: "Log"
    no: int
    type: str
    heading: str
    content: str
    temp: bool
    kvps: Optional[OrderedDict] = None  # Use OrderedDict for kvps
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
        **kwargs,
    ):
        if self.guid == self.log.guid:
            self.log.update_item(
                self.no,
                type=type,
                heading=heading,
                content=content,
                kvps=kvps,
                temp=temp,
                **kwargs,
            )

    def stream(self, heading: str | None = None, content: str | None = None, **kwargs):
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
        self.progress = ""
        self.progress_no = 0

    def log(
        self,
        type: Type,
        heading: str | None = None,
        content: str | None = None,
        kvps: dict | None = None,
        temp: bool | None = None,
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
            kvps=kvps,
            temp=temp or False,
        )
        self.logs.append(item)
        self.updates += [item.no]
        if heading and item.no >= self.progress_no:
            self.progress = heading
            self.progress_no = item.no
        return item

    def update_item(
        self,
        no: int,
        type: str | None = None,
        heading: str | None = None,
        content: str | None = None,
        kvps: dict | None = None,
        temp: bool | None = None,
        **kwargs,
    ):
        item = self.logs[no]
        if type is not None:
            item.type = type
        if heading is not None:
            item.heading = heading
            if no >= self.progress_no:
                self.progress = heading
                self.progress_no = no
        if content is not None:
            item.content = content
        if kvps is not None:
            item.kvps = OrderedDict(kvps)  # Use OrderedDict to keep the order

        if temp is not None:
            item.temp = temp

        if kwargs:
            if item.kvps is None:
                item.kvps = OrderedDict()  # Ensure kvps is an OrderedDict
            for k, v in kwargs.items():
                item.kvps[k] = v

        self.updates += [item.no]

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
        self.progress = ""
        self.progress_no = 0
