from abc import abstractmethod
import asyncio
from collections import OrderedDict
from collections.abc import Mapping
import json
import math
import uuid
from typing import Coroutine, Literal, TypedDict, cast, Union, Dict, List, Any
from helpers import messages, tokens, settings, call_llm
from enum import Enum
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from plugins._model_config.helpers.model_config import get_chat_model_config


BULK_MERGE_COUNT = 3
TOPICS_MERGE_COUNT = 3
CURRENT_TOPIC_RATIO = 0.5
HISTORY_TOPIC_RATIO = 0.3
HISTORY_BULK_RATIO = 0.2
CURRENT_TOPIC_ATTENTION_COMPRESSION = 0.65 # compress current topic's attention window to 65% of size
HISTORY_TOPIC_ATTENTION_COMPRESSION = 0 # compress history topic's attention window to 0% of size - only request and response remain intact
LARGE_MESSAGE_TO_CURRENT_TOPIC_RATIO = 0.5
LARGE_MESSAGE_TO_HISTORY_TOPIC_RATIO = 0.2
RAW_MESSAGE_OUTPUT_TEXT_TRIM = 100
COMPRESSION_TARGET_RATIO = 0.8


class RawMessage(TypedDict):
    raw_content: "MessageContent"
    preview: str | None


MessageContent = Union[
    List["MessageContent"],
    Dict[str, "MessageContent"],
    List[Dict[str, "MessageContent"]],
    str,
    List[str],
    RawMessage,
]


class OutputMessage(TypedDict, total=False):
    ai: bool
    content: MessageContent
    metadata: dict[str, Any]
    id: str
    sequence: int


class Record:
    def __init__(self):
        pass

    @abstractmethod
    def get_tokens(self) -> int:
        pass

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
    def __init__(
        self,
        ai: bool,
        content: MessageContent,
        tokens: int = 0,
        id: str = "",
        metadata: dict[str, Any] | None = None,
        sequence: int = 0,
    ):
        self.id = id or str(uuid.uuid4())
        self.ai = ai
        self.content = content
        self.metadata = metadata or {}
        self.sequence = sequence
        self.summary: str = ""
        self.tokens: int = tokens or self.calculate_tokens()

    def get_tokens(self) -> int:
        if not self.tokens:
            self.tokens = self.calculate_tokens()
        return self.tokens

    def calculate_tokens(self):
        text = self.output_text()
        return tokens.approximate_tokens(text)

    def set_summary(self, summary: str):
        self.summary = summary
        self.tokens = self.calculate_tokens()

    async def compress(self):
        return False

    def output(self):
        return [
            OutputMessage(
                ai=self.ai,
                content=self.summary or self.content,
                metadata=self.metadata,
                id=self.id,
                sequence=self.sequence,
            )
        ]

    def output_langchain(self):
        return output_langchain(self.output())

    def output_text(self, human_label="user", ai_label="ai"):
        return output_text(self.output(), ai_label, human_label)

    def to_dict(self):
        return {
            "_cls": "Message",
            "id": self.id,
            "ai": self.ai,
            "content": self.content,
            "metadata": self.metadata,
            "sequence": self.sequence,
            "summary": self.summary,
            "tokens": self.tokens,
        }

    @staticmethod
    def from_dict(data: dict, history: "History"):
        content = data.get("content", "Content lost")
        metadata = data.get("metadata", {})
        metadata = metadata if isinstance(metadata, dict) else {}
        if data["ai"]:
            from helpers.llm_result import result_from_metadata

            result = result_from_metadata(metadata)
            if result:
                metadata = {**metadata, **result.metadata()}
        msg = Message(
            ai=data["ai"],
            content=content,
            tokens=data.get("tokens", 0),
            id=data.get("id", ""),
            metadata=metadata,
            sequence=int(data.get("sequence", 0) or 0),
        )
        msg.summary = data.get("summary", "")
        msg.tokens = data.get("tokens", 0)
        return msg


