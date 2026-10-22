from helpers.extension import Extension
from agent import LoopData
from extensions.python.message_loop_end._10_organize_history import (
    DATA_NAME_TASK,
    compress_history,
)
from helpers.defer import DeferredTask, THREAD_BACKGROUND

MAX_SYNC_COMPRESSION_PASSES = 64


class OrganizeHistoryWait(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        from helpers.durable import background, history
        if background.enabled(self.agent):
            task = self.agent.get_data(DATA_NAME_TASK)
            if type(task) is background.TaskHandle:
                self.agent.context.log.set_progress("Compressing history...")
                await history.consume(self.agent, task)
                self.agent.set_data(DATA_NAME_TASK, None)
            passes = 0
            while self.agent.history.is_over_limit() and passes < MAX_SYNC_COMPRESSION_PASSES:
                task = history.enqueue(self.agent)
                if task is None:
                    break
                self.agent.set_data(DATA_NAME_TASK, task)
                compressed = await history.consume(self.agent, task)
                self.agent.set_data(DATA_NAME_TASK, None)
                if not compressed:
                    self._log_compression_stalled(self.agent.history.get_tokens(), self.agent.history.get_tokens())
                    break
                passes += 1
            return

        # sync action only required if the history is too large, otherwise leave it in background
        passes = 0
        while self.agent.history.is_over_limit():
            passes += 1
            before_tokens = self.agent.history.get_tokens()

            # get task
            task: DeferredTask | None = self.agent.get_data(DATA_NAME_TASK)

            # Check if the task is already done
            if task:
                if not task.is_ready():
                    self.agent.context.log.set_progress("Compressing history...")

                # Wait for the task to complete
                compressed = bool(await task.result())

                # Clear the coroutine data after it's done
                self.agent.set_data(DATA_NAME_TASK, None)
            else:
                # no task was running, start and wait
                self.agent.context.log.set_progress("Compressing history...")
                compressed = await compress_history(self.agent)

            after_tokens = self.agent.history.get_tokens()
            if not compressed or after_tokens >= before_tokens:
                self._log_compression_stalled(before_tokens, after_tokens)
                break

            if passes >= MAX_SYNC_COMPRESSION_PASSES:
                self._log_compression_stalled(
                    before_tokens, after_tokens, max_passes=True
                )
                break

    def _log_compression_stalled(
        self, before_tokens: int, after_tokens: int, max_passes: bool = False
    ) -> None:
        if not self.agent:
            return

        detail = (
            f"History compression stopped after {MAX_SYNC_COMPRESSION_PASSES} passes"
            if max_passes
            else "History compression could not reduce the prompt history further"
        )
        self.agent.context.log.log(
            type="warning",
            heading="History compression stalled",
            content=f"{detail}. Tokens before: {before_tokens}; after: {after_tokens}.",
        )
