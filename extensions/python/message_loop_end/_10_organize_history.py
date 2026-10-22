from helpers.extension import Extension
from agent import LoopData
from helpers.defer import DeferredTask, THREAD_BACKGROUND
from helpers.history import clear_responses_provider_state

DATA_NAME_TASK = "_organize_history_task"


async def compress_history(agent) -> bool:
    compressed = bool(await agent.history.compress())
    if compressed:
        clear_responses_provider_state(agent)
    return compressed


class OrganizeHistory(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        from helpers.durable import background, history
        if background.enabled(self.agent):
            task = self.agent.get_data(DATA_NAME_TASK)
            if type(task) is background.TaskHandle:
                return
            self.agent.set_data(DATA_NAME_TASK, history.enqueue(self.agent))
            return

        # is there a running task? if yes, skip this round, the wait extension will double check the context size
        task: DeferredTask|None = self.agent.get_data(DATA_NAME_TASK)
        if task and not task.is_ready():
            return

        # start task
        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(compress_history, self.agent)
        # set to agent to be able to wait for it
        self.agent.set_data(DATA_NAME_TASK, task)
