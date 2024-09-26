from agent import Agent
from config import AgentConfig


def test_generate_response():
    agent = Agent()
    response = agent.generate_response("Test prompt")
    assert response == "response_text"


def test_agent_config():
    config = AgentConfig()
    assert config.max_tool_response_length == 1000


if __name__ == "__main__":
    test_generate_response()
    test_agent_config()
    print("All tests passed.")
