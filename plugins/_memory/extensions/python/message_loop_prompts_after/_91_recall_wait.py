from helpers.extension import Extension
from agent import LoopData
from plugins._memory.extensions.python.message_loop_prompts_after._50_recall_memories import (
    DATA_NAME_ITER as DATA_NAME_ITER_MEMORIES,
    DATA_NAME_RESULT as DATA_NAME_RESULT_MEMORIES,
    DATA_NAME_RESULT_SCOPE as DATA_NAME_RESULT_SCOPE_MEMORIES,
    DATA_NAME_TASK as DATA_NAME_TASK_MEMORIES,
    apply_recall_result,
    get_recall_scope,
)
from helpers import plugins

class RecallWait(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):

        if not self.agent:
            return

        set = plugins.get_plugin_config("_memory", self.agent)
        if not set:
            return None

        task = self.agent.get_data(DATA_NAME_TASK_MEMORIES)
        iter = self.agent.get_data(DATA_NAME_ITER_MEMORIES) or 0

        if task:

            # if memory recall is set to delayed mode, do not await on the iteration it was called
            if set["memory_recall_delayed"]:
                if iter == loop_data.iteration and not task.done():
                    # insert info about delayed memory to extras
                    delay_text = self.agent.read_prompt("memory.recall_delay_msg.md")
                    loop_data.extras_temporary["memory_recall_delayed"] = delay_text
                    return

            # otherwise await the task
            result = await task
            if self.agent.get_data(DATA_NAME_RESULT_SCOPE_MEMORIES) == get_recall_scope(
                self.agent
            ):
                apply_recall_result(loop_data, result)
            else:
                apply_recall_result(loop_data, {})
            self.agent.set_data(DATA_NAME_RESULT_MEMORIES, None)
            self.agent.set_data(DATA_NAME_RESULT_SCOPE_MEMORIES, None)
            from helpers.durable.background import TaskHandle
            if type(task) is TaskHandle:
                self.agent.set_data(DATA_NAME_TASK_MEMORIES, None)
