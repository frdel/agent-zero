import os
import json
import base64
import asyncio
from functools import lru_cache
from typing import List

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric
from google.oauth2 import service_account


@lru_cache(maxsize=1)
def get_credentials():
    data = os.getenv("GA_KEY_JSON")
    if not data:
        raise RuntimeError("GA_KEY_JSON not configured")
    try:
        if os.path.exists(data):
            return service_account.Credentials.from_service_account_file(data)
        try:
            decoded = base64.b64decode(data)
            info = json.loads(decoded)
        except Exception:
            info = json.loads(data)
        return service_account.Credentials.from_service_account_info(info)
    except Exception as e:
        raise RuntimeError("Invalid GA_KEY_JSON") from e


@lru_cache(maxsize=1)
def get_client() -> BetaAnalyticsDataClient:
    creds = get_credentials()
    return BetaAnalyticsDataClient(credentials=creds)


async def run_report(property_id: str, dims: List[str], mets: List[str], start: str = "2024-01-01", end: str = "today") -> dict:
    client = get_client()
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name=d) for d in dims],
        metrics=[Metric(name=m) for m in mets],
        date_ranges=[DateRange(start_date=start, end_date=end)],
    )
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, client.run_report, request)
    return response.to_dict()
