from helpers.errors import HandledException
from helpers.extension import Extension
from helpers.settings import get_settings


STATE_KEY = "_unusable_response_failures"


class StopUnusableResponseLoop(Extension):
    def execute(self, data: dict | None = None, **kwargs):
        if not self.agent or not isinstance(data, dict):
            return

        call_kwargs = data.get("kwargs")
        message = call_kwargs.get("message") if isinstance(call_kwargs, dict) else None
        call_args = data.get("args")
        if message is None and isinstance(call_args, tuple) and len(call_args) > 1:
            message = call_args[1]

        if not isinstance(message, str):
            return
        if message not in {
            self.agent.read_prompt("fw.msg_misformat.md"),
            self.agent.read_prompt("fw.msg_repeat.md"),
            self.agent.read_prompt("fw.msg_empty_response.md"),
            self.agent.read_prompt("fw.msg_reasoning_only.md"),
            self.agent.read_prompt("fw.msg_thoughts_fallback.md"),
            self.agent.read_prompt("fw.msg_output_limit.md"),
        }:
            return

        loop_data = getattr(self.agent, "loop_data", None)
        state = getattr(loop_data, "params_persistent", None)
        iteration = getattr(loop_data, "iteration", None)
        if not isinstance(state, dict) or not isinstance(iteration, int):
            return

        previous = state.get(STATE_KEY, {})
        if not isinstance(previous, dict):
            previous = {}
        previous_iteration = previous.get("iteration")
        if previous_iteration == iteration:
            return

        count = (
            previous.get("count", 0) + 1
            if previous_iteration == iteration - 1
            else 1
        )
        state[STATE_KEY] = {"iteration": iteration, "count": count}
        limit = get_settings()["max_consecutive_unusable_responses"]
        if count < limit:
            return

        stop_message = self.agent.read_prompt(
            "fw.msg_unusable_response_limit.md", limit=limit
        )
        self.agent.context.log.log(type="warning", content=stop_message)
        data["exception"] = HandledException(stop_message)
