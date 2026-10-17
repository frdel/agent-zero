from agent import AgentContext
from helpers import projects, subagents
from helpers.api import ApiHandler, Request, Response
from helpers.persist_chat import save_tmp_chat
from helpers.state_monitor_integration import mark_dirty_for_context
from initialize import initialize_agent


class SetAgentProfile(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        context_id = str(input.get("context_id", "") or "").strip()
        profile = str(input.get("agent_profile", "") or "").strip()

        if not context_id:
            return Response(status=400, response="Missing context_id")
        if not profile:
            return Response(status=400, response="Missing agent_profile")

        context = AgentContext.get(context_id)
        if not context:
            return Response(status=404, response="Context not found")
        if context.is_running():
            return Response(
                status=409,
                response="Agent profile can be changed after the current run finishes.",
            )

        profiles = subagents.get_available_agents_dict(
            projects.get_context_project_name(context)
        )
        selected_profile = profiles.get(profile)
        if selected_profile is None:
            return Response(status=404, response=f"Agent profile '{profile}' not found")

        config = initialize_agent(override_settings={"agent_profile": profile})
        context.config = config
        context.agent0.config = config
        context.set_data("agent_profile_manually_set", True)

        save_tmp_chat(context)
        mark_dirty_for_context(context.id, reason="agent_profile_change")
        return {
            "ok": True,
            "agent_profile": profile,
            "agent_profile_label": selected_profile.title or profile,
        }
