from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Literal, TYPE_CHECKING

from helpers import extract_tools
from helpers.tool import coerce_bool
from helpers.defer import DeferredTask, THREAD_BACKGROUND
from helpers.extension import call_extensions_async
from helpers.print_style import PrintStyle

if TYPE_CHECKING:
    from agent import Agent, AgentConfig, AgentContext
    from helpers.log import LogItem


PARALLEL_JOBS_KEY = "_parallel_jobs"
PARALLEL_WORKER_PARENT_CONTEXT_KEY = "_parallel_parent_context_id"
PARALLEL_WORKER_JOB_KEY = "_parallel_job_id"
PARALLEL_WORKER_KIND_KEY = "_parallel_worker_kind"

CHILD_PARENT_CONTEXT_ID_KEY = "parent_context_id"
CHILD_PARENT_AGENT_NUMBER_KEY = "parent_agent_number"
CHILD_PARENT_CONTEXT_KIND_KEY = "parent_context_kind"
CHILD_PARENT_CONTEXT_LABEL_KEY = "parent_context_label"
CHILD_PARALLEL_JOB_ID_KEY = "parallel_job_id"
CHILD_PARALLEL_TOOL_NAME_KEY = "parallel_tool_name"

DEFAULT_MAX_CALLS = 8
DEFAULT_TIMEOUT_SECONDS = 300
POLL_INTERVAL_SECONDS = 0.5
DISALLOWED_PARALLEL_TOOLS = {"document_query", "response", "goal", "input", "input_remote"}

TERMINAL_STATES = {"success", "error", "cancelled", "timeout"}
JobState = Literal["pending", "running", "success", "error", "cancelled", "timeout"]
JobKind = Literal["tool", "subordinate"]


@dataclass
class NormalizedToolCall:
    index: int
    tool_name: str
    tool_args: dict[str, Any]


@dataclass
class ParallelJob:
    id: str
    parent_context_id: str
    index: int
    tool_name: str
    tool_args: dict[str, Any]
    kind: JobKind
    parent_agent: "Agent | None" = field(default=None, repr=False)
    state: JobState = "pending"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: str | None = None
    error: str | None = None
    worker_context_id: str | None = None
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    log_item: "LogItem | None" = field(default=None, repr=False)
    deferred_task: DeferredTask | None = field(default=None, repr=False)
    parent_history: list[tuple[Any, int]] = field(default_factory=list, repr=False)

    def elapsed(self) -> float:
        end = self.completed_at or time.time()
        start = self.started_at or self.created_at
        return max(0.0, end - start)


def extract_tool_calls(args: dict[str, Any]) -> Any:
    for key in ("tool_calls", "calls", "items"):
        if key in args:
            return args.get(key)
    return None


def normalize_parallel_tool_calls(raw_calls: Any) -> list[NormalizedToolCall]:
    if isinstance(raw_calls, str):
        try:
            raw_calls = json.loads(raw_calls)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "`tool_calls` must be an array of normal tool-call objects."
            ) from exc
    if not isinstance(raw_calls, list):
        raise ValueError("`tool_calls` must be an array of normal tool-call objects.")
    if not raw_calls:
        raise ValueError("`tool_calls` must contain at least one tool call.")
    if len(raw_calls) > DEFAULT_MAX_CALLS:
        raise ValueError(f"`tool_calls` supports at most {DEFAULT_MAX_CALLS} items.")

    calls: list[NormalizedToolCall] = []
    for index, raw_call in enumerate(raw_calls):
        try:
            tool_name, tool_args = extract_tools.normalize_tool_request(raw_call)
        except ValueError as exc:
            raise ValueError(f"tool_calls[{index}] is not a valid tool call: {exc}") from exc

        _ensure_parallel_tool_allowed(tool_name, tool_args)

        calls.append(
            NormalizedToolCall(
                index=index,
                tool_name=tool_name,
                tool_args=dict(tool_args),
            )
        )
    return calls


