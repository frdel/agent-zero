from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from agent import Agent
from initialize import get_available_models

app = FastAPI()
agent = Agent()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            response = await agent.generate_response(data)  # Await the async method
            await websocket.send_text(response)
    except WebSocketDisconnect:
        agent.append_message("WebSocket disconnected.")


if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8000)
