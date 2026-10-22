import re
import json
import time
import asyncio
from typing import TYPE_CHECKING

from helpers import plugins
from helpers import history as history_helpers
from helpers.errors import HandledException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

if TYPE_CHECKING:
    from agent import Agent
    from helpers.log import LogItem

PLUGIN_NAME = "_infection_check"
DATA_KEY = f"_plugin.{PLUGIN_NAME}"
DATA_KEY_PASSED = f"{DATA_KEY}.passed"
DATA_KEY_MONO = f"{DATA_KEY}.mono"

_RE_OK = re.compile(r"<ok\s*/>")
_RE_TERMINATE = re.compile(r"<terminate\s*/>")
_RE_CLARIFY = re.compile(r"<clarify>(.*?)</clarify>", re.DOTALL)


def get_config(agent: "Agent") -> dict:
    return plugins.get_plugin_config(PLUGIN_NAME, agent=agent) or {}


def get_checker(agent: "Agent") -> "InfectionChecker":
    """Get or create a checker for the current iteration.

    A new InfectionChecker is created when:
    - The monologue changes (detected via id(loop_data)).
    - The iteration within the same monologue changes.
    """
    loop = getattr(agent, "loop_data", None)
    iteration = loop.iteration if loop else -1
    mono_id = id(loop) if loop else None

    # Reset passed flag on new monologue
    if agent.get_data(DATA_KEY_MONO) != mono_id:
        agent.set_data(DATA_KEY_MONO, mono_id)
        agent.set_data(DATA_KEY_PASSED, False)
        agent.set_data(DATA_KEY, None)  # discard stale checker from previous monologue

    checker: "InfectionChecker | None" = agent.get_data(DATA_KEY)
    if checker is None or checker.iteration != iteration:
        checker = InfectionChecker(config=get_config(agent), iteration=iteration)
        agent.set_data(DATA_KEY, checker)
        agent.set_data(DATA_KEY_PASSED, False)  # re-check each iteration
    return checker


def parse_result(text: str) -> tuple[str, str]:
    """Find the *last* occurrence of any verdict tag in *text*."""
    pos = -1
    action, detail = "ok", ""
    for m in _RE_OK.finditer(text):
        if m.start() > pos:
            pos, action, detail = m.start(), "ok", ""
    for m in _RE_TERMINATE.finditer(text):
        if m.start() > pos:
            pos, action, detail = m.start(), "terminate", ""
    for m in _RE_CLARIFY.finditer(text):
        if m.start() > pos:
            pos, action, detail = m.start(), "clarify", m.group(1).strip()
    return action, detail


