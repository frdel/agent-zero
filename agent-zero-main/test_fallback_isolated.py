import unittest
from unittest.mock import patch, MagicMock


class AgentConfig:
    def __init__(self, chat_model, fallback_model):
        self.chat_model = chat_model
        self.fallback_model = fallback_model


class Agent:
    def __init__(self, number, config):
        self.config = config
        self.number = number
        self.agent_name = "Agent {}".format(self.number)

    def message_loop(self, msg):
        try:
            return self.config.chat_model(
                {"messages": [{"role": "user", "content": msg}]}
            )
        except Exception as e:
            if "rate limit" in str(e).lower():
                print(
                    "{}: Rate limit hit. Falling back to GPT-4o-mini.".format(
                        self.agent_name
                    )
                )
                return self.config.fallback_model(
                    {"messages": [{"role": "user", "content": msg}]}
                )
            else:
                raise e


class TestFallbackMechanism(unittest.TestCase):
    def setUp(self):
        self.chat_model = MagicMock()
        self.fallback_model = MagicMock()
        self.config = AgentConfig(
            chat_model=self.chat_model,
            fallback_model=self.fallback_model,
        )
        self.agent = Agent(0, self.config)

    @patch("builtins.print")
    def test_fallback_on_rate_limit(self, mock_print):
        # Mock the primary model to raise a rate limit exception
        self.chat_model.side_effect = Exception("rate limit exceeded")

        # Mock the fallback model to return a response
        self.fallback_model.return_value = "Fallback model response"

        # Run the message_loop
        response = self.agent.message_loop("Test message")

        # Check if the fallback model was used
        self.assertEqual(response, "Fallback model response")
        self.chat_model.assert_called_once()
        self.fallback_model.assert_called_once()
        mock_print.assert_called_with(
            "Agent 0: Rate limit hit. Falling back to GPT-4o-mini."
        )

    def test_no_fallback_on_normal_operation(self):
        # Mock the primary model to return a normal response
        self.chat_model.return_value = "Primary model response"

        # Run the message_loop
        response = self.agent.message_loop("Test message")

        # Check if the primary model was used and not the fallback
        self.assertEqual(response, "Primary model response")
        self.chat_model.assert_called_once()
        self.fallback_model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
