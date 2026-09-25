from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any


RESPONSE_METADATA_KEY = "responses"
LOCAL_FUNCTION_TOOL_TYPES = {"function_call"}
TEXT_OUTPUT_TYPES = {"message"}
REASONING_OUTPUT_TYPES = {"reasoning"}
TRUNCATED_FINISH_REASONS = {"length", "max_tokens"}


@dataclass
class ResponseItem:
    type: str
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_any(cls, item: Any) -> "ResponseItem":
        data = object_to_dict(item)
        return cls(type=str(data.get("type") or ""), data=data)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.data)


@dataclass
class ResponseFunctionCall:
    name: str
    arguments: dict[str, Any]
    call_id: str
    item_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_item(cls, item: ResponseItem) -> "ResponseFunctionCall | None":
        if item.type != "function_call":
            return None
        name = str(item.data.get("name") or "")
        if not name:
            return None
        return cls(
            name=name,
            arguments=parse_arguments(item.data.get("arguments")),
            call_id=str(item.data.get("call_id") or item.data.get("id") or ""),
            item_id=str(item.data.get("id") or ""),
            raw=dict(item.data),
        )


@dataclass
class LLMResult:
    response: str = ""
    reasoning: str = ""
    response_id: str = ""
    previous_response_id: str = ""
    input_items: list[dict[str, Any]] = field(default_factory=list)
    output_items: list[ResponseItem] = field(default_factory=list)
    provider_model_key: str = ""
    mode: str = "responses"
    state: str = "provider"
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    capability: dict[str, Any] = field(default_factory=dict)
    history_extras: str = ""
    finish_reason: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LLMResult":
        data = data or {}
        mode = data.get("mode")
        extras = data.get("history_extras")
        return cls(
            response=str(data.get("response") or ""),
            reasoning=str(data.get("reasoning") or ""),
            response_id=str(data.get("response_id") or ""),
            previous_response_id=str(data.get("previous_response_id") or ""),
            input_items=list(data.get("input_items") or []),
            output_items=[
                ResponseItem.from_any(item) for item in data.get("output_items") or []
            ],
            provider_model_key=str(data.get("provider_model_key") or ""),
            mode=str(mode if mode is not None else "responses"),
            state=str(data.get("state") or "provider"),
            usage=object_to_dict(data.get("usage") or {}),
            raw=object_to_dict(data.get("raw") or {}),
            capability=object_to_dict(data.get("capability") or {}),
            history_extras=extras if isinstance(extras, str) else "",
            finish_reason=str(data.get("finish_reason") or ""),
        )

    @classmethod
    def from_response(
        cls,
        response: Any,
        *,
        input_items: list[dict[str, Any]] | None = None,
        previous_response_id: str = "",
        provider_model_key: str = "",
        mode: str = "responses",
        state: str = "provider",
        capability: dict[str, Any] | None = None,
    ) -> "LLMResult":
        raw = object_to_dict(response)
        output_items = [ResponseItem.from_any(item) for item in as_list(raw.get("output"))]
        result = cls(
            response_id=str(raw.get("id") or ""),
            previous_response_id=str(
                raw.get("previous_response_id") or previous_response_id or ""
            ),
            input_items=list(input_items or []),
            output_items=output_items,
            provider_model_key=provider_model_key,
            mode=mode,
            state=state,
            usage=object_to_dict(raw.get("usage") or {}),
            raw=raw,
            capability=dict(capability or {}),
        )
        result.response = output_text(raw, output_items)
        result.reasoning = reasoning_text(output_items)
        if not result.response and result.function_calls:
            result.response = result.function_calls_text()
        return result

    @classmethod
    def from_chat(
        cls,
        *,
        response: str,
        reasoning: str = "",
        usage: dict[str, Any] | None = None,
        input_items: list[dict[str, Any]] | None = None,
        output_items: list[dict[str, Any]] | None = None,
        provider_model_key: str = "",
        capability: dict[str, Any] | None = None,
        finish_reason: str = "",
    ) -> "LLMResult":
        items = [ResponseItem.from_any(item) for item in output_items or []]
        if response and not items:
            items.append(
                ResponseItem(
                    type="message",
                    data={
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": response}],
                    },
                )
            )
        if reasoning:
            items.insert(
                0,
                ResponseItem(
                    type="reasoning",
                    data={
                        "type": "reasoning",
                        "summary": [{"type": "summary_text", "text": reasoning}],
                    },
                ),
            )
        result = cls(
            response=response,
            reasoning=reasoning,
            input_items=list(input_items or []),
            output_items=items,
            provider_model_key=provider_model_key,
            mode="chat_completions",
            state="off",
            usage=object_to_dict(usage or {}),
            capability=dict(capability or {}),
            finish_reason=finish_reason,
        )
        if not result.response and result.function_calls:
            result.response = result.function_calls_text()
        return result

    @classmethod
    def non_llm(cls) -> "LLMResult":
        """Sentinel for non-LLM AI turns; no response_id, mode/state off."""
        return cls(mode="", state="off")

    @property
    def truncated(self) -> bool:
        """True when the provider stopped because the output token limit was reached."""
        return self.finish_reason in TRUNCATED_FINISH_REASONS

    @property
    def function_calls(self) -> list[ResponseFunctionCall]:
        calls: list[ResponseFunctionCall] = []
        for item in self.output_items:
            call = ResponseFunctionCall.from_item(item)
            if call:
                calls.append(call)
        return calls

    @property
    def builtin_items(self) -> list[ResponseItem]:
        return [
            item
            for item in self.output_items
            if item.type
            and item.type not in TEXT_OUTPUT_TYPES
            and item.type not in REASONING_OUTPUT_TYPES
            and item.type not in LOCAL_FUNCTION_TOOL_TYPES
        ]

    def function_calls_text(self) -> str:
        calls = [
            {"tool_name": call.name, "tool_args": call.arguments}
            for call in self.function_calls
        ]
        if not calls:
            return ""
        if len(calls) == 1:
            return json.dumps(calls[0], ensure_ascii=False)
        return json.dumps(
            {"tool_name": "parallel_tool_calls", "tool_args": {"calls": calls}},
            ensure_ascii=False,
        )

    def repeat_response_text(self) -> str:
        """Compare public text and calls, excluding provider IDs and reasoning."""
        calls = self.function_calls_text()
        if not calls:
            return self.response
        return json.dumps([output_text(self.raw, self.output_items), calls], ensure_ascii=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "response": self.response,
            "reasoning": self.reasoning,
            "response_id": self.response_id,
            "previous_response_id": self.previous_response_id,
            "input_items": self.input_items,
            "output_items": [item.to_dict() for item in self.output_items],
            "provider_model_key": self.provider_model_key,
            "mode": self.mode,
            "state": self.state,
            "usage": self.usage,
            "raw": self.raw,
            "capability": self.capability,
            "history_extras": self.history_extras,
            "finish_reason": self.finish_reason,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            RESPONSE_METADATA_KEY: {
                "response_id": self.response_id,
                "previous_response_id": self.previous_response_id,
                "output_items": [item.to_dict() for item in self.output_items],
                "provider_model_key": self.provider_model_key,
                "mode": self.mode,
                "state": self.state,
                "usage": self.usage,
                "capability": self.capability,
                **({"history_extras": self.history_extras} if self.history_extras else {}),
            }
        }


