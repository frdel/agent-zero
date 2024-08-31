from dataclasses import dataclass
from typing import Optional, Dict
import uuid

@dataclass
class LogItem:
    no: int
    type: str
    heading: str
    content: str
    kvps: Optional[Dict] = None
    

class Log:

    guid = uuid.uuid4()
    version: int = 0
    last_updated: int = 0
    logs: list = []
    
    def __init__(self, type: str="placeholder", heading: str="", content: str="", kvps: dict|None = None):
        self.item = Log.log(type, heading, content, kvps)  # create placeholder log item that will be updated

    def update(self, type: Optional[str] = None, heading: str|None = None, content: str|None = None, kvps: dict|None = None):
        Log.edit(self.item.no, type=type, heading=heading, content=content, kvps=kvps)

    @staticmethod
    def reset():
        Log.guid = uuid.uuid4()
        Log.version = 0
        Log.last_updated = 0
        Log.logs = []
    
    @staticmethod    
    def log(type: str, heading: str|None = None, content: str|None = None, kvps: dict|None = None):
        item = LogItem(len(Log.logs), type, heading or "", content or "", kvps)
        Log.logs.append(item)
        Log.last_updated = item.no
        Log.version += 1
        return item
    
    @staticmethod
    def edit(no: int, type: Optional[str] = None, heading: str|None = None, content: str|None = None, kvps: dict|None = None):
        if 0 <= no < len(Log.logs):
            item = Log.logs[no]
            if type is not None:
                item.type = type
            if heading is not None:
                item.heading = heading
            if content is not None:
                item.content = content
            if kvps is not None:
                item.kvps = kvps

            Log.last_updated = no
            Log.version += 1
        else:
            raise IndexError("Log item number out of range")
