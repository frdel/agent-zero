"""Shared native, JSON and parallel tool invocation lifecycle."""
from __future__ import annotations

from helpers import extension


async def execute_tool(tool, tool_args, *, agent=None, tool_name=None,
                       extension_call=None, responses_item_factory=None):
    from helpers.durable.runtime import current
    agent = agent if agent is not None else tool.agent
    tool_name = tool_name if tool_name is not None else tool.name
    extension_call = extension_call or extension.call_extensions_async
    durable = current(agent)
    call_id = None
    previous_call_id = durable.active_call_id if durable else None
    agent.loop_data.current_tool = tool
    try:
        if durable:
            call_id, recorded = await durable.tool_begin(tool, tool_args)
            if recorded is not None:
                return recorded
        if durable:
            durable.active_call_id = call_id
            from helpers.durable.resources import local_value
            tool_args = local_value(agent.context, tool_args)
            tool.args = tool_args
        if durable and call_id in durable.resuming_args:
            # Before hooks already completed. Only audited policy/credential
            # preparation may run again; arbitrary tool methods do not replay.
            prepared = durable.resuming_args[call_id]
            tool_args = dict(prepared["payload"])
            from helpers.durable.resources import local_value
            tool_args = local_value(agent.context, tool_args)
            tool.args = tool_args
            log_id = prepared["result"].get("log_id")
            tool.log = next((item for item in agent.context.log.logs
                             if item.id == log_id and item.type == prepared["result"].get("log_type")), None)
            if log_id and tool.log is None:
                from helpers.durable.runtime import RecoveryHeld
                raise RecoveryHeld("workflow_log_projection_missing")
            await agent.handle_intervention()
            if call_id not in durable.resuming_bodies:
                await extension_call("tool_execute_before", agent, tool_args=tool_args or {}, tool_name=tool_name)
                if prepared["result"].get("hooks_pending"):
                    await durable.effective_tool_args(call_id, tool_args)
        else:
            await agent.handle_intervention()
            await tool.before_execution(**tool_args)
            await agent.handle_intervention()
            if durable:
                await durable.tool_hook_input(call_id, tool_args)
            await extension_call(
                "tool_execute_before", agent, tool_args=tool_args or {}, tool_name=tool_name
            )
            if durable:
                await durable.effective_tool_args(call_id, tool_args)
        if durable and call_id in durable.resuming_bodies:
            response = durable.resuming_bodies[call_id]
        else:
            response = await tool.execute(**tool_args)
            if durable:
                await durable.tool_body(call_id, response)
        if durable:
            await durable.finalization_intent(call_id)
            await durable.owner.wait_for_ancestors(durable.run_id, getattr(agent.context, "_durable_origin", None))
        await agent.handle_intervention()
        await extension_call(
            "tool_execute_after", agent, response=response, tool_name=tool_name
        )
        if responses_item_factory:
            response.additional = {
                **(response.additional or {}),
                "_responses_output_item": responses_item_factory(response),
            }
        await tool.after_execution(response)
        await agent.handle_intervention()
        if durable:
            await durable.tool_finalized(call_id, response)
        return response
    finally:
        if durable:
            durable.active_call_id = previous_call_id
        agent.loop_data.current_tool = None