def function_call_output_item(
    call_id: str,
    output: str,
    *,
    acknowledged_safety_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "type": "function_call_output",
        "call_id": str(call_id or ""),
        "output": output,
    }
    if acknowledged_safety_checks:
        item["acknowledged_safety_checks"] = acknowledged_safety_checks
    return item


def metadata_from_llm_result(result: LLMResult | None) -> dict[str, Any]:
    return result.metadata() if result else {}


def result_from_metadata(metadata: dict[str, Any] | None) -> LLMResult | None:
    if not isinstance(metadata, dict):
        return None
    data = metadata.get(RESPONSE_METADATA_KEY)
    if not isinstance(data, dict):
        return None
    return LLMResult.from_dict(data)


def object_to_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        dumped = obj.model_dump()
        return dict(dumped) if isinstance(dumped, dict) else {}
    if hasattr(obj, "dict"):
        dumped = obj.dict()
        return dict(dumped) if isinstance(dumped, dict) else {}
    return {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def output_text(raw: dict[str, Any], output_items: list[ResponseItem]) -> str:
    direct = raw.get("output_text")
    if isinstance(direct, str):
        return direct
    pieces: list[str] = []
    for item in output_items:
        if item.type != "message":
            continue
        for block in as_list(item.data.get("content")):
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type in {"output_text", "text", "input_text"}:
                text = block.get("text")
                if isinstance(text, str):
                    pieces.append(text)
            elif block_type == "refusal":
                refusal = block.get("refusal")
                if isinstance(refusal, str):
                    pieces.append(refusal)
    return "".join(pieces)


def reasoning_text(output_items: list[ResponseItem]) -> str:
    pieces: list[str] = []
    for item in output_items:
        if item.type != "reasoning":
            continue
        for block in as_list(item.data.get("summary")):
            if isinstance(block, dict):
                text = block.get("text") or block.get("reasoning")
                if isinstance(text, str):
                    pieces.append(text)
            elif isinstance(block, str):
                pieces.append(block)
    return "".join(pieces)


def parse_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments or "{}")
        except Exception:
            parsed = {"arguments": raw_arguments}
    else:
        parsed = {"arguments": raw_arguments}
    return parsed if isinstance(parsed, dict) else {"arguments": parsed}
