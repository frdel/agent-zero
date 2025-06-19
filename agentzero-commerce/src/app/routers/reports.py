from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models import Report, get_session

router = APIRouter()


@router.get("/reports", tags=["Reports"])
async def list_reports(offset: int = 0, limit: int = 100, session: AsyncSession = Depends(get_session)) -> List[Report]:
    result = await session.exec(select(Report).offset(offset).limit(limit))
    return result.all()


@router.get("/reports/{report_id}", tags=["Reports"])
async def get_report(report_id: int, session: AsyncSession = Depends(get_session)) -> Report:
    report = await session.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.post("/reports", tags=["Reports"], status_code=201)
async def create_report(report: Report, session: AsyncSession = Depends(get_session)) -> Report:
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report
