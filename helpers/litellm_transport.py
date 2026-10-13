from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import inspect
import json
from typing import Any, AsyncIterator, Iterator, Optional

from litellm import (
    ContentPolicyViolationError,
    acompletion,
    adelete_responses,
    aresponses,
    completion,
    delete_responses,
    responses,
)

from helpers import images, responses_history
from helpers.llm_result import LLMResult
from helpers.responses_tools import project_system_prompt


ChatChunk = dict[str, str]


class TransportMode(Enum):
    RESPONSES = "responses"
    CHAT_COMPLETIONS = "chat_completions"

    @classmethod
    def from_value(cls, value: Any) -> "TransportMode":
        return cls.RESPONSES if str(value or "").lower().strip() in RESPONSES_ALIASES else cls.CHAT_COMPLETIONS


class TransportRecovery(Enum):
    RAISE = "raise"
    RETRY_RESPONSES = "retry_responses"
    RETRY_LOCAL_RESPONSES = "retry_local_responses"
    FALLBACK_TO_CHAT = "fallback_to_chat"


RESPONSES_ALIASES = {"response", "responses", "responses_api"}
RESPONSES_REASONING_EFFORTS = {"minimal", "low", "medium", "high"}
RESPONSES_REASONING_FALLBACK_EFFORT = "high"
NO_REASONING_EFFORT_ALIASES = {"", "0", "false", "no", "none", "off", "disabled"}
RESPONSES_UNSUPPORTED_CACHE: set[str] = set()
RESPONSES_STATE_UNSUPPORTED_CACHE: set[str] = set()
RESPONSES_BUILTIN_UNSUPPORTED_CACHE: dict[str, set[str]] = {}
STREAM_USAGE_UNSUPPORTED_CACHE: set[str] = set()
OPENAI_RESPONSES_EXTRA_BODY_PARAMS = {
    "context_management",
    "prompt_cache_retention",
}
CACHE_CONTROL_PROMPT_PROVIDERS = {
    "anthropic",
    "bedrock",
    "databricks",
    "dashscope",
    "gemini",
    "gemini_api_oauth",
    "minimax",
    "openrouter",
    "vertex_ai",
    "vertexai",
    "z_ai",
    "zai",
}
OPENAI_PROMPT_CACHE_PROVIDERS = {"openai", "azure"}
RESPONSES_STATE_PROVIDER = "provider"
RESPONSES_STATE_LOCAL = "local"
RESPONSES_STATE_OFF = "off"
RESPONSES_STATES = {
    RESPONSES_STATE_PROVIDER,
    RESPONSES_STATE_LOCAL,
    RESPONSES_STATE_OFF,
}


@dataclass
class TransportPolicy:
    mode: TransportMode
    allow_fallback: bool = True
    retried_reasoning: bool = False
    fallback_error: Exception | None = None
    state_fallback_error: Exception | None = None
    cache_key: str = ""
    state: str = RESPONSES_STATE_PROVIDER

    @classmethod
    def from_request(
        cls,
        model: str,
        kwargs: dict[str, Any],
        messages: list[dict[str, Any]] | None = None,
    ) -> "TransportPolicy":
        mode = TransportMode.from_value(kwargs.pop("a0_api_mode", None))
        allow_fallback = _coerce_bool(
            kwargs.pop("a0_responses_fallback", True), default=True
        )
        cache_key = _responses_cache_key(model, kwargs)
        state = _normalize_responses_state(kwargs.get("responses_state"))

        if mode is TransportMode.CHAT_COMPLETIONS:
            _drop_responses_only_kwargs(kwargs)
            return cls(
                mode=mode,
                allow_fallback=allow_fallback,
                cache_key=cache_key,
                state=RESPONSES_STATE_OFF,
            )

        if (
            state == RESPONSES_STATE_PROVIDER
            and cache_key in RESPONSES_STATE_UNSUPPORTED_CACHE
        ):
            kwargs["responses_state"] = RESPONSES_STATE_LOCAL
            state = RESPONSES_STATE_LOCAL

        _filter_unsupported_builtin_tools(kwargs, cache_key)

        if _should_preserve_cache_control_on_chat(model, kwargs, messages or []):
            return cls(
                mode=TransportMode.CHAT_COMPLETIONS,
                allow_fallback=allow_fallback,
                cache_key=cache_key,
                state=RESPONSES_STATE_OFF,
            )

        if cache_key in RESPONSES_UNSUPPORTED_CACHE:
            return cls(
                mode=TransportMode.CHAT_COMPLETIONS,
                allow_fallback=allow_fallback,
                fallback_error=RuntimeError("Responses API previously failed"),
                cache_key=cache_key,
                state=RESPONSES_STATE_OFF,
            )

        return cls(
            mode=TransportMode.RESPONSES,
            allow_fallback=allow_fallback,
            cache_key=cache_key,
            state=state,
        )

    @property
    def using_responses(self) -> bool:
        return self.mode is TransportMode.RESPONSES

    def recover(self, exc: Exception, *, got_any_chunk: bool) -> TransportRecovery:
        if not self.using_responses or got_any_chunk:
            return TransportRecovery.RAISE
        if not self.retried_reasoning and _is_responses_reasoning_effort_error(exc):
            self.retried_reasoning = True
            return TransportRecovery.RETRY_RESPONSES
        if (
            self.state == RESPONSES_STATE_PROVIDER
            and _is_responses_state_unsupported_error(exc)
        ):
            self.state = RESPONSES_STATE_LOCAL
            self.state_fallback_error = exc
            if self.cache_key:
                RESPONSES_STATE_UNSUPPORTED_CACHE.add(self.cache_key)
            return TransportRecovery.RETRY_LOCAL_RESPONSES
        if self.allow_fallback and _is_responses_not_supported_error(exc):
            self.mode = TransportMode.CHAT_COMPLETIONS
            self.fallback_error = exc
            self.state = RESPONSES_STATE_OFF
            if self.cache_key:
                RESPONSES_UNSUPPORTED_CACHE.add(self.cache_key)
            return TransportRecovery.FALLBACK_TO_CHAT
        return TransportRecovery.RAISE


