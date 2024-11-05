import pytest
from agent import Agent, AgentContext
from agent.config import AgentConfig
from agent.agent_types import AgentException, LoopData, Response


def create_test_config():
    """Helper function to create a test config"""
    return AgentConfig(
        chat_model=None,
        utility_model=None,
        embeddings_model=None,
        knowledge_subdirs=["default"],
        auto_memory_count=0,
        rate_limit_requests=30,
        max_tool_response_length=3000,
        code_exec_docker_enabled=True,
        code_exec_ssh_enabled=True,
    )


def test_loop_data_initialization():
    """Test LoopData initialization and default values"""
    loop_data = LoopData()
    assert loop_data.iteration == -1
    assert loop_data.message == ""
    assert loop_data.history_from == 0
    assert isinstance(loop_data.history, list)
    assert isinstance(loop_data.system, list)
    assert isinstance(loop_data.messages, list)
    assert isinstance(loop_data.state, dict)
    assert isinstance(loop_data.context, dict)
    assert isinstance(loop_data.memory, dict)


def test_agent_context_initialization():
    """Test AgentContext initialization"""
    config = create_test_config()
    context = AgentContext(config=config)

    assert context.config == config
    assert context.id is not None
    assert context.name is None
    assert context.agent0 is not None
    assert context.log is not None
    assert context.paused is False
    assert context.streaming_agent is None
    assert context.process is None
    assert context.no > 0


def test_agent_context_management():
    """Test AgentContext static methods"""
    config = create_test_config()

    # Test context creation and retrieval
    context = AgentContext(config=config, id="test-id")
    assert AgentContext.get("test-id") == context

    # Test first context
    assert AgentContext.first() == context

    # Test context removal
    removed = AgentContext.remove("test-id")
    assert removed == context
    assert AgentContext.get("test-id") is None


def test_agent_initialization():
    """Test Agent initialization"""
    config = create_test_config()
    context = AgentContext(config=config)
    agent = Agent(0, config, context)

    assert agent.number == 0
    assert agent.agent_name == "Agent 0"
    assert agent.config == config
    assert agent.context == context
    assert isinstance(agent.history, list)
    assert agent.last_message == ""
    assert agent.intervention_message == ""
    assert isinstance(agent.data, dict)


def test_agent_data_management():
    """Test Agent data management methods"""
    config = create_test_config()
    context = AgentContext(config=config)
    agent = Agent(0, config, context)

    # Test data setting and getting
    agent.set_data("test_key", "test_value")
    assert agent.get_data("test_key") == "test_value"
    assert agent.get_data("nonexistent") is None


def test_response_initialization():
    """Test Response class initialization"""
    response = Response("test message", True)
    assert response.message == "test message"
    assert response.break_loop is True

    default_response = Response()
    assert default_response.message == ""
    assert default_response.break_loop is False


def test_invalid_agent_initialization():
    """Test Agent initialization with invalid config"""
    config = create_test_config()
    context = AgentContext(config=config)
    agent = Agent(0, config, context)

    # Create invalid config by setting required models to None
    invalid_config = AgentConfig(
        chat_model=None,
        utility_model=None,
        embeddings_model=None,
        knowledge_subdirs=["default"],
        auto_memory_count=0,
        rate_limit_requests=30,
        max_tool_response_length=3000,
        code_exec_docker_enabled=True,
        code_exec_ssh_enabled=True,
    )

    # Should raise AgentException during initialize() due to missing required models
    with pytest.raises(AgentException) as exc_info:
        agent.initialize(invalid_config)

    assert "Missing required config attribute" in str(exc_info.value)
