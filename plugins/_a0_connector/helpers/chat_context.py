"""Shared chat-context helpers for connector handlers."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any


class ConnectorContextError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        code: str = "BAD_REQUEST",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def get_existing_context(
    context_id: str,
    *,
    agent_profile: str | None = None,
    project_name: str | None = None,
):
    from agent import AgentContext
    from helpers import projects

    context = AgentContext.get(context_id)
    if context is None:
        raise ConnectorContextError(
            "Context not found",
            status_code=404,
            code="CONTEXT_NOT_FOUND",
        )

    if agent_profile and getattr(context.agent0.config, "profile", None) != agent_profile:
        raise ConnectorContextError(
            "Cannot change agent_profile on existing context",
            status_code=400,
            code="INVALID_AGENT_PROFILE",
        )

    existing_project = context.get_data(projects.CONTEXT_DATA_KEY_PROJECT)
    if project_name and existing_project and existing_project != project_name:
        raise ConnectorContextError(
            "Project can only be set on first message",
            status_code=400,
            code="PROJECT_CONFLICT",
        )

    return context


def create_context(
    *,
    lock: Any | None = None,
    current_context_id: str | None = None,
    agent_profile: str | None = None,
    project_name: str | None = None,
):
    from agent import AgentContext, AgentContextType
    from helpers import projects, settings
    from helpers.state_monitor_integration import mark_dirty_all
    from initialize import initialize_agent
    from plugins._model_config.helpers.model_config import is_chat_override_allowed

    override_settings: dict[str, str] = {}
    if agent_profile:
        override_settings["agent_profile"] = agent_profile

    with lock if lock is not None else nullcontext():
        current_context = AgentContext.get(current_context_id or "") if current_context_id else None

        context = AgentContext(
            config=initialize_agent(override_settings=override_settings),
            type=AgentContextType.USER,
            set_current=True,
        )

        if agent_profile:
            context.set_data("agent_profile_manually_set", True)

        if current_context and settings.get_settings().get("chat_inherit_project", True):
            current_project = current_context.get_data(projects.CONTEXT_DATA_KEY_PROJECT)
            if current_project:
                context.set_data(projects.CONTEXT_DATA_KEY_PROJECT, current_project)

            current_project_output = current_context.get_output_data(
                projects.CONTEXT_DATA_KEY_PROJECT
            )
            if current_project_output:
                context.set_output_data(
                    projects.CONTEXT_DATA_KEY_PROJECT,
                    current_project_output,
                )

        if current_context:
            model_override = current_context.get_data("chat_model_override")
            if model_override and is_chat_override_allowed(context.agent0):
                context.set_data("chat_model_override", model_override)

        if project_name:
            try:
                try:
                    projects.activate_project(context.id, project_name, mark_dirty=False)
                except TypeError as exc:
                    if "mark_dirty" not in str(exc):
                        raise
                    projects.activate_project(context.id, project_name)
            except Exception:
                AgentContext.remove(context.id)
                raise

        mark_dirty_all(reason="plugins._a0_connector.chat_context.create_context")
        return context
