"""Known history-prefix compression without background mutation of live state."""
from __future__ import annotations

import copy

from helpers.durable import background, execution

TASK = "_organize_history_task"


def enqueue(agent):
    from helpers.history import (History, HISTORY_TOPIC_RATIO,
        LARGE_MESSAGE_TO_HISTORY_TOPIC_RATIO, clear_responses_provider_state)
    if not agent.history.is_over_limit():
        return None
    from helpers.durable.runtime import current
    turn = current(agent)
    if turn is None:
        execution._held("background_shared_owner_unavailable")
    turn.owner.sync("assert_owner", turn.run_id)
    # Preserve the ordinary compressor's cheap first step on the owned loop.
    # A prefix summary cannot shrink the newest two messages it protects.
    topics = [(agent.history.current, None)] + [
        (topic, HISTORY_TOPIC_RATIO * LARGE_MESSAGE_TO_HISTORY_TOPIC_RATIO)
        for topic in agent.history.topics]
    for topic, ratio in topics:
        while agent.history.is_over_limit():
            changed = (topic.compress_large_messages() if ratio is None else
                       topic.compress_large_messages(ratio))
            if not changed:
                break
            clear_responses_provider_state(agent)
    if not agent.history.is_over_limit():
        return None
    background._audit(agent, utility=True)
    saved = agent.history.to_dict()
    prefix = copy.deepcopy(saved)
    prefix["current"]["messages"] = prefix["current"]["messages"][:-2]
    old = History.from_dict(prefix, History(agent))
    if not old.output_text().strip():
        return None
    return background.start(agent, "history:" + execution._digest(saved),
        {"kind": "history", "model": "utility", "input": saved,
         "messages": [{"role": "system", "content": agent.read_prompt("fw.topic_summary.sys.md")},
                      {"role": "human", "content": agent.read_prompt("fw.topic_summary.msg.md", content=old.output_text())}]},
        {"utility": agent.get_utility_model()})


def project(spec, summary):
    saved = copy.deepcopy(spec["input"])
    prefix = copy.deepcopy(saved["current"])
    prefix["messages"] = prefix["messages"][:-2]
    # Retain records beneath the summary for response-ID cleanup and inspection.
    records = saved["bulks"] + saved["topics"] + ([prefix] if prefix["messages"] else [])
    saved["bulks"] = [{"_cls": "Bulk", "records": records, "summary": summary}]
    saved["topics"] = []
    saved["current"]["messages"] = saved["current"]["messages"][-2:]
    return {"input": spec["input"], "history": saved}


async def consume(agent, task):
    from helpers.history import History, clear_responses_provider_state
    outcome = await task
    current, original = agent.history.to_dict(), outcome["input"]
    # New user messages may be appended while the detached summary runs. Only
    # an unchanged original prefix may be replaced by its committed projection.
    length = len(original["current"]["messages"])
    base, expected = copy.deepcopy(current), copy.deepcopy(original)
    suffix = base["current"]["messages"][length:]
    base["current"]["messages"] = base["current"]["messages"][:length]
    base["counter"] = expected["counter"]
    if base != expected:
        return False
    projected = copy.deepcopy(outcome["history"])
    projected["counter"] = current["counter"]
    projected["current"]["messages"].extend(suffix)
    restored = History.from_dict(projected, History(agent))
    if restored.get_tokens() >= agent.history.get_tokens():
        return False
    agent.history = restored
    clear_responses_provider_state(agent)
    return True
