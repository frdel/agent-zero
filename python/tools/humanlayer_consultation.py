from python.helpers.tool import Tool, Response
from python.helpers.humanlayer_client import HumanLayerClient


class HumanLayerConsultation(Tool):
    """
    HumanLayer Consultation Tool for Agent Zero.
    Implements human-as-tool functionality for asking humans questions and getting contextual responses.
    Enables agents to seek human input for complex decisions and domain expertise.
    """

    async def execute(self, **kwargs) -> Response:
        """
        Execute human consultation workflow.
        
        Expected args:
        - question: The question to ask the human
        - context: Additional context to help human provide informed response
        - timeout: Optional timeout in seconds (defaults to config setting)
        - contact_channel: Optional override for contact channel type
        """
        # Standard Agent Zero pattern: check for intervention
        await self.agent.handle_intervention()
        
        # Check if HumanLayer is enabled
        if not self.agent.config.additional.get("humanlayer_enabled", False):
            return Response(
                message="HumanLayer not enabled. Enable in agent configuration by setting humanlayer_enabled=True.",
                break_loop=False
            )
        
        try:
            # Initialize HumanLayer client with Agent Zero config
            client = HumanLayerClient(self.agent.config.additional)
            
            # Validate configuration before proceeding
            is_valid, errors = client.validate_configuration()
            if not is_valid:
                error_msg = "HumanLayer configuration invalid:\n" + "\n".join(f"- {error}" for error in errors)
                return Response(message=error_msg, break_loop=False)
            
            # Get HumanLayer client instance
            hl = await client.get_client()
            
            # Extract tool arguments
            question = self.args.get("question", "")
            context = self.args.get("context", "")
            timeout = int(self.args.get("timeout", client.get_timeout()))
            contact_channel_override = self.args.get("contact_channel")
            
            if not question.strip():
                return Response(
                    message="No question provided. Please specify a question in the 'question' argument.",
                    break_loop=False
                )
            
            # Get contact channel configuration
            try:
                contact_channel = client.get_contact_channel(contact_channel_override)
            except Exception as e:
                return Response(
                    message=f"Contact channel configuration error: {str(e)}",
                    break_loop=False
                )
            
            # Create human consultation tool
            try:
                human_tool = hl.human_as_tool(
                    contact_channel=contact_channel,
                    timeout_seconds=timeout
                )
                
                # Create consultation prompt with context
                consultation_prompt = f"Question: {question}"
                if context.strip():
                    consultation_prompt += f"\n\nContext: {context}"
                
                # Request human response
                try:
                    response = await human_tool(consultation_prompt)
                    
                    if response:
                        return Response(
                            message=f"💬 Human response: {response}",
                            break_loop=False
                        )
                    else:
                        return Response(
                            message="❓ Human provided empty response or did not respond.",
                            break_loop=False
                        )
                        
                except Exception as e:
                    # Handle timeouts and other exceptions
                    error_str = str(e).lower()
                    if "timeout" in error_str:
                        return Response(
                            message=f"⏱️ Human consultation timed out after {timeout} seconds. Proceeding with available information.",
                            break_loop=False
                        )
                    else:
                        return Response(
                            message=f"Consultation error: {str(e)}",
                            break_loop=False
                        )
                        
            except Exception as e:
                return Response(
                    message=f"Failed to create human consultation tool: {str(e)}",
                    break_loop=False
                )
                    
        except Exception as e:
            # Handle client initialization and other critical errors
            return Response(
                message=f"HumanLayer consultation system error: {str(e)}",
                break_loop=False
            )

    def get_log_object(self):
        """
        Custom logging for consultation requests.
        Uses Agent Zero's logging system with question icon.
        """
        return self.agent.context.log.log(
            type="humanlayer",
            heading=f"icon://help {self.agent.agent_name}: Consulting Human Expert",
            content="",
            kvps=self.args
        )

    async def before_execution(self, **kwargs):
        """
        Override before_execution to provide custom logging.
        Shows consultation request details clearly.
        """
        from python.helpers.print_style import PrintStyle
        
        PrintStyle(font_color="#1B4F72", padding=True, background_color="white", bold=True).print(
            f"{self.agent.agent_name}: 🤔 Consulting Human Expert"
        )
        
        self.log = self.get_log_object()
        
        # Display consultation request details
        if self.args and isinstance(self.args, dict):
            PrintStyle(font_color="#3498DB", bold=True).print("💭 HUMAN CONSULTATION REQUESTED")
            
            for key, value in self.args.items():
                PrintStyle(font_color="#85C1E9", bold=True).stream(f"{self.nice_key(key)}: ")
                PrintStyle(font_color="#85C1E9", padding=isinstance(value, str) and "\n" in value).stream(value)
                PrintStyle().print()
            
            PrintStyle(font_color="#8E44AD", bold=True).print("Waiting for human response...")

    async def after_execution(self, response: Response, **kwargs):
        """
        Override after_execution to provide custom logging for consultation results.
        """
        from python.helpers.print_style import PrintStyle
        from python.helpers.strings import sanitize_string
        
        # Add result to agent history
        text = sanitize_string(response.message.strip())
        self.agent.hist_add_tool_result(self.name, text)
        
        # Custom styling based on consultation result
        if "💬" in response.message:
            PrintStyle(font_color="#27AE60", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: 💬 Human Response Received"
            )
            PrintStyle(font_color="#27AE60").print(text)
        elif "❓" in response.message:
            PrintStyle(font_color="#F39C12", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: ❓ No Response"
            )
            PrintStyle(font_color="#F39C12").print(text)
        elif "⏱️" in response.message or "timeout" in response.message.lower():
            PrintStyle(font_color="#F39C12", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: ⏱️ Consultation Timeout"
            )
            PrintStyle(font_color="#F39C12").print(text)
        else:
            # Default styling for errors
            PrintStyle(font_color="#E74C3C", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: ❗ Consultation Error"
            )
            PrintStyle(font_color="#E74C3C").print(text)
        
        self.log.update(content=text)