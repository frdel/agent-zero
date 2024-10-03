from datetime import datetime
from python.helpers.extension import Extension
from agent import Agent, LoopData


class SystemPrompt(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # append main system prompt and tools
        main = get_main_prompt(self.agent)
        tools = get_tools_prompt(self.agent)
        loop_data.system.append(main)
        loop_data.system.append(tools)

def get_main_prompt(agent: Agent):
    return get_prompt("agent.system.main.md", agent)

def get_tools_prompt(agent: Agent):
    return get_prompt("agent.system.tools.md", agent)

def get_prompt(file: str, agent: Agent):
    # variables for system prompts
    # TODO: move variables to the end of chain
    # variables in system prompt would break prompt caching, better to add them to the last message in conversation
    vars = {
        "date_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agent_name": agent.agent_name,
    }
    return agent.read_prompt(file, **vars)