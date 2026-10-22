"""PostgreSQL workers: claimed runners, durable commands and remote run handles.

A database session loss never authorizes replacement effects. The journal phase
and unresolved call intent still decide whether a successor can continue.
Execution capacity is bounded per worker, not globally across deployments.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import threading
import time
import uuid
from contextlib import nullcontext
from types import SimpleNamespace

from helpers.durable import codec
from helpers.durable.runtime import ACTIVE, RecoveryHeld, RecoveryService
from helpers.durable.store import DurableStoreError, IntegrityError, OwnershipError, StaleRunError


def portable(data, payload=None):
    """Host-local resources require an explicit portability adapter."""
    if not data or data.get("requires_state_adapter"):
        return False
    context = data.get("context") or {}
    if context.get("data", {}).get("project") and not data.get("resources", {}).get("workspace"):
        return False
    values = [payload or {}, data.get("intervention") or {}]
    values += [data.get("origin") or {}]
    def local_attachment(value):
        if isinstance(value, dict):
            if value.get("attachments"):
                from helpers.durable.resources import portable_attachments
                if not portable_attachments(value["attachments"]):
                    return True
            return any(local_attachment(item) for item in value.values())
        if isinstance(value, list):
            return any(local_attachment(item) for item in value)
        return False
    return not any(local_attachment(value) for value in values)


def latest_header(owner, headers):
    """Order chat ownership by admission sequence, never a worker wall clock."""
    def key(header):
        sequence = header.get("admission_seq")
        if sequence is None:
            sequence = next((event["seq"] for event in owner.sync("read_events", header["run_id"])
                             if event["kind"] in ("admitted", "input_admitted")), 0)
        return sequence, header["run_id"]
    return max(headers, key=key)


def seed_context(owner, source, context_id):
    """Seed a new admission from current shared history and its reset fence."""
    if source.get("payloads_pruned") or not source.get("checkpoint"):
        head = owner.sync("get_context_head", context_id)
        if not head or head["run_id"] != source["run_id"]:
            raise RuntimeError("Shared chat checkpoint is unavailable")
        source = {**source, "checkpoint": head["checkpoint"]}
    generation = owner.sync("document_generation", context_id)
    data = copy.deepcopy(source["checkpoint"])
    if source["generation"] < generation:
        # Reset fences history as well as execution. Preserve configuration
        # and chat identity, never carry the old agent/session into a new
        # generation merely because its audit checkpoint is still retained.
        profile = (data["context"].get("agents") or [{}])[0].get("agent_profile", "")
        data["context"]["agents"] = [{"number": 0, "agent_profile": profile, "history": "", "data": {}}]
        data["context"]["log"] = {"guid": uuid.uuid4().hex, "logs": []}
        data["context"]["streaming_agent"] = 0
        data.update(agent_state={}, loop={}, temporary_log_ids={}, last_user_message_id=None, workflow_state={})
    return data, generation


class RunHandle:
    """A run identity can be awaited on any host without owning its coroutine."""
    def __init__(self, owner, run_id):
        self.owner, self.run_id = owner, run_id
        self._watchers = []

    async def result(self, timeout=None):
        async def wait():
            while True:
                run = await self.owner.io("get_run", self.run_id)
                if run["status"] not in ("running", "blocked"):
                    return await self.owner._reported_result(run)
                await asyncio.sleep(self.owner.scan_interval)
        return await wait() if timeout is None else await asyncio.wait_for(wait(), timeout)

    result_async = result

    def result_sync(self, timeout=None):
        return asyncio.run(self.result(timeout))

    def is_alive(self):
        return self.owner.sync("get_run", self.run_id)["status"] in ("running", "blocked")

    def add_done_callback(self, callback):
        from helpers.defer import DeferredTask
        watcher = DeferredTask("DurableRunResult").start_task(self.result)
        self._watchers.append(watcher)
        watcher.add_done_callback(callback)

    def kill(self, **kwargs):
        # Callers fence the exact run/context before cancelling local handles.
        # A remote future has no process or event loop to terminate.
        return None


class InputHandle(RunHandle):
    """An input's acknowledgment is distinct from the run it was queued behind."""
    def __init__(self, owner, run_id, request_id):
        super().__init__(owner, run_id)
        self.request_id = request_id

    async def result(self, timeout=None):
        async def wait():
            while True:
                receipt = await self.owner.io("get_command", self.run_id, self.request_id)
                if not receipt or not receipt["epoch_valid"] or receipt["status"] == "invalidated":
                    return "This queued input was stopped or invalidated. Review the chat before sending it again."
                if receipt["status"] == "applied":
                    if not (receipt.get("result") or {}).get("accepted"):
                        return "The queued input was not applied. Send it again after the current response finishes."
                    return await super(InputHandle, self).result()
                await asyncio.sleep(self.owner.scan_interval)
        return await wait() if timeout is None else await asyncio.wait_for(wait(), timeout)

    result_async = result


