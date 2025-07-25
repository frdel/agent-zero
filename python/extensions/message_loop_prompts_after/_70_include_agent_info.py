from python.helpers.extension import Extension
from agent import LoopData

class IncludeAgentInfo(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        
        # read prompt
        agent_info_prompt = self.agent.read_prompt(
            "agent.extras.agent_info.md",
            number=self.agent.number,
            profile=self.agent.config.profile or "Default",
        )

        # add agent info to the prompt
        loop_data.extras_temporary["agent_info"] = agent_info_prompt