class Topic(Record):
    def __init__(self, history: "History"):
        self.history = history
        self.summary: str = ""
        self.messages: list[Message] = []

    def get_tokens(self):
        if self.summary:
            return tokens.approximate_tokens(self.summary)
        else:
            return sum(self._message_tokens())

    def _message_tokens(self) -> list[int]:
        from helpers.llm_result import result_from_metadata
        from helpers.litellm_transport import TransportMode

        extras = []
        for msg in self.messages:
            result = result_from_metadata(msg.metadata) if msg.ai and not msg.summary else None
            extras.append(result.history_extras if result else "")
        include_extras = any(extras) and TransportMode.from_value(
            self.history.agent.get_chat_model().kwargs.get("a0_api_mode")
        ) is TransportMode.RESPONSES
        return [
            msg.get_tokens() + (tokens.approximate_tokens(extra) if include_extras and extra else 0)
            for msg, extra in zip(self.messages, extras)
        ]

    def add_message(
        self,
        ai: bool,
        content: MessageContent,
        tokens: int = 0,
        id: str = "",
        metadata: dict[str, Any] | None = None,
        sequence: int = 0,
    ) -> Message:
        msg = Message(
            ai=ai,
            content=content,
            tokens=tokens,
            id=id,
            metadata=metadata,
            sequence=sequence,
        )
        self.messages.append(msg)
        return msg

    def output(self) -> list[OutputMessage]:
        if self.summary:
            return [OutputMessage(ai=False, content=self.summary)]
        else:
            msgs = [m for r in self.messages for m in r.output()]
            return msgs

    async def summarize(self):
        self.summary = await self.summarize_messages(self.messages)
        return self.summary

    def compress_large_messages(self, message_ratio: float = CURRENT_TOPIC_RATIO * LARGE_MESSAGE_TO_CURRENT_TOPIC_RATIO) -> bool:
        from plugins._model_config.helpers.model_config import get_chat_model_config
        chat_cfg = get_chat_model_config()
        ctx_length = int(chat_cfg.get("ctx_length", 128000))
        ctx_history = float(chat_cfg.get("ctx_history", 0.7))
        msg_max_size = (
            ctx_length
            * ctx_history
            * message_ratio
        )
        large_msgs = []
        for m, tok in zip(self.messages, self._message_tokens()):
            if m.summary:
                continue
            # TODO refactor this
            out = m.output()
            text = output_text(out)
            leng = len(text)
            if tok > msg_max_size:
                large_msgs.append((m, tok, leng, out))
        large_msgs.sort(key=lambda x: x[1], reverse=True)
        for msg, tok, leng, out in large_msgs:
            trim_to_chars = leng * (msg_max_size / tok)
            # raw messages will be replaced as a whole, they would become invalid when truncated
            if _is_raw_message(out[0]["content"]):
                msg.set_summary(
                    "Message content replaced to save space in context window"
                )

            # regular messages will be truncated
            else:
                trunc = messages.truncate_dict_by_ratio(
                    self.history.agent,
                    out[0]["content"],
                    trim_to_chars * 1.15,
                    trim_to_chars * 0.85,
                )
                msg.set_summary(_json_dumps(trunc))

            return True
        return False

    async def compress(self) -> bool:
        compress = self.compress_large_messages()
        if not compress:
            compress = await self.compress_attention()
        return compress

    async def compress_attention(self, ratio: float = CURRENT_TOPIC_ATTENTION_COMPRESSION) -> bool:

        middle = len(self.messages) - 2
        if middle < 2:
            return False
        cnt_to_sum = middle - math.floor(middle * ratio)
        if cnt_to_sum < 1:
            return False
        msg_to_sum = self.messages[1 : cnt_to_sum + 1]
        summary = await self.summarize_messages(msg_to_sum)
        sum_msg_content = self.history.agent.parse_prompt(
            "fw.msg_summary.md", summary=summary
        )
        sum_msg = Message(False, sum_msg_content)
        self.messages[1 : cnt_to_sum + 1] = [sum_msg]
        return True

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
        topic.summary = data.get("summary", "")
        topic.messages = [
            Message.from_dict(m, history=history) for m in data.get("messages", [])
        ]
        return topic


