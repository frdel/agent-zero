from python.helpers import persist_chat, tokens
from python.helpers.extension import Extension
from agent import LoopData
import asyncio
from python.helpers.log import LogItem
from python.helpers import log
import math


class LogFromStream(Extension):

    async def execute(
        self,
        loop_data: LoopData = LoopData(),
        text: str = "",
        parsed: dict = {},
        **kwargs,
    ):

        heading = f"{self.agent.agent_name}: Generating..."
        if "headline" in parsed:
            heading = f"{self.agent.agent_name}: {parsed['headline']}"
        elif "thoughts" in parsed:
            # thought length indicator
            thoughts = "\n".join(parsed["thoughts"])
            length = math.ceil(len(thoughts) / 10) * 10
            heading = f"{self.agent.agent_name}: Thinking ({length})..."

        if "tool_name" in parsed:
            heading += f" ({parsed['tool_name']})"

        # create log message and store it in loop data temporary params
        if "log_item_generating" not in loop_data.params_temporary:
            loop_data.params_temporary["log_item_generating"] = (
                self.agent.context.log.log(
                    type="agent",
                    heading=heading,
                )
            )

        # update log message
        log_item = loop_data.params_temporary["log_item_generating"]

        # keep reasoning from previous logs in kvps
        kvps = {}
        if log_item.kvps is not None and "reasoning" in log_item.kvps:
            kvps["reasoning"] = log_item.kvps["reasoning"]
        kvps.update(parsed)

        # update the log item
        log_item.update(heading=heading, content=text, kvps=kvps)
