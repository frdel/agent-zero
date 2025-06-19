from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from ..ga_client import run_report

router = APIRouter()


class GARequest(BaseModel):
    property_id: str
    dims: List[str]
    mets: List[str]
    start: str = "2024-01-01"
    end: str = "today"
    dry_run: bool = False


@router.get("/ga/healthcheck", tags=["GA"])
async def ga_health():
    return {"status": "ok", "service": "google-analytics"}


@router.post("/ga/run_report", tags=["GA"])
async def ga_run_report(req: GARequest):
    if req.dry_run:
        return {"status": "dry_run"}
    data = await run_report(req.property_id, req.dims, req.mets, req.start, req.end)
    return data
