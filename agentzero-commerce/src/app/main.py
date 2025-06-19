import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_utils.tasks import repeat_every

from .routers import ga, reports
from .models import init_db, Report, async_session
from .ga_client import run_report

app = FastAPI(title="AgentZero-Commerce API")

origins = [
    "http://localhost:3000",
    "http://host.docker.internal:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ga.router)
app.include_router(reports.router)


@app.on_event("startup")
async def on_startup():
    await init_db()


@app.on_event("startup")
@repeat_every(seconds=60 * 60 * 24 * 7)
async def weekly_report() -> None:
    property_id = os.getenv("ENV_PROP_ID")
    if not property_id:
        return
    data = await run_report(property_id, ["eventName"], ["eventCount"])
    async with async_session() as session:
        report = Report(
            property_id=property_id,
            name="weekly_report",
            params={"dims": ["eventName"], "mets": ["eventCount"]},
            result=data,
        )
        session.add(report)
        await session.commit()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
