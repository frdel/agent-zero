import pytest
import httpx
from unittest.mock import AsyncMock, patch

from python.tools.ecommerce_tools import (
    FetchGaAccountSummaries,
    CreateReport,
    GetReport,
    ListReports,
    BASE_URL,
)
from python.helpers.tool import Response
from agent import Agent # Mock agent

# A mock Agent class or instance to pass to tool constructors
class MockAgent:
    def __init__(self):
        self.agent_name = "TestAgent"
        # Add other attributes/methods if the Tool class expects them
        # For example, if it uses agent.context.log or similar.
        self.context = AsyncMock() # Mock context if needed


@pytest.fixture
def mock_agent_instance():
    return MockAgent()

@pytest.mark.asyncio
async def test_fetch_ga_account_summaries_success(mock_agent_instance):
    mock_response_data = {"accounts": [{"id": "123", "name": "Test Account"}]}
    mock_httpx_response = httpx.Response(200, json=mock_response_data)

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_httpx_response)) as mock_get:
        tool = FetchGaAccountSummaries(agent=mock_agent_instance, name="FetchGaAccountSummaries", method=None, args={}, message="")
        response = await tool.execute()

        mock_get.assert_called_once_with(f"{BASE_URL}/ga/account_summaries")
        assert response.message == mock_httpx_response.text
        assert response.break_loop is False
        # To assert the JSON content, you'd typically json.loads(response.message)
        # For this example, checking text equality is fine as per tool's current implementation

@pytest.mark.asyncio
async def test_fetch_ga_account_summaries_http_error(mock_agent_instance):
    mock_httpx_response = httpx.Response(500, text="Internal Server Error")

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_httpx_response)) as mock_get:
        tool = FetchGaAccountSummaries(agent=mock_agent_instance, name="FetchGaAccountSummaries", method=None, args={}, message="")
        # Simulate raise_for_status() behavior for non-2xx codes
        mock_get.return_value.raise_for_status = AsyncMock(side_effect=httpx.HTTPStatusError("Error", request=mock_get.return_value.request, response=mock_get.return_value))
        response = await tool.execute()

        mock_get.assert_called_once_with(f"{BASE_URL}/ga/account_summaries")
        assert "HTTP error occurred: 500 - Internal Server Error" in response.message
        assert response.break_loop is False

@pytest.mark.asyncio
async def test_fetch_ga_account_summaries_request_error(mock_agent_instance):
    with patch("httpx.AsyncClient.get", AsyncMock(side_effect=httpx.RequestError("Network Error", request=None))) as mock_get:
        tool = FetchGaAccountSummaries(agent=mock_agent_instance, name="FetchGaAccountSummaries", method=None, args={}, message="")
        response = await tool.execute()

        mock_get.assert_called_once_with(f"{BASE_URL}/ga/account_summaries")
        assert "Request error occurred: Network Error" in response.message
        assert response.break_loop is False

@pytest.mark.asyncio
async def test_create_report_success(mock_agent_instance):
    report_payload = {"property_id": "prop1", "name": "Test Report", "params": {"dim": "date"}}
    mock_response_data = {"id": 1, **report_payload}
    mock_httpx_response = httpx.Response(200, json=mock_response_data)

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_httpx_response)) as mock_post:
        tool = CreateReport(agent=mock_agent_instance, name="CreateReport", method=None, args=report_payload, message="")
        response = await tool.execute(**report_payload)

        mock_post.assert_called_once_with(f"{BASE_URL}/reports/", json=report_payload)
        assert response.message == mock_httpx_response.text
        assert response.break_loop is False

@pytest.mark.asyncio
async def test_get_report_success(mock_agent_instance):
    report_id = 1
    mock_response_data = {"id": report_id, "name": "Fetched Report"}
    mock_httpx_response = httpx.Response(200, json=mock_response_data)

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_httpx_response)) as mock_get:
        tool = GetReport(agent=mock_agent_instance, name="GetReport", method=None, args={"report_id": report_id}, message="")
        response = await tool.execute(report_id=report_id)

        mock_get.assert_called_once_with(f"{BASE_URL}/reports/{report_id}")
        assert response.message == mock_httpx_response.text
        assert response.break_loop is False

@pytest.mark.asyncio
async def test_get_report_not_found(mock_agent_instance):
    report_id = 999
    mock_httpx_response = httpx.Response(404, text="Not Found")

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_httpx_response)) as mock_get:
        tool = GetReport(agent=mock_agent_instance, name="GetReport", method=None, args={"report_id": report_id}, message="")
        # Simulate raise_for_status() behavior for non-2xx codes
        mock_get.return_value.raise_for_status = AsyncMock(side_effect=httpx.HTTPStatusError("Error", request=mock_get.return_value.request, response=mock_get.return_value))
        response = await tool.execute(report_id=report_id)

        mock_get.assert_called_once_with(f"{BASE_URL}/reports/{report_id}")
        assert f"Report with ID {report_id} not found." in response.message
        assert response.break_loop is False

@pytest.mark.asyncio
async def test_list_reports_success(mock_agent_instance):
    mock_response_data = [{"id": 1, "name": "Report 1"}, {"id": 2, "name": "Report 2"}]
    mock_httpx_response = httpx.Response(200, json=mock_response_data)

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_httpx_response)) as mock_get:
        tool = ListReports(agent=mock_agent_instance, name="ListReports", method=None, args={}, message="")
        response = await tool.execute()

        mock_get.assert_called_once_with(f"{BASE_URL}/reports/", params={"skip": 0, "limit": 10})
        assert response.message == mock_httpx_response.text
        assert response.break_loop is False

@pytest.mark.asyncio
async def test_list_reports_with_filters(mock_agent_instance):
    filter_params = {"property_id": "prop123", "name": "Sales", "skip": 5, "limit": 20}
    mock_response_data = [{"id": 3, "name": "Sales Report"}]
    mock_httpx_response = httpx.Response(200, json=mock_response_data)

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_httpx_response)) as mock_get:
        tool = ListReports(agent=mock_agent_instance, name="ListReports", method=None, args=filter_params, message="")
        response = await tool.execute(**filter_params)

        mock_get.assert_called_once_with(f"{BASE_URL}/reports/", params=filter_params)
        assert response.message == mock_httpx_response.text
        assert response.break_loop is False
