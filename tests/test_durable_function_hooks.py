"""Recovery must not repeat implicit function wrappers outside phase fences."""
import json

import pytest

from helpers import extension
from helpers.durable import review
from helpers.llm_result import LLMResult
from test_durable_runtime import rig, admitted


@pytest.mark.parametrize("point,phase", [
    ("_functions/agent/Agent/monologue/start", "iteration_ready"),
    ("_functions/agent/Agent/monologue/end", "iteration_ready"),
    ("_functions/agent/Agent/call_chat_model_turn/end", "model_result"),
])
def test_recovery_holds_before_an_unaudited_function_wrapper(rig, monkeypatch, point, phase):
    hits = []

    class ExternalHook(extension.Extension):
        async def execute(self, **kwargs):
            hits.append("external effect")

    monkeypatch.setattr(extension, "_get_extension_classes", lambda name, **kwargs: [ExternalHook] if name == point else [])
    result = LLMResult.from_chat(response=json.dumps({"tool_name": "response", "tool_args": {"text": "Recorded"}}))
    run = admitted(rig, phase, result)
    assert review.resume_phase(rig.owner, rig.context, run) is None
    rig.owner.recover()
    from agent import AgentContext
    restored = AgentContext.get(rig.context.id)
    assert "not retried" in restored.task.result_sync(timeout=10)
    assert hits == [] and rig.requests == []
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "attention"