class ClusterRecoveryService(RecoveryService):
    distributed = True

    def __init__(self, root_or_dsn=None, *, dsn=None, namespace="agent_zero", scan_interval=0.25, enabled=True,
                 retain_terminal=100, max_age_days=30, **kwargs):
        dsn = dsn or root_or_dsn
        super().__init__(None, enabled=enabled, retain_terminal=retain_terminal,
                         max_age_days=max_age_days, backend="postgres", dsn=dsn, namespace=namespace)
        self.scan_interval = max(0.01, float(scan_interval))
        self.contexts = {}
        self._poller = None
        self._closing = False
        self._scan_lock = threading.RLock()
        self._view_revision = None
        self._maintenance_tasks = {}
        self._maintenance_failures = {}

    def close(self):
        self._closing = True
        if self._poller:
            self._poller.kill()
        for task in self._maintenance_tasks.values():
            task.kill()
        for context in list(self.contexts.values()):
            if context.task and context.task.is_alive():
                context.task.kill()
        super().close()

    def recover(self):
        if self.failed:
            return
        self.recovery_scanned = True
        self.scan()
        self._ensure_poller()

    def _ensure_poller(self):
        with self.lock:
            if self._poller is None and not self._closing:
                from helpers.defer import DeferredTask
                self._poller = DeferredTask("DurableClusterScan").start_task(self._poll)

    def wake_maintenance(self, run_id=None):
        self._ensure_poller()

    async def _maintain_context(self, run_id):
        from helpers.durable import maintenance
        from helpers.durable.resources import ResourceHeld
        from helpers.durable.workspaces import WorkspaceHeld
        def restore(run):
            self.sync("assert_owner", run["run_id"])
            return self.contexts.get(run["run_id"]) or self._restore_claimed(run)
        try:
            result = await maintenance.process(self, run_id, restore)
            if result.get("deleted"):
                from agent import AgentContext
                from helpers import task_scheduler
                scheduler = task_scheduler.TaskScheduler.get()
                for context_id in result["context_ids"]:
                    scheduler.cancel_tasks_by_context(context_id, terminate_thread=False)
                    for header in self.sync("list_run_headers", context_id=context_id):
                        context = self.contexts.pop(header["run_id"], None)
                        if context is not None and AgentContext.get(context_id) is context:
                            AgentContext.remove(context_id)
                    for task in scheduler.get_tasks_by_context_id(context_id):
                        await scheduler.remove_task_by_uuid(task.uuid)
                from helpers.durable.review import _dirty
                _dirty(result["context_ids"])
        except (ValueError, RecoveryHeld, maintenance.MaintenanceHeld, ResourceHeld, WorkspaceHeld, IntegrityError):
            self.sync("get_restore_state")  # A lost database session is worker-wide.
            if self.sync("owns", run_id) or self.sync("claim_maintenance", run_id):
                for command in self.sync("pending_commands", run_id):
                    if command["kind"] in maintenance.KINDS:
                        self.sync("ack_command", run_id, command["request_id"],
                                  result={"accepted": False, "error": "maintenance_requires_reconciliation"})
        except (OwnershipError, StaleRunError):
            # A cancelled execution may release its context while cleanup is
            # awaiting a target. The retained request moves to the next owner.
            return
        finally:
            if run_id not in self.driving:
                # process() releases newly acquired idle claims. Never remove
                # a concurrently admitted replacement context from its registry.
                self.contexts.pop(run_id, None)
                self.sync("release", run_id)

    def _drain_maintenance(self):
        from helpers.durable import maintenance
        from helpers.defer import DeferredTask
        for run_id, task in list(self._maintenance_tasks.items()):
            if task.is_ready():
                try:
                    task.result_sync(timeout=0)
                except (Exception, RecoveryHeld):
                    self.sync("get_restore_state")
                    self._maintenance_failures[run_id] = time.monotonic()
                    from helpers.print_style import PrintStyle
                    PrintStyle.warning("A shared chat maintenance request needs reconciliation; other chats remain available.")
                finally:
                    self._maintenance_tasks.pop(run_id, None)
        for header in self.sync("list_command_runs", maintenance.KINDS):
            run_id = header["run_id"]
            if run_id in self._maintenance_tasks:
                continue
            if time.monotonic() - self._maintenance_failures.get(run_id, float("-inf")) < 30:
                continue
            if len(self._maintenance_tasks) >= 2:
                break
            self._maintenance_tasks[run_id] = DeferredTask("DurableMaintenance").start_task(self._maintain_context, run_id)

    async def _poll(self):
        while not self._closing and not self.failed:
            try:
                self.scan()
                revision = self.sync("snapshot_revision")
                if revision != self._view_revision:
                    self._view_revision = revision
                    from helpers.state_monitor_integration import mark_dirty_all
                    mark_dirty_all(reason="durable.shared_revision")
            except (Exception, RecoveryHeld):
                # Lost sessions are never reconnected under an old claim.
                for context in list(self.contexts.values()):
                    if context.task and context.task.is_alive():
                        context.task.kill()
                self.failed = True
                return
            await asyncio.sleep(self.scan_interval)

    def scan(self):
        with self._scan_lock:
            if self.failed or self._closing:
                return
            self._drain_maintenance()
            if time.monotonic() - getattr(self, "_background_scan_at", float("-inf")) >= 1:
                from helpers.durable.background import recover_pending
                recover_pending(self)
                self._background_scan_at = time.monotonic()
            # Refresh controls even when this node has no available worker slot.
            for run_id, context in list(self.contexts.items()):
                if run_id in self._maintenance_tasks and run_id not in self.driving:
                    continue  # Idle cleanup owns this claim until its target settles.
                if not self.sync("owns", run_id):
                    if context.task and context.task.is_alive():
                        context.task.kill()
                    self.contexts.pop(run_id, None)
                    continue
                run = self.sync("get_run", run_id)
                if run["status"] not in ACTIVE:
                    if run["status"] == "cancelled" and context.task and context.task.is_alive():
                        from helpers.defer import DeferredTask
                        from helpers.durable.execution import cancel_sessions
                        if not getattr(context, "_durable_cancel_requested", False):
                            context._durable_cancel_requested = True
                            DeferredTask("DurableCommandCancel").start_task(cancel_sessions, context, run_id)
                        context.task.kill()
                    if run_id not in self.driving:
                        self.sync("release", run_id)
                        self.contexts.pop(run_id, None)
                    continue
                self.refresh_commands(context, run_id)
            for header in self.sync("list_run_headers", ACTIVE):
                run_id = header["run_id"]
                if run_id in self.driving or run_id in self._maintenance_tasks:
                    continue
                commands = self.sync("pending_commands", run_id)
                if header["status"] != "running" and not commands:
                    continue
                if not self.enabled and not commands:
                    continue
                if len(self.driving - self.waiting) >= 2 and not commands:
                    break
                if not self.sync("claim", run_id):
                    continue
                try:
                    run = self.sync("get_run", run_id)
                    if not portable(run.get("checkpoint"), run.get("input_payload")):
                        self.sync("transition", run_id, "needs_attention", status="attention",
                                  payload={"reason": "distributed_resource_adapter_required"})
                        self.sync("release", run_id)
                        continue
                    context = self.contexts.get(run_id) or self._restore_claimed(run)
                    self.refresh_commands(context, run_id)
                    run = self.sync("get_run", run_id)
                    if (self.enabled and run["status"] == "running"
                            and self.sync("can_resume", run_id) and run_id not in self.driving):
                        self.dispatch(context, run)
                    elif run_id not in self.driving:
                        self.sync("release", run_id)
                        self.contexts.pop(run_id, None)
                except (Exception, RecoveryHeld) as error:
                    from helpers.durable.resources import ResourceHeld
                    from helpers.durable.workspaces import WorkspaceHeld
                    reason = str(error) if isinstance(error, (ResourceHeld, WorkspaceHeld)) else "distributed_restore_requires_reconciliation"
                    try:
                        current = self.sync("get_run", run_id)
                        if current["status"] in ("running", "blocked"):
                            self.sync("transition", run_id, "needs_attention", status="attention",
                                      payload={"reason": reason})
                    except Exception:
                        pass
                    self.sync("release", run_id)
                    self.contexts.pop(run_id, None)

    def _construction_supported(self, data):
        from helpers import extension
        from helpers.durable.replay import AUDITED_INIT_HOOKS, AUDITED_INITIAL_HISTORY_HOOKS
        saved = data.get("context") or {}
        if data.get("construction_sources") is not None and data["construction_sources"] != codec.construction_sources():
            return False
        proxy = SimpleNamespace(config=SimpleNamespace(profile=saved.get("agent_profile") or ""),
                                context=SimpleNamespace(get_data=lambda key: saved.get("data", {}).get(key)))
        if any((cls.__name__, codec.identity(cls)["source"]) not in AUDITED_INIT_HOOKS
               for cls in extension._get_extension_classes("agent_init", agent=proxy)):
            return False
        points = [f"_functions/agent/{cls}/__init__/{when}"
                  for cls in ("Agent", "AgentContext") for when in ("start", "end")]
        points += [f"_functions/initialize/initialize_agent/{when}" for when in ("start", "end")]
        if any(extension._get_extension_classes(point, agent=proxy) for point in points):
            return False
        if not saved.get("log", {}).get("logs"):
            history_points = ["hist_add_before"] + [f"_functions/agent/Agent/{method}/{when}"
                              for method in ("hist_add_user_message", "hist_add_ai_response") for when in ("start", "end")]
            return all((cls.__name__, codec.identity(cls)["source"]) in AUDITED_INITIAL_HISTORY_HOOKS
                       for point in history_points for cls in extension._get_extension_classes(point, agent=proxy))
        return True

    def _restore_claimed(self, run):
        from helpers import persist_chat
        self.sync("assert_owner", run["run_id"])
        from helpers.durable import state_adapters
        state_adapters.validate(run["checkpoint"].get("plugin_state", {"version": 1, "entries": []}))
        from helpers.durable import resources, workspaces
        state = run["checkpoint"].get("resources") or {"version": 1}
        workspace = state.get("workspace")
        manager = resources.ResourceManager(self, run["context_id"], run["run_id"])
        scope = workspaces.managed_project(manager, workspace) if workspace else nullcontext(None)
        with scope as path:
            if not self._construction_supported(run["checkpoint"]):
                raise RecoveryHeld("constructor_hook_adapter_required")
            projection = SimpleNamespace(_durable_resources=state, _durable_workspace_path=path,
                                         _durable_workspace_origin=workspace)
            resources.restore_attachment_paths(manager, projection)
            context = persist_chat._deserialize_context(resources.local_value(projection, run["checkpoint"]["context"]))
        resources.restore_state(context, state)
        context._durable_workspace_path = path
        context._durable_workspace_origin = workspace
        context._durable_managed_workspace = bool(workspace)
        context._durable_resource_paths = projection._durable_resource_paths
        context._durable_recovery_owner = self
        context._durable_recovery_run_id = run["run_id"]
        context._durable_provider_descriptor = run["checkpoint"].get("environment", {}).get("provider_cleanup")
        context._durable_provider_cleanup_targets = dict(run["checkpoint"].get("provider_cleanup_targets", {}))
        context._durable_restored = True
        context._durable_origin = run["checkpoint"].get("origin")
        context._durable_workflow_state = run["checkpoint"].get("workflow_state", {})
        context._durable_ui_input_pending = bool(run["checkpoint"].get("ui_input_pending"))
        context.paused = run["status"] == "blocked" or bool(run["checkpoint"].get("paused"))
        context.set_output_data("durability", {"status": run["status"], "run_id": run["run_id"]})
        self.contexts[run["run_id"]] = context
        if run["checkpoint"].get("construction_sources"):
            # Audited local constructors may be repeated until this projection
            # commits. They run only after winning the real context claim.
            data = codec.checkpoint(context.agent0)
            if data.get("requires_state_adapter"):
                raise RecoveryHeld("constructor_state_adapter_required")
            self.sync("transition", run["run_id"], "admitted", checkpoint=data, status=run["status"])
        return context

    def dispatch(self, context, run):
        with self.lock:
            if run["run_id"] in self.driving:
                return context.task
            if not self.sync("claim", run["run_id"]):
                return RunHandle(self, run["run_id"])
            if (run["checkpoint"].get("resources") or {}).get("workspace") and not getattr(context, "_durable_managed_workspace", False):
                recovered = bool(getattr(context, "_durable_restored", False))
                context = self._restore_claimed(run)
                context._durable_restored = recovered
            # A fresh API context is usable only after its committed claim.
            self.contexts[run["run_id"]] = context
            return super().dispatch(context, run)

    def dispatch_for_run(self, run_id):
        # The periodic scanner is the correctness path; callers need no local
        # AgentContext and never steal a run already executing on another host.
        self._ensure_poller()
        return RunHandle(self, run_id)

    def _log_input(self, context, payload):
        if payload and not any(item.type == "user" and item.id == payload.get("id") for item in context.log.logs):
            from helpers.durable.resources import ResourceManager
            manager = ResourceManager(self, context.id)
            names = [manager.reference(uri)["name"] for uri in payload.get("attachments", [])]
            context.log.log(type="user", heading="", content=payload.get("message", ""),
                            kvps={"attachments": names}, id=payload.get("id"))

    async def run(self, context, run, started=None):
        try:
            if not portable(run["checkpoint"], run.get("input_payload")):
                if started is not None:
                    started.set()
                await self.io("transition", run["run_id"], "needs_attention", status="attention",
                              payload={"reason": "distributed_resource_adapter_required"})
                with self.lock:
                    self.driving.discard(run["run_id"])
                return "Distributed recovery requires a portable resource adapter."
            if not run["checkpoint"].get("ui_input_pending") and run["phase"] != "ui_input_ready":
                self._log_input(context, run.get("input_payload") if run["phase"] == "admitted"
                                else run["checkpoint"].get("intervention"))
            from helpers.durable.workspaces import project_override
            workspace = getattr(context, "_durable_workspace_origin", None)
            path = getattr(context, "_durable_workspace_path", None)
            scope = project_override(workspace["project_name"], path, manifest=workspace) if workspace and path else nullcontext()
            with scope:
                return await super().run(context, run, started)
        finally:
            try:
                self.sync("release", run["run_id"])
            except Exception:
                pass
            self.contexts.pop(run["run_id"], None)

    async def prepare_input(self, context, run):
        from helpers.durable.resources import ResourceManager, materialize_attachments
        manager = ResourceManager(self, context.id, run["run_id"])
        if not run["checkpoint"].get("ui_input_pending") and run["phase"] != "ui_input_ready":
            return materialize_attachments(manager, run["input_payload"], context)
        self.sync("assert_owner", run["run_id"])
        from helpers.durable.inputs import prepare
        result = await prepare(self, context, run["run_id"], run["input_payload"], "input_ui", initial=True)
        context._durable_ui_input_pending = False
        turn = getattr(context, "_durable_turn", None)
        if turn:
            turn.phase = "ui_input_ready"
        if result.get("model_not_configured"):
            raise RecoveryHeld("ui_model_not_configured")
        return materialize_attachments(manager, result["message"], context)

    def drain_recovery(self):
        # Polling claims the shared inventory; local queues are never authority.
        return None

    def maintain(self):
        # Only one collector computes a dependency graph and compacts at a time.
        if self.failed or not self.sync("try_role", "retention"):
            return
        try:
            super().maintain()
        finally:
            self.sync("release_role", "retention")

    def _mask_payload(self, context_id, payload):
        from helpers.secrets import get_secrets_manager
        proxy = SimpleNamespace(get_data=lambda key: None, id=context_id)
        manager = get_secrets_manager(proxy)
        def mask(value):
            if isinstance(value, str):
                return manager.mask_values(value)
            if isinstance(value, list):
                return [mask(item) for item in value]
            if isinstance(value, dict):
                return {key: mask(item) for key, item in value.items()}
            return value
        return mask(payload)

    def submit_command(self, run_id, kind, payload, request_id):
        if kind not in ("pause", "intervention", "review"):
            raise ValueError("Unsupported distributed command")
        run = self.sync("get_run", run_id)
        receipt = self.sync("enqueue_command", run_id, kind,
                            self._mask_payload(run["context_id"], payload), request_id)
        self._ensure_poller()
        return receipt

    def pause_remote(self, context_id, paused, request_id):
        run = next(iter(self.sync("list_run_headers", ACTIVE, context_id=context_id)), None)
        if not run:
            raise ValueError("No active durable run")
        return self.submit_command(run["run_id"], "pause", {"paused": bool(paused)}, request_id)

    def communicate_remote(self, context_id, message, broadcast_level=1, *, ui=False):
        message.id = message.id or uuid.uuid4().hex
        if message.attachments:
            from helpers.durable.resources import ResourceManager, capture_attachments
            message.attachments = capture_attachments(ResourceManager(self, context_id), list(message.attachments))
        headers = self.sync("list_run_headers", context_id=context_id)
        if not headers:
            genesis = self.sync("get_projection", "genesis:" + context_id)
            if not genesis:
                raise ValueError("Unknown shared context")
            data = copy.deepcopy(genesis["value"])
            payload = self._mask_payload(context_id, codec.message_payload(message))
            if (data.get("context") or {}).get("id") != context_id or not portable(data, payload):
                raise RuntimeError("Distributed input requires a portable resource adapter")
            if not self.enabled:
                raise RuntimeError("Distributed recovery is disabled")
            generation = self.sync("document_generation", context_id)
            data.update(ui_input_pending=bool(ui), result=None, terminal=None, paused=False, intervention=None, origin=None)
            run = self.sync("admit", context_id, message.id, payload, data, expected_generation=generation)
            return self.dispatch_for_run(run["run_id"])
        payload = self._mask_payload(context_id, codec.message_payload(message))
        request_id = "input:" + hashlib.sha256(message.id.encode()).hexdigest()
        for header in headers:
            prior = self.sync("get_command", header["run_id"], request_id)
            if prior:
                self.submit_command(header["run_id"], "intervention", {"message": payload, "ui": bool(ui)}, request_id)
                return InputHandle(self, header["run_id"], request_id)
        duplicate = next((row for row in headers if row["input_id"] == message.id), None)
        if duplicate:
            if not self.sync("matches_input", duplicate["run_id"], payload):
                raise ValueError("Message ID already admitted with different content")
            return self.dispatch_for_run(duplicate["run_id"])
        active = next((row for row in headers if row["status"] in ACTIVE), None)
        if active:
            if active["status"] == "attention":
                raise RuntimeError("Review the held durable run before sending new work")
            if broadcast_level != 1:
                raise ValueError("Distributed intervention broadcast requires an adapter")
            self.submit_command(active["run_id"], "intervention", {"message": payload, "ui": bool(ui)}, request_id)
            return InputHandle(self, active["run_id"], request_id)
        if not self.enabled:
            raise RuntimeError("Distributed recovery is disabled")
        latest = latest_header(self, headers)
        source = self.sync("get_run", latest["run_id"])
        data, generation = seed_context(self, source, context_id)
        if not portable(data, payload):
            raise RuntimeError("Distributed input requires a portable resource adapter")
        data.update(result=None, terminal=None, paused=False, intervention=None, origin=None, ui_input_pending=bool(ui))
        run = self.sync("admit", context_id, message.id, payload, data, expected_generation=generation)
        return self.dispatch_for_run(run["run_id"])

    def admit_from_context(self, context, message, *, ui=False):
        message.id = message.id or uuid.uuid4().hex
        from helpers.durable.resources import capture_context
        capture_context(self, context, message)
        context._durable_ui_input_pending = bool(ui)
        data = codec.checkpoint(context.agent0)
        payload = codec.masked(context.agent0, codec.message_payload(message))
        if not portable(data, payload):
            raise RuntimeError("Distributed input requires a portable resource adapter")
        run = self.sync("admit", context.id, message.id, payload, data)
        task = self.dispatch(context, run)
        self._ensure_poller()
        return task

    def communicate(self, context, message, broadcast_level=1):
        if self.sync("list_run_headers", context_id=context.id):
            return self.communicate_remote(context.id, message, broadcast_level)
        return self.admit_from_context(context, message)

    def submit_owned(self, context, message, origin):
        with self.lock:
            if not self.enabled or self.failed:
                raise RuntimeError("Distributed recovery is disabled or unavailable")
            from helpers.durable.resources import capture_context
            capture_context(self, context, message)
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
                return self.dispatch_for_run(run["run_id"])
            if origin["kind"] == "child":
                parent = self.sync("get_run", origin["parent_run_id"])
                if parent["status"] not in ("running", "blocked") or parent["context_id"] != origin["parent_context_id"]:
                    raise RecoveryHeld("parent_stopped_or_held")
            context._durable_origin = origin
            context._durable_restored = bool(getattr(context, "_durable_recovery_admission", False))
            context._durable_recovery_admission = False
            data = codec.checkpoint(context.agent0)
            run = self.sync("admit", context.id, message.id, payload, data)
            if not portable(data, payload):
                return self.dispatch_for_run(run["run_id"])
            return self.dispatch(context, run)

    def refresh_commands(self, context, run_id):
        """Apply and acknowledge input/control under the local snapshot lock."""
        from agent import UserMessage
        from helpers.durable import review
        with self.lock:
            self.sync("assert_owner", run_id)
            for command in self.sync("pending_commands", run_id):
                run = self.sync("get_run", run_id)
                kind, payload = command["kind"], command["payload"]
                if kind.startswith("maintenance_"):
                    continue
                request_id = command["request_id"]
                if kind == "review":
                    try:
                        review.resolve(self, payload["context_id"], run_id, payload["version"],
                                       payload["decision"], payload.get("note", ""), payload["request_id"],
                                       payload.get("call_id"))
                        result = {"accepted": True}
                    except (Exception, RecoveryHeld):
                        result = {"accepted": False, "error": "The review changed or requires a compatible worker. Refresh and review again."}
                    self.sync("ack_command", run_id, request_id, result=result)
                    continue
                if run["status"] not in ("running", "blocked"):
                    self.sync("ack_command", run_id, request_id, result={"accepted": False, "error": "This run is held or stopped."})
                    continue
                data = copy.deepcopy(run["checkpoint"])
                if kind == "pause":
                    paused = payload.get("paused")
                    if type(paused) is not bool or (not paused and (not self.enabled or not self.sync("can_resume", run_id))):
                        self.sync("ack_command", run_id, request_id, result={"accepted": False, "error": "Unpause requires enabled and selected recovery."})
                        continue
                    data["paused"] = paused
                    self.sync("apply_command", run_id, request_id, checkpoint=data, phase=run["phase"],
                              status="blocked" if paused else "running", result={"accepted": True})
                    context.paused = paused
                elif kind == "intervention":
                    if run["phase"] in {"terminal_ready", "finalizing", "scheduler_finalizing"}:
                        self.sync("ack_command", run_id, request_id, result={"accepted": False,
                            "error": "The current response is finishing; send new input after it completes."})
                        continue
                    if payload.get("ui") and run["phase"] in ("admitted", "ui_input_ready", "initializing"):
                        continue
                    message = payload.get("message")
                    if not isinstance(message, dict) or data.get("intervention") or context.agent0.intervention:
                        self.sync("ack_command", run_id, request_id, result={"accepted": False, "error": "An intervention is already pending."})
                        continue
                    if payload.get("ui"):
                        from helpers.durable.inputs import intervention
                        prepared = intervention(self, context, run_id, command)
                        if prepared is None:
                            continue
                        if prepared.get("model_not_configured"):
                            self.sync("ack_command", run_id, request_id, result={"accepted": False, "error": "The chat model is not configured."})
                            continue
                        message = prepared["message"]
                    from helpers.durable.resources import ResourceManager, materialize_attachments, checkpoint_state
                    local_message = materialize_attachments(ResourceManager(self, context.id, run_id), message, context)
                    self._log_input(context, message)
                    from helpers.persist_chat import _serialize_log
                    data["context"]["log"] = codec.masked(context.agent0, _serialize_log(context.log))
                    data["intervention"] = message
                    data["resources"] = checkpoint_state(context)
                    # Sending input never silently clears an independently queued pause.
                    self.sync("apply_command", run_id, request_id, checkpoint=data, phase=run["phase"],
                              status=run["status"], result={"accepted": True})
                    context.agent0.intervention = UserMessage(**local_message)

    async def wait_for_ancestors(self, run_id, origin):
        while True:
            self.sync("assert_owner", run_id)
            context = self.contexts[run_id]
            self.refresh_commands(context, run_id)
            fresh = await self.io("get_run", run_id)
            if fresh["status"] not in ("running", "blocked"):
                raise RecoveryHeld("stopped_or_held")
            context.paused = fresh["status"] == "blocked" or bool(fresh["checkpoint"].get("paused"))
            if not context.paused:
                return await super().wait_for_ancestors(run_id, origin)
            with self.lock:
                self.executing.discard(run_id)
                self.waiting.add(run_id)
            await asyncio.sleep(self.scan_interval)
