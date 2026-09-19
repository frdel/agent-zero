from helpers import files
from helpers.tool import Tool, Response
from agent import Agent
from helpers.log import LogItem
from plugins._memory.helpers import memory


class UpdateBehaviour(Tool):

    async def execute(self, adjustments="", **kwargs):

        # stringify adjustments if needed
        if not isinstance(adjustments, str):
            adjustments = str(adjustments)

        await update_behaviour(self.agent, self.log, adjustments)
        return Response(
            message=self.agent.read_prompt("behaviour.updated.md"), break_loop=False
        )


async def update_behaviour(agent: Agent, log_item: LogItem, adjustments: str):

    # get system message and current ruleset
    system = agent.read_prompt("behaviour.merge.sys.md")
    current_rules = read_rules(agent)

    # log query streamed by LLM
    async def log_callback(content):
        log_item.stream(ruleset=content)

    msg = agent.read_prompt(
        "behaviour.merge.msg.md", current_rules=current_rules, adjustments=adjustments
    )

    # call util llm to find solutions in history
    adjustments_merge = await agent.call_utility_model(
        system=system,
        message=msg,
        callback=log_callback,
    )
    adjustments_merge = normalize_ruleset(adjustments_merge)

    # update rules file
    rules_file = get_custom_rules_file(agent)
    files.write_file(rules_file, adjustments_merge)
    log_item.update(ruleset=adjustments_merge, result="Behaviour updated")


def get_custom_rules_file(agent: Agent):
    return files.get_abs_path(memory.get_memory_subdir_abs(agent), "behaviour.md")


def read_rules(agent: Agent):
    rules_file = get_custom_rules_file(agent)
    if files.exists(rules_file):
        return agent.read_prompt(rules_file)
    else:
        return agent.read_prompt("agent.system.behaviour_default.md")


def normalize_ruleset(ruleset: str):
    text = str(ruleset or "").strip()

    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("!!!", "")
    text = text.replace(".## ", ".\n## ")

    normalized_lines = []
    seen_structural_lines = set()
    previous_blank = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            if normalized_lines and not previous_blank:
                normalized_lines.append("")
            previous_blank = True
            continue

        if stripped.startswith("# ") and not stripped.startswith("## "):
            stripped = "#" + stripped
            line = stripped

        dedupe_key = stripped.casefold()
        if stripped.startswith(("## ", "* ")) and dedupe_key in seen_structural_lines:
            continue
        if stripped.startswith(("## ", "* ")):
            seen_structural_lines.add(dedupe_key)

        normalized_lines.append(line)
        previous_blank = False

    return "\n".join(normalized_lines).strip() + "\n"
