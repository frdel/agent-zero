import pytest
from agent import Agent, LoopData
from agent.agent_types import AgentException


def test_agent_initialization():
    agent = Agent()
    assert agent.loop_data is None
    assert agent.config == {}

    agent.initialize()
    assert isinstance(agent.loop_data, LoopData)
    assert agent.config == {}

    test_config = {"test": "value"}
    agent.initialize(test_config)
    assert agent.config == test_config


def test_loop_data():
    loop_data = LoopData()
    assert isinstance(loop_data.messages, list)
    assert isinstance(loop_data.state, dict)
    assert isinstance(loop_data.context, dict)
    assert isinstance(loop_data.memory, dict)


def test_invalid_config():
    agent = Agent()
    with pytest.raises(AgentException):
        agent.initialize(config="invalid_config")
