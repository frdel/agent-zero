from python.helpers import persist_chat, tokens
from python.helpers.extension import Extension
from agent import LoopData
import asyncio
from python.helpers.log import LogItem
from python.helpers import log


class LogFromStream(Extension):

    async def execute(
        self,
        loop_data: LoopData = LoopData(),
        text: str = "",
        parsed: dict = {},
        **kwargs
    ):

        # create log message and store it in loop data temporary params
        if "log_item_generating" not in loop_data.params_temporary:
            loop_data.params_temporary["log_item_generating"] = self.agent.context.log.log(
                type="agent",
                heading=f"{self.agent.agent_name}: Generating",
            )

        # update log message
        log_item = loop_data.params_temporary["log_item_generating"]
        log_item.update(content=text, kvps=parsed)