def _ensure_parallel_tool_allowed(tool_name: str, tool_args: dict[str, Any]) -> None:
    if tool_name == "parallel":
        raise ValueError("`parallel` cannot be nested inside another `parallel` call.")
    if (
        tool_name in {"code_execution_tool", "code_execution_remote"}
        and str(tool_args.get("runtime", "")).strip().lower() in {"output", "reset"}
    ):
        raise ValueError(
            "Use `parallel` with job_ids to await/cancel a running code job; "
            "call session tools sequentially."
        )
    if tool_name in DISALLOWED_PARALLEL_TOOLS:
        raise ValueError(
            f"`{tool_name}` cannot be used inside `parallel`; call it sequentially."
        )


def normalize_job_ids(raw_job_ids: Any) -> list[str]:
    if raw_job_ids is None:
        return []
    if isinstance(raw_job_ids, str):
        return [raw_job_ids]
    if isinstance(raw_job_ids, list):
        return [str(item) for item in raw_job_ids if str(item).strip()]
    raise ValueError("`job_ids` must be a string or an array of strings.")


def coerce_timeout(value: Any) -> int:
    if value in (None, ""):
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"`timeout` must be an integer number of seconds, got {value!r}.") from exc
    if timeout <= 0:
        raise ValueError("`timeout` must be greater than 0.")
    return timeout


def _parallel_worker_kind(agent: "Agent | None") -> JobKind | None:
    context = getattr(agent, "context", None)
    if not context:
        return None
    kind = context.get_data(PARALLEL_WORKER_KIND_KEY)
    if kind in {"tool", "subordinate"}:
        return kind
    if context.get_data(PARALLEL_WORKER_JOB_KEY):
        return "tool"
    return None


def is_parallel_worker(agent: "Agent | None") -> bool:
    return _parallel_worker_kind(agent) == "tool"


def get_parallel_worker_job(agent: "Agent") -> ParallelJob | None:
    if not is_parallel_worker(agent):
        return None
    context = agent.context
    parent_context_id = str(context.get_data(PARALLEL_WORKER_PARENT_CONTEXT_KEY) or "")
    job_id = str(context.get_data(PARALLEL_WORKER_JOB_KEY) or "")
    job = _get_job(parent_context_id, job_id)
    return job if job and job.kind == "tool" else None


def queue_parallel_parent_history(
    agent: "Agent",
    *,
    content: Any,
    tokens: int = 0,
) -> bool:
    job = get_parallel_worker_job(agent)
    if not job:
        return False
    job.parent_history.append((content, tokens))
    return True


def _jobs_for_context(context: "AgentContext") -> dict[str, ParallelJob]:
    jobs = context.get_data(PARALLEL_JOBS_KEY)
    if not isinstance(jobs, dict):
        jobs = {}
        context.set_data(PARALLEL_JOBS_KEY, jobs)
    return jobs


def _get_job(parent_context_id: str, job_id: str) -> ParallelJob | None:
    from agent import AgentContext

    context = AgentContext.get(parent_context_id)
    if not context:
        return None
    job = _jobs_for_context(context).get(job_id)
    return job if isinstance(job, ParallelJob) else None


def _new_job_id(tool_name: str) -> str:
    prefix = "".join(ch for ch in tool_name if ch.isalnum())[:12] or "job"
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def start_parallel_jobs(
    agent: "Agent",
    calls: list[NormalizedToolCall],
) -> list[ParallelJob]:
    for call in calls:
        _ensure_parallel_tool_allowed(call.tool_name, call.tool_args)
    jobs: list[ParallelJob] = []
    context = agent.context
    job_store = _jobs_for_context(context)

    for call in calls:
        kind: JobKind = "subordinate" if call.tool_name == "call_subordinate" else "tool"
        job = ParallelJob(
            id=_new_job_id(call.tool_name),
            parent_context_id=context.id,
            index=call.index,
            tool_name=call.tool_name,
            tool_args=call.tool_args,
            kind=kind,
            parent_agent=agent,
        )
        job_store[job.id] = job
        jobs.append(job)
        _log_parallel_child_started(agent, job)

        try:
            job.state = "running"
            job.started_at = time.time()
            task = DeferredTask(thread_name=THREAD_BACKGROUND)
            job.deferred_task = task
            if _parallel_worker_kind(agent) == "subordinate" and context.task:
                context.task.add_child_task(task)
            task.start_task(_run_parallel_job, context.id, job.id)
        except Exception as exc:
            _finish_job(job, "error", error=str(exc))

    return jobs


