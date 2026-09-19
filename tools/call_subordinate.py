import asyncio

from agent import Agent, AgentContext, UserMessage
from helpers import message_queue, persist_chat, projects, subagents
from helpers.errors import RepairableException
from helpers.tool import Tool, Response, coerce_bool
from initialize import initialize_agent
from extensions.python.hist_add_tool_result import _90_save_tool_call_file as save_tool_call_file
from plugins._model_config.helpers.model_config import DEFAULT_PRESET_NAME, get_configured_preset_name


SUBORDINATES_DATA_KEY = "_subordinates"
CHILD_PARENT_CONTEXT_ID_KEY = "parent_context_id"
CHILD_PARENT_AGENT_NUMBER_KEY = "parent_agent_number"
CHILD_PARENT_CONTEXT_KIND_KEY = "parent_context_kind"
CHILD_PARENT_CONTEXT_LABEL_KEY = "parent_context_label"
CHILD_SUBORDINATE_SLOT_KEY = "subordinate_slot"
DEFAULT_SUBORDINATE_SLOT = "default"


def _subordinate_profile_labels(agent: Agent) -> dict[str, str]:
    project = projects.get_context_project_name(agent.context) if agent.context else None
    return {
        name: subagent.title or name
        for name, subagent in subagents.get_available_agents_dict(project).items()
    }


def _validate_subordinate_profile(agent: Agent, profile: str) -> str:
    agent_profile = str(profile or "").strip()
    if not agent_profile:
        return ""

    labels = _subordinate_profile_labels(agent)
    if agent_profile in labels:
        return agent_profile

    available = ", ".join(
        f"{key} ({label})" if label and label != key else key
        for key, label in sorted(labels.items())
    )
    if not available:
        available = "none"
    raise RepairableException(
        f"Agent profile '{agent_profile}' not found. Use one of the available profiles: {available}."
    )


def _register_subordinate(parent: Agent, subordinate: Agent, slot: str) -> None:
    subordinates = parent.get_data(SUBORDINATES_DATA_KEY)
    if not isinstance(subordinates, dict):
        subordinates = {}
        parent.set_data(SUBORDINATES_DATA_KEY, subordinates)
    subordinates[subordinate.context.id] = subordinate
    subordinate.set_data(Agent.DATA_NAME_SUPERIOR, parent)
    if slot == DEFAULT_SUBORDINATE_SLOT and subordinate.context is parent.context:
        parent.set_data(Agent.DATA_NAME_SUBORDINATE, subordinate)


def _is_child_context(context: AgentContext, parent: Agent, slot: str | None = None) -> bool:
    if context.get_output_data(CHILD_PARENT_CONTEXT_ID_KEY) != parent.context.id:
        return False
    if context.get_output_data(CHILD_PARENT_AGENT_NUMBER_KEY) != parent.number:
        return False
    if context.agent0.number != parent.number + 1:
        return False
    return slot is None or context.get_output_data(CHILD_SUBORDINATE_SLOT_KEY) == slot


def _is_live_context(context: AgentContext) -> bool:
    return not isinstance(context, AgentContext) or AgentContext.get(context.id) is context


def _find_subordinate(parent: Agent, context_id: str, slot: str) -> Agent | None:
    registered = parent.get_data(SUBORDINATES_DATA_KEY)
    registered = registered if isinstance(registered, dict) else {}
    if context_id:
        subordinate = registered.get(context_id)
        if (
            subordinate
            and _is_live_context(subordinate.context)
            and _is_child_context(subordinate.context, parent)
        ):
            return subordinate
        context = AgentContext.get(context_id)
        if not context or not _is_child_context(context, parent):
            raise RepairableException(
                f"Subordinate context '{context_id}' was not found under {parent.agent_name}."
            )
        subordinate = context.agent0
        _register_subordinate(parent, subordinate, slot)
        return subordinate

    existing = parent.get_data(Agent.DATA_NAME_SUBORDINATE)
    if slot == DEFAULT_SUBORDINATE_SLOT and existing is not None:
        return existing

    registered_matches = [
        subordinate
        for subordinate in registered.values()
        if _is_live_context(subordinate.context)
        and _is_child_context(subordinate.context, parent, slot)
    ]
    if registered_matches:
        return max(
            registered_matches,
            key=lambda subordinate: subordinate.context.created_at,
        )

    matches = [
        context
        for context in AgentContext.all()
        if _is_child_context(context, parent, slot)
    ]
    if not matches:
        return None
    subordinate = max(matches, key=lambda context: context.created_at).agent0
    _register_subordinate(parent, subordinate, slot)
    return subordinate


