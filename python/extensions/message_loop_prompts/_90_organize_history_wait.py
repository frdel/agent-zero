from python.helpers.extension import Extension
from agent import LoopData
from python.extensions.message_loop_end._10_organize_history import DATA_NAME_TASK
import asyncio


class OrganizeHistoryWait(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):

        # sync action only required if the history is too large, otherwise leave it in background
        while self.agent.history.is_over_limit():
            # get task
            task = self.agent.get_data(DATA_NAME_TASK)

            # Check if the task is already done
            if task:
                if not task.done():
                    self.log()

                # Wait for the task to complete
                await task

                # Clear the coroutine data after it's done
                self.agent.set_data(DATA_NAME_TASK, None)
            else:
                # no task running, start and wait
                self.log()
                await self.agent.history.compress()

    def log(self):
        if not hasattr(self, 'log_item') or not self.log_item:
            self.log_item = self.agent.context.log.log(
                type="util", heading="Waiting for history to be compressed..."
            )