async def await_parallel_jobs(
    agent: "Agent",
    job_ids: list[str],
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    *,
    collect: bool = True,
    wait: bool = True,
) -> list[dict[str, Any]]:
    if not job_ids:
        raise ValueError("No `job_ids` were provided to await.")

    deadline = time.time() + timeout
    wait_timed_out_job_ids: set[str] = set()
    while True:
        await refresh_parallel_jobs(agent)
        jobs = [_jobs_for_context(agent.context).get(job_id) for job_id in job_ids]
        missing = [job_id for job_id, job in zip(job_ids, jobs) if job is None]
        if missing:
            raise ValueError(f"Unknown parallel job id(s): {', '.join(missing)}")

        active = [job for job in jobs if job and job.state not in TERMINAL_STATES]
        if not wait or not active:
            break

        if time.time() >= deadline:
            wait_timed_out_job_ids = {job.id for job in active}
            break

        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    snapshots = []
    for job_id in job_ids:
        job = _jobs_for_context(agent.context).get(job_id)
        if job:
            snapshot = _job_snapshot(job, include_result=True)
            if job.id in wait_timed_out_job_ids and job.state not in TERMINAL_STATES:
                snapshot["wait_timed_out"] = True
            snapshots.append(snapshot)

    if collect:
        await collect_parallel_jobs(agent, job_ids)

    return snapshots


async def cancel_parallel_jobs(agent: "Agent", job_ids: list[str]) -> list[dict[str, Any]]:
    if not job_ids:
        raise ValueError("No `job_ids` were provided to cancel.")

    await refresh_parallel_jobs(agent)
    snapshots = []
    for job_id in job_ids:
        job = _jobs_for_context(agent.context).get(job_id)
        if not job:
            raise ValueError(f"Unknown parallel job id: {job_id}")
        await _cancel_job(job)
        snapshots.append(_job_snapshot(job, include_result=True))
        await cleanup_parallel_job(agent, job)
        _jobs_for_context(agent.context).pop(job_id, None)
    return snapshots


async def refresh_parallel_jobs(agent: "Agent") -> list[ParallelJob]:
    jobs = list(_jobs_for_context(agent.context).values())
    for job in jobs:
        if job.state in TERMINAL_STATES:
            continue
        task = job.deferred_task
        if not task:
            continue
        if task.is_ready():
            try:
                await task.result()
            except asyncio.CancelledError:
                _finish_job(job, "cancelled", error="Parallel job was cancelled.")
            except Exception as exc:
                _finish_job(job, "error", error=str(exc))
        elif task.is_alive():
            job.state = "running"
            if job.started_at is None:
                job.started_at = time.time()
    return jobs


async def cleanup_parallel_job(agent: "Agent", job: ParallelJob) -> None:
    if job.deferred_task and job.deferred_task.is_alive():
        job.deferred_task.kill()
    # Direct workers remove their context in finally on their own event loop.


async def collect_parallel_jobs(
    agent: "Agent",
    job_ids: list[str],
    *,
    promote_parent_history: bool = False,
) -> None:
    jobs = _jobs_for_context(agent.context)
    for job_id in dict.fromkeys(job_ids):
        job = jobs.get(job_id)
        if not job or job.state not in TERMINAL_STATES:
            continue
        if promote_parent_history:
            for content, tokens in job.parent_history:
                agent.hist_add_message(False, content=content, tokens=tokens)
            job.parent_history.clear()
        await cleanup_parallel_job(agent, job)
        jobs.pop(job_id, None)