def get_or_create_subordinate(
    parent: Agent,
    *,
    profile: str = "",
    reset: bool | str = False,
    context_id: str = "",
    name: str = "",
    message: str = "",
    slot: str = DEFAULT_SUBORDINATE_SLOT,
) -> Agent:
    requested_profile = _validate_subordinate_profile(parent, profile)
    target_context_id = str(context_id or "").strip()
    reset_requested = coerce_bool(reset, False)
    if target_context_id and reset_requested:
        raise RepairableException(
            "`context_id` continues an existing subordinate and requires reset=false. "
            "Omit `context_id` to create a fresh subordinate."
        )

    subordinate = (
        None
        if reset_requested
        else _find_subordinate(parent, target_context_id, slot)
    )
    if subordinate:
        current_profile = str(getattr(subordinate.config, "profile", "") or "")
        if requested_profile and current_profile != requested_profile:
            raise RepairableException(
                f"Subordinate already uses profile '{current_profile or 'default'}'. "
                f"Set reset=true and omit `context_id` to switch to '{requested_profile}'."
            )
        if subordinate.context is not parent.context and subordinate.context.is_running():
            raise RepairableException(
                f"Subordinate context '{subordinate.context.id}' is still running. "
                "Wait for it to finish or stop it before continuing it."
            )
        label = str(name or "").strip()
        if label and subordinate.context is not parent.context:
            subordinate.context.name = label
            subordinate.context.set_output_data(CHILD_PARENT_CONTEXT_LABEL_KEY, label)
        return subordinate

    override_settings = {"agent_profile": requested_profile} if requested_profile else None
    subordinate = Agent(parent.number + 1, initialize_agent(override_settings=override_settings))
    context = subordinate.context
    context.name = str(name or "").strip() or _short_label(message) or subordinate.agent_name
    context.set_output_data(CHILD_PARENT_CONTEXT_ID_KEY, parent.context.id)
    context.set_output_data(CHILD_PARENT_AGENT_NUMBER_KEY, parent.number)
    context.set_output_data(CHILD_PARENT_CONTEXT_KIND_KEY, "subordinate")
    context.set_output_data(CHILD_PARENT_CONTEXT_LABEL_KEY, context.name)
    context.set_output_data(CHILD_SUBORDINATE_SLOT_KEY, slot)

    project = projects.get_context_project_name(parent.context)
    if project:
        projects.activate_project(context.id, project, mark_dirty=False)
    model_override = parent.context.get_data("chat_model_override")
    if model_override and get_configured_preset_name(subordinate) == DEFAULT_PRESET_NAME:
        context.set_data("chat_model_override", model_override)

    _register_subordinate(parent, subordinate, slot)
    return subordinate


async def run_subordinate(
    parent: Agent,
    subordinate: Agent,
    message: str,
    attachments: list[str] | None = None,
) -> str:
    assignment = str(message or "").strip()
    if not assignment:
        raise RepairableException("call_subordinate requires a non-empty `message`.")

    attachment_paths = [str(item) for item in attachments or []]
    if subordinate.context is not parent.context:
        message_queue.log_user_message(
            subordinate.context,
            assignment,
            attachment_paths,
            source=" (subordinate)",
        )
    subordinate.hist_add_user_message(
        UserMessage(message=assignment, attachments=attachment_paths)
    )
    if subordinate.context is not parent.context:
        persist_chat.save_tmp_chat(subordinate.context)

    try:
        result = await subordinate.monologue()
        subordinate.history.new_topic()
        return result
    finally:
        if subordinate.context is not parent.context:
            persist_chat.save_tmp_chat(subordinate.context)


def _short_label(text: str, limit: int = 80) -> str:
    return " ".join(str(text or "").split())[:limit].rstrip()


class Delegation(Tool):

    async def execute(self, message="", reset="", context_id="", **kwargs):
        attachments = kwargs.get("attachments")
        attachments = attachments if isinstance(attachments, list) else []
        subordinate = get_or_create_subordinate(
            self.agent,
            profile=kwargs.get("profile", kwargs.get("agent_profile", "")),
            reset=reset,
            context_id=context_id or kwargs.get("agent_id", ""),
            name=kwargs.get("name", ""),
            message=message,
        )
        if subordinate.context is self.agent.context:
            result = await run_subordinate(self.agent, subordinate, message, attachments)
        else:
            task = subordinate.context.run_task(
                run_subordinate, self.agent, subordinate, message, attachments
            )
            try:
                result = await task.result()
            except asyncio.CancelledError:
                caller = asyncio.current_task()
                if caller and caller.cancelling():
                    task.kill()
                    raise
                raise RepairableException(
                    f"Subordinate context '{subordinate.context.id}' was stopped."
                ) from None

        # hint to use includes for long responses
        additional = {"context_id": subordinate.context.id}
        if len(result) >= save_tool_call_file.LEN_MIN:
            hint = self.agent.read_prompt("fw.hint.call_sub.md")
            if hint:
                additional["hint"] = hint

        # result
        return Response(message=result, break_loop=False, additional=additional)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="subagent",
            heading=f"icon://communication {self.agent.agent_name}: Calling Subordinate Agent",
            content="",
            kvps=self.args,
        )
