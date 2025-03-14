import asyncio
from datetime import datetime
import json
from python.helpers.extension import Extension
from agent import Agent, LoopData
from python.helpers import dirty_json, files, memory
from python.helpers.log import LogItem
from python.extensions.message_loop_prompts import _20_behaviour_prompt



class BehaviourUpdate(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        log_item = self.agent.context.log.log(
            type="util",
            heading="Updating behaviour",
        )
        asyncio.create_task(self.update_rules(self.agent, loop_data, log_item))

    async def update_rules(self, agent: Agent, loop_data: LoopData, log_item: LogItem, **kwargs):
        adjustments = await self.get_adjustments(agent, loop_data, log_item)
        if adjustments:
            await self.merge_rules(agent, adjustments, loop_data, log_item)
    
    async def get_adjustments(self, agent: Agent, loop_data: LoopData, log_item: LogItem, **kwargs) -> list[str] | None:

        # get system message and chat history for util llm
        system = self.agent.read_prompt("behaviour.search.sys.md")
        msgs_text = self.agent.concat_messages(self.agent.history)

        # log query streamed by LLM
        def log_callback(content):
            log_item.stream(content=content)

        # call util llm to find solutions in history
        adjustments_json = await self.agent.call_utility_llm(
            system=system,
            msg=msgs_text,
            callback=log_callback,
        )

        adjustments = dirty_json.DirtyJson.parse_string(adjustments_json)

        if adjustments:
            log_item.update(adjustments=adjustments)
            return adjustments # type: ignore # for now let's assume the model gets it right and outputs an array
        else:
            log_item.update(heading="No updates to behaviour")
            return None

    async def merge_rules(self, agent: Agent, adjustments: list[str], loop_data: LoopData, log_item: LogItem, **kwargs):
        # get system message and current ruleset
        system = self.agent.read_prompt("behaviour.merge.sys.md")
        current_rules = _20_behaviour_prompt.read_rules(agent)
            
        # log query streamed by LLM
        def log_callback(content):
            log_item.stream(ruleset=content)

        msg = self.agent.read_prompt("behaviour.merge.msg.md", current_rules=current_rules, adjustments=json.dumps(adjustments))

        # call util llm to find solutions in history
        adjustments_merge = await self.agent.call_utility_llm(
            system=system,
            msg=msg,
            callback=log_callback,
        )

        # update rules file
        rules_file = _20_behaviour_prompt.get_custom_rules_file(agent)
        files.write_file(rules_file, adjustments_merge)
        log_item.update(heading="Behaviour updated")