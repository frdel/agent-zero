from datetime import datetime
from python.helpers.extension import Extension
from agent import Agent, LoopData
from python.helpers import files, memory


class BehaviourPrompt(Extension):

    async def execute(self, system_prompt: list[str]=[], loop_data: LoopData = LoopData(), **kwargs):
        prompt = read_rules(self.agent)
        system_prompt.insert(0, prompt) #.append(prompt)

def get_custom_rules_file(agent: Agent):
    return memory.get_memory_subdir_abs(agent) + f"/behaviour.md"

def read_rules(agent: Agent):
    rules_file = get_custom_rules_file(agent)
    if files.exists(rules_file):
        rules = files.read_file(rules_file) # no includes and vars here, that could crash
        return agent.read_prompt("agent.system.behaviour.md", rules=rules)
    else:
        rules = agent.read_prompt("agent.system.behaviour_default.md")
        return agent.read_prompt("agent.system.behaviour.md", rules=rules)
  