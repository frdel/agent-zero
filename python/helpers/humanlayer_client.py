from typing import Dict, Any, Optional
from dataclasses import dataclass
import os


@dataclass
class ApprovalResult:
    approved: bool
    comment: Optional[str] = None
    feedback: Optional[str] = None


@dataclass  
class ConsultationResult:
    response: str
    context: Optional[str] = None


class HumanLayerClient:
    """
    HumanLayer client wrapper for Agent Zero integration.
    Handles client initialization, contact channel management, and configuration validation.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None

    async def get_client(self):
        """
        Get or create AsyncHumanLayer client instance.
        Uses lazy initialization for better error handling.
        """
        if not self.client:
            try:
                # Import here to avoid dependency issues if humanlayer not installed
                from humanlayer import AsyncHumanLayer
                
                api_key = self.config.get("humanlayer_api_key") or os.getenv("HUMANLAYER_API_KEY")
                if not api_key:
                    raise ValueError("HumanLayer API key not found. Set humanlayer_api_key in config or HUMANLAYER_API_KEY environment variable.")
                
                self.client = AsyncHumanLayer(
                    api_key=api_key,
                    verbose=self.config.get("humanlayer_verbose", True),
                    run_id=self.config.get("humanlayer_run_id", "agent-zero")
                )
            except ImportError:
                raise ImportError("HumanLayer package not installed. Install with: pip install humanlayer>=0.3.0")
            except Exception as e:
                raise Exception(f"Failed to initialize HumanLayer client: {str(e)}")
        
        return self.client

    def get_contact_channel(self, channel_override: Optional[str] = None):
        """
        Get contact channel configuration based on channel type.
        Supports Slack, Email, and CLI channels.
        """
        try:
            from humanlayer import ContactChannel, SlackContactChannel, EmailContactChannel
        except ImportError:
            raise ImportError("HumanLayer package not installed. Install with: pip install humanlayer>=0.3.0")

        channel_type = channel_override or self.config.get("humanlayer_default_contact_channel", "slack")
        channels_config = self.config.get("humanlayer_contact_channels", {})

        if channel_type == "slack":
            slack_config = channels_config.get("slack", {})
            if not slack_config.get("channel_id"):
                # Fallback to environment variable or default
                channel_id = os.getenv("HUMANLAYER_SLACK_CHANNEL_ID", "")
                if not channel_id:
                    raise ValueError("Slack channel ID not configured. Set in humanlayer_contact_channels.slack.channel_id or HUMANLAYER_SLACK_CHANNEL_ID environment variable.")
            else:
                channel_id = slack_config["channel_id"]

            return ContactChannel(
                slack=SlackContactChannel(
                    channel_or_user_id=channel_id,
                    context_about_channel_or_user=slack_config.get("context", "Agent Zero Integration"),
                    experimental_slack_blocks=slack_config.get("use_blocks", True)
                )
            )
        
        elif channel_type == "email":
            email_config = channels_config.get("email", {})
            email_address = email_config.get("address") or os.getenv("HUMANLAYER_EMAIL_ADDRESS")
            if not email_address:
                raise ValueError("Email address not configured. Set in humanlayer_contact_channels.email.address or HUMANLAYER_EMAIL_ADDRESS environment variable.")

            return ContactChannel(
                email=EmailContactChannel(
                    address=email_address,
                    context_about_user=email_config.get("context", "Agent Zero User"),
                    subject=email_config.get("subject", "Agent Zero Approval Request")
                )
            )
        
        else:
            # Default to CLI/webhook contact channel
            return None  # HumanLayer will use default CLI channel

    def validate_configuration(self) -> tuple[bool, list[str]]:
        """
        Validate HumanLayer configuration and return validation results.
        Returns (is_valid, list_of_errors)
        """
        errors = []

        # Check if HumanLayer is enabled
        if not self.config.get("humanlayer_enabled", False):
            return True, []  # Not enabled, so configuration doesn't need to be valid

        # Check API key
        api_key = self.config.get("humanlayer_api_key") or os.getenv("HUMANLAYER_API_KEY")
        if not api_key:
            errors.append("HumanLayer API key not found. Set humanlayer_api_key in config or HUMANLAYER_API_KEY environment variable.")

        # Check contact channel configuration
        default_channel = self.config.get("humanlayer_default_contact_channel", "slack")
        channels_config = self.config.get("humanlayer_contact_channels", {})

        if default_channel == "slack":
            slack_config = channels_config.get("slack", {})
            if not slack_config.get("channel_id") and not os.getenv("HUMANLAYER_SLACK_CHANNEL_ID"):
                errors.append("Slack channel ID not configured for default channel type 'slack'.")

        elif default_channel == "email":
            email_config = channels_config.get("email", {})
            if not email_config.get("address") and not os.getenv("HUMANLAYER_EMAIL_ADDRESS"):
                errors.append("Email address not configured for default channel type 'email'.")

        # Validate timeout settings
        timeout = self.config.get("humanlayer_approval_timeout", 300)
        if not isinstance(timeout, int) or timeout <= 0:
            errors.append("humanlayer_approval_timeout must be a positive integer (seconds).")

        return len(errors) == 0, errors

    def get_timeout(self) -> int:
        """Get configured timeout in seconds, with fallback to default."""
        return self.config.get("humanlayer_approval_timeout", 300)

    def is_enabled(self) -> bool:
        """Check if HumanLayer integration is enabled."""
        return self.config.get("humanlayer_enabled", False)