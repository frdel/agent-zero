from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="AgentZero-Commerce API")

@app.get("/ga/healthcheck", tags=["GA"])
async def ga_health():
    return JSONResponse({"status": "ok",
                         "service": "google-analytics",
                         "detail": "stub"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
