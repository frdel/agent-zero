from datetime import datetime
from typing import Any, Optional
from python.helpers.extension import Extension
from python.helpers.mcp_handler import MCPConfig
from agent import Agent, LoopData
from python.helpers.localization import Localization


class SystemPrompt(Extension):

    async def execute(self, system_prompt: list[str] = [], loop_data: LoopData = LoopData(), **kwargs: Any):
        # append main system prompt and tools
        main = get_main_prompt(self.agent)
        tools = get_tools_prompt(self.agent)
        mcp_tools = get_mcp_tools_prompt(self.agent)

        system_prompt.append(main)
        system_prompt.append(tools)
        if mcp_tools:
            system_prompt.append(mcp_tools)


def get_main_prompt(agent: Agent):
    return agent.read_prompt("agent.system.main.md")


def get_tools_prompt(agent: Agent):
    prompt = agent.read_prompt("agent.system.tools.md")
    
    # Add mem0 tools documentation if enabled
    from python.helpers.settings import get_settings
    settings = get_settings()
    if settings.get("memory_backend") == "mem0" and settings.get("mem0_enabled", False):
        try:
            mem0_tools = agent.read_prompt("agent.system.tool.memory.mem0.md")
            prompt += '\n\n' + mem0_tools
        except FileNotFoundError:
            pass  # Gracefully handle missing mem0 documentation
    
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
        
