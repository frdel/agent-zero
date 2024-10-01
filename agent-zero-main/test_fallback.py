import unittest
import asyncio
from agent import Agent, AgentConfig


class TestAgentFallback(unittest.TestCase):
    def setUp(self):
        self.config = AgentConfig(
            chat_model=None,  # You need to provide appropriate models here
            utility_model=None,
            embeddings_model=None,
        )
        self.agent = Agent(number=1, config=self.config)

    async def async_generate_response(self, prompt):
        return self.agent.generate_response(prompt)

    def test_generate_response(self):
        response = asyncio.run(self.async_generate_response("Test prompt"))
        self.assertIsInstance(response, str, "Response should be a string")
        self.assertTrue(len(response) > 0, "Response should not be empty")

    def test_agent_config(self):
        self.assertEqual(
            self.config.max_tool_response_length,
            3000,
            "max_tool_response_length should be 3000",
        )

    def test_agent_number(self):
        self.assertEqual(self.agent.number, 1, "Agent number should be 1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
