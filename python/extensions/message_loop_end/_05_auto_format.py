from python.helpers.extension import Extension
from python.helpers.auto_format import auto_format_response, is_valid_agent_response, detect_misformat
from agent import LoopData


class AutoFormatResponse(Extension):
    """
    Auto-formatting extension that detects and corrects malformed responses
    by creating a formatted version that can be used by the agent.
    """
    
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """
        Detect malformed responses and attempt to provide auto-formatting guidance.
        This runs at the end of each message loop iteration.
        """
        try:
            # Check if we have a recent response that might be malformed
            if not hasattr(self.agent, 'last_raw_response'):
                return
                
            raw_response = getattr(self.agent, 'last_raw_response', '')
            if not raw_response:
                return
                
            # Check if the response is likely malformed
            if not detect_misformat(raw_response):
                return
                
            self.agent.context.log.log(type="info", content="Detected potentially malformed response, attempting auto-correction")
            
            # Try to auto-format the response
            formatted_response = await self._auto_format_response(raw_response)
            
            if formatted_response:
                # Store the corrected version for reference
                self.agent.set_data('auto_formatted_response', formatted_response)
                
                # Add a helpful message to the agent's context
                formatting_note = f"""
Note: The previous response was auto-formatted to proper JSON structure.
Original contained: {raw_response[:100]}...
Formatted version: {formatted_response[:100]}...

Please ensure future responses follow the exact JSON format:
{{"thoughts": ["reasoning"], "tool_name": "tool", "tool_args": {{"key": "value"}}}}
"""

                # Add as a temporary context for the agent using loop_data
                loop_data.extras_temporary["auto_format_note"] = formatting_note
                
                self.agent.context.log.log(type="info", content="Successfully auto-formatted response and provided guidance")
            else:
                self.agent.context.log.log(type="warning", content="Auto-formatting failed - response remains malformed")

        except Exception as e:
            self.agent.context.log.log(type="error", content=f"Auto-formatting extension error: {str(e)}")
    
    async def _auto_format_response(self, raw_response: str) -> str | None:
        """
        Use multiple strategies to auto-format a malformed response.
        """
        try:
            # Strategy 1: Try local auto-formatting utility
            local_formatted = auto_format_response(raw_response)
            if local_formatted and is_valid_agent_response(local_formatted):
                self.agent.context.log.log(type="info", content="Auto-formatted using local utility")
                return local_formatted

            # Strategy 2: Try model-based formatting
            model_formatted = await self._format_with_model(raw_response)
            if model_formatted and is_valid_agent_response(model_formatted):
                self.agent.context.log.log(type="info", content="Auto-formatted using utility model")
                return model_formatted

            # Strategy 3: Create a simple wrapper format
            simple_formatted = self._create_simple_format(raw_response)
            if simple_formatted:
                self.agent.context.log.log(type="info", content="Auto-formatted using simple wrapper")
                return simple_formatted
            
            return None
            
        except Exception as e:
            self.agent.context.log.log(type="error", content=f"Auto-formatting failed: {str(e)}")
            return None
    
    async def _format_with_model(self, response_text: str) -> str | None:
        """
        Use the utility model to format the malformed response.
        """
        try:
            # Load the auto-formatting prompt template with static instructions
            system_prompt = self.agent.read_prompt("fw.msg_autoformat.md")
            
            # The variable part goes in the user message
            message = f"Convert this malformed response to proper JSON format:\n\n{response_text}"
            
            # Call the utility model to perform the formatting
            formatted_response = await self.agent.call_utility_model(
                system=system_prompt,
                message=message
            )
            
            return formatted_response.strip() if formatted_response else None
            
        except Exception as e:
            self.agent.context.log.log(type="error", content=f"Model-based auto-formatting failed: {str(e)}")
            return None
    
    def _create_simple_format(self, response_text: str) -> str | None:
        """
        Create a simple JSON wrapper for the response as a fallback.
        """
        try:
            import json
            
            # Create a basic structure
            formatted = {
                "thoughts": ["Auto-formatted response due to malformed JSON"],
                "tool_name": "response",
                "tool_args": {
                    "text": response_text.strip()
                }
            }
            
            return json.dumps(formatted, ensure_ascii=False)
            
        except Exception as e:
            self.agent.context.log.log(type="error", content=f"Simple formatting failed: {str(e)}")
            return None