@dataclass
class LiteLLMTransport:
    model: str
    messages: list[dict[str, Any]]
    kwargs: dict[str, Any]
    stop: Optional[list[str]] = None
    policy: TransportPolicy = field(init=False)
    last_result: LLMResult | None = field(init=False, default=None)
    last_request_state: str = field(init=False, default=RESPONSES_STATE_PROVIDER)
    explicit_prompt_caching: bool = field(init=False, default=False)
    history_prefix_hash: str = field(init=False, default="")
    history_extras: str = field(init=False, default="")
    stream_usage_retried: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self.kwargs = _without_stream_kwarg(dict(self.kwargs))
        self.explicit_prompt_caching = _coerce_bool(
            self.kwargs.pop("a0_explicit_prompt_caching", False), default=False
        )
        if self.explicit_prompt_caching:
            self.messages = apply_chat_prompt_cache_markers(
                self.messages,
                model=self.model,
                kwargs=self.kwargs,
            )
        self.policy = TransportPolicy.from_request(
            self.model,
            self.kwargs,
            messages=self.messages,
        )

    def complete(self) -> ChatChunk:
        while True:
            try:
                if self.policy.mode is TransportMode.CHAT_COMPLETIONS:
                    raw_response = completion(**self._chat_request(stream=False))
                    parsed = ChatCompletionsTransport.parse(raw_response)
                    self.last_result = self._llm_result_from_chat(
                        parsed, raw_response
                    )
                    return parsed
                request = self._responses_request(stream=False)
                raw_response = responses(**request)
                parsed = ResponsesTransport.parse_response(raw_response)
                self.last_result = self._llm_result_from_response(
                    raw_response, request
                )
                return parsed
            except Exception as exc:
                if self._recover(exc, got_any_chunk=False):
                    continue
                raise

    async def acomplete(self) -> ChatChunk:
        while True:
            try:
                if self.policy.mode is TransportMode.CHAT_COMPLETIONS:
                    raw_response = await acompletion(
                        **self._chat_request(stream=False)
                    )
                    parsed = ChatCompletionsTransport.parse(raw_response)
                    self.last_result = self._llm_result_from_chat(
                        parsed, raw_response
                    )
                    return parsed
                request = self._responses_request(stream=False)
                raw_response = await aresponses(**request)
                parsed = ResponsesTransport.parse_response(raw_response)
                self.last_result = self._llm_result_from_response(
                    raw_response, request
                )
                return parsed
            except Exception as exc:
                if self._recover(exc, got_any_chunk=False):
                    continue
                raise

    def stream(self) -> Iterator[ChatChunk]:
        while True:
            iterator = None
            exhausted = False
            got_any_chunk = False
            try:
                if self.policy.mode is TransportMode.CHAT_COMPLETIONS:
                    iterator = completion(**self._chat_request(stream=True))
                    parser = ChatCompletionsStreamParser()
                    for chunk in iterator:
                        parsed = parser.parse(chunk)
                        if _has_chunk_delta(parsed):
                            got_any_chunk = True
                            yield parsed
                    parsed = parser.flush()
                    if _has_chunk_delta(parsed):
                        got_any_chunk = True
                        yield parsed
                    self.last_result = self._stream_result_from_chat_parser(parser)
                else:
                    request = self._responses_request(stream=True)
                    iterator = responses(**request)
                    parser = ResponsesEventParser()
                    for event in iterator:
                        parsed = parser.parse(event)
                        if _has_chunk_delta(parsed):
                            got_any_chunk = True
                            yield parsed
                    self.last_result = self._stream_result_from_parser(
                        parser, request
                    )
                exhausted = True
                return
            except Exception as exc:
                if self._recover(exc, got_any_chunk=got_any_chunk):
                    continue
                raise
            finally:
                if iterator is not None and not exhausted:
                    _close_sync_stream(iterator)

    async def astream(self) -> AsyncIterator[ChatChunk]:
        while True:
            iterator = None
            exhausted = False
            got_any_chunk = False
            try:
                if self.policy.mode is TransportMode.CHAT_COMPLETIONS:
                    iterator = await acompletion(**self._chat_request(stream=True))
                    parser = ChatCompletionsStreamParser()
                    async for chunk in iterator:  # type: ignore[union-attr]
                        parsed = parser.parse(chunk)
                        if _has_chunk_delta(parsed):
                            got_any_chunk = True
                            yield parsed
                    parsed = parser.flush()
                    if _has_chunk_delta(parsed):
                        got_any_chunk = True
                        yield parsed
                    self.last_result = self._stream_result_from_chat_parser(parser)
                else:
                    request = self._responses_request(stream=True)
                    iterator = await aresponses(**request)
                    parser = ResponsesEventParser()
                    async for event in iterator:  # type: ignore[union-attr]
                        parsed = parser.parse(event)
                        if _has_chunk_delta(parsed):
                            got_any_chunk = True
                            yield parsed
                    self.last_result = self._stream_result_from_parser(
                        parser, request
                    )
                exhausted = True
                return
            except Exception as exc:
                if self._recover(exc, got_any_chunk=got_any_chunk):
                    continue
                raise
            finally:
                if iterator is not None and not exhausted:
                    await _close_async_stream(iterator)

    def _recover(self, exc: Exception, *, got_any_chunk: bool) -> bool:
        if (
            self.policy.using_responses
            and not got_any_chunk
            and self.kwargs.get("responses_builtin_tools")
            and _is_responses_builtin_tool_error(exc)
        ):
            downgraded = _builtin_tool_types(self.kwargs.get("responses_builtin_tools"))
            if downgraded:
                RESPONSES_BUILTIN_UNSUPPORTED_CACHE.setdefault(
                    self.policy.cache_key, set()
                ).update(downgraded)
                self.kwargs["_a0_responses_builtin_downgrades"] = sorted(downgraded)
                self.kwargs["responses_builtin_tools"] = []
                return True

        recovery = self.policy.recover(exc, got_any_chunk=got_any_chunk)
        if recovery is TransportRecovery.RETRY_RESPONSES:
            self.kwargs["reasoning"] = {
                "effort": RESPONSES_REASONING_FALLBACK_EFFORT
            }
            return True
        if recovery is TransportRecovery.RETRY_LOCAL_RESPONSES:
            self.kwargs["responses_state"] = RESPONSES_STATE_LOCAL
            self.kwargs.pop("previous_response_id", None)
            return True
        if self._recover_stream_usage_rejection(exc):
            return True
        return recovery is TransportRecovery.FALLBACK_TO_CHAT

    def _recover_stream_usage_rejection(self, exc: Exception) -> bool:
        if self.stream_usage_retried or not _is_stream_usage_rejected_error(exc):
            return False
        self.stream_usage_retried = True
        if self.policy.cache_key:
            STREAM_USAGE_UNSUPPORTED_CACHE.add(self.policy.cache_key)
        return True

    def _chat_request(self, *, stream: bool) -> dict[str, Any]:
        chat_kwargs = ChatCompletionsTransport.prepare_kwargs(
            self.kwargs,
            fallback_error=self.policy.fallback_error,
            model=self.model,
            messages=self.messages,
            explicit_prompt_caching=self.explicit_prompt_caching,
        )
        request = {
            "model": self.model,
            "messages": ChatCompletionsTransport.prepare_messages(
                self.messages,
                model=self.model,
                kwargs=self.kwargs,
            ),
            "stream": stream,
            **chat_kwargs,
        }
        if (
            stream
            and not self.stream_usage_retried
            and self.policy.cache_key not in STREAM_USAGE_UNSUPPORTED_CACHE
        ):
            request["stream_options"] = {
                **(request.get("stream_options") or {}),
                "include_usage": True,
            }
        if self.stop is not None:
            request["stop"] = self.stop
        return request

    def _responses_request(self, *, stream: bool) -> dict[str, Any]:
        response_kwargs = ResponsesTransport.from_chat(
            self.messages,
            self.kwargs,
            stop=self.stop,
            model=self.model,
        )
        self.last_request_state = _normalize_responses_state(
            self.kwargs.get("responses_state")
        )
        self.history_prefix_hash = ""
        self.history_extras = ""
        context = self.kwargs.get("responses_history_context")
        if (
            self.last_request_state == RESPONSES_STATE_LOCAL
            and _has_tools(self.kwargs.get("a0_responses_function_tools"))
            and isinstance(context, dict)
            and all(isinstance(context.get(key), list) for key in ("prompt", "prefix", "groups"))
        ):
            replacements = self.kwargs.get("responses_prompt_replacements")
            prompt = project_system_prompt(context.get("prompt", []), replacements)
            if response_kwargs.get("input") == prompt:
                prefix = project_system_prompt(context.get("prefix", []), replacements)
                scope = {"affinity": self.policy.cache_key, "tools": response_kwargs.get("tools")}
                self.history_prefix_hash = responses_history.prefix_hashes(prefix, scope)[-1]
                self.history_extras = responses_history.prompt_extras(prompt, prefix)
                if self.history_extras and isinstance(context.get("extras"), str):
                    self.history_extras = context["extras"]
                    prompt = deepcopy(prefix)
                    responses_history.append_extras(prompt, self.history_extras)
                response_kwargs["input"] = responses_history.project_history(
                    prompt, context.get("groups", []), scope,
                )
        return {
            "model": self.model,
            "stream": stream,
            **response_kwargs,
        }

    def _llm_result_from_chat(
        self, parsed: ChatChunk, response: Any = None
    ) -> LLMResult:
        return LLMResult.from_chat(
            response=parsed["response_delta"],
            reasoning=parsed["reasoning_delta"],
            usage=_reported_usage(response),
            input_items=ResponsesTransport.input_from_messages(self.messages),
            output_items=parsed.get("_output_items"),
            provider_model_key=self.model,
            capability=self._capability_metadata(),
        )

    def _llm_result_from_response(
        self, response: Any, request: dict[str, Any]
    ) -> LLMResult:
        result = LLMResult.from_response(
            response,
            input_items=_as_list(request.get("input")),
            previous_response_id=str(request.get("previous_response_id") or ""),
            provider_model_key=self.model,
            mode=TransportMode.RESPONSES.value,
            state=self.last_request_state,
            capability=self._capability_metadata(),
        )
        result.usage = _reported_usage(response)
        result.history_extras = self.history_extras
        return result

    def _stream_result_from_parser(
        self, parser: "ResponsesEventParser", request: dict[str, Any]
    ) -> LLMResult | None:
        response = parser.finish()
        return self._llm_result_from_response(response, request) if response is not None else None

    def _stream_result_from_chat_parser(
        self, parser: "ChatCompletionsStreamParser"
    ) -> LLMResult | None:
        output_items = parser.output_items()
        if not output_items and not parser.usage:
            return None
        return LLMResult.from_chat(
            response=parser.function_calls_text(),
            usage=parser.usage,
            input_items=ResponsesTransport.input_from_messages(self.messages),
            output_items=output_items,
            provider_model_key=self.model,
            capability=self._capability_metadata(),
        )

    def _capability_metadata(self) -> dict[str, Any]:
        return {
            "mode": self.policy.mode.value,
            "state": self.policy.state,
            "cache_key": self.policy.cache_key,
            **(
                {responses_history.PREFIX_HASH: self.history_prefix_hash}
                if self.policy.using_responses and self.history_prefix_hash else {}
            ),
            "fallback_error": _exception_text(self.policy.fallback_error)
            if self.policy.fallback_error
            else "",
            "state_fallback_error": _exception_text(self.policy.state_fallback_error)
            if self.policy.state_fallback_error
            else "",
            "builtin_tool_downgrades": list(
                self.kwargs.get("_a0_responses_builtin_downgrades") or []
            ),
        }


