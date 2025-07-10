from python.helpers.extension import Extension
from python.helpers.auto_format import auto_format_response, is_valid_agent_response, detect_misformat
from agent import LoopData


class AutoformatToolRequest(Extension):
    """
    Auto-formatting extension that detects and corrects malformed tool requests
    by creating a formatted version that can be used by the agent.
    """
    
    async def execute(self, tool_request_data=None, loop_data: LoopData = LoopData(), **kwargs):
        """
        Detect malformed tool requests and attempt to auto-format them.
        This runs for every tool request processing.
        """
        if not tool_request_data:
            return
            
        try:
            # Only process if tool_request is None (meaning original parsing failed)
            if tool_request_data.tool_request is not None:
                return
                
            message = tool_request_data.message
            if not message:
                return
                
            # Check if the message is likely malformed
            if not detect_misformat(message):
                return
                
            self.agent.context.log.log(type="info", content="Detected potentially malformed tool request, attempting auto-correction")
            
            # Try to auto-format the response
            formatted_response = await self._auto_format_response(message)
            
            if formatted_response:
                # Try to parse the formatted response
                from python.helpers import extract_tools
                parsed = extract_tools.json_parse_dirty(formatted_response)
                
                if parsed:
                    # Update the tool request data object
                    tool_request_data.tool_request = parsed
                    
                    self.agent.context.log.log(type="info", content="Successfully auto-formatted tool request")
                else:
                    self.agent.context.log.log(type="warning", content="Auto-formatting produced unparseable result")
            else:
                self.agent.context.log.log(type="warning", content="Auto-formatting failed - tool request remains malformed")

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