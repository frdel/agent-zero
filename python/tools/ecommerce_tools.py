"""Tools for interacting with the AgentZero Commerce submodule."""

import httpx
import os
from typing import Optional, Dict, Any, List
from python.helpers.tool import Tool, Response

BASE_URL = os.getenv("AGENTZERO_COMMERCE_BASE_URL", "http://localhost:8080")


class FetchGaAccountSummaries(Tool):
    """Fetches Google Analytics account summaries from the commerce submodule."""

    def __init__(self, agent, name, method, args, message, **kwargs):
        super().__init__(agent, "FetchGaAccountSummaries", method, args, message, **kwargs)

    async def execute(self, **kwargs) -> Response:
        """Fetches Google Analytics account summaries.

        Returns:
            A Response object with the API response or error message.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{BASE_URL}/ga/account_summaries")
                response.raise_for_status()
                return Response(message=response.text, break_loop=False)
            except httpx.HTTPStatusError as e:
                return Response(message=f"HTTP error occurred: {e.response.status_code} - {e.response.text}", break_loop=False)
            except httpx.RequestError as e:
                return Response(message=f"Request error occurred: {str(e)}", break_loop=False)


class CreateReport(Tool):
    """Creates a new report in the commerce submodule."""

    def __init__(self, agent, name, method, args, message, **kwargs):
        super().__init__(agent, "CreateReport", method, args, message, **kwargs)

    async def execute(self, property_id: str, name: str, params: Dict[str, Any], **kwargs) -> Response:
        """Creates a new report.

        Args:
            property_id: The property ID for the report.
            name: The name of the report.
            params: A dictionary of parameters for the report.

        Returns:
            A Response object with the API response or error message.
        """
        async with httpx.AsyncClient() as client:
            try:
                api_response = await client.post(
                    f"{BASE_URL}/reports/",
                    json={"property_id": property_id, "name": name, "params": params},
                )
                api_response.raise_for_status()
                return Response(message=api_response.text, break_loop=False)
            except httpx.HTTPStatusError as e:
                return Response(message=f"HTTP error occurred: {e.response.status_code} - {e.response.text}", break_loop=False)
            except httpx.RequestError as e:
                return Response(message=f"Request error occurred: {str(e)}", break_loop=False)


class GetReport(Tool):
    """Retrieves a specific report from the commerce submodule by its ID."""

    def __init__(self, agent, name, method, args, message, **kwargs):
        super().__init__(agent, "GetReport", method, args, message, **kwargs)

    async def execute(self, report_id: int, **kwargs) -> Response:
        """Retrieves a specific report by its ID.

        Args:
            report_id: The ID of the report to retrieve.

        Returns:
            A Response object with the API response or error message.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{BASE_URL}/reports/{report_id}")
                response.raise_for_status()
                return Response(message=response.text, break_loop=False)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return Response(message=f"Report with ID {report_id} not found.", break_loop=False)
                return Response(message=f"HTTP error occurred: {e.response.status_code} - {e.response.text}", break_loop=False)
            except httpx.RequestError as e:
                return Response(message=f"Request error occurred: {str(e)}", break_loop=False)


class ListReports(Tool):
    """Lists reports from the commerce submodule, with optional filters."""

    def __init__(self, agent, name, method, args, message, **kwargs):
        super().__init__(agent, "ListReports", method, args, message, **kwargs)

    async def execute(
        self,
        property_id: Optional[str] = None,
        name: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
        **kwargs
    ) -> Response:
        """Lists reports with optional filters.

        Args:
            property_id: Optional filter by property ID.
            name: Optional filter by report name.
            skip: Number of reports to skip.
            limit: Maximum number of reports to return.

        Returns:
            A Response object with the list of reports or error message.
        """
        query_params = {"skip": skip, "limit": limit}
        if property_id:
            query_params["property_id"] = property_id
        if name:
            query_params["name"] = name

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{BASE_URL}/reports/", params=query_params)
                response.raise_for_status()
                return Response(message=response.text, break_loop=False) # Returning raw text, might need json parsing by caller
            except httpx.HTTPStatusError as e:
                return Response(message=f"HTTP error occurred: {e.response.status_code} - {e.response.text}", break_loop=False)
            except httpx.RequestError as e:
                return Response(message=f"Request error occurred: {str(e)}", break_loop=False)
