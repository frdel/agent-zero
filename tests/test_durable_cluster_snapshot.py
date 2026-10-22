"""A UI host reads another worker's committed chat without executable shadows."""
import asyncio
import copy

from agent import AgentContext, UserMessage
from helpers.durable import runtime
from helpers.state_snapshot import StateRequestV1, build_snapshot_from_request, validate_snapshot_schema_v1
from test_durable_cluster import nodes, rig


def test_shared_snapshot_follows_remote_results_updates_resets_and_genesis(nodes, monkeypatch):
    context = nodes.rig.context
    context.name = "Remote conversation"
    task = nodes.second.admit_from_context(context, UserMessage("Remote request", id="remote-ui-input"))
    assert task.result_sync(timeout=10) == "Done"
    run, = nodes.second.sync("list_runs")
    empty = copy.deepcopy(run["checkpoint"]["context"])
    empty.update(id="shared-draft", name="Unstarted shared draft")
    empty["log"]["logs"] = []
    empty["agent_profile"] = "snapshot-profile"
    nodes.second.sync("put_projection", "chat:shared-draft", empty, 0)
    from helpers.task_scheduler import PlannedTask, TaskPlan
    scheduled = PlannedTask(uuid="shared-draft", name="Shared task", prompt="Do work",
                            system_prompt="System", plan=TaskPlan(todo=[]))
    nodes.second.sync("put_projection", "scheduler:tasks", {"tasks": [scheduled.model_dump(mode="json")]}, 0)
    with monkeypatch.context() as ui:
        registry = dict(AgentContext._contexts)
        def forbid(*args, **kwargs):
            raise AssertionError("Snapshot constructed, selected, or inspected an executable context")
        ui.setattr(AgentContext, "__init__", forbid)
        ui.setattr(AgentContext, "get", forbid)
        ui.setattr(AgentContext, "all", forbid)
        ui.setattr(AgentContext, "use", forbid)
        ui.setattr("helpers.extension.call_extensions_sync", forbid)
        ui.setattr("helpers.extension.call_extensions_async", forbid)
        ui.setattr(runtime, "_service", nodes.first)
        ui.setattr("helpers.state_snapshot._get_agent_profile_labels", lambda: {"snapshot-profile": "Snapshot Profile"})
        def snapshot(context_id=context.id, cursor=0, collections=True):
            result = asyncio.run(build_snapshot_from_request(
                request=StateRequestV1(context_id, cursor, 0, "UTC"), include_collections=collections))
            validate_snapshot_schema_v1(result)
            assert AgentContext._contexts == registry
            return result
        first = snapshot()
        assert first["context"] == context.id and not first["deselect_chat"]
        assert any(item["type"] == "response" and "Done" in item["content"] for item in first["logs"])
        assert {item["id"] for item in first["contexts"]} == {context.id}
        shared_task, = first["tasks"]
        assert shared_task["id"] == "shared-draft" and shared_task["task_name"] == "Shared task"
        assert shared_task["agent_profile_label"] == "Snapshot Profile" and shared_task["plan"]["todo"] == []
        assert first["log_progress"] == "Complete" and not first["log_progress_active"]
        assert snapshot(cursor=first["log_version"])["logs"] == []
        # Another committed checkpoint updates an existing log item without adding
        # an item. A log-count cursor would silently miss this change.
        data = copy.deepcopy(run["checkpoint"])
        admitted = nodes.second.sync("admit", context.id, "ui-followup", {"message": "Followup"}, data)
        assert nodes.second.sync("claim", admitted["run_id"])
        response = next(item for item in data["context"]["log"]["logs"] if item["type"] == "response")
        response["content"] = "Remote saved update"
        nodes.second.sync("transition", admitted["run_id"], "iteration_ready", checkpoint=data)
        second = snapshot(cursor=first["log_version"], collections=False)
        assert second["contexts"] is None and second["tasks"] is None
        assert second["log_guid"] != first["log_guid"]
        assert any(item["content"] == "Remote saved update" for item in second["logs"])
        before_guid = second["log_guid"]
        response["content"] = "Another committed edit"
        nodes.second.sync("transition", admitted["run_id"], "iteration_ready", checkpoint=data)
        third = snapshot(cursor=second["log_version"])
        assert third["log_guid"] == before_guid and third["log_version"] > second["log_version"]
        assert any(item["content"] == "Another committed edit" for item in third["logs"])
        nodes.first.sync("control", context.id, "reset")
        reset = snapshot(cursor=third["log_version"])
        assert reset["context"] == context.id and reset["logs"] == []
        assert reset["log_guid"] != third["log_guid"] and reset["log_progress"] == "Waiting for input"
        selected_draft = snapshot("shared-draft")
        assert selected_draft["context"] == "shared-draft" and selected_draft["logs"] == []
        nodes.first.sync("control", context.id, "delete")
        assert snapshot()["deselect_chat"]
        assert snapshot()["contexts"] == []
        assert [item["id"] for item in snapshot()["tasks"]] == ["shared-draft"]
