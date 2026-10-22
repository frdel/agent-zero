"""Explicit child manifests and joins for the opt-in local recovery runner.

Live task objects are projections only. The manifest, child admission and join
records decide whether a child may execute; an unresolved tool never gets a new
worker merely because its parent restarted.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time

from helpers.durable import codec


def _held(reason):
    from helpers.durable.runtime import RecoveryHeld
    raise RecoveryHeld(reason)


def _turn(agent):
    from helpers.durable.runtime import current
    turn = current(agent)
    if turn is None or not getattr(turn, "active_call_id", None):
        _held("child_workflow_requires_tool_owner")
    return turn


def _key(turn, suffix):
    return turn.active_call_id + ":" + suffix


def restore_context(context, origin):
    """Rebuild explicit ownership and worker metadata without runtime objects."""
    if origin.get("kind") != "child":
        return
    context._durable_origin = origin
    fields = {
        "parent_context_id": origin["parent_context_id"],
        "parent_agent_number": origin["parent_agent_number"],
        "parent_context_kind": "subordinate" if origin["mode"] == "subordinate" else "parallel",
        "parent_context_label": context.name or "",
    }
    if origin.get("slot"):
        fields["subordinate_slot"] = origin["slot"]
    if origin.get("job_id"):
        fields["parallel_job_id"] = origin["job_id"]
        fields["parallel_tool_name"] = origin["tool_name"]
        context.set_data("_parallel_parent_context_id", origin["parent_context_id"])
        context.set_data("_parallel_job_id", origin["job_id"])
        context.set_data("_parallel_worker_kind", origin["mode"])
    for name, value in fields.items():
        context.set_output_data(name, value)


async def dispatch_tool(context, origin):
    from agent import LoopData
    from helpers.parallel_tools import execute_tool_call
    context.agent0.loop_data = context.agent0.loop_data or LoopData()
    return await execute_tool_call(context.agent0, origin["tool_name"], dict(origin["tool_args"]))


def queue_parent_history(agent, *, content, tokens=0):
    """Commit opted-in parent content before acknowledging it to a child tool."""
    from helpers.durable.runtime import current
    turn = current(agent)
    origin = getattr(agent.context, "_durable_origin", None) or {}
    if not turn or origin.get("kind") != "child" or origin.get("mode") != "tool":
        return False
    with turn.owner.lock:
        calls = turn.owner.sync("calls", turn.run_id)
        index = sum(call["kind"] == "parent_history" for call in calls)
        identifier = f"parent-history:{index}"
        payload = codec.masked(agent, {"content": content, "tokens": int(tokens)})
        turn.owner.sync("start_call", turn.run_id, identifier, "parent_history", payload)
        turn.owner.sync("finish_call", turn.run_id, identifier, {"queued": True})
    return True


def descendant_context_ids(owner, parent_run_id):
    """Follow latest ownership using both genesis and independently hashed manifests.

    A corrupt child checkpoint cannot hide its still-owned descendants from
    Stop. A later independent input does retire the old ownership link.
    """
    latest = {}
    for header in owner.sync("list_run_headers"):
        old = latest.get(header["context_id"])
        if getattr(owner, "distributed", False):
            from helpers.durable.cluster import latest_header
            newer = old is None or latest_header(owner, [old, header])["run_id"] == header["run_id"]
        else:
            newer = old is None or header["created_at"] > old["created_at"]
        if newer:
            latest[header["context_id"]] = header
    descendants, frontier, visited = [], {parent_run_id}, set()
    while frontier:
        following = set()
        for parent_id in frontier:
            try:
                calls = owner.sync("calls", parent_id)
            except Exception:
                calls = []  # independently valid child origins remain usable
            for call in calls:
                if call["kind"] != "workflow" or call["status"] != "completed" or not call.get("result"):
                    continue
                for child in call["result"]["children"]:
                    header = latest.get(child["context_id"])
                    if header and header["input_id"] == child["input_id"]:
                        if child["context_id"] not in descendants:
                            descendants.append(child["context_id"])
                        following.add(header["run_id"])
        for header in latest.values():
            if header.get("payloads_pruned"):
                continue
            try:
                run = owner.sync("get_run", header["run_id"])
            except Exception:
                continue
            origin = (run.get("checkpoint") or {}).get("origin") or {}
            if origin.get("kind") == "child" and origin.get("parent_run_id") in frontier:
                if run["context_id"] not in descendants:
                    descendants.append(run["context_id"])
                following.add(run["run_id"])
        visited.update(frontier)
        frontier = following - visited
    return descendants


async def _manifest(turn, specifications):
    owner, parent = turn.owner, turn.agent
    from helpers.durable.resources import canonical_value, capture_context
    descriptor = canonical_value(parent.context, codec.masked(parent, {"specifications": specifications}))
    identifier = _key(turn, "workflow")
    found = await owner.io("get_call", turn.run_id, identifier)
    if found:
        if found["status"] != "completed":
            _held("child_creation_interrupted")
        if found["payload"] != descriptor:
            _held("child_manifest_changed")
        return found["result"]["children"]
    # The intent covers constructors and project/profile hooks as well as genesis.
    await owner.io("start_call", turn.run_id, identifier, "workflow",
                   descriptor)
    from agent import AgentContext, AgentContextType
    from helpers.parallel_tools import _clone_config, _copy_project
    from tools.call_subordinate import get_or_create_subordinate
    children = []
    for index, spec in enumerate(specifications):
        args = spec["args"]
        digest = hashlib.sha256(f"{turn.run_id}:{turn.active_call_id}:{index}".encode()).hexdigest()[:24]
        job_id = f"durable-{digest}"
        mode = "subordinate" if spec["name"] == "call_subordinate" else "tool"
        slot = "default" if len(specifications) == 1 and spec.get("direct") else job_id
        if mode == "subordinate":
            message = str(args.get("message") or "").strip()
            if not message:
                raise ValueError("call_subordinate requires a non-empty `message`.")
            subordinate = get_or_create_subordinate(
                parent, profile=args.get("profile", args.get("agent_profile", "")),
                reset=args.get("reset", False), context_id=args.get("context_id", args.get("agent_id", "")),
                name=args.get("name", ""), message=message, slot=slot)
            context = subordinate.context
            if context is parent.context:
                _held("legacy_shared_subordinate_adapter_required")
            attachments = args.get("attachments") if isinstance(args.get("attachments"), list) else []
        else:
            message, attachments = "Parallel tool invocation", []
            context = AgentContext(_clone_config(parent.context.config), name=f"parallel:{spec['name']}",
                                   type=AgentContextType.BACKGROUND)
            context.set_data("chat_model_override", parent.context.get_data("chat_model_override"))
            _copy_project(parent.context, context)
            context.agent0.last_user_message = parent.last_user_message
        origin = {"kind": "child", "mode": mode, "parent_run_id": turn.run_id,
                  "parent_call_id": turn.active_call_id, "parent_context_id": parent.context.id,
                  "parent_agent_number": parent.number, "index": index, "job_id": job_id,
                  "tool_name": spec["name"], "tool_args": args, "slot": slot}
        origin = codec.masked(parent, origin)
        restore_context(context, origin)
        if getattr(owner, "distributed", False):
            from agent import UserMessage
            pending = UserMessage(message, attachments=attachments, id=job_id)
            capture_context(owner, context, pending)
            attachments = pending.attachments
            origin = canonical_value(parent.context, origin)
            if "attachments" in origin["tool_args"]:
                origin["tool_args"]["attachments"] = attachments
            restore_context(context, origin)
        genesis = codec.checkpoint(context.agent0)
        genesis["origin"] = origin
        children.append({"job_id": job_id, "index": index, "context_id": context.id,
                         "input_id": job_id, "message": message, "attachments": attachments,
                         "origin": origin, "genesis": genesis})
    await owner.io("finish_call", turn.run_id, identifier, codec.masked(parent, {"children": children}))
    return children


def _child_run(owner, child):
    return next((owner.sync("get_run", header["run_id"])
                 for header in owner.sync("list_run_headers", context_id=child["context_id"])
                 if header["input_id"] == child["input_id"]), None)


def _submit(turn, child):
    from agent import AgentContext, UserMessage
    from helpers import persist_chat
    owner = turn.owner
    run = _child_run(owner, child)
    if run and run["status"] != "running" and run["status"] != "completed":
        _held("child_requires_attention")
    if run and (run.get("payloads_pruned") or not run.get("checkpoint")):
        _held("child_outcome_retained_without_payload")
    if run and run["status"] == "completed":
        from helpers.defer import DeferredTask
        return DeferredTask("DurableChildResult").start_task(owner._reported_result, run)
    if getattr(owner, "distributed", False):
        from helpers.durable.cluster import RunHandle
        if run is None and not turn.recovered:
            context = AgentContext.get(child["context_id"])
            if context is not None:
                return owner.submit_owned(context, UserMessage(child["message"], attachments=child["attachments"],
                                                               id=child["input_id"]), child["origin"])
        if run is None:
            # Genesis already committed with the parent manifest is authority.
            # Do not construct an executable shadow context on a joining host.
            parent = owner.sync("get_run", child["origin"]["parent_run_id"])
            if parent["status"] not in ("running", "blocked") or parent["context_id"] != child["origin"]["parent_context_id"]:
                _held("parent_stopped_or_held")
            run = owner.sync("admit", child["context_id"], child["input_id"],
                             codec.message_payload(UserMessage(child["message"], attachments=child["attachments"],
                                                                id=child["input_id"])), child["genesis"])
        owner.dispatch_for_run(run["run_id"])
        return RunHandle(owner, run["run_id"])
    context = AgentContext.get(child["context_id"])
    if run and run["run_id"] in owner.driving and context is not None and context.task:
        return context.task
    if context is None:
        if run is None and child["genesis"].get("requires_state_adapter"):
            _held("child_genesis_state_adapter_required")
        context = persist_chat._deserialize_context((run or {}).get("checkpoint", child["genesis"])["context"])
        context._durable_restored = run is not None
        if run is None and codec.environment(context.agent0) != child["genesis"]["environment"]:
            _held("child_genesis_configuration_changed")
    restore_context(context, child["origin"])
    if run is None:
        # Saved wrapper genesis is recovery provenance even when the child had
        # not reached its own admission transaction before the interruption.
        context._durable_recovery_admission = bool(turn.recovered)
    return owner.submit_owned(context, UserMessage(child["message"], attachments=child["attachments"],
                                                   id=child["input_id"]), child["origin"])


async def _join(turn, child, task, *, timeout=None):
    owner = turn.owner
    identifier = _key(turn, "join:" + child["job_id"])
    previous = await owner.io("get_call", turn.run_id, identifier)
    attempt = 0
    while previous and previous["status"] == "completed" and previous["result"].get("wait_timed_out"):
        attempt += 1
        identifier = _key(turn, "join:" + child["job_id"] + f":wait:{attempt}")
        previous = await owner.io("get_call", turn.run_id, identifier)
    if previous and previous["status"] == "completed":
        return previous["result"]
    await owner.io("start_call", turn.run_id, identifier, "child_join", {"job_id": child["job_id"]})
    try:
        if timeout is None:
            await owner.await_child(turn, task)
        else:
            await asyncio.wait_for(owner.await_child(turn, task), timeout)
    except asyncio.TimeoutError:
        # The read-only wait completed by timing out. The shielded child keeps
        # its invocation owner; no unknown external outcome is invented here.
        result = {"job_id": child["job_id"], "tool_name": child["origin"]["tool_name"],
                  "state": "running", "context_id": child["context_id"],
                  "duration_seconds": 0, "wait_timed_out": True}
        await owner.io("finish_call", turn.run_id, identifier, result)
        return result
    run = _child_run(owner, child)
    if not run or run["status"] != "completed":
        _held("child_requires_attention")
    history = [call["payload"] for call in await owner.io("calls", run["run_id"])
               if call["kind"] == "parent_history" and call["status"] == "completed"]
    result = {"job_id": child["job_id"], "tool_name": child["origin"]["tool_name"],
              "state": "success", "context_id": child["context_id"],
              "result": run["checkpoint"].get("terminal", ""), "duration_seconds": 0,
              "child_run_id": run["run_id"], "parent_history": history}
    await owner.io("finish_call", turn.run_id, identifier, result)
    return result


def _public(result):
    return {key: value for key, value in result.items() if key not in ("child_run_id", "parent_history")}


async def execute_subordinate(tool, args):
    from helpers.tool import Response
    turn = _turn(tool.agent)
    children = await _manifest(turn, [{"name": "call_subordinate", "args": args, "direct": True}])
    child = children[0]
    result = await _join(turn, child, _submit(turn, child))
    additional = {"context_id": child["context_id"]}
    from extensions.python.hist_add_tool_result import _90_save_tool_call_file
    if len(result["result"]) >= _90_save_tool_call_file.LEN_MIN:
        hint = tool.agent.read_prompt("fw.hint.call_sub.md")
        if hint:
            additional["hint"] = hint
    return Response(message=result["result"], break_loop=False, additional=additional)


def _inventory(turn):
    """Rebuild handles across parent turns; collected handles remain tombstoned."""
    children, collected = {}, set()
    for header in turn.owner.sync("list_run_headers", context_id=turn.agent.context.id):
        if header.get("payloads_pruned"):
            continue
        for call in turn.owner.sync("calls", header["run_id"]):
            if call["status"] != "completed" or call.get("result") is None:
                continue
            if call["kind"] == "workflow":
                for child in call["result"]["children"]:
                    children[child["job_id"]] = child
            elif call["kind"] == "child_collection":
                collected.update(call["result"]["job_ids"])
    return {key: child for key, child in children.items() if key not in collected}


async def execute_parallel(tool, args):
    from helpers import parallel_tools as parallel
    from helpers.tool import Response
    from helpers.tool_policy import ensure_tool_allowed
    turn = _turn(tool.agent)
    action = str(args.get("action") or "").strip().lower()
    timeout = parallel.coerce_timeout(args.get("timeout"))
    requested = parallel.normalize_job_ids(args.get("job_ids"))
    children = []
    raw = parallel.extract_tool_calls(args)
    if raw is not None and action != "cancel":
        calls = parallel.normalize_parallel_tool_calls(raw)
        for call in calls:
            ensure_tool_allowed(turn.agent, call.tool_name)
        children = await _manifest(turn, [{"name": call.tool_name, "args": call.tool_args} for call in calls])
    handles = _inventory(turn)
    ids = list(dict.fromkeys([*requested, *(child["job_id"] for child in children)]))
    if not ids:
        raise ValueError("Provide tool_calls or job_ids.")
    if any(job_id not in handles for job_id in ids):
        raise ValueError("Unknown or already collected parallel job id.")
    selected = [handles[job_id] for job_id in ids]
    if action == "cancel":
        results = []
        for child in selected:
            run = _child_run(turn.owner, child)
            if run:
                from helpers.durable.runtime import control
                control(child["context_id"], "cancel")
                from agent import AgentContext
                context = AgentContext.get(child["context_id"])
                if context and context.task:
                    context.task.kill()
            results.append({"job_id": child["job_id"], "tool_name": child["origin"]["tool_name"],
                            "state": "cancelled", "context_id": child["context_id"], "duration_seconds": 0})
        tool._durable_collection = results
        return Response(parallel.format_parallel_results(results), break_loop=False)
    tasks = [_submit(turn, child) for child in selected]
    wait = parallel.coerce_bool(args.get("wait"), action not in {"start", "background", "collect"})
    if action in {"await", "wait"}:
        wait = True
    if not wait and children and not requested:
        # A background start yields durable handles even if a very fast child
        # finishes before this wrapper returns. Only an explicit collect joins it.
        jobs = [{"job_id": child["job_id"], "tool_name": child["origin"]["tool_name"],
                 "state": "running", "context_id": child["context_id"], "duration_seconds": 0}
                for child in selected]
        return Response(json.dumps({"status": "started", "jobs": jobs,
                        "instruction": "Use the parallel tool with job_ids to await or cancel these background jobs."},
                        ensure_ascii=False, separators=(",", ":")), break_loop=False)
    deadline = time.monotonic() + timeout
    results = []
    for child, task in zip(selected, tasks):
        run = _child_run(turn.owner, child)
        if wait or (run and run["status"] == "completed"):
            remaining = deadline - time.monotonic()
            if remaining > 0:
                result = await _join(turn, child, task, timeout=remaining)
                results.append(result)
                continue
        results.append({"job_id": child["job_id"], "tool_name": child["origin"]["tool_name"],
                        "state": "running", "context_id": child["context_id"], "duration_seconds": 0,
                        **({"wait_timed_out": True} if wait else {})})
    tool._durable_collection = [result for result in results if result["state"] == "success"]
    return Response(parallel.format_parallel_results([_public(result) for result in results]), break_loop=False)


async def collect(tool):
    """History then collection watermark share the parent's atomic checkpoint."""
    turn = _turn(tool.agent)
    results = getattr(tool, "_durable_collection", [])
    if not results:
        return
    identifier = _key(turn, "collection")
    previous = await turn.owner.io("get_call", turn.run_id, identifier)
    if previous and previous["status"] == "completed":
        return
    ids = [result["job_id"] for result in results]
    await turn.owner.io("start_call", turn.run_id, identifier, "child_collection", {"job_ids": ids})
    for result in results:
        for message in result.get("parent_history", []):
            tool.agent.hist_add_message(False, content=message["content"], tokens=message["tokens"])
    with turn.owner.lock:
        projection = codec.checkpoint(tool.agent, result=turn.result)
        await turn.owner.io("finish_call", turn.run_id, identifier, {"job_ids": ids},
                            checkpoint=projection, phase="tools")


