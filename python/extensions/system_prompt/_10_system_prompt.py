from datetime import datetime, timezone
from python.helpers.extension import Extension
from agent import Agent, LoopData
from python.helpers.localization import Localization


class SystemPrompt(Extension):

    async def execute(self, system_prompt: list[str]=[], loop_data: LoopData = LoopData(), **kwargs):
        # append main system prompt and tools
        main = get_main_prompt(self.agent)
        tools = get_tools_prompt(self.agent)
        system_prompt.append(main)
        system_prompt.append(tools)


def get_main_prompt(agent: Agent):
    return agent.read_prompt("agent.system.main.md")


def get_tools_prompt(agent: Agent):
    prompt = agent.read_prompt("agent.system.tools.md")
    if agent.config.chat_model.vision:
        prompt += '\n' + agent.read_prompt("agent.system.tools_vision.md")
    return prompt