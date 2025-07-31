from typing import Any
from python.helpers.extension import Extension
from agent import Agent, LoopData


class HumanLayerPrompts(Extension):
    """
    HumanLayer Prompts Extension for Agent Zero.
    Conditionally loads HumanLayer tool prompts based on configuration.
    Only includes HumanLayer tools when enabled and properly configured.
    """

    async def execute(self, system_prompt: list[str] = [], loop_data: LoopData = LoopData(), **kwargs: Any):
        """
        Conditionally append HumanLayer tool prompts to system prompt.
        Only loads prompts when HumanLayer is enabled in agent configuration.
        """
        # Check if HumanLayer is enabled in agent configuration
        if not self.agent or not self.agent.config.additional.get("humanlayer_enabled", False):
            return  # HumanLayer not enabled, skip loading tools
        
        try:
            # Load HumanLayer tool prompts
            approval_prompt = self.agent.read_prompt("agent.system.tool.humanlayer_approval.md")
            consultation_prompt = self.agent.read_prompt("agent.system.tool.humanlayer_consultation.md")
            contact_prompt = self.agent.read_prompt("agent.system.tool.humanlayer_contact.md")
            
            # Append to system prompt list
            system_prompt.extend([approval_prompt, consultation_prompt, contact_prompt])
            
        except Exception as e:
            # Graceful degradation - log warning but don't break system
            if hasattr(self.agent, 'context') and hasattr(self.agent.context, 'log'):
                self.agent.context.log.log(
                    type="warning",
                    heading="HumanLayer Extension Warning",
                    content=f"Could not load HumanLayer tool prompts: {str(e)}",
                    kvps={}
                )
            else:
                # Fallback logging if context not available
                print(f"Warning: Could not load HumanLayer prompts: {str(e)}")