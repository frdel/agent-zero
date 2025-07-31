from python.helpers.tool import Tool, Response
from python.helpers.humanlayer_client import HumanLayerClient


class HumanLayerContact(Tool):
    """
    HumanLayer Contact Management Tool for Agent Zero.
    Handles contact channel configuration, testing, and management.
    Supports multi-channel setup with Slack, Email, and other contact methods.
    """

    async def execute(self, **kwargs) -> Response:
        """
        Execute contact management operations.
        
        Expected args:
        - action: Operation to perform (test, configure, list, validate)
        - channel_type: Type of channel (slack, email, cli)
        - channel_config: Configuration details for the channel
        """
        # Standard Agent Zero pattern: check for intervention
        await self.agent.handle_intervention()
        
        # Check if HumanLayer is enabled
        if not self.agent.config.additional.get("humanlayer_enabled", False):
            return Response(
                message="HumanLayer not enabled. Enable in agent configuration by setting humanlayer_enabled=True.",
                break_loop=False
            )
        
        action = self.args.get("action", "validate").lower()
        
        try:
            # Initialize HumanLayer client with Agent Zero config
            client = HumanLayerClient(self.agent.config.additional)
            
            if action == "validate":
                return await self._validate_configuration(client)
            elif action == "test":
                return await self._test_channel(client)
            elif action == "list":
                return await self._list_channels(client)
            elif action == "configure":
                return await self._configure_channel(client)
            else:
                return Response(
                    message=f"Unknown action '{action}'. Available actions: validate, test, list, configure",
                    break_loop=False
                )
                
        except Exception as e:
            return Response(
                message=f"HumanLayer contact management error: {str(e)}",
                break_loop=False
            )

    async def _validate_configuration(self, client: HumanLayerClient) -> Response:
        """Validate current HumanLayer configuration."""
        is_valid, errors = client.validate_configuration()
        
        if is_valid:
            return Response(
                message="✅ HumanLayer configuration is valid and ready to use.",
                break_loop=False
            )
        else:
            error_msg = "❌ HumanLayer configuration issues found:\n"
            error_msg += "\n".join(f"• {error}" for error in errors)
            error_msg += "\n\nPlease fix these issues before using HumanLayer tools."
            return Response(message=error_msg, break_loop=False)

    async def _test_channel(self, client: HumanLayerClient) -> Response:
        """Test connectivity to configured contact channel."""
        try:
            channel_type_override = self.args.get("channel_type")
            contact_channel = client.get_contact_channel(channel_type_override)
            
            # Get HumanLayer client instance
            hl = await client.get_client()
            
            # Test with a simple approval request (short timeout)
            @hl.require_approval(
                contact_channel=contact_channel,
                timeout_seconds=10  # Short timeout for testing
            )
            async def test_connection():
                return "Test connection successful"
            
            # Attempt test (this will likely timeout, but validates channel config)
            try:
                result = await test_connection()
                return Response(
                    message="✅ Contact channel test successful. Channel is reachable.",
                    break_loop=False
                )
            except Exception as e:
                error_str = str(e).lower()
                if "timeout" in error_str:
                    return Response(
                        message="⚠️ Contact channel appears to be configured correctly (test timed out as expected), but verify human can receive messages.",
                        break_loop=False
                    )
                else:
                    return Response(
                        message=f"❌ Contact channel test failed: {str(e)}",
                        break_loop=False
                    )
                    
        except Exception as e:
            return Response(
                message=f"❌ Contact channel configuration error: {str(e)}",
                break_loop=False
            )

    async def _list_channels(self, client: HumanLayerClient) -> Response:
        """List all configured contact channels."""
        config = client.config
        channels_config = config.get("humanlayer_contact_channels", {})
        default_channel = config.get("humanlayer_default_contact_channel", "slack")
        
        if not channels_config:
            return Response(
                message="📋 No contact channels explicitly configured. Using default channel type with environment variables.",
                break_loop=False
            )
        
        message = "📋 Configured Contact Channels:\n\n"
        
        for channel_type, channel_config in channels_config.items():
            is_default = "🌟" if channel_type == default_channel else "  "
            message += f"{is_default} **{channel_type.upper()}**\n"
            
            if channel_type == "slack":
                channel_id = channel_config.get("channel_id", "Not configured")
                context = channel_config.get("context", "Not configured")
                message += f"   • Channel ID: {channel_id}\n"
                message += f"   • Context: {context}\n"
            elif channel_type == "email":
                address = channel_config.get("address", "Not configured")
                subject = channel_config.get("subject", "Agent Zero Approval Request")
                message += f"   • Address: {address}\n"
                message += f"   • Subject: {subject}\n"
            
            message += "\n"
        
        message += f"Default channel: **{default_channel}**"
        
        return Response(message=message, break_loop=False)

    async def _configure_channel(self, client: HumanLayerClient) -> Response:
        """Configure a new contact channel (demonstration only - would need persistence)."""
        channel_type = self.args.get("channel_type", "").lower()
        channel_config = self.args.get("channel_config", {})
        if not isinstance(channel_config, dict):
            channel_config = {}
        
        if not channel_type:
            return Response(
                message="❌ Please specify channel_type (slack, email) for configuration.",
                break_loop=False
            )
        
        if channel_type not in ["slack", "email"]:
            return Response(
                message="❌ Unsupported channel type. Supported types: slack, email",
                break_loop=False
            )
        
        # Validate channel configuration            
        if channel_type == "slack":
            if not channel_config.get("channel_id"):
                return Response(
                    message="❌ Slack configuration requires 'channel_id' field.",
                    break_loop=False
                )
        elif channel_type == "email":
            if not channel_config.get("address"):
                return Response(
                    message="❌ Email configuration requires 'address' field.",
                    break_loop=False
                )
        
        # Note: In a real implementation, this would persist the configuration
        # For now, we just validate and show what would be configured
        message = f"✅ Channel configuration validated for **{channel_type}**:\n\n"
        for key, value in channel_config.items():
            message += f"• {key}: {value}\n"
        
        message += "\n⚠️ Note: Configuration changes require restarting Agent Zero to take effect."
        message += "\nAdd this to your agent configuration:\n\n"
        message += f"```json\n"
        message += f'"humanlayer_contact_channels": {{\n'
        message += f'  "{channel_type}": {{\n'
        for key, value in channel_config.items():
            message += f'    "{key}": "{value}",\n'
        message += f'  }}\n'
        message += f'}}\n```'
        
        return Response(message=message, break_loop=False)

    def get_log_object(self):
        """
        Custom logging for contact management operations.
        """
        return self.agent.context.log.log(
            type="humanlayer",
            heading=f"icon://settings {self.agent.agent_name}: Managing Contact Channels",
            content="",
            kvps=self.args
        )

    async def before_execution(self, **kwargs):
        """
        Override before_execution to provide custom logging.
        """
        from python.helpers.print_style import PrintStyle
        
        action = self.args.get("action", "validate")
        PrintStyle(font_color="#1B4F72", padding=True, background_color="white", bold=True).print(
            f"{self.agent.agent_name}: ⚙️ Contact Management - {action.title()}"
        )
        
        self.log = self.get_log_object()
        
        if self.args and isinstance(self.args, dict):
            for key, value in self.args.items():
                PrintStyle(font_color="#85C1E9", bold=True).stream(f"{self.nice_key(key)}: ")
                PrintStyle(font_color="#85C1E9", padding=isinstance(value, str) and "\n" in value).stream(value)
                PrintStyle().print()

    async def after_execution(self, response: Response, **kwargs):
        """
        Override after_execution to provide custom logging.
        """
        from python.helpers.print_style import PrintStyle
        from python.helpers.strings import sanitize_string
        
        # Add result to agent history
        text = sanitize_string(response.message.strip())
        self.agent.hist_add_tool_result(self.name, text)
        
        # Custom styling based on result
        if "✅" in response.message:
            PrintStyle(font_color="#27AE60", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: ✅ Configuration Valid"
            )
            PrintStyle(font_color="#27AE60").print(text)
        elif "❌" in response.message:
            PrintStyle(font_color="#E74C3C", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: ❌ Configuration Issues"
            )
            PrintStyle(font_color="#E74C3C").print(text)
        elif "⚠️" in response.message:
            PrintStyle(font_color="#F39C12", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: ⚠️ Warning"
            )
            PrintStyle(font_color="#F39C12").print(text)
        else:
            # Default styling
            PrintStyle(font_color="#3498DB", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: 📋 Contact Information"
            )
            PrintStyle(font_color="#3498DB").print(text)
        
        self.log.update(content=text)