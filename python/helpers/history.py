from abc import abstractmethod
from python.helpers import tokens

class Record():
    def __init__(self):    
        pass

    @abstractmethod
    def get_tokens(self) -> int:
        pass

class Message(Record):
    def __init__(self):
        self.segments: list[str]
        self.human: bool


class Monologue:
    def __init__(self):
        self.summary: str = ""
        self.messages: list[Message] = []

    def finish(self):
        pass


class History:
    def __init__(self):
        self.monologues: list[Monologue] = []
        self.messages: list[Message] = []
        self.start_monologue()

    def current_monologue(self):
        return self.monologues[-1]

    def start_monologue(self):
        if self.monologues:
            self.current_monologue().finish()
        self.monologues.append(Monologue())
        return self.current_monologue()
