from abc import abstractmethod
import asyncio
from collections import OrderedDict
import json
import math
from typing import Coroutine, Literal, TypedDict, cast
from python.helpers import messages, tokens, settings, call_llm
from enum import Enum
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

BULK_MERGE_COUNT = 3
TOPICS_KEEP_COUNT = 3
CURRENT_TOPIC_RATIO = 0.5
HISTORY_TOPIC_RATIO = 0.3
HISTORY_BULK_RATIO = 0.2
TOPIC_COMPRESS_RATIO = 0.65
LARGE_MESSAGE_TO_TOPIC_RATIO = 0.25

MessageContent = (
    list["MessageContent"]
    | OrderedDict[str, "MessageContent"]
    | list[OrderedDict[str, "MessageContent"]]
    | str
    | list[str]
)


class OutputMessage(TypedDict):
    ai: bool
    content: MessageContent


class Record:
    def __init__(self):
        pass

    def get_tokens(self) -> int:
        out = self.output_text()
        return tokens.approximate_tokens(out)

    @abstractmethod
    async def compress(self) -> bool:
        pass

    @abstractmethod
    def output(self) -> list[OutputMessage]:
        pass

    @abstractmethod
    async def summarize(self) -> str:
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        pass

    @staticmethod
    def from_dict(data: dict, history: "History"):
        cls = data["_cls"]
        return globals()[cls].from_dict(data, history=history)

    def output_langchain(self):
        return output_langchain(self.output())

    def output_text(self, human_label="user", ai_label="ai"):
        return output_text(self.output(), ai_label, human_label)


class Message(Record):
    def __init__(self, ai: bool, content: MessageContent):
        self.ai = ai
        self.content = content
        self.summary: MessageContent = ""

    async def compress(self):
        return False

    def output(self):
        return [OutputMessage(ai=self.ai, content=self.summary or self.content)]

    def output_langchain(self):
        return output_langchain(self.output())

    def output_text(self, human_label="user", ai_label="ai"):
        return output_text(self.output(), ai_label, human_label)

    def to_dict(self):
        return {
            "_cls": "Message",
            "ai": self.ai,
            "content": self.content,
            "summary": self.summary,
        }

    @staticmethod
    def from_dict(data: dict, history: "History"):
        msg = Message(ai=data["ai"], content=data.get("content", "Content lost"))
        msg.summary = data.get("summary", "")
        return msg


class Topic(Record):
    def __init__(self, history: "History"):
        self.history = history
        self.summary: str = ""
        self.messages: list[Message] = []

    def add_message(self, ai: bool, content: MessageContent):
        msg = Message(ai=ai, content=content)
        self.messages.append(msg)
        return msg

    def output(self) -> list[OutputMessage]:
        if self.summary:
            return [OutputMessage(ai=False, content=self.summary)]
        else:
            msgs = [m for r in self.messages for m in r.output()]
            return group_outputs_abab(msgs)

    async def summarize(self):
        self.summary = await self.summarize_messages(self.messages)
        return self.summary

    async def compress_large_messages(self) -> bool:
        set = settings.get_settings()
        msg_max_size = (
            set["chat_model_ctx_length"]
            * set["chat_model_ctx_history"]
            * HISTORY_TOPIC_RATIO
            * LARGE_MESSAGE_TO_TOPIC_RATIO
        )
        large_msgs = []
        for m in (m for m in self.messages if not m.summary):
            out = m.output()
            text = output_text(out)
            tok = tokens.approximate_tokens(text)
            leng = len(text)
            if tok > msg_max_size:
                large_msgs.append((m, tok, leng, out))
        large_msgs.sort(key=lambda x: x[1], reverse=True)
        for msg, tok, leng, out in large_msgs:
            trim_to_chars = leng * (msg_max_size / tok)
            trunc = messages.truncate_dict_by_ratio(
                self.history.agent,
                out[0]["content"],
                trim_to_chars * 1.15,
                trim_to_chars * 0.85,
            )
            msg.summary = trunc

            return True
        return False

    async def compress(self) -> bool:
        compress = await self.compress_large_messages()
        if not compress:
            compress = await self.compress_attention()
        return compress

    async def compress_attention(self) -> bool:

        if len(self.messages) > 2:
            cnt_to_sum = math.ceil((len(self.messages) - 2) * TOPIC_COMPRESS_RATIO)
            msg_to_sum = self.messages[1 : cnt_to_sum + 1]
            summary = await self.summarize_messages(msg_to_sum)
            sum_msg_content = self.history.agent.parse_prompt(
                "fw.msg_summary.md", summary=summary
            )
            sum_msg = Message(False, sum_msg_content)
            self.messages[1 : cnt_to_sum + 1] = [sum_msg]
            return True
        return False

    async def summarize_messages(self, messages: list[Message]):
        msg_txt = [m.output_text() for m in messages]
        summary = await self.history.agent.call_utility_model(
            system=self.history.agent.read_prompt("fw.topic_summary.sys.md"),
            message=self.history.agent.read_prompt(
                "fw.topic_summary.msg.md", content=msg_txt
            ),
        )
        return summary

    def to_dict(self):
        return {
            "_cls": "Topic",
            "summary": self.summary,
            "messages": [m.to_dict() for m in self.messages],
        }

    @staticmethod
    def from_dict(data: dict, history: "History"):
        topic = Topic(history=history)
        topic.summary = data["summary"]
        topic.messages = [
            Message.from_dict(m, history=history) for m in data["messages"]
        ]
        return topic


