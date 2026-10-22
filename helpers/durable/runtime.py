"""Opt-in single-process recovery coordinator and phase-aware chat runner."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import functools
import hashlib
import threading
import uuid
from pathlib import Path

from helpers.durable import codec
from helpers.durable.store import LocalStore, DurableStoreError, StaleRunError

_service = None
_service_lock = threading.RLock()
ACTIVE = ("running", "blocked", "attention")
UNSUPPORTED_TOOLS = {"parallel_tool_calls", "scheduler", "a2a_chat"}


class RecoveryHeld(BaseException):
    """Bypass repair/retry extensions: uncertainty cannot become another effect."""


def service():
    return _service


def current(agent):
    turn = getattr(getattr(agent, "context", None), "_durable_turn", None)
    return turn if turn and turn.agent is agent else None


def initialize():
    """One startup owner. A failed store never silently enables legacy execution."""
    global _service
    from helpers import files, settings
    with _service_lock:
        if _service is not None:
            return _service
        backend = settings.get_settings().get("durability_backend", "off")
        root = Path(files.get_abs_path("usr/durability"))
        if backend == "off" and not (root / "state.sqlite3").exists():
            return None
        values = settings.get_settings()
        _service = RecoveryService(root, enabled=backend != "off",
                                   retain_terminal=values.get("durability_retention_runs", 100),
                                   max_age_days=values.get("durability_retention_days", 30))
        if backend not in ("off", "local"):
            _service.failed = True
        return _service


class RecoveryService:
    def __init__(self, root, *, enabled=True, retain_terminal=100, max_age_days=30):
        self.enabled = enabled
        self.retain_terminal, self.max_age_days = retain_terminal, max_age_days
        self.lock = threading.RLock()
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="DurableStore")
        self.store = None
        self.failed = False
        self.driving = set()
        self.waiting = set()
        self.executing = set()
        self.recovery_queue = []
        self.recovery_scanned = False
        try:
            self.store = self.worker.submit(LocalStore, root).result()
        except Exception:
            self.failed = True

    def sync(self, method, *args, **kwargs):
        if self.failed or self.store is None:
            raise DurableStoreError("Local recovery storage unavailable; execution is held")
        return self.worker.submit(functools.partial(getattr(self.store, method), *args, **kwargs)).result()

    async def io(self, method, *args, **kwargs):
        if self.failed or self.store is None:
            raise RecoveryHeld("storage_unavailable")
        try:
            return await asyncio.wrap_future(self.worker.submit(
                functools.partial(getattr(self.store, method), *args, **kwargs)))
        except StaleRunError:
            raise RecoveryHeld("stopped_or_reset")
        except Exception:
            raise RecoveryHeld("storage_failure")

    def close(self):
        if self.store:
            self.worker.submit(self.store.close).result()
        self.worker.shutdown(wait=True)

    def communicate(self, context, message, broadcast_level=1):
        with self.lock:
            headers = self.sync("list_run_headers", context_id=context.id)
            if not self.enabled and not any(run["status"] in ACTIVE for run in headers):
                return None
            if context.type.value != "user" or context.get_agent() is not context.agent0:
                raise RuntimeError("Local recovery does not yet support this workflow")
            message.id = message.id or uuid.uuid4().hex
            payload = codec.masked(context.agent0, codec.message_payload(message))
            duplicate = next((run for run in headers if run["input_id"] == message.id), None)
            if duplicate:
                duplicate = self.sync("get_run", duplicate["run_id"])
                if not self.sync("matches_input", duplicate["run_id"], payload):
                    raise ValueError("Message ID already admitted with different content")
                if duplicate["run_id"] in self.driving:
                    return context.task
                from helpers.defer import DeferredTask
                return DeferredTask("DurableResult").start_task(self._reported_result, duplicate)
            input_key = "input:" + hashlib.sha256(message.id.encode()).hexdigest()
            for header in headers:
                previous = self.sync("get_call", header["run_id"], input_key)
                if previous:
                    if not self.sync("matches_call", header["run_id"], input_key, payload):
                        raise ValueError("Message ID already admitted with different content")
                    if header["run_id"] in self.driving:
                        return context.task
                    from helpers.defer import DeferredTask
                    return DeferredTask("DurableResult").start_task(
                        self._reported_result, self.sync("get_run", header["run_id"]))
            active = next((run for run in headers if run["status"] in ACTIVE), None)
            if active:
                active = self.sync("get_run", active["run_id"])
                turn = current(context.agent0)
                if not turn or active["run_id"] not in self.driving:
                    raise RuntimeError("Stop the held durable run before starting a new attempt")
                if broadcast_level != 1:
                    raise RuntimeError("Durable intervention broadcast requires a child-workflow adapter")
                input_key = "input:" + hashlib.sha256(message.id.encode()).hexdigest()
                previous = self.sync("get_call", active["run_id"], input_key)
                if previous and previous["status"] == "completed":
                    if previous["payload"] != payload:
                        raise ValueError("Message ID already admitted with different content")
                    return context.task
                if active["checkpoint"].get("intervention") or context.agent0.intervention:
                    raise RuntimeError("An intervention is already pending; wait for it or stop the run")
                self.sync("start_call", active["run_id"], input_key, "intervention", payload)
                data = active["checkpoint"]
                data["intervention"] = payload
                data["paused"] = False
                self.sync("finish_call", active["run_id"], input_key, {"accepted": True},
                          checkpoint=data, phase=active["phase"])
                context.agent0.intervention = message
                context.paused = False
                return context.task
            if not self.enabled:
                return None
            if any(row["run_id"] in self.driving for row in headers):
                raise RuntimeError("The previous run is still stopping; wait before starting a new attempt")
            context.agent0.intervention = None
            context._durable_restored = False
            context._durable_origin = None
            if context.paused:
                context.paused = False
            run = self.sync("admit", context.id, message.id, payload, codec.checkpoint(context.agent0))
            return self.dispatch(context, run)

    async def _reported_result(self, run):
        if run.get("payloads_pruned"):
            return "Local recovery: this message is already recorded; its retained payload has expired. Use a new message ID for new work."
        if run["status"] == "completed":
            return run["checkpoint"].get("terminal", "")
        return "Local recovery: this message is already recorded. Stop the held run before starting a new attempt."

    def submit_owned(self, context, message, origin):
        """Scheduler/child admission shares the direct-chat ownership gate."""
        with self.lock:
            if not self.enabled:
                raise RuntimeError("Local recovery is disabled; owned work is held")
            if self.failed:
                raise RuntimeError("Local recovery storage unavailable; execution is held")
            message.id = message.id or uuid.uuid4().hex
            payload = codec.masked(context.agent0, codec.message_payload(message))
            origin = codec.masked(context.agent0, origin)
            if origin.get("kind") not in ("scheduler", "child"):
                raise ValueError("Unknown durable workflow origin")
            headers = self.sync("list_run_headers", context_id=context.id)
            duplicate = next((row for row in headers if row["input_id"] == message.id), None)
            if duplicate:
                if not self.sync("matches_input", duplicate["run_id"], payload):
                    raise ValueError("Message ID already admitted with different content")
                run = self.sync("get_run", duplicate["run_id"])
                if run.get("checkpoint") and run["checkpoint"].get("origin") != origin:
                    raise ValueError("Workflow identity already admitted with different ownership")
                if run["run_id"] in self.driving:
                    return context.task
                if run["status"] == "running" and not run["checkpoint"].get("paused"):
                    if not self.sync("can_resume", run["run_id"]):
                        raise RecoveryHeld("restored_backup_requires_review")
                    context._durable_restored = True
                    context._durable_origin = origin
                    return self.dispatch(context, run)
                from helpers.defer import DeferredTask
                return DeferredTask("DurableResult").start_task(self._reported_result, run)
            if origin["kind"] == "child":
                parent = self.sync("get_run", origin["parent_run_id"])
                if parent["status"] not in ("running", "blocked") or parent["context_id"] != origin["parent_context_id"]:
                    raise RecoveryHeld("parent_stopped_or_held")
            if any(row["status"] in ACTIVE or row["run_id"] in self.driving for row in headers):
                raise RuntimeError("Context already owns durable work; stop or join it first")
            context._durable_origin = origin
            # A constructor/genesis restored from a committed parent manifest
            # has not certified a new target merely because admission is new.
            context._durable_restored = bool(getattr(context, "_durable_recovery_admission", False))
            context._durable_recovery_admission = False
            context.agent0.intervention = None
            context.paused = False
            run = self.sync("admit", context.id, message.id, payload, codec.checkpoint(context.agent0))
            return self.dispatch(context, run)

    async def wait_for_ancestors(self, run_id, origin):
        """A paused ancestor blocks new effects without becoming a failed child."""
        while True:
            link, seen, paused = origin or {}, {run_id}, False
            while link.get("kind") == "child":
                parent_id = link["parent_run_id"]
                if parent_id in seen:
                    raise RecoveryHeld("workflow_ownership_cycle")
                seen.add(parent_id)
                parent = await self.io("get_run", parent_id)
                if parent["context_id"] != link["parent_context_id"] or parent["status"] not in ("running", "blocked", "completed"):
                    raise RecoveryHeld("parent_stopped_or_held")
                paused |= parent["status"] == "blocked"
                link = (parent.get("checkpoint") or {}).get("origin") or {}
            if not paused:
                with self.lock:
                    self.waiting.discard(run_id)
                await self.acquire_slot(run_id)
                return
            with self.lock:
                self.executing.discard(run_id)
                self.waiting.add(run_id)
            self.drain_recovery()
            await asyncio.sleep(0.05)

    async def acquire_slot(self, run_id):
        # All context runners share the framework event loop. Keep ownership
        # reservations separate from execution capacity so waiting parents cannot
        # starve their children, including nested batches restored after a crash.
        while True:
            with self.lock:
                if run_id in self.executing:
                    return
                if len(self.executing) < 2:
                    self.executing.add(run_id)
                    return
            await asyncio.sleep(0.01)

    async def await_child(self, turn, task):
        """Waiting parents retain ownership while yielding bounded recovery capacity."""
        with self.lock:
            self.waiting.add(turn.run_id)
            self.executing.discard(turn.run_id)
        self.drain_recovery()
        try:
            from helpers.defer import DeferredTask
            if isinstance(task, DeferredTask):
                return await task.result_async()
            return await task.result()
        finally:
            with self.lock:
                self.waiting.discard(turn.run_id)

    def dispatch(self, context, run):
        with self.lock:
            if run["run_id"] in self.driving:
                return context.task
            self.driving.add(run["run_id"])
            context.set_output_data("durability", {"status": "resuming", "run_id": run["run_id"]})
            try:
                started = threading.Event()
                task = context.run_task(self.run, context, run, started)
                def release_unstarted(_future):
                    if not started.is_set():
                        with self.lock:
                            self.driving.discard(run["run_id"])
                        self.drain_recovery()
                task.add_done_callback(release_unstarted)
                return task
            except BaseException:
                self.driving.discard(run["run_id"])
                raise

    async def run(self, context, run, started=None):
        if started is not None:
            started.set()
        turn = None
        origin = None
        try:
            await self.acquire_slot(run["run_id"])
            fresh = await self.io("get_run", run["run_id"])
            if fresh["status"] not in ACTIVE:
                return "Stopped"
            if not self.enabled or not await self.io("can_resume", run["run_id"]):
                raise RecoveryHeld("restored_backup_requires_review_or_backend_disabled")
            run = fresh
            turn = Turn(self, context.agent0, run)
            context._durable_turn = turn
            context._durable_origin = origin = run["checkpoint"].get("origin")
            if origin and origin.get("kind") == "child":
                await self.wait_for_ancestors(run["run_id"], origin)
            if run["phase"] != "admitted":
                codec.restore(context, run["checkpoint"])
            elif codec.environment(context.agent0) != run["checkpoint"]["environment"]:
                raise RecoveryHeld("admission_configuration_changed")
            elif getattr(context, "_durable_restored", False) and run["checkpoint"].get("requires_state_adapter"):
                raise RecoveryHeld("plugin_state_adapter_required")
            if origin and origin.get("kind") == "scheduler":
                from helpers.durable import scheduler
                if run["phase"] != "scheduler_finalizing":
                    await scheduler.prepare(self, context, run)
            if origin and origin.get("kind") == "child":
                from helpers.durable import workflows
                workflows.restore_context(context, origin)
            tool_child = bool(origin and origin.get("kind") == "child" and origin.get("mode") == "tool")
            if turn.recovered and not codec.function_resume_supported(run["checkpoint"], run["phase"]):
                raise RecoveryHeld("function_hook_adapter_required")
            if run["phase"] == "admitted":
                from agent import UserMessage, LoopData
                await turn.save("initializing")
                if not tool_child:
                    context.agent0.hist_add_user_message(UserMessage(**run["input_payload"]))
                context.agent0.loop_data = LoopData(user_message=context.agent0.last_user_message)
                if not tool_child:
                    from helpers import extension
                    await extension.call_extensions_async("monologue_start", context.agent0,
                                                          loop_data=context.agent0.loop_data)
                await turn.save("tools" if tool_child else "iteration_ready")
            elif run["phase"] not in ("iteration_ready", "model_ready", "model_result", "tools", "scheduler_finalizing", "model_retry"):
                # A provider result remains available even when lifecycle finalization
                # needs an adapter. Never issue a replacement provider request here.
                raise RecoveryHeld("interrupted_" + run["phase"])
            if run["phase"] == "scheduler_finalizing":
                result = run["checkpoint"]["terminal"]
            elif tool_child:
                turn.tool_index = 0
                result = await workflows.dispatch_tool(context, origin)
            else:
                result = await context.agent0.monologue()
                if origin and origin.get("kind") == "child" and origin.get("mode") == "subordinate":
                    context.agent0.history.new_topic()
            if origin and origin.get("kind") == "scheduler":
                await turn.save("scheduler_finalizing", terminal=result)
                await scheduler.complete(self, context, run, result)
            await turn.save("completed", status="completed", terminal=result)
            context.set_output_data("durability", {"status": "complete", "run_id": run["run_id"]})
            return result
        except asyncio.CancelledError:
            try:
                await self.io("transition", run["run_id"], "cancelled", status="cancelled")
            except RecoveryHeld:
                pass
            await self._scheduler_halted(context, run, "cancelled")
            raise
        except RecoveryHeld as reason:
            if turn is not None:
                turn.holding = True
            headers = self.sync("list_run_headers", context_id=context.id)
            if any(item["run_id"] == run["run_id"] and item["status"] == "cancelled" for item in headers):
                return "Stopped"
            text = "Local recovery needs attention. The interrupted action was not retried. Stop this run before starting a new attempt."
            try:
                await self.io("transition", run["run_id"], "needs_attention", status="attention",
                              payload={"reason": str(reason), "resume_phase": turn.phase if turn else run["phase"]})
            except RecoveryHeld:
                pass
            await self._scheduler_halted(context, run, "attention")
            context.set_output_data("durability", {"status": "needs_attention", "run_id": run["run_id"]})
            context.log.log(type="warning", content=text)
            return text
        except Exception:
            if turn is not None:
                turn.holding = True
            await self.io("transition", run["run_id"], "needs_attention", status="attention",
                          payload={"reason": "execution_or_checkpoint_failed"})
            await self._scheduler_halted(context, run, "attention")
            context.set_output_data("durability", {"status": "needs_attention", "run_id": run["run_id"]})
            raise
        finally:
            if turn is not None and getattr(context, "_durable_turn", None) is turn:
                context.streaming_agent = None
                context._durable_turn = None
            with self.lock:
                self.driving.discard(run["run_id"])
                self.waiting.discard(run["run_id"])
                self.executing.discard(run["run_id"])
            if origin and origin.get("kind") == "child" and origin.get("mode") == "tool":
                from agent import AgentContext
                try:
                    header = next((item for item in self.sync("list_run_headers", context_id=context.id)
                                   if item["run_id"] == run["run_id"]), None)
                    if header and header["status"] in ("completed", "cancelled"):
                        with AgentContext._contexts_lock:
                            if AgentContext._contexts.get(context.id) is context:
                                AgentContext._contexts.pop(context.id)
                except Exception:
                    pass
            self.drain_recovery()
            self.maintain()

    def maintain(self):
        """Reclaim terminal private payloads without retiring ownership evidence."""
        if self.failed:
            return
        try:
            from helpers.durable.workflows import protected_run_ids
            with self.lock:
                protected = protected_run_ids(self) | self.driving
                self.sync("compact", retain_terminal=self.retain_terminal, max_age_days=self.max_age_days,
                          protected_run_ids=protected)
        except Exception:
            from helpers.print_style import PrintStyle
            PrintStyle.warning("Local recovery retention needs attention; recorded work was preserved")

    async def _scheduler_halted(self, context, run, status):
        origin = (run.get("checkpoint") or {}).get("origin")
        if origin and origin.get("kind") == "scheduler":
            from helpers.durable.scheduler import halted
            try:
                await halted(self, context, run, status)
            except (Exception, RecoveryHeld):
                # Never obscure cancellation/uncertainty with a secondary projection failure.
                context.log.log(type="warning", content="Scheduler state projection needs reconciliation.")

    def recover(self):
        """Called after chat restoration; unsupported phases stay visible and inert."""
        from agent import AgentContext
        from helpers import persist_chat
        with self.lock:
            if self.recovery_scanned:
                return
            self.recovery_scanned = True
        if self.failed:
            from helpers.print_style import PrintStyle
            PrintStyle.warning("Local recovery storage unavailable; durable execution is held")
            return
        try:
            candidates = self.sync("list_run_headers", ACTIVE)
        except Exception:
            self.failed = True
            return
        for header in candidates:
            run = header
            try:
                run = self.sync("get_run", header["run_id"])
                data = run["checkpoint"]
                if data["context"]["id"] != run["context_id"]:
                    raise ValueError("Checkpoint context identity mismatch")
                # Rebuild after legacy load, never promote chat.json to authority.
                context = persist_chat._deserialize_context(data["context"])
                context._durable_restored = True
                context._durable_origin = data.get("origin")
                context._durable_workflow_state = data.get("workflow_state", {})
                if context._durable_origin and context._durable_origin.get("kind") == "child":
                    from helpers.durable.workflows import restore_context
                    restore_context(context, context._durable_origin)
                context.paused = bool(data.get("paused"))
                persist_chat.mark_chat_saved(context)
                context.log.guid = uuid.uuid4().hex
                for item in context.log.logs:
                    item.guid = context.log.guid
                if self.enabled and self.sync("can_resume", run["run_id"]) and run["status"] == "running" and not context.paused:
                    self.recovery_queue.append((context, run))
                    context.set_output_data("durability", {"status": "waiting_for_recovery", "run_id": run["run_id"]})
                else:
                    context.set_output_data("durability", {"status": "needs_attention", "run_id": run["run_id"]})
                    context.log.log(type="warning", content="A durable run is held. Stop it before starting a new attempt.")
            except Exception:
                context = AgentContext.get(run["context_id"])
                if context:
                    context.set_output_data("durability", {"status": "needs_attention", "run_id": run["run_id"]})
                # A corrupt payload cannot safely be rewritten; isolate it and
                # retain its active header so new admission cannot bypass it.
                continue
        self.maintain()
        self.drain_recovery()

    def drain_recovery(self):
        with self.lock:
            if self.failed:
                return
            while self.recovery_queue and len(self.driving - self.waiting) < 2:
                context, run = self.recovery_queue.pop(0)
                header = next((item for item in self.sync("list_run_headers", context_id=context.id)
                               if item["run_id"] == run["run_id"]), None)
                if header and header["status"] == "running":
                    self.dispatch(context, run)


class Turn:
    def __init__(self, owner, agent, run):
        self.owner, self.agent, self.run_id = owner, agent, run["run_id"]
        self.phase = run["phase"]
        self.result = None
        if run["checkpoint"].get("result"):
            from helpers.llm_result import LLMResult
            self.result = LLMResult.from_dict(run["checkpoint"]["result"])
        self.holding = False
        self.recovered = run["phase"] != "admitted" or bool(getattr(agent.context, "_durable_restored", False))
        self.tool_index = 0
        self.active_call_id = None
        self.resuming_args = {}
        self.document_sessions = {}
        self.resuming_bodies = {}

    def document_session(self, call_id):
        from helpers.durable.documents import DocumentSession
        if call_id not in self.document_sessions:
            self.document_sessions[call_id] = DocumentSession(self, call_id)
        return self.document_sessions[call_id]

    async def save(self, phase, *, status="running", terminal=None):
        # Serialize snapshot+enqueue with synchronous input/control admission.
        # Otherwise an older snapshot could overwrite an acknowledged intervention.
        with self.owner.lock:
            try:
                data = codec.checkpoint(self.agent, result=self.result, terminal=terminal)
            except Exception:
                raise RecoveryHeld("unsupported_checkpoint_state")
            await self.owner.io("transition", self.run_id, phase, checkpoint=data, status=status)
            self.phase = phase

    async def monologue(self):
        from helpers import extension
        agent = self.agent
        while True:
            agent.context.streaming_agent = agent
            if self.phase == "model_retry":
                await self.model_retry()
            if self.phase == "model_result":
                # Arbitrary model completion hooks can make external calls. Without
                # an adapter we retain the provider result and hold finalization.
                if (extension._get_extension_classes("chat_model_call_after", agent=agent)
                        or extension._get_extension_classes("_functions/agent/Agent/call_chat_model_turn/end", agent=agent)):
                    raise RecoveryHeld("model_completion_hook_adapter_required")
                for point in ("reasoning_stream_end", "response_stream_end"):
                    if not _audited_hooks(agent, point):
                        raise RecoveryHeld("stream_completion_hook_adapter_required")
                await self.save("finishing_model")
                await extension.call_extensions_async("reasoning_stream_end", agent, loop_data=agent.loop_data)
                await extension.call_extensions_async("response_stream_end", agent, loop_data=agent.loop_data)
                await self.save("model_ready")
            if self.phase == "iteration_ready":
                agent.loop_data.iteration += 1
                agent.loop_data.params_temporary = {}
                self.result = None
                await self.save("preparing")
                self.result = await agent._call_model_with_stream()
                await self.save("model_ready")
            if self.phase == "model_ready":
                await self.save("processing_model")
                data = {"llm_result": self.result}
                await extension.call_extensions_async("message_loop_result", agent,
                                                      loop_data=agent.loop_data, result_data=data)
                if data.get("skip_default_processing"):
                    await self.end_iteration()
                    continue
                item = agent.loop_data.params_temporary.get("log_item_generating")
                agent.hist_add_ai_response(self.result.response, llm_result=self.result,
                                           id=item.id if item else f"{self.run_id}:{agent.loop_data.iteration}:assistant")
                self.project_response()
                await self.save("tools")
            if self.phase != "tools":
                raise RecoveryHeld("unsupported_continuation_phase")
            if self.result.builtin_items:
                raise RecoveryHeld("provider_builtin_adapter_required")
            self.tool_index = 0
            result = await agent.process_llm_result_tools(self.result)
            await self.end_iteration(terminal=result)
            if result:
                await self.save("finalizing", terminal=result)
                await extension.call_extensions_async("monologue_end", agent, loop_data=agent.loop_data)
                return result

    async def end_iteration(self, terminal=None):
        from helpers import extension
        await self.save("iteration_finalizing", terminal=terminal)
        await extension.call_extensions_async("message_loop_end", self.agent, loop_data=self.agent.loop_data)
        await self.save("terminal_ready" if terminal else "iteration_ready", terminal=terminal)

    def project_response(self):
        """Commit the final response projection even if preview chunks were lost."""
        from helpers import extract_tools
        result = self.result
        text = None
        for call in result.function_calls:
            if call.name == "response":
                text = call.arguments.get("text") or call.arguments.get("message")
        if not result.function_calls:
            request = extract_tools.extract_tool_request(result.response)
            if request:
                name, arguments = extract_tools.normalize_tool_request(request)
                if name == "response":
                    text = arguments.get("text") or arguments.get("message")
            elif result.mode == "responses":
                text = result.response
        if not isinstance(text, str) or not text.strip():
            return
        params = self.agent.loop_data.params_temporary
        item = params.get("log_item_response")
        if item is None:
            generating = params.get("log_item_generating")
            item = self.agent.context.log.log(
                type="response", heading=f"icon://chat {self.agent.agent_name}: Responding",
                id=generating.id if generating else f"{self.run_id}:{self.agent.loop_data.iteration}:assistant")
            params["log_item_response"] = item
        item.update(content=text)

    async def model_intent(self, model, messages, kwargs, *, explicit_caching=True,
                           background=False, stream_response=False, stream_reasoning=False):
        await self.owner.wait_for_ancestors(self.run_id, getattr(self.agent.context, "_durable_origin", None))
        from helpers.durable.retry import describe_model
        payload = describe_model(self.agent, model, messages, kwargs,
                                 explicit_caching=explicit_caching, background=background,
                                 stream_response=stream_response, stream_reasoning=stream_reasoning)
        call_id = f"model:{self.agent.loop_data.iteration}"
        await self.owner.io("start_call", self.run_id, call_id, "model", payload)
        await self.save("model_inflight")
        return call_id

    async def model_retry(self):
        """Consume one operator grant and invoke the retained inference request."""
        from helpers.durable.retry import retry_eligibility, restore_messages
        logical_id = f"model:{self.agent.loop_data.iteration}"
        original = await self.owner.io("get_call", self.run_id, logical_id)
        eligible, _reason = retry_eligibility(self.agent, original)
        if not eligible:
            raise RecoveryHeld("model_retry_descriptor_ineligible")
        grant = await self.owner.io("get_retry", self.run_id, logical_id)
        if not grant or grant["state"] != "pending" or not grant["epoch_valid"]:
            raise RecoveryHeld("model_retry_requires_fresh_operator_grant")
        await self.owner.wait_for_ancestors(self.run_id, getattr(self.agent.context, "_durable_origin", None))
        await self.agent.handle_intervention()
        attempt = await self.owner.io("begin_retry", self.run_id, logical_id)
        payload = original["payload"]
        # After this checkpoint a lost outcome is uncertain again. A consumed
        # grant is never permission to send the same alias after restart.
        await self.save("model_inflight")
        async def discard_stream(*_args):
            return None
        result = await self.agent.get_chat_model().unified_turn(
            messages=restore_messages(payload),
            response_callback=discard_stream if payload["stream_response"] else None,
            reasoning_callback=discard_stream if payload["stream_reasoning"] else None,
            rate_limiter_callback=None if payload["background"] else self.agent.rate_limiter_callback,
            explicit_caching=payload["explicit_caching"],
            **{**payload["options"], **payload["transport"], "a0_retry_attempts": 0},
        )
        await self.model_result(attempt["call_id"], result)

    async def model_result(self, call_id, result):
        with self.owner.lock:
            self.result = result
            payload = codec.result_payload(self.agent, result)
            try:
                projection = codec.checkpoint(self.agent, result=result)
            except Exception:
                await self.owner.io("finish_call", self.run_id, call_id, payload)
                raise RecoveryHeld("unsupported_checkpoint_state")
            try:
                await self.owner.io("finish_call", self.run_id, call_id, payload,
                                    checkpoint=projection, phase="model_result")
            except RecoveryHeld:
                # Cancel fences continuation but permits a known late outcome.
                # Reset/delete still reject this plain write by generation.
                await self.owner.io("finish_call", self.run_id, call_id, payload)
                raise
            self.phase = "model_result"

    async def tool_begin(self, tool, args):
        await self.owner.wait_for_ancestors(self.run_id, getattr(self.agent.context, "_durable_origin", None))
        if tool.name in UNSUPPORTED_TOOLS:
            raise RecoveryHeld("workflow_adapter_required")
        call_id = f"tool:{self.agent.loop_data.iteration}:{self.tool_index}"
        self.tool_index += 1
        payload = {"tool": codec.identity(tool), "name": tool.name, "method": tool.method,
                   "args": codec.masked(self.agent, args)}
        existing = await self.owner.io("get_call", self.run_id, call_id)
        workflow = _audited_workflow(tool)
        if self.recovered and existing is None:
            from helpers.durable.replay import AUDITED_TOOLS
            if not workflow and (type(tool).__name__, codec.identity(tool)["source"]) not in AUDITED_TOOLS:
                raise RecoveryHeld("recovered_target_adapter_required")
        if existing:
            if existing["payload"] != payload:
                raise RecoveryHeld("tool_identity_or_arguments_changed")
            logical_id = call_id
            grant = await self.owner.io("get_retry", self.run_id, logical_id)
            if grant:
                from helpers.durable.retry import retry_eligibility
                prepared = await self.owner.io("get_call", self.run_id, logical_id + ":args")
                eligible, _reason = retry_eligibility(self.agent, existing, prepared=prepared, tool=tool)
                if not eligible or not grant["epoch_valid"]:
                    raise RecoveryHeld("tool_retry_requires_current_audit")
                if grant["state"] == "pending":
                    from helpers.tool_policy import ensure_tool_allowed
                    try:
                        ensure_tool_allowed(self.agent, tool.name)
                    except Exception:
                        raise RecoveryHeld("tool_retry_access_denied")
                    existing = await self.owner.io("begin_retry", self.run_id, logical_id)
                    call_id = existing["call_id"]
                    await self.owner.io("start_call", self.run_id, call_id + ":args", "arguments", prepared["payload"])
                    await self.owner.io("finish_call", self.run_id, call_id + ":args", prepared["result"])
                    self.resuming_args[call_id] = prepared
                    return call_id, None
                existing = await self.owner.io("get_call", self.run_id, grant["call_id"])
                if existing is None or existing["status"] != "completed":
                    raise RecoveryHeld("explicit_tool_attempt_outcome_unknown")
                call_id = existing["call_id"]
            finalized = await self.owner.io("get_call", self.run_id, call_id + ":final")
            if finalized and finalized["status"] == "completed":
                result = finalized["result"]
                if result.get("finalized"):
                    from helpers.tool import Response
                    return call_id, Response(**result["response"])
            if existing["status"] == "completed":
                conflicts = existing.get("document_conflicts") or []
                if conflicts and all(item.get("status") == "resolved" for item in conflicts) and finalized is None:
                    from helpers.tool_policy import ensure_tool_allowed
                    try:
                        ensure_tool_allowed(self.agent, tool.name)
                    except Exception:
                        raise RecoveryHeld("tool_access_changed")
                    prepared = await self.owner.io("get_call", self.run_id, call_id + ":args")
                    if prepared and prepared["status"] == "completed":
                        from helpers.tool import Response
                        self.resuming_args[call_id] = prepared
                        self.resuming_bodies[call_id] = Response(**existing["result"]["response"])
                        return call_id, None
                raise RecoveryHeld("tool_finalization_interrupted")
            if workflow:
                prepared = await self.owner.io("get_call", self.run_id, call_id + ":args")
                if not prepared or prepared["status"] != "completed" or not _audited_hooks(self.agent, "tool_execute_before"):
                    raise RecoveryHeld("workflow_preparation_interrupted")
                self.resuming_args[call_id] = prepared
                return call_id, None
            if existing["replay"] != "safe" or tool.replay != "safe":
                raise RecoveryHeld("tool_outcome_unknown")
            # Safe body alone does not certify before/after hooks. The first local
            # tier audits only the pure response tool without extra tool hooks.
            from helpers.durable.replay import AUDITED_TOOLS
            if (type(tool).__name__, codec.identity(tool)["source"]) not in AUDITED_TOOLS or not all(_audited_hooks(self.agent, point)
                                                   for point in ("tool_execute_before", "tool_execute_after")):
                raise RecoveryHeld("tool_lifecycle_adapter_required")
        await self.owner.io("start_call", self.run_id, call_id, "tool", payload, replay=tool.replay)
        await self.save("tools")
        return call_id, None

    async def effective_tool_args(self, call_id, args):
        identifier = call_id + ":args"
        data = codec.masked(self.agent, args)
        await self.owner.io("start_call", self.run_id, identifier, "arguments", data)
        tool = self.agent.loop_data.current_tool
        log = getattr(tool, "log", None)
        with self.owner.lock:
            projection = codec.checkpoint(self.agent, result=self.result)
            await self.owner.io("finish_call", self.run_id, identifier,
                                {"prepared": True, "log_id": getattr(log, "id", None),
                                 "log_type": getattr(log, "type", None)},
                                checkpoint=projection, phase="tools")

    async def tool_body(self, call_id, response):
        # Immutable body outcome. Finalization lives in a separate event/call.
        data = codec.masked(self.agent, {"message": response.message, "break_loop": response.break_loop,
                                         "additional": response.additional})
        outcome = {"response": data, "finalized": False}
        session = self.document_sessions.get(call_id)
        edits = session.edits() if session else []
        try:
            recorded = await self.owner.io("finish_call", self.run_id, call_id, outcome, document_edits=edits)
        except RecoveryHeld:
            if not edits:
                raise
            await self.owner.io("finish_call", self.run_id, call_id, outcome)
            raise
        if recorded.get("document_conflicts"):
            raise RecoveryHeld("document_conflict")

    async def finalization_intent(self, call_id):
        # Separate known body completion from potentially effectful post hooks.
        await self.owner.io("start_call", self.run_id, call_id + ":final", "finalization", {"body": call_id})

    async def tool_finalized(self, call_id, response):
        data = codec.masked(self.agent, {"message": response.message, "break_loop": response.break_loop,
                                         "additional": response.additional})
        # Distinct immutable finalization record avoids overwriting body evidence.
        final_id = call_id + ":final"
        await self.owner.io("start_call", self.run_id, final_id, "finalization", {"body": call_id})
        with self.owner.lock:
            projection = codec.checkpoint(self.agent, result=self.result)
            await self.owner.io("finish_call", self.run_id, final_id, {"response": data, "finalized": True},
                                checkpoint=projection, phase="tools")
            self.phase = "tools"


def _audited_workflow(tool):
    from helpers.durable.workflows import supports
    from helpers.durable.replay import AUDITED_WORKFLOWS
    return supports(tool) and (type(tool).__name__, codec.identity(tool)["source"]) in AUDITED_WORKFLOWS


def _audited_hooks(agent, point):
    from helpers import extension
    from helpers.durable.replay import AUDITED_HOOKS
    return all((cls.__name__, codec.identity(cls)["source"]) in AUDITED_HOOKS
               for cls in extension._get_extension_classes(point, agent=agent))


def control(context_id, action):
    owner = service()
    if owner is not None:
        from agent import AgentContext
        from helpers.durable.workflows import descendant_context_ids
        with owner.lock:
            descendants = set()
            for header in owner.sync("list_run_headers", context_id=context_id):
                descendants.update(descendant_context_ids(owner, header["run_id"]))
            descendants.discard(context_id)
            owner.sync("control_many", [context_id, *sorted(descendants)], action)
            for child_id in descendants:
                child = AgentContext.get(child_id)
                if child and child.task:
                    child.task.kill()
        return sorted(descendants)
    return []


def pause_context(context, paused):
    owner = service()
    if owner:
        with owner.lock:
            run = next(iter(owner.sync("list_run_headers", ACTIVE, context_id=context.id)), None)
            if run:
                if run["status"] == "attention":
                    raise RuntimeError("Review the held run in Recovery & documents before changing pause state")
                if not paused and (not owner.enabled or not owner.sync("can_resume", run["run_id"])):
                    raise RuntimeError("Local recovery is held; unpause is unavailable for a disabled backend or restored pilot backup")
                run = owner.sync("get_run", run["run_id"])
                data = run["checkpoint"]
                data["paused"] = bool(paused)
                updated = owner.sync("transition", run["run_id"], run["phase"], checkpoint=data,
                                     status="blocked" if paused else "running")
                context.paused = bool(paused)
                if not paused and run["run_id"] not in owner.driving:
                    owner.dispatch(context, updated)
                return
    context.paused = bool(paused)


def guard_context(context):
    """Prevent legacy admission from bypassing held durable work after rollback."""
    owner = service()
    if owner is None:
        return None
    if owner.failed:
        raise RuntimeError("Local recovery storage unavailable; execution is held")
    return owner
