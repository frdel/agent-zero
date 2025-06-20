import pytest
import httpx
from unittest.mock import AsyncMock, patch

from agent import Agent, AgentConfig, ModelConfig, AgentContext, UserMessage
from python.helpers.tool import TOOL_MODULES
from python.tools import ecommerce_tools

# Ensure ecommerce_tools is in TOOL_MODULES for discovery
if ecommerce_tools not in TOOL_MODULES:
    TOOL_MODULES.append(ecommerce_tools)

@pytest.fixture
def test_agent_config():
    """Provides a basic AgentConfig for testing."""
    return AgentConfig(
        chat_model=ModelConfig(provider="ollama", name="mock_chat_model"),
        utility_model=ModelConfig(provider="ollama", name="mock_utility_model"),
        embeddings_model=ModelConfig(provider="ollama", name="mock_embeddings_model"),
        browser_model=ModelConfig(provider="ollama", name="mock_browser_model"),
        mcp_servers="mock_mcp_server",
        prompts_subdir="default",
    )

@pytest.fixture
def test_agent(test_agent_config):
    """Provides an Agent instance for integration tests."""
    context = AgentContext(config=test_agent_config)
    agent_instance = Agent(number=0, config=test_agent_config, context=context)
    # Mock history methods that might be called during process_tools
    agent_instance.hist_add_warning = AsyncMock()
    agent_instance.hist_add_tool_result = AsyncMock()
    agent_instance.hist_add_ai_response = AsyncMock() # process_tools adds AI response (the tool request)
    return agent_instance

@pytest.mark.asyncio
async def test_agent_loads_and_uses_fetch_ga_account_summaries(test_agent):
    tool_name = "FetchGaAccountSummaries"
    agent_message_content = f'{{"tool_name": "{tool_name}", "tool_args": {{}}}}'

    mock_api_response_data = {"accounts": [{"id": "789", "name": "Live Test Account"}]}
    mock_httpx_response = httpx.Response(200, json=mock_api_response_data, text=str(mock_api_response_data)) # Ensure text is also populated

    # Patch httpx.AsyncClient within the scope of the ecommerce_tools module
    with patch('python.tools.ecommerce_tools.httpx.AsyncClient') as MockAsyncClient:
        # Configure the mock client instance that will be created by the tool
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.get = AsyncMock(return_value=mock_httpx_response)

        # Agent's process_tools will call hist_add_ai_response with the agent_message_content
        # and then hist_add_tool_result with the tool's output.
        await test_agent.process_tools(agent_message_content)

        # Check that hist_add_ai_response was called with the initial tool request
        test_agent.hist_add_ai_response.assert_called_once_with(agent_message_content)

        # Check that the tool's execute method was effectively called (via httpx mock)
        mock_client_instance.get.assert_called_once_with(f"{ecommerce_tools.BASE_URL}/ga/account_summaries")

        # Check that hist_add_tool_result was called with the correct tool name and mocked result
        test_agent.hist_add_tool_result.assert_called_once_with(
            tool_name,
            str(mock_api_response_data) # The tool returns response.text
        )

@pytest.mark.asyncio
async def test_agent_uses_create_report_with_args(test_agent):
    tool_name = "CreateReport"
    tool_args = {"property_id": "prop123", "name": "My New Report", "params": {"metrics": ["sessions"]}}
    # Construct the JSON string carefully, ensuring proper escaping if tool_args were more complex
    agent_message_content = f'{{"tool_name": "{tool_name}", "tool_args": {{"property_id": "{tool_args["property_id"]}", "name": "{tool_args["name"]}", "params": {{"metrics": ["sessions"]}}}}}}'

    mock_api_response_data = {"id": 5, **tool_args}
    mock_httpx_response = httpx.Response(200, json=mock_api_response_data, text=str(mock_api_response_data))

    with patch('python.tools.ecommerce_tools.httpx.AsyncClient') as MockAsyncClient:
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.post = AsyncMock(return_value=mock_httpx_response)

        await test_agent.process_tools(agent_message_content)

        test_agent.hist_add_ai_response.assert_called_once_with(agent_message_content)
        mock_client_instance.post.assert_called_once_with(f"{ecommerce_tools.BASE_URL}/reports/", json=tool_args)
        test_agent.hist_add_tool_result.assert_called_once_with(
            tool_name,
            str(mock_api_response_data)
        )

@pytest.mark.asyncio
async def test_agent_handles_tool_not_found(test_agent):
    tool_name = "NonExistentTool"
    agent_message_content = f'{{"tool_name": "{tool_name}", "tool_args": {{}}}}'

    # No need to mock httpx as the tool shouldn't be found/executed
    await test_agent.process_tools(agent_message_content)

    test_agent.hist_add_ai_response.assert_called_once_with(agent_message_content)

    # Agent should add a warning if the tool is not found
    test_agent.hist_add_warning.assert_called_once()
    args, _ = test_agent.hist_add_warning.call_args
    warning_message = args[0]
    assert f"Tool '{tool_name}' not found" in warning_message

    # hist_add_tool_result should NOT be called
    test_agent.hist_add_tool_result.assert_not_called()

@pytest.mark.asyncio
async def test_agent_handles_tool_api_error(test_agent):
    tool_name = "FetchGaAccountSummaries"
    agent_message_content = f'{{"tool_name": "{tool_name}", "tool_args": {{}}}}'

    error_response_text = "Simulated API Error"
    mock_httpx_response = httpx.Response(500, text=error_response_text)

    with patch('python.tools.ecommerce_tools.httpx.AsyncClient') as MockAsyncClient:
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        # Simulate raise_for_status() behavior for non-2xx codes
        mock_client_instance.get = AsyncMock(return_value=mock_httpx_response)
        mock_httpx_response.raise_for_status = AsyncMock(side_effect=httpx.HTTPStatusError("Simulated error", request=mock_httpx_response.request, response=mock_httpx_response))


        await test_agent.process_tools(agent_message_content)

        test_agent.hist_add_ai_response.assert_called_once_with(agent_message_content)
        mock_client_instance.get.assert_called_once_with(f"{ecommerce_tools.BASE_URL}/ga/account_summaries")

        # The tool should return a Response object with the error message
        expected_tool_output = f"HTTP error occurred: 500 - {error_response_text}"
        test_agent.hist_add_tool_result.assert_called_once_with(
            tool_name,
            expected_tool_output
        )