class Bulk(Record):
    def __init__(self, history: "History"):
        self.history = history
        self.summary: str = ""
        self.records: list[Record] = []

    def output(
        self, human_label: str = "user", ai_label: str = "ai"
    ) -> list[OutputMessage]:
        if self.summary:
            return [OutputMessage(ai=False, content=self.summary)]
        else:
            msgs = [m for r in self.records for m in r.output()]
            return group_outputs_abab(msgs)

    async def compress(self):
        return False

    async def summarize(self):
        self.summary = await self.history.agent.call_utility_model(
            system=self.history.agent.read_prompt("fw.topic_summary.sys.md"),
            message=self.history.agent.read_prompt(
                "fw.topic_summary.msg.md", content=self.output_text()
            ),
        )
        return self.summary

    def to_dict(self):
        return {
            "_cls": "Bulk",
            "summary": self.summary,
            "records": [r.to_dict() for r in self.records],
        }

    @staticmethod
    def from_dict(data: dict, history: "History"):
        bulk = Bulk(history=history)
        bulk.summary = data["summary"]
        cls = data["_cls"]
        bulk.records = [Record.from_dict(r, history=history) for r in data["records"]]
        return bulk


class History(Record):
    def __init__(self, agent):
        from agent import Agent

        self.bulks: list[Bulk] = []
        self.topics: list[Topic] = []
        self.current = Topic(history=self)
        self.agent: Agent = agent

    def is_over_limit(self):
        limit = get_ctx_size_for_history()
        total = self.get_tokens()
        return total > limit

    def get_bulks_tokens(self) -> int:
        return sum(record.get_tokens() for record in self.bulks)

    def get_topics_tokens(self) -> int:
        return sum(record.get_tokens() for record in self.topics)

    def get_current_topic_tokens(self) -> int:
        return self.current.get_tokens()

    def get_tokens(self) -> int:
        return (
            self.get_bulks_tokens()
            + self.get_topics_tokens()
            + self.get_current_topic_tokens()
        )

    def add_message(self, ai: bool, content: MessageContent):
        return self.current.add_message(ai, content=content)

    def new_topic(self):
        if self.current.messages:
            self.topics.append(self.current)
            self.current = Topic(history=self)

    def output(self) -> list[OutputMessage]:
        result: list[OutputMessage] = []
        result += [m for b in self.bulks for m in b.output()]
        result += [m for t in self.topics for m in t.output()]
        result += self.current.output()
        result = group_outputs_abab(result)
        return result

    @staticmethod
    def from_dict(data: dict, history: "History"):
        history.bulks = [Bulk.from_dict(b, history=history) for b in data["bulks"]]
        history.topics = [Topic.from_dict(t, history=history) for t in data["topics"]]
        history.current = Topic.from_dict(data["current"], history=history)
        return history

    def to_dict(self):
        return {
            "_cls": "History",
            "bulks": [b.to_dict() for b in self.bulks],
            "topics": [t.to_dict() for t in self.topics],
            "current": self.current.to_dict(),
        }

    def serialize(self):
        data = self.to_dict()
        return json.dumps(data)

    async def compress(self):
        compressed = False
        while True:
            curr, hist, bulk = (
                self.get_current_topic_tokens(),
                self.get_topics_tokens(),
                self.get_bulks_tokens(),
            )
            total = get_ctx_size_for_history()
            ratios = [
                (curr, CURRENT_TOPIC_RATIO, "current_topic"),
                (hist, HISTORY_TOPIC_RATIO, "history_topic"),
                (bulk, HISTORY_BULK_RATIO, "history_bulk"),
            ]
            ratios = sorted(ratios, key=lambda x: (x[0] / total) / x[1], reverse=True)
            compressed_part = False
            for ratio in ratios:
                if ratio[0] > ratio[1] * total:
                    over_part = ratio[2]
                    if over_part == "current_topic":
                        compressed_part = await self.current.compress()
                    elif over_part == "history_topic":
                        compressed_part = await self.compress_topics()
                    else:
                        compressed_part = await self.compress_bulks()
                    if compressed_part:
                        break

            if compressed_part:
                compressed = True
                continue
            else:
                return compressed

    async def compress_topics(self) -> bool:
        # summarize topics one by one
        for topic in self.topics:
            if not topic.summary:
                await topic.summarize()
                return True

        # move oldest topic to bulks and summarize
        for topic in self.topics:
            bulk = Bulk(history=self)
            bulk.records.append(topic)
            if topic.summary:
                bulk.summary = topic.summary
            else:
                await bulk.summarize()
            self.bulks.append(bulk)
            self.topics.remove(topic)
        return True

    async def compress_bulks(self):
        # merge bulks if possible
        compressed = await self.merge_bulks_by(BULK_MERGE_COUNT)
        # remove oldest bulk if necessary
        if not compressed:
            self.bulks.pop(0)
        return compressed

    async def merge_bulks_by(self, count: int):
        if len(self.bulks) > 0:
            return False
        bulks = await asyncio.gather(
            *[
                self.merge_bulks(self.bulks[i : i + count])
                for i in range(0, len(self.bulks), count)
            ]
        )
        self.bulks = bulks
        return True

    async def merge_bulks(self, bulks: list[Bulk]) -> Bulk:
        bulk = Bulk(history=self)
        bulk.records = cast(list[Record], bulks)
        await bulk.summarize()
        return bulk


