from helpers.extension import Extension
from agent import Agent, LoopData
from helpers import files

# Direct import - this extension lives inside the memory plugin
from plugins._memory.helpers import memory


class BehaviourPrompt(Extension):

    async def execute(self, system_prompt: list[str]=[], loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        prompt = read_rules(self.agent)
        system_prompt.insert(0, prompt)


def get_custom_rules_file(agent: Agent):
    return files.get_abs_path(memory.get_memory_subdir_abs(agent), "behaviour.md")


def read_rules(agent: Agent):
    rules_file = get_custom_rules_file(agent)
    if files.exists(rules_file):
        rules = files.read_file(rules_file)
        return agent.read_prompt("agent.system.behaviour.md", rules=rules)
    else:
        rules = agent.read_prompt("agent.system.behaviour_default.md")
        return agent.read_prompt("agent.system.behaviour.md", rules=rules)