async def extras(agent):
    from helpers.durable.runtime import current
    turn = current(agent)
    if not turn:
        return ""
    lines = []
    for child in _inventory(turn).values():
        if child["origin"].get("mode") == "subordinate" and child["origin"].get("slot") == "default":
            continue
        run = _child_run(turn.owner, child)
        state = run["status"] if run else "pending"
        lines.append(f"- {child['job_id']}: {child['origin']['tool_name']} [{state}]")
    return "parallel jobs:\n" + "\n".join(lines) if lines else ""


def supports(tool):
    """Only these exact bundled wrappers have a child-manifest adapter."""
    from tools.call_subordinate import Delegation
    from tools.parallel import ParallelTool
    return type(tool) in (Delegation, ParallelTool)


def protected_run_ids(owner):
    """Retain live handles and their collection tombstones as one dependency graph.

    A collection in a newer turn must survive whenever an older source manifest
    remains, otherwise its collected handles could become visible again.
    Fully consumed terminal components may be compacted in chronological order.
    """
    protected, manifests, collected, joined, by_input, parents = set(), {}, {}, {}, {}, {}
    for header in owner.sync("list_run_headers"):
        if header.get("payloads_pruned"):
            continue
        run = owner.sync("get_run", header["run_id"])
        by_input[(header["context_id"], header["input_id"])] = header["run_id"]
        origin = (run.get("checkpoint") or {}).get("origin") or {}
        if origin.get("kind") == "child":
            parents[header["run_id"]] = origin["parent_run_id"]
        if header["status"] in ("running", "blocked", "attention"):
            protected.add(header["run_id"])
            if origin.get("kind") == "child":
                protected.add(origin["parent_run_id"])
        for call in owner.sync("calls", header["run_id"]):
            if call["status"] != "completed" or call.get("result") is None:
                continue
            if call["kind"] == "workflow":
                direct = all(spec.get("direct") for spec in call["payload"]["specifications"])
                manifests.setdefault(header["run_id"], []).extend(
                    (child, direct) for child in call["result"]["children"])
            elif call["kind"] == "child_collection":
                for job_id in call["result"]["job_ids"]:
                    collected.setdefault(job_id, set()).add(header["run_id"])
            elif call["kind"] == "child_join" and call["result"].get("state") == "success":
                joined.setdefault(call["result"]["job_id"], set()).add(header["run_id"])
    for parent_id, children in manifests.items():
        if any(child["job_id"] not in (joined if direct else collected) for child, direct in children):
            protected.add(parent_id)
    changed = True
    while changed:
        previous = set(protected)
        protected.update(parents[run_id] for run_id in previous if run_id in parents)
        for parent_id, children in manifests.items():
            if parent_id not in protected:
                continue
            for child, direct in children:
                child_id = by_input.get((child["context_id"], child["input_id"]))
                if child_id:
                    protected.add(child_id)
                protected.update((joined if direct else collected).get(child["job_id"], ()))
        changed = previous != protected
    return protected
