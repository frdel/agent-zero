import time
from typing import Any

from plugins._context_window.helpers.usage import (
    PROVIDER_USAGE_KEY,
    _mapping,
    _optional_non_negative_int,
    _temporary_params,
    provider_usage_snapshot,
)

OUTPUT_TIMING_KEY = "_context_window_output_timing"
OUTPUT_SPEED_KEY = "context_window_output_speed"
# Shorter windows are dominated by the one decode step that callbacks can
# miss at either end of the stream.
MIN_OUTPUT_SECONDS = 1.0
clock = time.monotonic


def start_output_timing(agent: Any, data: dict[str, Any]) -> None:
    """Time the streamed deltas of one main model call.

    The wrappers only take timestamps: they pass every argument through and
    return the inner callback result unchanged, so early stop and the usage
    drain keep working.
    """
    kwargs = data.get("kwargs")
    if not isinstance(kwargs, dict):
        return

    timing: dict[str, Any] = {
        "first": None,
        "last": None,
        "deltas": 0,
        "answer_first": None,
        "answer_last": None,
        "answer_deltas": 0,
        "reasoning_chars": 0,
        "paused": False,
    }

    def timed(callback: Any, reasoning: bool) -> Any:
        async def timed_callback(chunk: str, full: str):
            now = clock()
            if timing["first"] is None:
                timing["first"] = now
            timing["last"] = now
            timing["deltas"] += 1
            if reasoning:
                timing["reasoning_chars"] = len(full or "")
            else:
                if timing["answer_first"] is None:
                    timing["answer_first"] = now
                timing["answer_last"] = now
                timing["answer_deltas"] += 1
            return await callback(chunk, full)

        return timed_callback

    for key, reasoning in (("response_callback", False), ("reasoning_callback", True)):
        callback = kwargs.get(key)
        if callback is not None:
            kwargs[key] = timed(callback, reasoning)
    data[OUTPUT_TIMING_KEY] = timing
    params = _temporary_params(agent)
    if params is not None:
        params[OUTPUT_TIMING_KEY] = timing


def flag_output_pause(agent: Any) -> None:
    """Mark the streaming call as paused.

    Runs where the agent waits for a pause. The provider keeps generating
    meanwhile, so the window no longer measures generation.
    """
    params = _temporary_params(agent)
    timing = params.get(OUTPUT_TIMING_KEY) if params is not None else None
    context = getattr(agent, "context", None)
    if isinstance(timing, dict) and getattr(context, "paused", False):
        timing["paused"] = True


def finish_output_timing(agent: Any, data: dict[str, Any]) -> Any:
    params = _temporary_params(agent)
    if params is not None:
        params.pop(OUTPUT_TIMING_KEY, None)
    return data.pop(OUTPUT_TIMING_KEY, None)


def measure_output_speed(
    provider_usage: Any, timing: Any
) -> dict[str, int | float] | None:
    """Decode speed: tokens after the first one per second of streaming.

    When the provider reports reasoning that was not streamed (hidden or only
    summarized), that reasoning ran outside the stream, so only the answer
    counts: output tokens minus reasoning tokens over the answer deltas.

    Returns None instead of a guess when the provider reports no output tokens,
    the call was paused, or the window is too short.
    """
    if not isinstance(timing, dict) or timing.get("paused"):
        return None
    output = provider_usage_snapshot(provider_usage).get("output_tokens")
    if output is None:
        return None
    first, last, deltas = timing.get("first"), timing.get("last"), timing.get("deltas", 0)
    hidden = _unstreamed_reasoning_tokens(provider_usage, timing.get("reasoning_chars", 0))
    if hidden:
        output -= hidden
        first, last = timing.get("answer_first"), timing.get("answer_last")
        deltas = timing.get("answer_deltas", 0)
    if deltas < 2 or first is None or last is None:
        return None
    seconds = last - first
    if not seconds >= MIN_OUTPUT_SECONDS:
        return None
    if output < 2:
        return None
    return {
        "tokens_per_second": round((output - 1) / seconds, 1),
        "output_tokens": int(output),
        "seconds": round(seconds, 2),
    }


def record_output_speed(agent: Any, result: Any, timing: Any) -> None:
    """Add the call's speed to the provider usage recorded just before it."""
    if agent is None:
        return
    speed = measure_output_speed(getattr(result, "usage", None), timing)
    data = getattr(agent, "data", None)
    stored = data.get(PROVIDER_USAGE_KEY) if isinstance(data, dict) else None
    if speed and isinstance(stored, dict):
        agent.set_data(
            PROVIDER_USAGE_KEY,
            {**stored, "output_tokens_per_second": speed["tokens_per_second"]},
        )

    params = _temporary_params(agent)
    if params is not None:
        if speed:
            params[OUTPUT_SPEED_KEY] = speed
        else:
            params.pop(OUTPUT_SPEED_KEY, None)


def log_output_speed(loop_data: Any) -> None:
    params = getattr(loop_data, "params_temporary", None)
    if not isinstance(params, dict):
        return
    speed = params.pop(OUTPUT_SPEED_KEY, None)
    log_item = params.get("log_item_generating")
    if speed and log_item is not None:
        # A keyword update merges into the item's kvps instead of replacing them.
        log_item.update(output_speed=speed)


def _unstreamed_reasoning_tokens(provider_usage: Any, reasoning_chars: int) -> int:
    # Hidden or summarized reasoning is generated outside the answer's stream.
    # Streamed reasoning text runs several characters per token.
    if not isinstance(provider_usage, dict):
        return 0
    details = {
        **_mapping(provider_usage.get("completion_tokens_details")),
        **_mapping(provider_usage.get("output_tokens_details")),
    }
    reasoning_tokens = _optional_non_negative_int(details.get("reasoning_tokens")) or 0
    return reasoning_tokens if reasoning_chars < reasoning_tokens / 2 else 0