class Bulk(Record):
    def __init__(self, history: "History"):
        self.history = history
        self.summary: str = ""
        self.records: list[Record] = []

    def get_tokens(self):
        if self.summary:
            return tokens.approximate_tokens(self.summary)
        else:
            return sum([r.get_tokens() for r in self.records])

    def output(
        self, human_label: str = "user", ai_label: str = "ai"
    ) -> list[OutputMessage]:
        if self.summary:
            return [OutputMessage(ai=False, content=self.summary)]
        else:
            msgs = [m for r in self.records for m in r.output()]
            return msgs

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

        self.counter = 0
        self.bulks: list[Bulk] = []
        self.topics: list[Topic] = []
        self.current = Topic(history=self)
        self.agent: Agent = agent

    def get_tokens(self) -> int:
        return (
            self.get_bulks_tokens()
            + self.get_topics_tokens()
            + self.get_current_topic_tokens()
        )

    def is_over_limit(self):
        limit = self._get_ctx_size_for_history()
        total = self.get_tokens()
        return total > limit

    def get_bulks_tokens(self) -> int:
        return sum(record.get_tokens() for record in self.bulks)

    def get_topics_tokens(self) -> int:
        return sum(record.get_tokens() for record in self.topics)

    def get_current_topic_tokens(self) -> int:
        return self.current.get_tokens()

    def add_message(
        self,
        ai: bool,
        content: MessageContent,
        tokens: int = 0,
        id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        self.counter += 1
        return self.current.add_message(
            ai,
            content=content,
            tokens=tokens,
            id=id,
            metadata=metadata,
            sequence=self.counter,
        )

    def new_topic(self):
        if self.current.messages:
            self.topics.append(self.current)
            self.current = Topic(history=self)

    def output(self) -> list[OutputMessage]:
        self.trim_embeds(self._get_max_embeds())
        result: list[OutputMessage] = []
        result += [m for b in self.bulks for m in b.output()]
        result += [m for t in self.topics for m in t.output()]
        result += self.current.output()
        return result

    def messages_since(self, sequence: int) -> list[Message]:
        return [
            message
            for message in self.all_messages()
            if int(message.sequence or 0) > int(sequence or 0)
        ]

    def all_messages(self) -> list[Message]:
        messages: list[Message] = []
        for bulk in self.bulks:
            messages.extend(_messages_from_record(bulk))
        for topic in self.topics:
            messages.extend(topic.messages)
        messages.extend(self.current.messages)
        return messages

    def latest_llm_result_for_model(self, provider_model_key: str):
        from helpers.llm_result import result_from_metadata

        for message in reversed(self.all_messages()):
            if not message.ai:
                continue
            result = result_from_metadata(message.metadata)
            if not result:
                continue
            if result.provider_model_key == provider_model_key and result.response_id:
                return result
        return None

    def trim_embeds(self, max_embeds: int) -> int:
        if max_embeds == -1:
            return 0

        embeds_count = 0
        removed = 0

        for record in reversed(self.bulks + self.topics + [self.current]):
            embeds_count, removed_now = self._trim_embeds_in_record(record, embeds_count, max_embeds)
            removed += removed_now

        return removed

    def remove_all_embeds(self) -> int:
        return self.trim_embeds(0)

    def _trim_embeds_in_record(
        self, record: Record, embeds_count: int, max_embeds: int
    ) -> tuple[int, int]:
        if isinstance(record, Message):
            if record.summary:
                return embeds_count, 0

            if not _is_raw_message(record.content):
                return embeds_count, 0

            raw_message = cast(dict[str, Any], record.content)
            raw_content = raw_message.get("raw_content", [])
            if not isinstance(raw_content, list):
                return embeds_count, 0

            embeds_in_message = sum(1 for item in raw_content if _is_embedded_data(item))
            if embeds_in_message <= 0:
                return embeds_count, 0

            if embeds_count + embeds_in_message > max_embeds:
                record.set_summary("embedded data removed")
                return embeds_count + embeds_in_message, embeds_in_message

            return embeds_count + embeds_in_message, 0

        if isinstance(record, Topic):
            removed = 0
            for message in reversed(record.messages):
                embeds_count, removed_now = self._trim_embeds_in_record(message, embeds_count, max_embeds)
                removed += removed_now
            return embeds_count, removed

        if isinstance(record, Bulk):
            removed = 0
            for nested in reversed(record.records):
                embeds_count, removed_now = self._trim_embeds_in_record(nested, embeds_count, max_embeds)
                removed += removed_now
            return embeds_count, removed

        return embeds_count, 0

    @staticmethod
    def from_dict(data: dict, history: "History"):
        history.counter = data.get("counter", 0)
        history.bulks = [Bulk.from_dict(b, history=history) for b in data["bulks"]]
        history.topics = [Topic.from_dict(t, history=history) for t in data["topics"]]
        history.current = Topic.from_dict(data["current"], history=history)
        return history

    def to_dict(self):
        return {
            "_cls": "History",
            "counter": self.counter,
            "bulks": [b.to_dict() for b in self.bulks],
            "topics": [t.to_dict() for t in self.topics],
            "current": self.current.to_dict(),
        }

    def serialize(self):
        data = self.to_dict()
        return _json_dumps(data)

    async def compress(self):
        compressed = False
        total = self._get_ctx_size_for_history()
        curr, hist, bulk = (
            self.get_current_topic_tokens(),
            self.get_topics_tokens(),
            self.get_bulks_tokens(),
        )
        if (curr + hist + bulk) <= total:
            return False

        target = total * COMPRESSION_TARGET_RATIO
        prev_total = curr + hist + bulk + 1
        while True:
            curr, hist, bulk = (
                self.get_current_topic_tokens(),
                self.get_topics_tokens(),
                self.get_bulks_tokens(),
            )

            # safeguard against infinite loop in case LLM bloats the summary for some reason
            if (curr + hist + bulk) >= prev_total:
                break
            prev_total = curr + hist + bulk

            ratios = [
                (curr, CURRENT_TOPIC_RATIO, "current_topic"),
                (hist, HISTORY_TOPIC_RATIO, "history_topic"),
                (bulk, HISTORY_BULK_RATIO, "history_bulk"),
            ]
            ratios = sorted(ratios, key=lambda x: (x[0] / target) / x[1], reverse=True)
            compressed_part = False
            for ratio in ratios:
                if ratio[0] > ratio[1] * target:
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
        return compressed

    async def compress_topics(self) -> bool:

        # 1. first identify large messages and compress them cheaply
        for topic in self.topics:
            if topic.compress_large_messages(HISTORY_TOPIC_RATIO*LARGE_MESSAGE_TO_HISTORY_TOPIC_RATIO):
                return True

        # 2. summarize topics attention window one by one
        for topic in self.topics:
            if await topic.compress_attention(HISTORY_TOPIC_ATTENTION_COMPRESSION):
                return True

        # 3. move oldest topics to bulks in chunks
        if self.topics:
            count = TOPICS_MERGE_COUNT if len(self.topics) >= TOPICS_MERGE_COUNT else 1
            chunk = self.topics[:count]
            bulk = Bulk(history=self)
            bulk.records.extend(chunk)
            await bulk.summarize()
            self.bulks.append(bulk)
            self.topics[:count] = []
            return True
        return False

    async def compress_bulks(self):
        # merge bulks if possible
        compressed = await self.merge_bulks_by(BULK_MERGE_COUNT)
        # remove oldest bulk if necessary
        if not compressed:
            self.bulks.pop(0)
            return True
        return compressed

    async def merge_bulks_by(self, count: int):
        # if bulks is empty, return False
        if len(self.bulks) == 0:
            return False
        # merge bulks in groups of count, even if there are fewer than count
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

    def _get_ctx_size_for_history(self) -> int:
        chat_cfg = get_chat_model_config(self.agent)
        ctx_length = int(chat_cfg.get("ctx_length", 128000))
        ctx_history = float(chat_cfg.get("ctx_history", 0.7))
        return int(ctx_length * ctx_history)

    def _get_max_embeds(self) -> int:
        chat_cfg = get_chat_model_config(self.agent)
        if not chat_cfg.get("vision", False):
            return 0

        max_embeds = int(chat_cfg.get("max_embeds", 10))
        if max_embeds <= 0:
            max_embeds = -1
        return max_embeds



def deserialize_history(json_data: str, agent) -> History:
    history = History(agent=agent)
    if json_data:
        data = _json_loads(json_data)
        history = History.from_dict(data, history=history)
    return history


def _stringify_output(output: OutputMessage, ai_label="ai", human_label="human"):
    return f'{ai_label if output["ai"] else human_label}: {_stringify_content(output["content"])}'


def _stringify_content(content: MessageContent) -> str:
    # already a string
    if isinstance(content, str):
        return content
    
    # raw messages return preview or trimmed json
    if _is_raw_message(content):
        raw_message = cast(dict[str, Any], content)
        preview = raw_message.get("preview")
        if isinstance(preview, str) and preview:
            return preview
        text = _json_dumps(content)
        if len(text) > RAW_MESSAGE_OUTPUT_TEXT_TRIM:
            return text[:RAW_MESSAGE_OUTPUT_TEXT_TRIM] + "... TRIMMED"
        return text
    
    # regular messages of non-string are dumped as json
    return _json_dumps(content)


def _output_content_langchain(content: MessageContent):
    if isinstance(content, str):
        return content
    if _is_raw_message(content):
        raw_content = cast(dict[str, Any], content).get("raw_content")
        return raw_content if raw_content is not None else _json_dumps(content)
    try:
        return _json_dumps(content)
    except Exception as e:
        raise e


def group_outputs_abab(outputs: list[OutputMessage]) -> list[OutputMessage]:
    result = []
    for out in outputs:
        if result and result[-1]["ai"] == out["ai"]:
            result[-1] = OutputMessage(
                ai=result[-1]["ai"],
                content=_merge_outputs(result[-1]["content"], out["content"]),
            )
        else:
            result.append(out)
    return result


def group_messages_abab(messages: list[BaseMessage]) -> list[BaseMessage]:
    result = []
    for msg in messages:
        if result and isinstance(result[-1], type(msg)):
            # create new instance of the same type with merged content
            result[-1] = type(result[-1])(content=_merge_outputs(result[-1].content, msg.content))  # type: ignore
        else:
            result.append(msg)
    return result


def output_langchain(messages: list[OutputMessage]):
    result = []
    for m in messages:
        content = _output_content_langchain(content=m["content"])
        if not content or (isinstance(content, str) and not content.strip()):
            continue # skip empty messages, models 
        if m["ai"]:
            result.append(AIMessage(content))  # type: ignore
        else:
            result.append(HumanMessage(content))  # type: ignore
    # ensure message type alternation
    result = group_messages_abab(result)
    while result and isinstance(result[0], AIMessage):
        result.pop(0)
    return result


def output_text(messages: list[OutputMessage], ai_label="ai", human_label="human"):
    return "\n".join(_stringify_output(o, ai_label, human_label) for o in messages)


def clear_responses_provider_state(agent) -> None:
    key = getattr(agent, "DATA_NAME_RESPONSES_STATE", "responses_state")
    get_data = getattr(agent, "get_data", None)
    set_data = getattr(agent, "set_data", None)
    if not callable(get_data) or not callable(set_data):
        return

    state = get_data(key)
    if not isinstance(state, dict):
        return

    state = dict(state)
    removed = False
    for field in ("response_id", "previous_response_id"):
        if field in state:
            state.pop(field, None)
            removed = True

    if removed:
        set_data(key, state)


def _merge_outputs(a: MessageContent, b: MessageContent) -> MessageContent:
    if isinstance(a, str) and isinstance(b, str):
        return a + "\n" + b

    def make_list(obj: MessageContent) -> list[MessageContent]:
        if isinstance(obj, list):
            return obj  # type: ignore
        if isinstance(obj, dict):
            return [obj]
        if isinstance(obj, str):
            return [{"type": "text", "text": obj}]
        return [obj]

    a = make_list(a)
    b = make_list(b)

    return cast(MessageContent, a + b)


def _merge_properties(
    a: Dict[str, MessageContent], b: Dict[str, MessageContent]
) -> Dict[str, MessageContent]:
    result = a.copy()
    for k, v in b.items():
        if k in result:
            result[k] = _merge_outputs(result[k], v)
        else:
            result[k] = v
    return result


def _is_raw_message(obj: object) -> bool:
    return isinstance(obj, Mapping) and "raw_content" in obj


def _is_embedded_data(obj: object) -> bool:
    return isinstance(obj, Mapping) and obj.get("type") == "image_url"


def _messages_from_record(record: Record) -> list[Message]:
    if isinstance(record, Message):
        return [record]
    if isinstance(record, Topic):
        return list(record.messages)
    if isinstance(record, Bulk):
        messages: list[Message] = []
        for nested in record.records:
            messages.extend(_messages_from_record(nested))
        return messages
    return []


def _json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _json_loads(obj):
    return json.loads(obj)
