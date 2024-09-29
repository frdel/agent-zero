from python.helpers.extension import Extension
from agent import Agent, LoopData


class RecallMemories(Extension):

    INTERVAL = 3
    HISTORY = 5
    RESULTS = 3
    THRESHOLD = 0.1

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # collect and concatenate tool instructions
        sys = concat_tool_prompts(self.agent)
        # append to system message
        loop_data.system.append(sys)


def concat_tool_prompts(agent: Agent):
    tools = agent.read_prompts("agent.system.tool.*.md")
    tools = "\n\n".join(tools)
    sys = agent.read_prompt("agent.system.tools.md", tools=tools)
    return sys
