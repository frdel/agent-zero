from datetime import datetime
from python.helpers.extension import Extension
from agent import Agent, LoopData


class SystemPrompt(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # collect and concatenate main prompts
        main = concat_main_prompts(self.agent)
        # collect and concatenate tool instructions
        tools = concat_tool_prompts(self.agent)
        # append to system message
        loop_data.system.append(main)
        loop_data.system.append(tools)


def concat_main_prompts(agent: Agent):
    # variables for prompts
    vars = {
        "date_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agent_name": agent.agent_name,
    }

    # prompt files
    mains = agent.read_prompts("agent.system.main.*.md", **vars)
    mains = "\n\n".join(mains)
    return mains


def concat_tool_prompts(agent: Agent):
    # prompt files
    tools = agent.read_prompts("agent.system.tool.*.md")
    tools = "\n\n".join(tools)
    # tools template
    sys = agent.read_prompt("agent.system.tools.md", tools=tools)
    return sys