class InfectionChecker:

    def __init__(self, config: dict, iteration: int):
        self.mode: str = config.get("mode", "thoughts")
        self.model_choice: str = config.get("model", "utility")
        self.prompt: str = config.get("prompt", "")
        self.history_size: int = int(config.get("history_size", 10))
        self.max_clarifications: int = int(config.get("max_clarifications", 3))
        self.iteration = iteration

        # Accumulated text from stream callbacks
        self.reasoning_log = ""
        self.response_log = ""

        # Background analysis task
        self._task: asyncio.Task | None = None
        self._check_msgs: list = []

    # -- collection ----------------------------------------------------------

    def collect_reasoning(self, full_text: str):
        self.reasoning_log = full_text

    def collect_response(self, full_text: str):
        # Stop collecting once background analysis has started
        if self._task is None:
            self.response_log = full_text

    # -- analysis trigger ----------------------------------------------------

    def start_analysis(self, agent: "Agent"):
        """Fire-and-forget background check (called from stream extensions)."""
        if self._task is not None:
            return
        snapshot = self._build_log()
        if not snapshot.strip():
            return
        from helpers.durable import background
        if background.enabled(agent):
            self._task = self._durable_analysis(agent, snapshot, "background")
            return
        self._task = asyncio.create_task(self._run_check(agent, snapshot))

    # -- gate (called before every tool execution) ---------------------------

    async def gate(self, agent: "Agent", tool_name: str = "", tool_args: dict | None = None):
        """Block until the safety check passes or terminate the agent."""
        try:
            await self._gate_inner(agent, tool_name, tool_args)
        except HandledException:
            raise
        except Exception as e:
            from helpers.durable import background
            if background.enabled(agent):
                from helpers.durable.runtime import RecoveryHeld
                raise RecoveryHeld("infection_check_requires_reconciliation") from None
            from helpers.print_style import PrintStyle
            PrintStyle(font_color="red", padding=True).print(
                f"Infection check error (non-fatal): {e}"
            )
            try:
                agent.context.log.set_progress("Infection check: error (non-fatal)")
            except Exception:
                pass

    async def _gate_inner(self, agent: "Agent", tool_name: str, tool_args: dict | None):
        if agent.get_data(DATA_KEY_PASSED):
            return
        if not self.reasoning_log and not self.response_log:
            return

        _log = agent.context.log
        _log.set_progress("Infection check: analyzing...")

        # Attach tool context for _build_log()
        if tool_name:
            self._tool_name = tool_name
            try:
                self._tool_args = dict(tool_args) if tool_args else {}
            except Exception:
                self._tool_args = {}
        else:
            self._tool_name = ""
            self._tool_args = {}

        action, detail, cot = None, "", ""

        from helpers.durable.background import TaskHandle
        if type(self._task) is TaskHandle:
            # The immutable request may still be running on its broker. An
            # unknown verdict cannot be converted into a fresh safety request
            # or a permissive return merely because its worker disappeared.
            action, detail, cot = await self._task

        # Fast path: reuse result if background task already finished.
        if action is None and self._task is not None and self._task.done():
            try:
                action, detail, cot = self._task.result()
                _log.set_progress("Infection check: evaluating result...")
            except Exception:
                pass

        # Slow path: rebuild with full tool context.
        if action is None:
            _log.set_progress("Infection check: analyzing with tool context...")
            if self._task is not None:
                from helpers.durable.background import TaskHandle
                if type(self._task) is not TaskHandle:
                    self._task.cancel()
                    try:
                        await self._task
                    except (asyncio.CancelledError, Exception):
                        pass
                self._task = None

            snapshot = self._build_log()
            if not snapshot.strip():
                return

            from helpers.durable import background
            self._task = (self._durable_analysis(agent, snapshot, "gate") if background.enabled(agent)
                          else asyncio.create_task(self._run_check(agent, snapshot)))
            try:
                action, detail, cot = await self._task
            except asyncio.CancelledError:
                if background.enabled(agent):
                    from helpers.durable.runtime import RecoveryHeld
                    raise RecoveryHeld("infection_check_interrupted") from None
                return
            except Exception:
                if background.enabled(agent):
                    from helpers.durable.runtime import RecoveryHeld
                    raise RecoveryHeld("infection_check_requires_reconciliation") from None
                return

        from helpers.durable.background import TaskHandle
        if type(self._task) is TaskHandle and (not self._check_msgs or not isinstance(self._check_msgs[-1], AIMessage)):
            self._check_msgs.append(AIMessage(content=cot))

        if action == "ok":
            _log.set_progress("Infection check: passed")
            agent.set_data(DATA_KEY_PASSED, True)
            return

        if action == "clarify":
            warn = agent.context.log.log(
                type="warning",
                heading="Infection check: requesting clarification",
                content=f"Safety concern:\n{cot}" if cot else "",
            )
            action, detail, cot = await self._clarify_loop(agent, detail, warn)
            if action == "ok":
                warn.update(heading="Infection check: clarification passed")
                agent.set_data(DATA_KEY_PASSED, True)
                return

        # terminate
        self._do_terminate(agent, detail, cot)

    # -- internals -----------------------------------------------------------

    def _build_log(self) -> str:
        parts: list[str] = []
        if self.reasoning_log:
            parts.append(f"## Agent Reasoning\n{self.reasoning_log}")
        if self.response_log:
            parts.append(f"## Agent Response\n{self.response_log}")
        if getattr(self, "_tool_name", ""):
            try:
                args_str = json.dumps(self._tool_args, ensure_ascii=False, default=str, indent=2)
            except Exception:
                args_str = str(getattr(self, "_tool_args", {}))
            parts.append(f"## Tool About to Execute\nTool: {self._tool_name}\nArguments:\n{args_str}")
        return "\n\n".join(parts)

    def _get_model(self, agent: "Agent"):
        if self.model_choice == "main":
            return agent.get_chat_model()
        return agent.get_utility_model()

    def _prepare_check_messages(self, agent: "Agent", log_text: str):
        # Build context from recent history
        hist = agent.history.output()
        if self.history_size > 0:
            hist = hist[-self.history_size :]

        # Filter out previously blocked entries
        filtered: list = []
        for entry in hist:
            content = str(entry.get("content", "")) if isinstance(entry, dict) else ""
            if "[BLOCKED]" in content:
                if filtered:
                    filtered.pop()  # also remove the user message before it
                continue
            filtered.append(entry)

        hist_text = history_helpers.output_text(filtered, ai_label="assistant", human_label="user")
        user_msg = (
            f"## Recent Conversation History\n{hist_text}\n\n"
            f"## Current Agent Output to Analyze\n{log_text}"
        )
        self._check_msgs = [
            SystemMessage(content=self.prompt),
            HumanMessage(content=user_msg),
        ]
        return self._check_msgs

    def _durable_analysis(self, agent, log_text, phase):
        from helpers.durable import background
        values = self._prepare_check_messages(agent, log_text)
        name = f"checker:{self.iteration}:{phase}:" + background.execution._digest(background.messages(values))
        return background.inference(agent, name, self._get_model(agent), values, checker=True)

    async def _run_check(self, agent: "Agent", log_text: str) -> tuple[str, str, str]:
        self._prepare_check_messages(agent, log_text)

        model = self._get_model(agent)
        response, _ = await model.unified_call(
            messages=list(self._check_msgs),
        )
        self._check_msgs.append(AIMessage(content=response))

        action, detail = parse_result(response)
        return action, detail, response

    async def _clarify_loop(
        self, agent: "Agent", clarify_text: str, log_item: "LogItem"
    ) -> tuple[str, str, str]:
        cot_parts: list[str] = []
        from helpers.durable import background
        durable = background.enabled(agent)
        if durable:
            state = getattr(self, "_durable_clarification", None)
            if state is None:
                state = {"initial": clarify_text, "base": background.messages(self._check_msgs),
                         "history": background.messages(agent.history.output_langchain())}
                self._durable_clarification = state
            clarify_text = state["initial"]
            roles = {"system": SystemMessage, "human": HumanMessage, "ai": AIMessage}
            self._check_msgs = [roles[item["role"]](content=item["content"]) for item in state["base"]]
            series = background.execution._digest(state)

        # Throttled log display — avoids per-token stream() and O(n²) masking.
        _buf = ""
        _last_flush = 0.0
        _INTERVAL = 0.25  # seconds between UI pushes

        def _flush():
            nonlocal _last_flush
            log_item.update(content=_buf)
            _last_flush = time.monotonic()

        def _append(text: str):
            nonlocal _buf
            _buf += text
            if time.monotonic() - _last_flush >= _INTERVAL:
                _flush()

        for i in range(self.max_clarifications):
            log_item.update(
                heading=f"Infection check: clarification {i + 1}/{self.max_clarifications}",
            )
            _buf = f"Safety model question:\n{clarify_text}\n\nAgent response:\n"
            _flush()

            # Clone conversation and ask the agent to explain
            chat_msgs = ([roles[item["role"]](content=item["content"]) for item in state["history"]]
                         if durable else agent.history.output_langchain())
            chat_msgs.append(HumanMessage(content=clarify_text))

            async def _agent_cb(chunk: str, full: str):
                if chunk:
                    _append(chunk)

            if durable:
                agent_resp = await background.inference(agent, f"checker:{self.iteration}:clarify:{series}:{i}:agent",
                    agent.get_chat_model(), chat_msgs)
            else:
                agent_resp, _ = await agent.get_chat_model().unified_call(
                    messages=chat_msgs, response_callback=_agent_cb)
            cot_parts.append(f"Q: {clarify_text}\nA: {agent_resp}")
            _append("\n\nSafety model verdict:\n")
            _flush()

            # Feed agent's response back to the check model
            self._check_msgs.append(
                HumanMessage(
                    content=(
                        f"The agent responded:\n\n{agent_resp}\n\n"
                        "Re-evaluate and provide your verdict."
                    )
                )
            )

            async def _check_cb(chunk: str, full: str):
                if chunk:
                    _append(chunk)

            if durable:
                check_resp = await background.inference(agent, f"checker:{self.iteration}:clarify:{series}:{i}:verdict",
                    self._get_model(agent), list(self._check_msgs))
            else:
                check_resp, _ = await self._get_model(agent).unified_call(
                    messages=list(self._check_msgs), response_callback=_check_cb)
            self._check_msgs.append(AIMessage(content=check_resp))
            cot_parts.append(f"Safety: {check_resp}")
            _flush()

            action, detail = parse_result(check_resp)
            if action != "clarify":
                return action, detail, "\n\n".join(cot_parts)
            clarify_text = detail

        return "terminate", "Max clarifications exceeded.", "\n\n".join(cot_parts)

    def _do_terminate(self, agent: "Agent", detail: str, cot: str):
        import uuid as _uuid
        content = cot or detail or "Malicious behavior detected."
        msg_id = str(_uuid.uuid4())
        agent.context.log.log(
            type="warning",
            heading="Infection check: TERMINATED",
            content=content,
            id=msg_id,
        )

        # Replace last AI message with a blocked marker
        try:
            msgs = agent.history.current.messages
            if msgs and msgs[-1].ai:
                msgs.pop()
            agent.history.add_message(
                ai=True, content="[BLOCKED] Response terminated by security policy.",
                id=msg_id,
            )
        except Exception:
            pass

        # Desktop notification
        from helpers.notification import (
            NotificationManager,
            NotificationType,
            NotificationPriority,
        )

        NotificationManager.send_notification(
            type=NotificationType.ERROR,
            priority=NotificationPriority.HIGH,
            title="Infection Check",
            message="Threat detected — agent execution terminated.",
            detail=detail or "Malicious behavior detected.",
            display_time=8,
        )

        # process_chain_end won't fire after HandledException,
        # so schedule queue resumption before raising.
        self._schedule_queue_resume(agent)

        raise HandledException(
            Exception("Infection check terminated: " + (detail or "threat detected"))
        )

    @staticmethod
    def _schedule_queue_resume(agent: "Agent"):
        from helpers import message_queue as mq

        if agent.number != 0:
            return
        context = agent.context
        if not mq.has_queue(context):
            return

        async def _resume():
            total_wait = 0.0
            while context.is_running() and total_wait < 60:
                await asyncio.sleep(0.1)
                total_wait += 0.1
            if not context.is_running():
                mq.send_next(context)

        asyncio.create_task(_resume())
