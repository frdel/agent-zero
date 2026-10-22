"""Versioned operator decisions and bounded, masked recovery projections."""
from __future__ import annotations

import hashlib

from helpers.durable import codec
from helpers.durable.store import ConflictError, StaleRunError

ACTIVE = ("running", "blocked", "attention")
SAFE_PHASES = {"admitted", "iteration_ready", "model_result", "model_ready", "tools", "scheduler_finalizing"}
PUBLIC_REASONS = {
    "tool_outcome_unknown": "The interrupted tool has no committed result. Verify its external outcome.",
    "model_retry_requires_fresh_operator_grant": "The previous model attempt needs another explicit review.",
    "document_conflict": "A concurrent document edit needs reconciliation. The tool result was preserved.",
    "tool_finalization_interrupted": "The body result is known; interrupted postprocessing needs an adapter.",
    "restored_backup_requires_review": "Select this restored run before reviewing continuation.",
    "storage_failure": "Recovery storage needs attention.",
    "storage_unavailable": "Recovery storage is unavailable.",
}


class ReviewError(ValueError):
    def __init__(self, message, *, required_ids=()):
        super().__init__(message)
        self.required_ids = sorted(required_ids)


def context_for(context_id):
    from agent import AgentContext
    context = AgentContext.get(context_id)
    if context is None:
        raise ReviewError("This chat is unavailable. Restore its compatible context before continuing.")
    return context


def scoped_header(owner, context_id, run_id):
    # Check the payload-free identity before decoding private checkpoint data.
    header = next((row for row in owner.sync("list_run_headers", context_id=context_id)
                   if row["run_id"] == run_id), None)
    if header is None:
        raise KeyError("Unknown run in this chat")
    return header


def scoped_run(owner, context_id, run_id):
    scoped_header(owner, context_id, run_id)
    return owner.sync("get_run", run_id)


def checkpoint_phase(owner, run):
    """Only the exact committed watermark identifies the saved continuation."""
    event = next((row for row in owner.sync("read_events", run["run_id"], max(0, run["checkpoint_seq"] - 1))
                  if row["seq"] == run["checkpoint_seq"]), None)
    if not event or not event.get("payload"):
        return None
    if event["kind"] in ("admitted", "input_admitted"):
        return "admitted"
    if event["kind"] in ("transition", "call_result", "operator_resolution", "retry_granted"):
        return event["payload"].get("phase")
    return None


def compatible(context, run):
    data = run.get("checkpoint")
    return bool(data and not run.get("payloads_pruned") and data.get("version") == codec.VERSION
                and not data.get("requires_state_adapter")
                and data.get("context", {}).get("id") == context.id
                and codec.environment(context.agent0) == data.get("environment"))


def resume_phase(owner, context, run):
    from helpers.durable.runtime import _audited_hooks
    from helpers.durable.replay import AUDITED_TOOLS, AUDITED_WORKFLOWS
    if not owner.enabled or owner.failed or run["status"] not in ACTIVE or run["run_id"] in owner.driving:
        return None
    if not owner.sync("can_resume", run["run_id"]) or not compatible(context, run):
        return None
    if any(item["status"] != "resolved" for item in owner.sync("list_document_conflicts", run["run_id"])):
        return None
    phase = checkpoint_phase(owner, run)
    if phase not in SAFE_PHASES:
        return None
    if not codec.function_resume_supported(run["checkpoint"], phase):
        return None
    calls = owner.sync("calls", run["run_id"])
    by_id = {item["call_id"]: item for item in calls}
    for call in calls:
        if call["kind"] not in ("model", "tool") or call.get("logical_call_id"):
            continue
        retry = owner.sync("get_retry", run["run_id"], call["call_id"])
        current = by_id.get(retry["call_id"], call) if retry and retry["epoch_valid"] else call
        if retry and retry["epoch_valid"] and current["status"] == "intent":
            return None  # A new attempt needs its own grant/consumption path.
        if current["kind"] == "model":
            if current["status"] != "completed":
                return None
            continue
        final = by_id.get(current["call_id"] + ":final")
        if final and final["status"] == "completed":
            continue
        if final:  # Postprocessing may already have had effects.
            return None
        try:
            from helpers.tool_policy import ensure_tool_allowed
            ensure_tool_allowed(context.agent0, (call.get("payload") or {})["name"])
        except Exception:
            return None
        conflicts = current.get("document_conflicts") or []
        if current["status"] == "completed":
            if conflicts and all(item["status"] == "resolved" for item in conflicts) and by_id.get(call["call_id"] + ":args", {}).get("status") == "completed":
                continue
            return None
        payload = call.get("payload") or {}
        implementation = payload.get("tool") or {}
        pin = (implementation.get("class", "").rsplit(".", 1)[-1], implementation.get("source"))
        if pin in AUDITED_WORKFLOWS and by_id.get(call["call_id"] + ":args", {}).get("status") == "completed" and _audited_hooks(context.agent0, "tool_execute_before"):
            continue
        if call["replay"] == "safe" and pin in AUDITED_TOOLS and all(_audited_hooks(context.agent0, point) for point in ("tool_execute_before", "tool_execute_after")):
            continue
        return None
    return phase


