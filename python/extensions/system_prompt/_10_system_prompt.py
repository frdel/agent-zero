from datetime import datetime
from typing import Any, Optional
from python.helpers.extension import Extension
from python.helpers.mcp_handler import MCPConfig
from python.helpers.secrets import SecretsManager
from agent import Agent, LoopData
from python.helpers.localization import Localization


class SystemPrompt(Extension):

    async def execute(self, system_prompt: list[str] = [], loop_data: LoopData = LoopData(), **kwargs: Any):
        # append main system prompt and tools
        main = get_main_prompt(self.agent)
        tools = get_tools_prompt(self.agent)
        mcp_tools = get_mcp_tools_prompt(self.agent)
        secrets_prompt = get_secrets_prompt(self.agent)

        system_prompt.append(main)
        system_prompt.append(tools)
        if mcp_tools:
            system_prompt.append(mcp_tools)
        if secrets_prompt:
            system_prompt.append(secrets_prompt)


def get_main_prompt(agent: Agent):
    return agent.read_prompt("agent.system.main.md")


def get_tools_prompt(agent: Agent):
    prompt = agent.read_prompt("agent.system.tools.md")
    if agent.config.chat_model.vision:
        prompt += '\n' + agent.read_prompt("agent.system.tools_vision.md")
    return prompt


def get_mcp_tools_prompt(agent: Agent):
    mcp_config = MCPConfig.get_instance()
    if mcp_config.servers:
        pre_progress = agent.context.log.progress
        agent.context.log.set_progress("Collecting MCP tools") # MCP might be initializing, better inform via progress bar
        tools = MCPConfig.get_instance().get_tools_prompt()
        agent.context.log.set_progress(pre_progress) # return original progress
        return tools
    return ""


def get_secrets_prompt(agent: Agent):
    secrets_manager = SecretsManager.get_instance()
    keys = secrets_manager.get_keys()
    if not keys:
        return ""
    
    keys_list = ", ".join([f"§§{key}§§" for key in keys])
    return f"""# Available Secret Placeholders

You have access to the following secret placeholders that will be replaced with actual values during tool execution:
{keys_list}

**Important Guidelines:**
- Use the exact placeholder format: §§KEY_NAME§§ (double section sign markers)
- Secret values may contain special characters that need escaping in JSON strings
- When using secrets in JSON, properly escape quotes, backslashes, and newlines
- Placeholders work in all tool arguments (code, commands, API calls, etc.)
- Examples: §§DATABASE_PASSWORD§§, §§API_TOKEN§§, §§SSH_KEY§§
- Never expose actual secret values in your responses - only use placeholders
- Tool execution will fail with a RepairableException if a placeholder is not found in the secrets store"""
        