class _ChatReasoningFilter:
    marker = "__ENCRYPTED_REASONING__"

    def __init__(self) -> None:
        self.pending = ""
        self.encrypted = False

    def feed(self, text: str, *, final: bool = False) -> str:
        if self.encrypted:
            return ""
        text = self.pending + text
        self.pending = ""
        if self.marker in text:
            self.encrypted = True
            return text.partition(self.marker)[0]
        if not final:
            for length in range(min(len(text), len(self.marker) - 1), 0, -1):
                if text.endswith(self.marker[:length]):
                    self.pending = text[-length:]
                    return text[:-length]
        return text


class ChatCompletionsTransport:
    @staticmethod
    def prepare_messages(
        messages: list[dict[str, Any]],
        *,
        model: str = "",
        kwargs: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if _prompt_cache_mode(model, kwargs or {}) == "prompt_cache_key":
            stripped = _without_cache_control(messages)
            return stripped if isinstance(stripped, list) else messages
        return messages

    @staticmethod
    def prepare_kwargs(
        kwargs: dict[str, Any],
        fallback_error: Exception | None = None,
        *,
        model: str = "",
        messages: list[dict[str, Any]] | None = None,
        explicit_prompt_caching: bool = False,
    ) -> dict[str, Any]:
        chat_kwargs = dict(kwargs)
        cache_mode = _prompt_cache_mode(model, chat_kwargs)
        _drop_internal_transport_kwargs(chat_kwargs)
        if not _has_tools(chat_kwargs.get("tools")):
            chat_kwargs.pop("tools", None)
            chat_kwargs.pop("tool_choice", None)
            chat_kwargs.pop("parallel_tool_calls", None)
        if cache_mode == "prompt_cache_key":
            _prepare_openai_prompt_cache_params(
                chat_kwargs,
                messages or [],
                model=model,
            )
        elif cache_mode == "cache_control" and (
            explicit_prompt_caching or _has_cache_control(messages or [])
        ):
            _apply_tool_cache_control(chat_kwargs)
        if fallback_error is not None:
            chat_kwargs.setdefault("drop_params", True)
        return {key: value for key, value in chat_kwargs.items() if value is not None}

    @staticmethod
    def parse(
        chunk: Any, *, reasoning_filter: _ChatReasoningFilter | None = None
    ) -> ChatChunk:
        choice = _first_choice(chunk)
        finish_reason = _get_value(choice, "finish_reason")
        if finish_reason in {"content_filter", "refusal"}:
            raise ContentPolicyViolationError(
                message=f"Model provider refused the response (finish_reason={finish_reason}). "
                "Review the request and provider restrictions before retrying.",
                model=str(_get_value(chunk, "model") or ""),
                llm_provider="",
            )
        delta = _get_value(choice, "delta") or {}
        message = _get_value(choice, "message") or _get_value(
            _get_value(choice, "model_extra") or {}, "message"
        ) or {}
        response_delta = _get_value(delta, "content") or _get_value(
            message, "content"
        ) or ""
        reasoning_delta = (
            _get_value(delta, "reasoning_content")
            or _get_value(message, "reasoning_content")
            or _get_value(delta, "reasoning")
            or _get_value(message, "reasoning")
            or ""
        )
        reasoning_delta = (reasoning_filter or _ChatReasoningFilter()).feed(
            reasoning_delta, final=reasoning_filter is None
        )
        parsed = {"reasoning_delta": reasoning_delta, "response_delta": response_delta}
        tool_calls = _as_list(_get_value(message, "tool_calls"))
        call_text = ChatCompletionsTransport.tool_calls_text(tool_calls)
        if call_text:
            parsed["response_delta"] = call_text
            parsed["_output_items"] = ChatCompletionsTransport.output_items(tool_calls)
            if response_delta:
                parsed["_output_items"].insert(0, {
                    "type": "message", "role": "assistant",
                    "content": [{"type": "output_text", "text": response_delta}],
                })
        return parsed

    @classmethod
    def tool_calls_text(cls, tool_calls: Any) -> str:
        calls = [cls.tool_call_object(call) for call in _as_list(tool_calls)]
        calls = [call for call in calls if call]
        if not calls:
            return ""
        if len(calls) == 1:
            return json.dumps(calls[0], ensure_ascii=False)
        return json.dumps(
            {"tool_name": "parallel_tool_calls", "tool_args": {"calls": calls}},
            ensure_ascii=False,
        )

    @classmethod
    def output_items(cls, tool_calls: Any) -> list[dict[str, Any]]:
        items = []
        for index, tool_call in enumerate(_as_list(tool_calls)):
            item = cls.function_call_item(tool_call, fallback_index=index)
            if item:
                items.append(item)
        return items

    @classmethod
    def function_call_item(
        cls, tool_call: Any, *, fallback_index: int = 0
    ) -> dict[str, Any]:
        function = _get_value(tool_call, "function") or {}
        name = _get_value(function, "name") or _get_value(tool_call, "name")
        if not name:
            return {}
        raw_arguments = _get_value(function, "arguments")
        if raw_arguments is None:
            raw_arguments = _get_value(tool_call, "arguments") or "{}"
        call_id = str(_get_value(tool_call, "id") or f"call_{fallback_index}")
        return {
            "type": "function_call",
            "id": call_id,
            "call_id": call_id,
            "name": str(name),
            "arguments": raw_arguments
            if isinstance(raw_arguments, str)
            else json.dumps(raw_arguments),
        }

    @classmethod
    def tool_call_object(cls, tool_call: Any) -> dict[str, Any]:
        item = cls.function_call_item(tool_call)
        if not item:
            return {}
        return ResponsesTransport.function_call_object(item)


class ChatCompletionsStreamParser:
    def __init__(self) -> None:
        self.reasoning_filter = _ChatReasoningFilter()
        self.tool_calls: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []
        self.emitted = False
        self.usage: dict[str, Any] = {}

    def parse(self, chunk: Any) -> ChatChunk:
        if usage := _reported_usage(chunk):
            self.usage.update(usage)
        parsed = ChatCompletionsTransport.parse(chunk, reasoning_filter=self.reasoning_filter)
        choice = _first_choice(chunk)
        delta = _get_value(choice, "delta") or {}
        self._append_tool_calls(_get_value(delta, "tool_calls"))
        self._append_legacy_function_call(_get_value(delta, "function_call"))

        if _get_value(choice, "finish_reason") in {"tool_calls", "function_call"}:
            text = self._emit()
            if text and not parsed["response_delta"]:
                parsed["response_delta"] = text
        return parsed

    def flush(self) -> ChatChunk:
        return {
            "reasoning_delta": self.reasoning_filter.feed("", final=True),
            "response_delta": self._emit(),
        }

    def function_calls_text(self) -> str:
        return ChatCompletionsTransport.tool_calls_text(self._ordered_tool_calls())

    def output_items(self) -> list[dict[str, Any]]:
        return ChatCompletionsTransport.output_items(self._ordered_tool_calls())

    def _append_tool_calls(self, tool_calls: Any) -> None:
        for fallback_index, tool_call in enumerate(_as_list(tool_calls)):
            key = self._tool_call_key(tool_call, fallback_index)
            current = self._current_tool_call(key)
            if _get_value(tool_call, "id"):
                current["id"] = _get_value(tool_call, "id")
            if _get_value(tool_call, "type"):
                current["type"] = _get_value(tool_call, "type")
            self._append_function_delta(current, _get_value(tool_call, "function"))

    def _append_legacy_function_call(self, function_call: Any) -> None:
        if not function_call:
            return
        current = self._current_tool_call("0")
        current["type"] = "function"
        self._append_function_delta(current, function_call)

    def _append_function_delta(self, tool_call: dict[str, Any], delta: Any) -> None:
        if not delta:
            return
        function = tool_call.setdefault("function", {})
        if _get_value(delta, "name"):
            function["name"] = _get_value(delta, "name")
        if _get_value(delta, "arguments") is not None:
            function["arguments"] = str(function.get("arguments") or "") + str(
                _get_value(delta, "arguments") or ""
            )

    def _current_tool_call(self, key: str) -> dict[str, Any]:
        if key not in self.tool_calls:
            self.tool_calls[key] = {"type": "function", "function": {}}
            self.order.append(key)
        return self.tool_calls[key]

    def _ordered_tool_calls(self) -> list[dict[str, Any]]:
        return [self.tool_calls[key] for key in self.order]

    def _emit(self) -> str:
        if self.emitted:
            return ""
        text = self.function_calls_text()
        if text:
            self.emitted = True
        return text

    @staticmethod
    def _tool_call_key(tool_call: Any, fallback_index: int) -> str:
        index = _get_value(tool_call, "index")
        if index is not None:
            return str(index)
        if _get_value(tool_call, "id"):
            return str(_get_value(tool_call, "id"))
        return str(fallback_index)


class ResponsesTransport:
    @staticmethod
    def input_from_model_messages(model: Any, messages: list) -> list[dict[str, Any]]:
        if not hasattr(model, "_convert_messages"):
            return []
        return ResponsesTransport.input_from_messages(model._convert_messages(messages))

    @classmethod
    def from_chat(
        cls,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
        stop: Optional[list[str]] = None,
        model: str = "",
    ) -> dict[str, Any]:
        request = cls.prepare_kwargs(kwargs, stop=stop, model=model, messages=messages)
        state = _normalize_responses_state(kwargs.get("responses_state"))
        input_items = cls._select_input_items(kwargs, messages, state)
        if _has_tools(kwargs.get("a0_responses_function_tools")):
            input_items = project_system_prompt(input_items, kwargs.get("responses_prompt_replacements"))
        request["input"] = input_items or ""
        cls.apply_state(request, kwargs, state=state)
        return request

    @classmethod
    def from_input(
        cls,
        input_items: list[dict[str, Any]],
        kwargs: dict[str, Any],
        stop: Optional[list[str]] = None,
        model: str = "",
        messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        request = cls.prepare_kwargs(kwargs, stop=stop, model=model, messages=messages)
        state = _normalize_responses_state(kwargs.get("responses_state"))
        items = list(input_items or [])
        if _has_tools(kwargs.get("a0_responses_function_tools")):
            items = project_system_prompt(items, kwargs.get("responses_prompt_replacements"))
        request["input"] = items or ""
        cls.apply_state(request, kwargs, state=state)
        return request

    @classmethod
    def prepare_kwargs(
        cls,
        kwargs: dict[str, Any],
        stop: Optional[list[str]] = None,
        model: str = "",
        messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        request = dict(kwargs)
        response_function_tools = request.pop("a0_responses_function_tools", None)
        response_builtin_tools = request.pop("responses_builtin_tools", None)
        _drop_responses_only_kwargs(request)
        _drop_legacy_transport_kwargs(request)
        request.pop("stop", None)

        max_completion_tokens = request.pop("max_completion_tokens", None)
        max_tokens = request.pop("max_tokens", None)
        if "max_output_tokens" not in request:
            request["max_output_tokens"] = max_completion_tokens or max_tokens

        reasoning_effort = request.pop("reasoning_effort", None)
        if "reasoning" in request:
            request["reasoning"] = cls.normalize_reasoning(request["reasoning"])
        elif reasoning_effort is not None:
            request["reasoning"] = cls.normalize_reasoning(reasoning_effort)

        response_format = request.pop("response_format", None)
        if response_format is not None:
            text_param, text_format = cls.text_from_response_format(response_format)
            if text_param is not None and "text" not in request:
                request["text"] = text_param
            if text_format is not None and "text_format" not in request:
                request["text_format"] = text_format

        functions = request.pop("functions", None)
        if functions and "tools" not in request:
            request["tools"] = [
                {"type": "function", **function}
                for function in functions
                if isinstance(function, dict)
            ]

        tools = cls.tools_from_chat(request.pop("tools", None))
        tools = cls.merge_response_tools(
            tools,
            response_function_tools=response_function_tools,
            response_builtin_tools=response_builtin_tools,
        )
        if _has_tools(tools):
            request["tools"] = tools
        else:
            request.pop("tools", None)

        function_call = request.pop("function_call", None)
        if function_call is not None and "tool_choice" not in request:
            request["tool_choice"] = cls.tool_choice_from_function_call(function_call)
        elif "tool_choice" in request:
            request["tool_choice"] = cls.tool_choice_from_chat(request["tool_choice"])

        if _has_tools(response_function_tools):
            request.setdefault("tool_choice", "required")
            request.setdefault("parallel_tool_calls", False)

        if not _has_tools(request.get("tools")):
            request.pop("tool_choice", None)
            request.pop("parallel_tool_calls", None)

        cls.prepare_prompt_caching(request, messages or [], model=model)
        request.pop("a0_prompt_cache_mode", None)

        _ = stop
        return {key: value for key, value in request.items() if value is not None}

    @classmethod
    def _select_input_items(
        cls,
        kwargs: dict[str, Any],
        messages: list[dict[str, Any]],
        state: str,
    ) -> list[dict[str, Any]]:
        provider_items = kwargs.get("responses_input_items")
        local_items = kwargs.get("responses_local_input_items")
        previous_response_id = kwargs.get("previous_response_id")

        if (
            state == RESPONSES_STATE_PROVIDER
            and previous_response_id
            and isinstance(provider_items, list)
        ):
            return [dict(item) for item in provider_items if isinstance(item, dict)]

        if state == RESPONSES_STATE_LOCAL and isinstance(local_items, list):
            return [dict(item) for item in local_items if isinstance(item, dict)]

        return cls.input_from_messages(messages)

    @staticmethod
    def apply_state(
        request: dict[str, Any],
        kwargs: dict[str, Any],
        *,
        state: str,
    ) -> None:
        if state == RESPONSES_STATE_PROVIDER:
            request.setdefault("store", True)
            previous_response_id = str(kwargs.get("previous_response_id") or "")
            if previous_response_id:
                request["previous_response_id"] = previous_response_id
        elif state == RESPONSES_STATE_LOCAL:
            request.setdefault("store", False)
        else:
            request.setdefault("store", False)

    @classmethod
    def merge_response_tools(
        cls,
        tools: Any,
        *,
        response_function_tools: Any = None,
        response_builtin_tools: Any = None,
    ) -> list[Any]:
        merged: list[Any] = []
        for source in (tools, response_function_tools, response_builtin_tools):
            source_tools = (
                source if isinstance(source, list) else [source] if source else []
            )
            for tool in source_tools:
                normalized = cls.normalize_response_tool(tool)
                if normalized:
                    merged.append(normalized)
        return merged

    @staticmethod
    def normalize_response_tool(tool: Any) -> dict[str, Any] | None:
        if isinstance(tool, str):
            tool = {"type": tool}
        if not isinstance(tool, dict):
            return None
        normalized = dict(tool)
        if normalized.get("type") == "function":
            normalized["parameters"] = _normalize_function_parameters(
                normalized.get("parameters")
            )
        return normalized

    @staticmethod
    def prepare_prompt_caching(
        request: dict[str, Any],
        messages: list[dict[str, Any]],
        model: str = "",
    ) -> None:
        if _prompt_cache_mode(model, request) == "prompt_cache_key":
            _prepare_openai_prompt_cache_params(request, messages, model=model)
        elif not _is_openai_prompt_cache_provider(model, request):
            return

        for key in OPENAI_RESPONSES_EXTRA_BODY_PARAMS:
            if key not in request:
                continue
            extra_body = request.get("extra_body")
            if not isinstance(extra_body, dict):
                extra_body = {}
            extra_body.setdefault(key, request.pop(key))
            request["extra_body"] = extra_body

    @classmethod
    def input_from_messages(
        cls, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        response_input: list[dict[str, Any]] = []

        for message in messages:
            role = str(message.get("role") or "user")
            content = message.get("content", "")

            if role == "tool":
                response_input.append(
                    {
                        "type": "function_call_output",
                        "call_id": str(message.get("tool_call_id") or ""),
                        "output": _content_to_text(content),
                    }
                )
                continue

            tool_calls = message.get("tool_calls")
            if role == "assistant" and isinstance(tool_calls, list) and tool_calls:
                if _has_real_content(content):
                    response_input.append(
                        {
                            "role": "assistant",
                            "content": cls.content_from_chat(content, role=role),
                        }
                    )
                response_input.extend(cls.tool_calls_from_chat(tool_calls))
                continue

            response_input.append(
                {
                    "role": role
                    if role in {"user", "assistant", "system", "developer"}
                    else "user",
                    "content": cls.content_from_chat(content, role=role),
                }
            )

        return response_input

    @classmethod
    def content_from_chat(cls, content: Any, role: str = "user") -> Any:
        content = images.prepare_content(content)
        if not isinstance(content, list):
            return content
        return [
            converted
            for item in content
            if (converted := cls.content_part_from_chat(item, role=role)) is not None
        ]

    @staticmethod
    def content_part_from_chat(item: Any, role: str = "user") -> Any:
        if not isinstance(item, dict):
            return item

        item_type = item.get("type")
        if item_type in {"input_text", "output_text", "input_image", "input_file"}:
            return dict(item)
        if item_type == "text":
            return {
                "type": "output_text" if role == "assistant" else "input_text",
                "text": item.get("text", ""),
            }
        if item_type == "image_url":
            image_url = item.get("image_url")
            if isinstance(image_url, dict):
                url = image_url.get("url", "")
                detail = image_url.get("detail")
            else:
                url = image_url or ""
                detail = item.get("detail")
            result = {"type": "input_image", "image_url": url}
            if detail:
                result["detail"] = detail
            return result

        return dict(item)

    @staticmethod
    def tool_calls_from_chat(tool_calls: list[Any]) -> list[dict[str, Any]]:
        response_input: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function = tool_call.get("function") or {}
            if not isinstance(function, dict):
                function = {}
            response_input.append(
                {
                    "type": "function_call",
                    "call_id": str(tool_call.get("id") or ""),
                    "id": str(tool_call.get("id") or ""),
                    "name": str(function.get("name") or tool_call.get("name") or ""),
                    "arguments": str(function.get("arguments") or ""),
                    "status": "completed",
                }
            )
        return response_input

    @staticmethod
    def tools_from_chat(tools: Any) -> Any:
        if not isinstance(tools, list):
            return tools
        response_tools: list[Any] = []
        for tool in tools:
            if not isinstance(tool, dict):
                response_tools.append(tool)
                continue
            if tool.get("type") == "function" and isinstance(
                tool.get("function"), dict
            ):
                function = tool["function"]
                response_tool = {
                    "type": "function",
                    "name": function.get("name", ""),
                    "description": function.get("description", ""),
                    "parameters": _normalize_function_parameters(
                        function.get("parameters")
                    ),
                }
                if "strict" in function:
                    response_tool["strict"] = function["strict"]
                response_tools.append(response_tool)
            else:
                response_tools.append(dict(tool))
        return response_tools

    @staticmethod
    def tool_choice_from_function_call(function_call: Any) -> Any:
        if isinstance(function_call, str):
            return function_call
        if isinstance(function_call, dict) and function_call.get("name"):
            return {"type": "function", "name": function_call["name"]}
        return function_call

    @staticmethod
    def tool_choice_from_chat(tool_choice: Any) -> Any:
        if (
            isinstance(tool_choice, dict)
            and tool_choice.get("type") == "function"
            and isinstance(tool_choice.get("function"), dict)
        ):
            return {"type": "function", "name": tool_choice["function"].get("name", "")}
        return tool_choice

    @staticmethod
    def text_from_response_format(response_format: Any) -> tuple[Any, Any]:
        if isinstance(response_format, type):
            return None, response_format
        if not isinstance(response_format, dict):
            return response_format, None

        format_type = response_format.get("type")
        if format_type == "json_schema":
            schema = response_format.get("json_schema") or {}
            return (
                {
                    "format": {
                        "type": "json_schema",
                        "name": schema.get("name", "response_schema"),
                        "schema": schema.get("schema", {}),
                        "strict": schema.get("strict", False),
                    }
                },
                None,
            )
        if format_type:
            return {"format": {"type": format_type}}, None
        return response_format, None

    @staticmethod
    def normalize_reasoning(reasoning: Any) -> Any:
        if isinstance(reasoning, dict):
            normalized = dict(reasoning)
            if "effort" in normalized:
                effort = _normalize_reasoning_effort(normalized.get("effort"))
                if effort is None:
                    normalized.pop("effort", None)
                else:
                    normalized["effort"] = effort
            return normalized or None
        if reasoning is None:
            return None
        effort = _normalize_reasoning_effort(reasoning)
        return {"effort": effort} if effort is not None else None

    @classmethod
    def parse_response(cls, response: Any) -> ChatChunk:
        response_delta = cls.output_text(response)
        reasoning_delta = cls.reasoning_text(response)
        if not response_delta:
            response_delta = cls.function_calls_text(response)
        return {"reasoning_delta": reasoning_delta, "response_delta": response_delta}

    @classmethod
    def parse_event(cls, event: Any) -> ChatChunk:
        return ResponsesEventParser().parse(event)

    @classmethod
    def output_text(cls, response: Any) -> str:
        output_text = _get_value(response, "output_text")
        if isinstance(output_text, str):
            return output_text

        pieces: list[str] = []
        for item in _as_list(_get_value(response, "output")):
            if _get_value(item, "type") != "message":
                continue
            for block in _as_list(_get_value(item, "content")):
                block_type = _get_value(block, "type")
                if block_type in {"output_text", "text"}:
                    text = _get_value(block, "text")
                    if isinstance(text, str):
                        pieces.append(text)
                elif block_type == "refusal":
                    refusal = _get_value(block, "refusal")
                    if isinstance(refusal, str):
                        pieces.append(refusal)
        return "".join(pieces)

    @staticmethod
    def reasoning_text(response: Any) -> str:
        pieces: list[str] = []
        for item in _as_list(_get_value(response, "output")):
            if _get_value(item, "type") != "reasoning":
                continue
            for block in _as_list(_get_value(item, "summary")):
                text = _get_value(block, "text") or _get_value(block, "reasoning")
                if isinstance(text, str):
                    pieces.append(text)
        return "".join(pieces)

    @classmethod
    def function_calls_text(cls, response: Any) -> str:
        calls = [
            cls.function_call_object(item)
            for item in _as_list(_get_value(response, "output"))
        ]
        calls = [call for call in calls if call]
        if not calls:
            return ""
        if len(calls) == 1:
            return json.dumps(calls[0])
        return json.dumps(
            {"tool_name": "parallel_tool_calls", "tool_args": {"calls": calls}}
        )

    @classmethod
    def function_call_text(cls, item: Any) -> str:
        call = cls.function_call_object(item)
        if not call:
            return ""
        return json.dumps(call, ensure_ascii=False)

    @staticmethod
    def function_call_object(item: Any) -> dict[str, Any]:
        if _get_value(item, "type") != "function_call":
            return {}
        name = _get_value(item, "name")
        if not name:
            return {}
        raw_arguments = _get_value(item, "arguments") or "{}"
        if isinstance(raw_arguments, str):
            try:
                args = json.loads(raw_arguments or "{}")
            except Exception:
                args = {"arguments": raw_arguments}
        elif isinstance(raw_arguments, dict):
            args = raw_arguments
        else:
            args = {"arguments": raw_arguments}
        if not isinstance(args, dict):
            args = {"arguments": args}
        return {
            "tool_name": str(name),
            "tool_args": args,
        }


class ResponsesEventParser:
    """Stateful parser for Responses streaming events."""

    def __init__(self) -> None:
        self.output_items: dict[str, dict[str, Any]] = {}
        self.output_index_keys: dict[str, str] = {}
        self.emitted_function_calls: set[str] = set()
        self.streamed_function_calls: dict[str, str] = {}
        self.pending_function_calls: dict[str, Any] = {}
        self.commentary: dict[str, str] = {}
        self.seen_response_delta = False
        self.seen_reasoning_delta = False
        self.completed_response: Any = None

    @property
    def function_calls(self) -> dict[str, dict[str, Any]]:
        return {key: item for key, item in self.output_items.items() if item.get("type") == "function_call"}

    def finish(self) -> dict[str, Any] | None:
        if self.completed_response is None:
            if self.function_calls:
                raise RuntimeError("Responses stream ended before native tool calls completed")
            return None
        response = _object_to_dict(self.completed_response)
        output = list(_as_list(response.get("output")))
        has_terminal_output = bool(output)
        positions = {key: int(index) for index, key in self.output_index_keys.items()}
        streamed = sorted(
            enumerate(self.output_items.items()),
            key=lambda entry: positions.get(entry[1][0], entry[0]),
        )
        for fallback_index, (key, item) in streamed:
            if has_terminal_output and not item.get("id") and not item.get("call_id"):
                continue  # An unidentified stream fragment cannot add another terminal call.
            match = next((
                index for index, final in enumerate(output)
                if _get_value(final, "type") == item.get("type") and any(
                    item.get(field) and item[field] == _get_value(final, field)
                    for field in ("id", "call_id")
                )
            ), None)
            if match is None:
                output.insert(min(positions.get(key, fallback_index), len(output)), dict(item))
            else:
                output[match] = {
                    **item,
                    **{field: value for field, value in _object_to_dict(output[match]).items() if value is not None},
                }
        response["output"] = output
        return response

    def parse(self, event: Any) -> ChatChunk:
        event_type = _get_value(event, "type") or ""
        response_delta = ""
        reasoning_delta = ""
        is_commentary = False

        if event_type in {
            "response.output_text.delta",
            "response.refusal.delta",
            "response.text.delta",
        }:
            response_delta = str(_get_value(event, "delta") or "")
            key = self._event_key(event)
            item = self.output_items.get(key, {})
            if event_type != "response.refusal.delta" and item.get("phase") == "commentary":
                self.commentary[key] = self.commentary.get(key, "") + response_delta
                is_commentary = True
        elif event_type in {
            "response.reasoning_summary_text.delta",
            "response.reasoning_text.delta",
        }:
            reasoning_delta = str(_get_value(event, "delta") or "")
        elif event_type == "response.output_item.added":
            self._remember_output_item(_get_value(event, "item"), event)
        elif event_type == "response.function_call_arguments.delta":
            response_delta = self._append_function_call_arguments(event)
        elif event_type == "response.function_call_arguments.done":
            response_delta = self._complete_function_call(event)
        elif event_type == "response.output_item.done":
            response_delta = self._complete_output_item(_get_value(event, "item"), event)
        elif event_type == "response.completed":
            response_delta, reasoning_delta = self._complete_response(event)
        elif event_type == "response.incomplete":
            raise RuntimeError("Responses generation incomplete; tool calls were not executed")
        elif event_type == "response.failed":
            raise RuntimeError(self._response_error_message(event))
        elif event_type == "error":
            error = _get_value(event, "error")
            message = _get_value(error, "message") or error
            raise RuntimeError(str(message))

        if response_delta:
            self.seen_response_delta = True
        if reasoning_delta:
            self.seen_reasoning_delta = True

        parsed = {"reasoning_delta": reasoning_delta, "response_delta": response_delta}
        is_call = event_type in {
            "response.function_call_arguments.delta", "response.function_call_arguments.done",
        } or event_type == "response.output_item.done"
        if self.commentary and response_delta and (is_commentary or is_call):
            parsed["response_preview"] = self._commentary_preview()
        return parsed

    def _commentary_preview(self) -> str:
        preview = {"thoughts": list(self.commentary.values())}
        calls = [(key, item) for key, item in self.function_calls.items()
                 if key in self.emitted_function_calls or key in self.streamed_function_calls]
        if len(calls) == 1:
            key, item = calls[0]
            if key in self.streamed_function_calls:
                return (json.dumps(preview, ensure_ascii=False)[:-1]
                        + ',"tool_name":' + json.dumps(item["name"], ensure_ascii=False)
                        + ',"tool_args":' + item["arguments"])
            preview.update(ResponsesTransport.function_call_object(item))
        elif calls:
            preview.update(tool_name="parallel_tool_calls", tool_args={
                "calls": [ResponsesTransport.function_call_object(item) for _, item in calls],
            })
        return json.dumps(preview, ensure_ascii=False)

    def _remember_output_item(self, item: Any, event: Any) -> str:
        item_type = _get_value(item, "type")
        if not item_type:
            return ""
        key = self._event_key(event, item)
        if not key:
            return ""
        current = self.output_items.get(key, {})
        merged = {**current, **{field: value for field, value in _object_to_dict(item).items() if value is not None}}
        self.output_items[key] = merged
        output_index = _get_value(event, "output_index")
        if output_index is not None:
            self.output_index_keys[str(output_index)] = key
        return key

    def _append_function_call_arguments(self, event: Any) -> str:
        key = self._event_key(event)
        if not key:
            return ""
        current = self.output_items.setdefault(key, {"type": "function_call"})
        delta = str(_get_value(event, "delta") or "")
        current["arguments"] = str(current.get("arguments") or "") + delta
        if (
            not current.get("name")
            or key in self.emitted_function_calls
            or key in self.pending_function_calls
            or (self.streamed_function_calls and key not in self.streamed_function_calls)
        ):
            return ""
        if key not in self.streamed_function_calls:
            self.streamed_function_calls[key] = str(current["arguments"])
            return (
                '{"tool_name":' + json.dumps(current["name"], ensure_ascii=False)
                + ',"tool_args":' + str(current["arguments"])
            )
        self.streamed_function_calls[key] += delta
        return delta

    def _complete_function_call(self, event: Any) -> str:
        key = self._event_key(event)
        if not key:
            return ""
        current = self.output_items.setdefault(key, {"type": "function_call"})
        if _get_value(event, "arguments") is not None:
            current["arguments"] = _get_value(event, "arguments")
        if _get_value(event, "name"):
            current["name"] = _get_value(event, "name")
        if key in self.streamed_function_calls:
            return self._finish_function_call(key, current)
        return self._emit_function_call(key, current)

    def _complete_output_item(self, item: Any, event: Any) -> str:
        key = self._remember_output_item(item, event)
        current = self.output_items.get(key, {})
        if current.get("type") != "function_call":
            return ""
        if key in self.streamed_function_calls:
            return self._finish_function_call(key, current)
        return self._emit_function_call(key, current)

    def _finish_function_call(self, key: str, item: Any) -> str:
        streamed = self.streamed_function_calls.pop(key)
        arguments = str(_get_value(item, "arguments") or "")
        self.emitted_function_calls.add(key)
        tail = arguments[len(streamed) :] if arguments.startswith(streamed) else ""
        pending = self.pending_function_calls
        self.pending_function_calls = {}
        return tail + "}" + "".join(
            self._emit_function_call(pending_key, pending_item)
            for pending_key, pending_item in pending.items()
        )

    def _complete_response(self, event: Any) -> tuple[str, str]:
        self.completed_response = _get_value(event, "response")
        if self.seen_response_delta or self.emitted_function_calls:
            return "", ""
        parsed = ResponsesTransport.parse_response(self.completed_response)
        if self.seen_reasoning_delta:
            parsed["reasoning_delta"] = ""
        return parsed["response_delta"], parsed["reasoning_delta"]

    def _emit_function_call(self, key: str, item: Any) -> str:
        if key in self.emitted_function_calls:
            return ""
        if self.streamed_function_calls:
            self.pending_function_calls[key] = item
            return ""
        text = ResponsesTransport.function_call_text(item)
        if text:
            self.emitted_function_calls.add(key)
        return text

    def _event_key(self, event: Any, item: Any = None) -> str:
        key = _get_value(event, "item_id") or _get_value(item, "id")
        if key:
            return str(key)
        output_index = _get_value(event, "output_index")
        if output_index is not None:
            output_key = self.output_index_keys.get(str(output_index))
            if output_key:
                return output_key
            return f"output:{output_index}"
        return ""

    def _response_error_message(self, event: Any) -> str:
        response = _get_value(event, "response") or {}
        error = _get_value(response, "error") or _get_value(event, "error")
        message = _get_value(error, "message") or error
        return str(message or "Responses API request failed")


def clear_transport_capability_cache() -> None:
    RESPONSES_UNSUPPORTED_CACHE.clear()
    RESPONSES_STATE_UNSUPPORTED_CACHE.clear()
    RESPONSES_BUILTIN_UNSUPPORTED_CACHE.clear()
    STREAM_USAGE_UNSUPPORTED_CACHE.clear()


def delete_stored_response_ids(
    response_ids: list[str], **kwargs: Any
) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    for response_id in response_ids:
        try:
            delete_responses(response_id=response_id, **kwargs)
        except Exception as exc:
            errors.append((response_id, _exception_text(exc)))
    return errors


async def adelete_stored_response_ids(
    response_ids: list[str], **kwargs: Any
) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    for response_id in response_ids:
        try:
            await adelete_responses(response_id=response_id, **kwargs)
        except Exception as exc:
            errors.append((response_id, _exception_text(exc)))
    return errors


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", "none"}:
            return False
    return bool(value)


def _responses_cache_key(model: str, kwargs: dict[str, Any]) -> str:
    api_base = (
        kwargs.get("api_base")
        or kwargs.get("base_url")
        or kwargs.get("api_base_url")
        or ""
    )
    custom_provider = kwargs.get("custom_llm_provider") or ""
    return "|".join(str(part) for part in (model, custom_provider, api_base))


def _drop_legacy_transport_kwargs(kwargs: dict[str, Any]) -> None:
    kwargs.pop("a0_api_mode", None)
    kwargs.pop("a0_responses_fallback", None)


def _drop_responses_only_kwargs(kwargs: dict[str, Any]) -> None:
    kwargs.pop("responses_state", None)
    kwargs.pop("responses_delete_on_chat_delete", None)
    kwargs.pop("responses_input_items", None)
    kwargs.pop("responses_local_input_items", None)
    kwargs.pop("responses_prompt_replacements", None)
    kwargs.pop("responses_history_context", None)
    kwargs.pop("previous_response_id", None)
    kwargs.pop("_a0_responses_builtin_downgrades", None)


def _drop_internal_transport_kwargs(kwargs: dict[str, Any]) -> None:
    _drop_legacy_transport_kwargs(kwargs)
    kwargs.pop("a0_prompt_cache_mode", None)
    kwargs.pop("a0_explicit_prompt_caching", None)
    kwargs.pop("a0_responses_function_tools", None)
    kwargs.pop("responses_builtin_tools", None)
    _drop_responses_only_kwargs(kwargs)


def _normalize_responses_state(value: Any) -> str:
    normalized = str(value or RESPONSES_STATE_PROVIDER).strip().lower()
    return normalized if normalized in RESPONSES_STATES else RESPONSES_STATE_PROVIDER


def _filter_unsupported_builtin_tools(kwargs: dict[str, Any], cache_key: str) -> None:
    unsupported = RESPONSES_BUILTIN_UNSUPPORTED_CACHE.get(cache_key)
    if not unsupported:
        return
    tools = kwargs.get("responses_builtin_tools")
    if not isinstance(tools, list):
        return
    filtered = []
    downgraded = []
    for tool in tools:
        tool_type = _response_tool_type(tool)
        if tool_type in unsupported:
            downgraded.append(tool_type)
            continue
        filtered.append(tool)
    if downgraded:
        kwargs["responses_builtin_tools"] = filtered
        kwargs["_a0_responses_builtin_downgrades"] = sorted(set(downgraded))


def _builtin_tool_types(tools: Any) -> set[str]:
    return {
        tool_type
        for tool in _as_list(tools)
        if (tool_type := _response_tool_type(tool))
    }


def _response_tool_type(tool: Any) -> str:
    if isinstance(tool, str):
        return tool
    if isinstance(tool, dict):
        return str(tool.get("type") or "")
    return ""


def _normalize_function_parameters(parameters: Any) -> dict[str, Any]:
    if not isinstance(parameters, dict):
        return _permissive_function_parameters()

    normalized = dict(parameters)
    normalized.setdefault("type", "object")
    if normalized.get("type") == "object" and not isinstance(
        normalized.get("properties"), dict
    ):
        normalized["properties"] = {}
    return normalized or _permissive_function_parameters()


def _permissive_function_parameters() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "additionalProperties": True}


def apply_chat_prompt_cache_markers(
    messages: list[dict[str, Any]],
    *,
    model: str = "",
    kwargs: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if _prompt_cache_mode(model, kwargs or {}) != "cache_control":
        return [dict(message) for message in messages]

    prepared = [_strip_message_cache_control(message) for message in messages]
    for index in _prompt_cache_message_indexes(prepared):
        prepared[index] = _message_with_cache_control(prepared[index])
    return prepared


def _prompt_cache_message_indexes(messages: list[dict[str, Any]]) -> list[int]:
    indexes: list[int] = []

    leading_context: list[int] = []
    for index, message in enumerate(messages):
        role = str(message.get("role") or "")
        if role in {"system", "developer"}:
            leading_context.append(index)
            continue
        break
    if leading_context:
        indexes.append(leading_context[-1])

    # The trailing user/tool result includes extras rebuilt on every turn.
    assistant_indexes = [
        index
        for index, message in enumerate(messages)
        if str(message.get("role") or "") == "assistant" and message.get("content")
    ]
    return indexes + assistant_indexes[-2:]


def _strip_message_cache_control(message: dict[str, Any]) -> dict[str, Any]:
    result = dict(message)
    result.pop("cache_control", None)
    return result


def _message_with_cache_control(message: dict[str, Any]) -> dict[str, Any]:
    result = dict(message)
    result["content"] = _content_with_cache_control(result.get("content", ""))
    return result


def _content_with_cache_control(content: Any) -> Any:
    marker = _cache_control_marker()
    if isinstance(content, list):
        blocks = [_copy_content_block(block) for block in content]
        if not blocks:
            return [{"type": "text", "text": "", "cache_control": marker}]
        for index in range(len(blocks) - 1, -1, -1):
            block = blocks[index]
            if isinstance(block, dict):
                if block.get("type") in {"thinking", "redacted_thinking"}:
                    continue
                block["cache_control"] = marker
                return blocks
            if isinstance(block, str):
                blocks[index] = {
                    "type": "text",
                    "text": block,
                    "cache_control": marker,
                }
                return blocks
        return blocks

    if isinstance(content, dict):
        block = dict(content)
        block["cache_control"] = marker
        return block

    return [
        {
            "type": "text",
            "text": _content_to_text(content),
            "cache_control": marker,
        }
    ]


def _copy_content_block(block: Any) -> Any:
    if isinstance(block, dict):
        return dict(block)
    if isinstance(block, list):
        return [_copy_content_block(item) for item in block]
    return block


def _apply_tool_cache_control(kwargs: dict[str, Any]) -> None:
    tools = kwargs.get("tools")
    if not isinstance(tools, list) or not tools or _has_cache_control(tools):
        return

    prepared = [dict(tool) if isinstance(tool, dict) else tool for tool in tools]
    for index in range(len(prepared) - 1, -1, -1):
        tool = prepared[index]
        if not isinstance(tool, dict):
            continue
        if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            function = dict(tool["function"])
            function["cache_control"] = _cache_control_marker()
            tool = dict(tool)
            tool["function"] = function
            prepared[index] = tool
        else:
            tool = dict(tool)
            tool["cache_control"] = _cache_control_marker()
            prepared[index] = tool
        kwargs["tools"] = prepared
        return


def _cache_control_marker() -> dict[str, str]:
    return {"type": "ephemeral"}


def _should_preserve_cache_control_on_chat(
    model: str,
    kwargs: dict[str, Any],
    messages: list[dict[str, Any]],
) -> bool:
    if not (_has_cache_control(messages) or _has_cache_control(kwargs.get("tools"))):
        return False
    return (
        _prompt_cache_mode(model, kwargs) == "cache_control"
        or not _is_native_responses_provider(model, kwargs)
    )


def _prompt_cache_mode(model: str, kwargs: dict[str, Any]) -> str:
    value = kwargs.get("a0_prompt_cache_mode")
    mode = "auto" if value is None else str(value).strip().lower()
    if mode not in {"auto", "prompt_cache_key", "cache_control", "off"}:
        raise ValueError(
            "a0_prompt_cache_mode must be auto, prompt_cache_key, cache_control, or off"
        )
    if mode != "auto":
        return mode
    if _is_openai_prompt_cache_provider(model, kwargs):
        return "prompt_cache_key"
    if _supports_cache_control_markers(model, kwargs):
        return "cache_control"
    return "off"


def _is_native_responses_provider(model: str, kwargs: dict[str, Any]) -> bool:
    api_base = _api_base(kwargs)
    if "openrouter.ai" in api_base or "anthropic.com" in api_base:
        return False

    provider = _normalized_provider(model, kwargs)
    return provider in {"openai", "azure", "azure_ai", "xai"}


def _supports_cache_control_markers(
    model: str,
    kwargs: dict[str, Any],
) -> bool:
    api_base = _api_base(kwargs)
    if "openrouter.ai" in api_base or "anthropic.com" in api_base:
        return True
    provider = _normalized_provider(model, kwargs)
    return provider in CACHE_CONTROL_PROMPT_PROVIDERS


def _is_openai_prompt_cache_provider(model: str, kwargs: dict[str, Any]) -> bool:
    api_base = _api_base(kwargs)
    provider = _normalized_provider(model, kwargs)

    if api_base:
        if "api.openai.com" in api_base:
            return provider in {"", "openai"}
        if "openai.azure.com" in api_base:
            return provider in {"", "azure", "openai"}
        return False

    if not provider and str(model):
        provider = "openai"
    return provider in OPENAI_PROMPT_CACHE_PROVIDERS


def _api_base(kwargs: dict[str, Any]) -> str:
    return str(
        kwargs.get("api_base")
        or kwargs.get("base_url")
        or kwargs.get("api_base_url")
        or ""
    ).lower()


def _normalized_provider(model: str, kwargs: dict[str, Any]) -> str:
    provider = str(kwargs.get("custom_llm_provider") or "").strip().lower()
    if not provider and "/" in str(model):
        provider = str(model).split("/", 1)[0].strip().lower()
    return provider.replace("-", "_")


def _prepare_openai_prompt_cache_params(
    request: dict[str, Any],
    messages: list[dict[str, Any]],
    *,
    model: str = "",
) -> None:
    extra_body = request.get("extra_body")
    if "prompt_cache_key" in request or (
        isinstance(extra_body, dict) and "prompt_cache_key" in extra_body
    ):
        return

    sanitized_messages = _without_cache_control(messages)
    sanitized_request = _without_cache_control(request)
    prompt_cache_key = _default_prompt_cache_key(
        model,
        sanitized_messages if isinstance(sanitized_messages, list) else messages,
        sanitized_request if isinstance(sanitized_request, dict) else request,
    )
    if prompt_cache_key:
        request["prompt_cache_key"] = prompt_cache_key


def _default_prompt_cache_key(
    model: str,
    messages: list[dict[str, Any]],
    request: dict[str, Any],
) -> str:
    material = _prompt_cache_key_material(messages, request)
    if not material:
        return ""
    digest = hashlib.sha256(
        json.dumps(
            {
                "model": model,
                "material": material,
            },
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:32]
    return f"a0-{digest}"


def _prompt_cache_key_material(
    messages: list[dict[str, Any]],
    request: dict[str, Any],
) -> dict[str, Any]:
    material: dict[str, Any] = {}

    leading_messages: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "")
        if role not in {"system", "developer"}:
            break
        leading_messages.append(
            {
                "role": role,
                "content": message.get("content"),
            }
        )
    if leading_messages:
        material["messages"] = leading_messages

    if request.get("instructions"):
        material["instructions"] = request["instructions"]
    if request.get("prompt"):
        material["prompt"] = request["prompt"]
    if request.get("tools"):
        material["tools"] = request["tools"]

    return material


def _has_cache_control(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("cache_control") is not None:
            return True
        return any(_has_cache_control(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_cache_control(item) for item in value)
    return False


def _without_cache_control(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_cache_control(item)
            for key, item in value.items()
            if key != "cache_control"
        }
    if isinstance(value, list):
        return [_without_cache_control(item) for item in value]
    return value


def _object_to_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        dumped = obj.model_dump()
        return dict(dumped) if isinstance(dumped, dict) else {}
    if hasattr(obj, "dict"):
        dumped = obj.dict()
        return dict(dumped) if isinstance(dumped, dict) else {}
    return {}


def _reported_usage(response: Any) -> dict[str, Any]:
    usage = _object_to_dict(_get_value(response, "usage"))
    hidden = _object_to_dict(_get_value(response, "_hidden_params"))
    if usage.get("cost") is None:
        usage.pop("cost", None)
        if hidden.get("response_cost") is not None:
            usage["cost"] = hidden["response_cost"]
    return usage


def _normalize_reasoning_effort(effort: Any) -> str | None:
    if isinstance(effort, str):
        normalized = effort.strip().lower()
    else:
        normalized = str(effort).strip().lower() if effort is not None else ""
    if normalized in RESPONSES_REASONING_EFFORTS:
        return normalized
    if normalized in NO_REASONING_EFFORT_ALIASES:
        return None
    return RESPONSES_REASONING_FALLBACK_EFFORT


def _is_responses_reasoning_effort_error(exc: Exception) -> bool:
    text = _exception_text(exc).lower()
    return (
        "response.reasoning.effort" in text
        and "minimal" in text
        and "high" in text
        and "none" in text
    )


def _is_responses_not_supported_error(exc: Exception) -> bool:
    text = _exception_text(exc).lower()
    if any(marker in text for marker in ("429", "too many requests", "rate limit")):
        return False
    if _is_sse_json_decode_error(exc):
        return True
    if _is_bad_request_error(exc) and _looks_like_responses_request_rejected(text):
        return True
    if _is_server_error(exc) and _looks_like_responses_endpoint(text):
        return True
    if _is_not_found_error(exc) and _looks_like_responses_endpoint_not_found(text):
        return True
    if "/v1/responses" in text and any(
        marker in text for marker in ("404", "not found")
    ):
        return True
    return any(
        marker in text
        for marker in (
            "responses api",
            "does not support responses",
            "not support responses",
            "unsupportedparamserror",
            "does not support parameters",
            "no 'tools' defined while 'tool_choice' is specified",
            "tools` must not be an empty array",
            "tools must not be an empty array",
            "not available through this proxy",
            "litellm[proxy]",
            "no module named 'fastapi'",
        )
    )


def _is_not_found_error(exc: Exception) -> bool:
    if _exception_status_code(exc) == 404:
        return True
    return "notfounderror" in _exception_type_chain(exc).lower()


def _is_bad_request_error(exc: Exception) -> bool:
    if _exception_status_code(exc) == 400:
        return True
    type_chain = _exception_type_chain(exc).lower()
    if "badrequesterror" in type_chain:
        return True
    text = _exception_text(exc).lower()
    return "400" in text and "bad request" in text


def _is_stream_usage_rejected_error(exc: Exception) -> bool:
    text = _exception_text(exc).lower()
    if "stream_options" not in text:
        return False
    return _is_bad_request_error(exc) or _exception_status_code(exc) == 422


def _is_server_error(exc: Exception) -> bool:
    status_code = _exception_status_code(exc)
    if isinstance(status_code, int) and 500 <= status_code < 600:
        return True
    type_chain = _exception_type_chain(exc).lower()
    if "internalservererror" in type_chain:
        return True
    text = _exception_text(exc).lower()
    return any(
        marker in text
        for marker in (
            "500 internal server error",
            "server error '500",
            "internalservererror",
        )
    )


def _is_sse_json_decode_error(exc: Exception) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, json.JSONDecodeError) and _looks_like_sse_payload(
            current.doc
        ):
            return True
        current = current.__cause__ or (
            current.__context__ if current.__context__ is not current.__cause__ else None
        )
    return _looks_like_sse_payload(_exception_text(exc))


def _looks_like_sse_payload(text: Any) -> bool:
    if not isinstance(text, str):
        return False
    lowered = text.lstrip().lower()
    return lowered.startswith("event:") and "\ndata:" in lowered


def _looks_like_responses_request_rejected(text: str) -> bool:
    if "/v1/responses" in text or "responses api" in text:
        return True
    return any(
        marker in text
        for marker in (
            "input_image",
            "response.input",
            "expected object, received string",
            "expected string, received array",
            "zod",
            "failed to deserialize input",
            "failed to deserialize response",
            "failed to deserialize responses",
            "cannot determine type",
        )
    )


def _looks_like_responses_endpoint_not_found(text: str) -> bool:
    if "/v1/responses" in text:
        return True
    if "not found" not in text:
        return False
    if "openaiexception" in text:
        return True
    return "detail" in text and "not found" in text


def _looks_like_responses_endpoint(text: str) -> bool:
    return "/responses" in text or "path /api/v1/responses" in text


def _is_responses_state_unsupported_error(exc: Exception) -> bool:
    text = _exception_text(exc).lower()
    if any(marker in text for marker in ("429", "too many requests", "rate limit")):
        return False
    if "404" in text and "/v1/responses/" in text:
        return True
    return any(
        marker in text
        for marker in (
            "previous_response_id",
            "store",
            "stored response",
            "response not found",
            "no response found",
            "does not support response storage",
            "doesn't support response storage",
            "response storage is not supported",
            "state is not supported",
        )
    )


def _is_responses_builtin_tool_error(exc: Exception) -> bool:
    text = _exception_text(exc).lower()
    if any(marker in text for marker in ("429", "too many requests", "rate limit")):
        return False
    return any(
        marker in text
        for marker in (
            "unsupported tool",
            "unsupported tools",
            "invalid tool",
            "tool type",
            "tools[",
            "web_search",
            "file_search",
            "code_interpreter",
            "image_generation",
            "computer_use_preview",
            "mcp",
        )
    )


def _exception_text(exc: Exception | None) -> str:
    if exc is None:
        return ""
    parts = [exc.__class__.__name__, str(exc)]
    for attr in ("status_code", "code", "message", "body"):
        value = getattr(exc, attr, None)
        if value not in (None, ""):
            parts.append(f"{attr}={value}")
    response = getattr(exc, "response", None)
    if response is not None:
        response_text = getattr(response, "text", None)
        if response_text:
            parts.append(str(response_text))
        response_url = getattr(response, "url", None)
        if response_url:
            parts.append(str(response_url))
    cause = getattr(exc, "__cause__", None)
    context = getattr(exc, "__context__", None)
    if cause is not None:
        parts.append(str(cause))
    if context is not None and context is not cause:
        parts.append(str(context))
    return "\n".join(parts)


def _exception_status_code(exc: Exception | None) -> int | None:
    if exc is None:
        return None
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _exception_type_chain(exc: Exception | None) -> str:
    names: list[str] = []
    current = exc
    while current is not None:
        names.append(current.__class__.__name__)
        cause = getattr(current, "__cause__", None)
        context = getattr(current, "__context__", None)
        current = cause or (context if context is not cause else None)
    return "\n".join(names)


def _close_sync_stream(stream: Any) -> None:
    for method_name in ("close", "aclose"):
        close = getattr(stream, method_name, None)
        if close is None:
            continue
        result = close()
        if inspect.isawaitable(result):
            result.close()
        return


async def _close_async_stream(stream: Any) -> None:
    for method_name in ("aclose", "close"):
        close = getattr(stream, method_name, None)
        if close is None:
            continue
        result = close()
        if inspect.isawaitable(result):
            await result
        return


def _without_stream_kwarg(kwargs: dict[str, Any]) -> dict[str, Any]:
    kwargs.pop("stream", None)
    return kwargs


def _first_choice(chunk: Any) -> Any:
    choices = _get_value(chunk, "choices") or []
    return choices[0] if choices else {}


def _get_value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    value = getattr(obj, key, None)
    if value is not None:
        return value
    return _object_to_dict(obj).get(key)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _has_tools(tools: Any) -> bool:
    if isinstance(tools, list):
        return bool(tools)
    return bool(tools)


def _has_chunk_delta(chunk: ChatChunk) -> bool:
    return bool(chunk.get("response_delta") or chunk.get("reasoning_delta"))


def _has_real_content(content: Any) -> bool:
    if content == "empty":
        return False
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return len(content) > 0
    return content is not None


def _content_to_text(content: Any) -> str:
    content = images.prepare_content(content)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, str):
                pieces.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    pieces.append(text)
        return "\n".join(pieces)
    return "" if content is None else str(content)