def retry_eligibility(owner, context, run, call):
    if not owner.enabled or owner.failed or run["status"] not in ACTIVE or run["run_id"] in owner.driving:
        return False, "Wait for this run to stop executing before reviewing another attempt."
    if not owner.sync("can_resume", run["run_id"]):
        return False, "Select this restored run first."
    if not compatible(context, run):
        return False, "The saved configuration or implementation is incompatible."
    if not codec.function_resume_supported(run["checkpoint"], "model_result" if call["kind"] == "model" else "tools"):
        return False, "An interrupted function hook requires a recovery adapter."
    if call["status"] != "intent" or call.get("logical_call_id"):
        return False, "A known result is never retried."
    if owner.sync("list_document_conflicts", run["run_id"]):
        return False, "Reconcile the document separately; its tool body must not repeat."
    attempts = [item for item in owner.sync("calls", run["run_id"]) if item.get("logical_call_id") == call["call_id"]]
    if len(attempts) >= 2 or any(item["status"] == "completed" for item in attempts):
        return False, "The attempt budget is exhausted or an outcome is already known."
    grant = owner.sync("get_retry", run["run_id"], call["call_id"])
    if grant and grant["epoch_valid"] and grant["state"] == "pending":
        return False, "An authorized attempt is already pending."
    from helpers.durable.retry import retry_eligibility as eligible
    prepared = owner.sync("get_call", run["run_id"], call["call_id"] + ":args") if call["kind"] == "tool" else None
    return eligible(context.agent0, call, prepared=prepared)


def status(owner, context_id=None, offset=0):
    if type(offset) is not int or offset < 0:
        raise ReviewError("Run inventory offset must be a nonnegative integer")
    if owner is None:
        return {"available": False, "enabled": False, "restore": {"required": False, "epoch": None}, "runs": [], "documents": [], "next_offset": None, "total": 0}
    if owner.failed:
        return {"available": False, "enabled": owner.enabled, "restore": {"required": False, "epoch": None}, "runs": [], "documents": [], "next_offset": None, "total": 0}
    with owner.lock:
        rows = owner.sync("list_run_headers", context_id=context_id)
        rows.sort(key=lambda row: (row["status"] not in ACTIVE, -row["created_at"], row["run_id"]))
        result = []
        for header in rows[offset:offset + 50]:
            review = owner.sync("get_review", header["run_id"])
            from agent import AgentContext
            context = AgentContext.get(header["context_id"])
            item = {key: review[key] for key in ("run_id", "context_id", "status", "phase", "version", "restore_selected")}
            item.update(name=str(context.name if context and context.name else header["context_id"])[:160],
                        can_resume=False, calls=[], document_conflicts=[], reason="Recorded work requires review.",
                        actions={"resume": False, "stop": header["status"] in ACTIVE,
                                 "confirm_completed": header["status"] in ACTIVE, "confirm_not_completed": header["status"] in ACTIVE,
                                 "new_attempt": False})
            try:
                run = owner.sync("get_run", header["run_id"])
                events = owner.sync("read_events", run["run_id"], max(0, run["checkpoint_seq"] - 1))
                detail = next((event["payload"].get("detail") for event in reversed(events)
                               if event["kind"] == "transition" and event.get("payload") and event["payload"].get("detail")), {})
                # Reasons are internal identifiers only, never arbitrary exception/provider text.
                reason = detail.get("reason", "") if isinstance(detail, dict) else ""
                item["reason"] = PUBLIC_REASONS.get(reason, item["reason"])
                item["can_resume"] = bool(context and resume_phase(owner, context, run))
                item["actions"]["resume"] = item["can_resume"]
                visible_calls = [call for call in owner.sync("calls", run["run_id"])
                                 if call["kind"] in ("model", "tool") and not call.get("logical_call_id")]
                item["call_count"] = len(visible_calls)
                for call in visible_calls[-20:]:
                    may_retry, why = retry_eligibility(owner, context, run, call) if context else (False, "Chat context unavailable.")
                    payload = call.get("payload") or {}
                    grant = owner.sync("get_retry", run["run_id"], call["call_id"])
                    latest = (owner.sync("get_call", run["run_id"], grant["call_id"]) or call) if grant and grant["epoch_valid"] else call
                    item["calls"].append({"call_id": call["call_id"], "kind": call["kind"],
                                          "name": str(payload.get("name", "Model inference"))[:100],
                                          "status": latest["status"], "has_result": latest["status"] == "completed",
                                          "attempt": latest.get("attempt", 1),
                                          "may_retry": may_retry, "retry_reason": why})
                    item["actions"]["new_attempt"] |= may_retry
                pending = [conflict for conflict in owner.sync("list_document_conflicts", run["run_id"])
                           if conflict["status"] == "pending"]
                item["conflict_count"] = len(pending)
                # Two bounded proposals per row keep this endpoint bounded even
                # for large histories. Resolving these exposes the next pair.
                for conflict in pending[:2]:
                    stored = owner.sync("read_document", run["context_id"], conflict["kind"])
                    item["document_conflicts"].append({"id": conflict["conflict_id"], "kind": conflict["kind"],
                        "status": conflict["status"], "expected_revision": conflict["expected_revision"],
                        "current_revision": stored["revision"] if stored else 0,
                        "proposed_value": codec.masked(context.agent0, conflict["proposed"]) if context else None})
            except BaseException as exc:
                # RecoveryHeld derives from BaseException; do not swallow shutdowns.
                from helpers.durable.runtime import RecoveryHeld
                if not isinstance(exc, (Exception, RecoveryHeld)):
                    raise
                item["reason"] = "Saved recovery data or its implementation needs attention."
                item["can_resume"] = False
                item["actions"]["resume"] = False
                item["actions"]["new_attempt"] = False
                for call in item["calls"]:
                    call["may_retry"] = False
            result.append(codec.masked(context.agent0, item) if context else item)
        return {"available": True, "enabled": owner.enabled, "restore": owner.sync("get_restore_state"),
                "runs": result, "documents": [], "total": len(rows),
                "next_offset": offset + 50 if offset + 50 < len(rows) else None}


