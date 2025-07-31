from python.helpers.tool import Tool, Response
from python.helpers.humanlayer_client import HumanLayerClient


class HumanLayerApproval(Tool):
    """
    HumanLayer Approval Tool for Agent Zero.
    Implements human-in-the-loop approval workflows using HumanLayer's @require_approval() functionality.
    Blocks operations until human approval is received through configured contact channels.
    """

    async def execute(self, **kwargs) -> Response:
        """
        Execute approval request workflow.
        
        Expected args:
        - operation: Description of the operation requiring approval
        - context: Additional context for the human to make informed decision
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
            operation = self.args.get("operation", "Unknown operation")
            context = self.args.get("context", "")
            timeout = int(self.args.get("timeout", client.get_timeout()))
            contact_channel_override = self.args.get("contact_channel")
            
            # Get contact channel configuration
            try:
                contact_channel = client.get_contact_channel(contact_channel_override)
            except Exception as e:
                return Response(
                    message=f"Contact channel configuration error: {str(e)}",
                    break_loop=False
                )
            
            # Create approval function dynamically using HumanLayer's require_approval decorator
            @hl.require_approval(
                contact_channel=contact_channel,
                timeout_seconds=timeout
            )
            async def approve_operation():
                return f"Operation approved: {operation}"
            
            # Request approval from human
            try:
                result = await approve_operation()
                
                # HumanLayer returns strings for both success and errors
                # Need to parse the response to determine outcome
                if isinstance(result, str):
                    if "Error" in result or "error" in result:
                        return Response(
                            message=f"Approval failed: {result}",
                            break_loop=False
                        )
                    elif "denied" in result.lower() or "rejected" in result.lower():
                        return Response(
                            message=f"Operation denied by human: {result}",
                            break_loop=False
                        )
                    else:
                        # Success case
                        return Response(
                            message=f"✅ {result}",
                            break_loop=False
                        )
                else:
                    # Unexpected response type
                    return Response(
                        message=f"Unexpected approval response: {result}",
                        break_loop=False
                    )
                    
            except Exception as e:
                # Handle timeouts and other exceptions
                error_str = str(e).lower()
                if "timeout" in error_str:
                    return Response(
                        message=f"⏱️ Approval request timed out after {timeout} seconds. Operation not approved.",
                        break_loop=False
                    )
                elif "denied" in error_str or "rejected" in error_str:
                    return Response(
                        message=f"❌ Operation denied by human: {str(e)}",
                        break_loop=False
                    )
                else:
                    # Other errors
                    return Response(
                        message=f"Approval system error: {str(e)}",
                        break_loop=False
                    )
                    
        except Exception as e:
            # Handle client initialization and other critical errors
            return Response(
                message=f"HumanLayer approval system error: {str(e)}",
                break_loop=False
            )

    def get_log_object(self):
        """
        Custom logging for approval requests.
        Uses Agent Zero's logging system with security icon.
        """
        return self.agent.context.log.log(
            type="humanlayer",
            heading=f"icon://security {self.agent.agent_name}: Requesting Human Approval",
            content="",
            kvps=self.args
        )

    async def before_execution(self, **kwargs):
        """
        Override before_execution to provide custom logging.
        Shows approval request details clearly.
        """
        from python.helpers.print_style import PrintStyle
        
        PrintStyle(font_color="#1B4F72", padding=True, background_color="white", bold=True).print(
            f"{self.agent.agent_name}: 🔐 Requesting Human Approval"
        )
        
        self.log = self.get_log_object()
        
        # Display approval request details
        if self.args and isinstance(self.args, dict):
            PrintStyle(font_color="#D35400", bold=True).print("⚠️  APPROVAL REQUIRED")
            
            for key, value in self.args.items():
                PrintStyle(font_color="#85C1E9", bold=True).stream(f"{self.nice_key(key)}: ")
                PrintStyle(font_color="#85C1E9", padding=isinstance(value, str) and "\n" in value).stream(value)
                PrintStyle().print()
            
            PrintStyle(font_color="#8E44AD", bold=True).print("Waiting for human response...")

    async def after_execution(self, response: Response, **kwargs):
        """
        Override after_execution to provide custom logging for approval results.
        """
        from python.helpers.print_style import PrintStyle
        from python.helpers.strings import sanitize_string
        
        # Add result to agent history
        text = sanitize_string(response.message.strip())
        self.agent.hist_add_tool_result(self.name, text)
        
        # Custom styling based on approval result
        if "✅" in response.message or "approved" in response.message.lower():
            PrintStyle(font_color="#27AE60", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: ✅ Approval Granted"
            )
            PrintStyle(font_color="#27AE60").print(text)
        elif "❌" in response.message or "denied" in response.message.lower():
            PrintStyle(font_color="#E74C3C", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: ❌ Approval Denied"
            )
            PrintStyle(font_color="#E74C3C").print(text)
        elif "⏱️" in response.message or "timeout" in response.message.lower():
            PrintStyle(font_color="#F39C12", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: ⏱️ Approval Timeout"
            )
            PrintStyle(font_color="#F39C12").print(text)
        else:
            # Default styling
            PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: Response from tool '{self.name}'"
            )
            PrintStyle(font_color="#85C1E9").print(text)
        
        self.log.update(content=text)