async def build_parallel_jobs_extras(agent: "Agent") -> str:
    await refresh_parallel_jobs(agent)
    jobs = [
        job
        for job in _jobs_for_context(agent.context).values()
        if isinstance(job, ParallelJob) and job.state not in {"cancelled", "timeout"}
    ]
    if not jobs:
        return ""

    active = [job for job in jobs if job.state not in TERMINAL_STATES]
    ready = [job for job in jobs if job.state in TERMINAL_STATES]
    if not active and not ready:
        return ""

    lines = ["parallel jobs:"]
    if active:
        lines.append("running:")
        for job in active:
            lines.append(
                f"- {job.id}: {job.tool_name} [{job.state}], running for {job.elapsed():.1f}s"
            )
    if ready:
        lines.append("ready to collect with `parallel` and `job_ids`:")
        for job in ready:
            lines.append(
                f"- {job.id}: {job.tool_name} [{job.state}], duration {job.elapsed():.1f}s"
            )
    lines.append("call the `parallel` tool with `job_ids` to await/collect results or `action: \"cancel\"` to cancel.")
    return "\n".join(lines)


def format_started_jobs(jobs: list[ParallelJob]) -> str:
    payload = {
        "status": "started",
        "jobs": [_job_snapshot(job, include_result=False) for job in jobs],
        "instruction": "Use the parallel tool with job_ids to await or cancel these background jobs.",
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def format_parallel_results(results: list[dict[str, Any]]) -> str:
    states = [result.get("state") for result in results]
    has_active_jobs = any(state not in TERMINAL_STATES for state in states)
    wait_timed_out = any(result.get("wait_timed_out") for result in results)
    if has_active_jobs:
        status = "waiting" if wait_timed_out else "running"
    elif states and all(state == "success" for state in states):
        status = "success"
    elif states and all(state == "cancelled" for state in states):
        status = "cancelled"
    elif any(state == "success" for state in states):
        status = "partial"
    else:
        status = "error"

    payload = {
        "status": status,
        "jobs": results,
    }
    if wait_timed_out:
        payload["wait_timeout"] = True
    if has_active_jobs:
        payload["instruction"] = (
            "Some jobs are still running. Call `parallel` with `action: \"await\"` "
            "and the listed `job_ids` to wait again, or `action: \"cancel\"` to stop them."
        )
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


async def _run_parallel_job(parent_context_id: str, job_id: str) -> None:
    job = _get_job(parent_context_id, job_id)
    if not job:
        return
    try:
        if job.kind == "subordinate":
            result = await _run_subordinate_context_job(parent_context_id, job)
        else:
            result = await _run_direct_tool_job(parent_context_id, job)
        _finish_job(job, "success", result=result)
    except asyncio.CancelledError:
        _finish_job(job, "cancelled", error="Parallel job was cancelled.")
        raise
    except Exception as exc:
        _finish_job(job, "error", error=str(exc))
        PrintStyle.error(f"Parallel job {job.id} failed: {exc}")


async def _run_subordinate_context_job(parent_context_id: str, job: ParallelJob) -> str:
    from agent import AgentContext
    from helpers.tool_policy import ensure_tool_allowed
    from tools.call_subordinate import get_or_create_subordinate, run_subordinate

    parent_context = AgentContext.get(parent_context_id)
    if not parent_context:
        raise ValueError("Parent context not found.")
    parent_agent = job.parent_agent or parent_context.agent0
    ensure_tool_allowed(parent_agent, "call_subordinate")

    args = job.tool_args
    message = str(args.get("message") or "").strip()
    if not message:
        raise ValueError("call_subordinate requires `tool_args.message`.")

    context_id = str(args.get("context_id") or args.get("agent_id") or "").strip()
    reset = args.get("reset", False)
    slot = (
        job.id
        if coerce_bool(reset, False) and not context_id
        else "default"
    )
    attachments = args.get("attachments") if isinstance(args.get("attachments"), list) else []
    subordinate = get_or_create_subordinate(
        parent_agent,
        profile=str(args.get("profile") or args.get("agent_profile") or ""),
        reset=reset,
        context_id=context_id,
        name=str(args.get("name") or ""),
        message=message,
        slot=slot,
    )
    worker_context = subordinate.context
    job.worker_context_id = worker_context.id
    if job.deferred_task:
        worker_context.task = job.deferred_task

    worker_context.set_data(PARALLEL_WORKER_PARENT_CONTEXT_KEY, parent_context.id)
    worker_context.set_data(PARALLEL_WORKER_JOB_KEY, job.id)
    worker_context.set_data(PARALLEL_WORKER_KIND_KEY, job.kind)
    worker_context.set_output_data(CHILD_PARALLEL_JOB_ID_KEY, job.id)
    worker_context.set_output_data(CHILD_PARALLEL_TOOL_NAME_KEY, job.tool_name)
    return await run_subordinate(parent_agent, subordinate, message, attachments)


async def _run_direct_tool_job(parent_context_id: str, job: ParallelJob) -> str:
    from agent import AgentContext, AgentContextType, LoopData

    parent_context = AgentContext.get(parent_context_id)
    if not parent_context:
        raise ValueError("Parent context not found.")

    worker_context: AgentContext | None = None
    try:
        worker_context = AgentContext(
            config=_clone_config(parent_context.config),
            name=f"parallel:{job.tool_name}",
            type=AgentContextType.BACKGROUND,
        )
        worker_context.set_data(PARALLEL_WORKER_PARENT_CONTEXT_KEY, parent_context_id)
        worker_context.set_data(PARALLEL_WORKER_JOB_KEY, job.id)
        worker_context.set_data(PARALLEL_WORKER_KIND_KEY, job.kind)
        worker_context.set_data(
            "chat_model_override",
            parent_context.get_data("chat_model_override"),
        )
        job.worker_context_id = worker_context.id
        _copy_project(parent_context, worker_context)

        worker_agent = worker_context.agent0
        worker_agent.last_user_message = parent_context.agent0.last_user_message
        worker_agent.loop_data = LoopData()
        return await execute_tool_call(
            worker_agent,
            job.tool_name,
            job.tool_args,
            log_item=job.log_item,
        )
    finally:
        if worker_context:
            await _remove_context(worker_context.id)


async def execute_tool_call(
    agent: "Agent",
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    log_item: "LogItem | None" = None,
) -> str:
    _ensure_parallel_tool_allowed(tool_name, tool_args)

    tool = _resolve_parallel_tool(agent, tool_name, tool_args, strict=True)
    if not tool:
        raise ValueError(f"Tool '{tool_name}' not found or could not be initialized.")

    original_get_log_object = None
    if log_item is not None:
        original_get_log_object = tool.get_log_object
        tool.get_log_object = lambda: log_item

    agent.loop_data.current_tool = tool
    try:
        await agent.handle_intervention()
        await tool.before_execution(**tool_args)
        await agent.handle_intervention()
        await call_extensions_async(
            "tool_execute_before",
            agent,
            tool_args=tool_args or {},
            tool_name=tool_name,
        )
        response = await tool.execute(**tool_args)
        await agent.handle_intervention()
        await call_extensions_async(
            "tool_execute_after",
            agent,
            response=response,
            tool_name=tool_name,
        )
        await tool.after_execution(response)
        await agent.handle_intervention()
        return response.message
    finally:
        if original_get_log_object is not None:
            tool.get_log_object = original_get_log_object
        agent.loop_data.current_tool = None


def _resolve_parallel_tool(
    agent: "Agent",
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    strict: bool = False,
):
    message = json.dumps({"tool_name": tool_name, "tool_args": tool_args})

    tool = None
    try:
        import helpers.mcp_handler as mcp_helper

        tool = mcp_helper.MCPConfig.get_instance().get_tool(agent, tool_name)
    except ImportError:
        tool = None
    except Exception as exc:
        if strict:
            raise
        PrintStyle.warning(f"Failed to initialize MCP tool '{tool_name}' for parallel job: {exc}")

    if not tool:
        get_tool = getattr(agent, "get_tool", None)
        if not callable(get_tool):
            if strict:
                raise ValueError(f"Tool '{tool_name}' not found or could not be initialized.")
            return None
        try:
            tool = get_tool(
                name=tool_name,
                method=None,
                args=tool_args,
                message=message,
                loop_data=getattr(agent, "loop_data", None),
            )
        except Exception as exc:
            if strict:
                raise
            PrintStyle.warning(f"Failed to initialize tool '{tool_name}' for parallel job: {exc}")
            tool = None

    if not tool:
        return None

    try:
        tool.args = tool_args
    except Exception:
        pass

    return tool


async def _cancel_job(
    job: ParallelJob,
    *,
    state: JobState = "cancelled",
    message: str = "Parallel job was cancelled.",
) -> None:
    if job.deferred_task and job.deferred_task.is_alive():
        job.deferred_task.kill()
    _finish_job(job, state, error=message)


def _finish_job(
    job: ParallelJob,
    state: JobState,
    *,
    result: str | None = None,
    error: str | None = None,
) -> None:
    job.state = state
    job.completed_at = time.time()
    if job.started_at is None:
        job.started_at = job.created_at
    if result is not None:
        job.result = result
    if error is not None:
        job.error = error
    _update_parallel_child_log(job)


async def _remove_context(context_id: str | None) -> None:
    if not context_id:
        return
    from agent import AgentContext
    from helpers import persist_chat

    context = AgentContext.get(context_id)
    if context:
        try:
            context.reset()
        except Exception:
            pass
        AgentContext.remove(context_id)
    persist_chat.remove_chat(context_id)


def _log_parallel_child_started(agent: "Agent", job: ParallelJob) -> None:
    if job.kind == "subordinate":
        job.log_item = agent.context.log.log(
            type="subagent",
            heading=f"icon://communication {agent.agent_name}: Calling Subordinate Agent",
            content="",
            kvps=job.tool_args,
            id=job.log_id,
        )
        return

    tool = _resolve_parallel_tool(agent, job.tool_name, job.tool_args)
    if tool is not None:
        try:
            job.log_item = tool.get_log_object()
            if job.log_item is not None:
                return
        except Exception as exc:
            PrintStyle.warning(
                f"Failed to derive parallel child log for {job.tool_name}: {exc}"
            )

    heading = f"icon://construction {agent.agent_name}: Using tool '{job.tool_name}'"
    job.log_item = agent.context.log.log(
        type="tool",
        heading=heading,
        content="",
        kvps=job.tool_args,
        id=job.log_id,
        _tool_name=job.tool_name,
    )


def _update_parallel_child_log(job: ParallelJob) -> None:
    if not job.log_item or job.log_item.content:
        return  # streamed or tool-written content is user-visible; never replace it
    if job.state == "success":
        content = job.result if job.result else "(completed without textual output)"
    else:
        content = f"Error: {job.error or job.state}"
    try:
        job.log_item.update(content=content)
    except Exception:
        pass


def _job_snapshot(job: ParallelJob, *, include_result: bool) -> dict[str, Any]:
    data: dict[str, Any] = {
        "job_id": job.id,
        "tool_name": job.tool_name,
        "state": job.state,
        "duration_seconds": round(job.elapsed(), 3),
    }
    if job.worker_context_id:
        data["context_id"] = job.worker_context_id
    if include_result:
        if job.result is not None:
            data["result"] = job.result
        if job.error is not None:
            data["error"] = job.error
    return data


def _clone_config(config: "AgentConfig") -> "AgentConfig":
    try:
        return replace(
            config,
            knowledge_subdirs=list(config.knowledge_subdirs),
            additional=dict(config.additional),
        )
    except Exception:
        return config


def _copy_project(parent_context: "AgentContext", worker_context: "AgentContext") -> None:
    try:
        from helpers import projects

        project_name = projects.get_context_project_name(parent_context)
        if project_name:
            projects.activate_project(worker_context.id, project_name, mark_dirty=False)
    except Exception:
        pass