def deserialize_history(json_data: str, agent) -> History:
    history = History(agent=agent)
    if json_data:
        data = json.loads(json_data)
        history = History.from_dict(data, history=history)
    return history


def get_ctx_size_for_history() -> int:
    set = settings.get_settings()
    return int(set["chat_model_ctx_length"] * set["chat_model_ctx_history"])


def serialize_output(output: OutputMessage, ai_label="ai", human_label="human"):
    return f'{ai_label if output["ai"] else human_label}: {serialize_content(output["content"])}'


def serialize_content(content: MessageContent) -> str:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content)
    except Exception as e:
        raise e


def group_outputs_abab(outputs: list[OutputMessage]) -> list[OutputMessage]:
    result = []
    for out in outputs:
        if result and result[-1]["ai"] == out["ai"]:
            result[-1] = OutputMessage(
                ai=result[-1]["ai"],
                content=merge_outputs(result[-1]["content"], out["content"]),
            )
        else:
            result.append(out)
    return result


def output_langchain(messages: list[OutputMessage]):
    result = []
    for m in messages:
        if m["ai"]:
            result.append(AIMessage(content=serialize_content(m["content"])))
        else:
            result.append(HumanMessage(content=serialize_content(m["content"])))
    return result


def output_text(messages: list[OutputMessage], ai_label="ai", human_label="human"):
    return "\n".join(serialize_output(o, ai_label, human_label) for o in messages)


def merge_outputs(a: MessageContent, b: MessageContent) -> MessageContent:
    if not isinstance(a, list):
        a = [a]
    if not isinstance(b, list):
        b = [b]
    return a + b  # type: ignore
    # return merge_properties(a, b)


def merge_properties(a: MessageContent, b: MessageContent) -> MessageContent:
    if isinstance(a, list):
        if isinstance(b, list):
            return a + b  # type: ignore
        else:
            return a + [b]
    elif isinstance(b, list):
        return [a] + b  # type: ignore
    elif isinstance(a, dict) and isinstance(b, dict):
        for key, value in b.items():
            if key in a:
                a[key] = merge_properties(a[key], value)
            else:
                a[key] = value
        return a
    elif isinstance(a, str) and isinstance(b, str):
        return a + b
    raise ValueError(f"Cannot merge {a} and {b}")