def _dirty(context_ids):
    from helpers.state_monitor_integration import mark_dirty_for_context
    for context_id in context_ids:
        mark_dirty_for_context(context_id, reason="durability_review")


def _dispatch(owner, context, run_id):
    context._durable_restored = True
    return owner.dispatch(context, owner.sync("get_run", run_id))


def resolve(owner, context_id, run_id, version, decision, note, request_id, call_id=None):
    from agent import AgentContext
    from helpers.durable.workflows import descendant_context_ids
    if not isinstance(note, str) or len(note.encode()) > 4096:
        raise ReviewError("Evidence must contain at most 4096 bytes")
    with owner.lock:
        # Stopping must remain possible even if a private checkpoint is corrupt.
        # Only continuation/retry needs to deserialize that checkpoint.
        run = scoped_header(owner, context_id, run_id)
        if decision in ("resume", "new_attempt"):
            run = owner.sync("get_run", run_id)
        context = AgentContext.get(context_id)
        note = codec.masked(context.agent0, note) if context else ""
        prior = owner.sync("get_review_request", run_id, request_id)
        if prior:
            args = prior["request"]
            same_note = (prior["note"] == note if prior["note"] is not None else
                         prior["note_digest"] == hashlib.sha256(note.encode()).hexdigest())
            if prior["decision"] != decision or args.get("expected_version") != version or not same_note or prior["call_id"] != call_id:
                raise ConflictError("Review request already has different content")
            if not prior["epoch_valid"]:
                raise ConflictError("This decision belongs to another restore epoch")
            # Dispatch is deliberately outside the SQL transaction. Repair its
            # lost acknowledgement only while the committed decision is still
            # runnable; a consumed attempt or changed phase never gets replayed.
            if decision in ("resume", "new_attempt") and context and run["status"] == "running" and run_id not in owner.driving:
                if decision == "resume":
                    if resume_phase(owner, context, run):
                        _dispatch(owner, context, run_id)
                else:
                    grant = owner.sync("get_retry", run_id, call_id)
                    if (owner.enabled and owner.sync("can_resume", run_id) and compatible(context, run)
                            and grant and grant["state"] == "pending" and grant["epoch_valid"]):
                        _dispatch(owner, context, run_id)
            return prior["result"]
        if run["status"] not in ACTIVE:
            raise StaleRunError("This run is already stopped or complete")
        if owner.sync("get_review", run_id)["version"] != version:
            raise ConflictError("Recovery review is stale")
        if decision not in ("resume", "stop", "confirmed_completed", "confirmed_not_completed", "new_attempt"):
            raise ReviewError("Unknown recovery decision")
        if not isinstance(note, str) or len(note.encode()) > 4096:
            raise ReviewError("Evidence must contain at most 4096 bytes")
        if decision in ("confirmed_completed", "confirmed_not_completed") and not note.strip():
            raise ReviewError("Record the evidence used to verify this outcome")
        if decision in ("resume", "new_attempt"):
            context = context_for(context_id)
            if decision == "new_attempt":
                call = owner.sync("get_call", run_id, call_id)
                allowed, reason = retry_eligibility(owner, context, run, call) if call else (False, "Unknown call")
                if not allowed:
                    raise ReviewError(reason)
                result = owner.sync("prepare_retry", run_id, call_id, version, request_id,
                                    "model_retry" if call["kind"] == "model" else "tools", eligible=True,
                                    note=note)
            else:
                phase = resume_phase(owner, context, run)
                if not phase:
                    raise ReviewError("This continuation requires reconciliation or a compatible adapter")
                result = owner.sync("record_resolution", run_id, version, decision, note, request_id, call_id, phase=phase)
            _dispatch(owner, context, run_id)
        else:
            descendants = set()
            # Background jobs can belong to an earlier parent turn. Match the
            # context-wide Stop closure and preserve latest child ownership.
            for header in owner.sync("list_run_headers", context_id=context_id):
                descendants.update(descendant_context_ids(owner, header["run_id"]))
            descendants.discard(context_id)
            context = AgentContext.get(context_id)
            masked_note = codec.masked(context.agent0, note) if context else "Operator evidence recorded; context unavailable for text masking."
            result = owner.sync("record_resolution", run_id, version, decision, masked_note, request_id,
                                call_id, context_ids=sorted(descendants))
            for identity in (context_id, *descendants):
                related = AgentContext.get(identity)
                if related and related.task:
                    related.task.kill()
        _dirty((context_id,))
        return result


