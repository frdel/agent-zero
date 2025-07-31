from python.helpers import settings
from python.helpers.humanlayer_client import HumanLayerClient
from agent import Agent


async def humanlayer_validate(request):
    """
    Validate HumanLayer configuration and test connectivity.
    
    Returns:
        dict: Validation results with status and details
    """
    try:
        # Get current settings
        current_settings = settings.get_settings()
        
        # Create HumanLayer client configuration from current settings
        config = {
            "humanlayer_enabled": current_settings["humanlayer_enabled"],
            "humanlayer_api_key": current_settings["humanlayer_api_key"],
            "humanlayer_default_contact_channel": current_settings["humanlayer_default_contact_channel"],
            "humanlayer_approval_timeout": current_settings["humanlayer_approval_timeout"],
            "humanlayer_verbose": current_settings["humanlayer_verbose"],
            "humanlayer_contact_channels": {
                "slack": {
                    "channel_id": current_settings["humanlayer_slack_channel_id"],
                    "context": current_settings["humanlayer_slack_context"],
                    "use_blocks": current_settings["humanlayer_slack_use_blocks"]
                },
                "email": {
                    "address": current_settings["humanlayer_email_address"],
                    "subject": current_settings["humanlayer_email_subject"],
                    "context": current_settings["humanlayer_email_context"]
                }
            }
        }
        
        # Create HumanLayer client
        client = HumanLayerClient(config)
        
        # Validate configuration
        is_valid, errors = client.validate_configuration()
        
        if not is_valid:
            return {
                "status": "error",
                "message": "Configuration validation failed",
                "errors": errors,
                "valid": False
            }
        
        # If enabled, try to test the connection
        if current_settings["humanlayer_enabled"]:
            try:
                # Test basic client initialization
                hl_client = await client.get_client()
                
                # Test contact channel setup
                contact_channel = client.get_contact_channel()
                
                return {
                    "status": "success",
                    "message": "HumanLayer configuration is valid and ready to use",
                    "valid": True,
                    "details": {
                        "enabled": True,
                        "api_key_configured": bool(current_settings["humanlayer_api_key"]),
                        "default_channel": current_settings["humanlayer_default_contact_channel"],
                        "timeout": current_settings["humanlayer_approval_timeout"],
                        "contact_channels_configured": len([
                            ch for ch in ["slack", "email"] 
                            if config["humanlayer_contact_channels"][ch].get("channel_id" if ch == "slack" else "address")
                        ])
                    }
                }
                
            except Exception as e:
                return {
                    "status": "warning",
                    "message": f"Configuration is valid but connection test failed: {str(e)}",
                    "valid": True,
                    "connection_error": str(e)
                }
        else:
            return {
                "status": "info",
                "message": "HumanLayer is disabled. Enable to activate human-in-the-loop workflows.",
                "valid": True,
                "details": {
                    "enabled": False
                }
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to validate HumanLayer configuration: {str(e)}",
            "valid": False,
            "error": str(e)
        }