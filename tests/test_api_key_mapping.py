#!/usr/bin/env python3
"""Test script to verify API key mapping works for different providers."""

import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_api_key_mapping():
    """Test that API keys are correctly mapped for different providers."""

    # Import GraphRAG helper
    from python.helpers.graphrag_helper import GraphRAGHelper

    # Test scenarios: each contains (provider, model_name, expected_env_vars)
    test_scenarios = [
        ("openrouter", "openai/gpt-4.1", ["OPENROUTER_API_KEY", "OPENAI_API_KEY"]),
        ("openai", "gpt-4", ["OPENAI_API_KEY"]),
        ("anthropic", "claude-3-sonnet", ["ANTHROPIC_API_KEY"]),
        ("google", "gemini-pro", ["GOOGLE_API_KEY", "GEMINI_API_KEY"]),
    ]

    for provider, model_name, expected_env_vars in test_scenarios:
        logger.info(f"Testing provider: {provider}, model: {model_name}")

        # Clear environment variables
        for var in expected_env_vars:
            if var in os.environ:
                del os.environ[var]

        # Create a helper instance (this triggers _setup_api_keys)
        try:
            # Mock the settings for this test
            import python.helpers.graphrag_helper as helper_module
            original_get_settings = helper_module.get_settings

            def mock_get_settings():
                return {
                    "chat_model_provider": provider,
                    "chat_model_name": model_name,
                    "chat_model_api_base": "",
                    "chat_model_kwargs": {"temperature": "0"},
                }

            helper_module.get_settings = mock_get_settings

            # This should trigger the API key mapping
            helper = GraphRAGHelper()

            # Check that the expected environment variables are set
            for var in expected_env_vars:
                if var in os.environ and os.environ[var] != "None":
                    logger.info(f"✓ {var} is correctly set")
                else:
                    logger.warning(f"✗ {var} is missing or None")

            # Restore original settings function
            helper_module.get_settings = original_get_settings

        except Exception as e:
            logger.error(f"✗ Failed to create helper for {provider}: {e}")
            continue

        logger.info(f"Completed test for {provider}\n")

if __name__ == "__main__":
    test_api_key_mapping()