def restore_select(owner, run_ids, versions, epoch, request_id):
    """Selection is explicit; connected active dependencies require review too."""
    if type(run_ids) is not list or not run_ids or len(run_ids) > 1000 or type(versions) is not dict:
        raise ReviewError("Select between 1 and 1000 restored runs")
    with owner.lock:
        selected = set(run_ids)
        if len(selected) != len(run_ids) or set(versions) != selected:
            raise ReviewError("Each selected run requires its exact review version")
        prior = owner.sync("get_review_request", run_ids[0], request_id)
        if not prior:
            active = {row["run_id"]: row for row in owner.sync("list_run_headers", ACTIVE)}
            if not selected <= active.keys():
                raise ReviewError("Only active restored runs can be selected")
            graph = {identity: set() for identity in active}
            by_input = {(header["context_id"], header["input_id"]): identity for identity, header in active.items()}
            for identity, header in active.items():
                try:
                    run = owner.sync("get_run", identity)
                except Exception:
                    if identity in selected:
                        raise ReviewError("A selected run has unreadable recovery data; reconcile its storage first.")
                    continue  # An unrelated corrupt row cannot block healthy selection.
                origin = (run.get("checkpoint") or {}).get("origin") or {}
                parent = origin.get("parent_run_id") if origin.get("kind") == "child" else None
                if parent in graph:
                    graph[identity].add(parent)
                    graph[parent].add(identity)
                # Independently verified manifests preserve links even when a
                # child's checkpoint cannot be decoded.
                try:
                    calls = owner.sync("calls", identity)
                except Exception:
                    calls = []
                for call in calls:
                    if call["kind"] != "workflow" or call["status"] != "completed" or not call.get("result"):
                        continue
                    for child in call["result"].get("children", []):
                        child_id = by_input.get((child["context_id"], child["input_id"]))
                        if child_id:
                            graph[identity].add(child_id)
                            graph[child_id].add(identity)
            required, frontier = set(selected), set(selected)
            while frontier:
                following = set().union(*(graph[identity] for identity in frontier)) - required
                required.update(following)
                frontier = following
            missing = {identity for identity in required - selected if not owner.sync("can_resume", identity)}
            if missing:
                raise ReviewError("Review the related parent and child runs before selecting this workflow.", required_ids=missing)
        result = owner.sync("select_restore", run_ids, epoch, versions, request_id)
        # A selection never changes an uncertain run to runnable. Known-safe
        # running checkpoints can continue; attention rows need their own decision.
        for identity in run_ids:
            run = owner.sync("get_run", identity)
            from agent import AgentContext
            context = AgentContext.get(run["context_id"])
            if context and run["status"] == "running" and not run["checkpoint"].get("paused") and resume_phase(owner, context, run):
                _dispatch(owner, context, identity)
        _dirty(owner.sync("get_run", identity)["context_id"] for identity in run_ids)
        return result
