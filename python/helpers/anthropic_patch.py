"""
Monkey patch for langchain-anthropic 0.3.3 to fix the NoneType + int error
in _create_usage_metadata function.
"""

def patch_anthropic():
    try:
        from langchain_anthropic.chat_models import _create_usage_metadata
        import langchain_anthropic.chat_models as chat_models
        
        # Store the original function
        original_create_usage_metadata = _create_usage_metadata
        
        # Create a patched version
        def patched_create_usage_metadata(anthropic_usage):
            if anthropic_usage is None:
                return None
            
            # Safely get attributes with defaults
            input_tokens = getattr(anthropic_usage, "input_tokens", None) or 0
            output_tokens = getattr(anthropic_usage, "output_tokens", None) or 0
            
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            }
        
        # Replace the function
        chat_models._create_usage_metadata = patched_create_usage_metadata
        print("Successfully patched langchain-anthropic usage metadata handling")
        
    except Exception as e:
        print(f"Failed to patch langchain-anthropic: {e}")

# Auto-patch on import
patch_anthropic()