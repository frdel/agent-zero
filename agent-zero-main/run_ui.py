from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys
import os
import json
import uuid
from typing import Dict, List, Any
from dotenv import load_dotenv
from pydantic import SecretStr

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from agent import Agent, AgentConfig
from typing import Any

# Import necessary language models
from langchain_groq import ChatGroq
from models import get_available_models, get_model_by_name, get_embedding_model_by_name

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the Groq API key from environment variables
groq_api_key = os.getenv("GROQ_API_KEY")
groq_api_key_secret = SecretStr(groq_api_key) if groq_api_key else None

# Create AgentConfig with Groq's Llama 3.2 model
chat_model = ChatGroq(
    model="llama-3.2-3b-preview",
    api_key=groq_api_key_secret,
    stop_sequences=[],  # Add stop sequences here if needed
)
utility_model = ChatGroq(
    model="llama-3.2-3b-preview",
    api_key=groq_api_key_secret,
    stop_sequences=[],  # Add stop sequences here if needed
)
config = AgentConfig(
    chat_model=chat_model,
    utility_model=utility_model,
    embeddings_model=None,  # We'll set this to None for now
)

# Create Agent instance
agent = Agent(number=1, config=config)


# Custom StaticFiles class to disable caching
class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response


# Mount the static files directory with caching disabled
app.mount(
    "/static",
    NoCacheStaticFiles(directory=os.path.join(current_dir, "webui")),
    name="static",
)

# In-memory storage for chat contexts and messages
chat_contexts: Dict[str, Dict[str, Any]] = {}


# Function to handle response generation
async def generate_agent_response(prompt: str) -> str:
    print(f"Generating response for prompt: {prompt}")  # Debug: Log the prompt

    try:
        response = agent.generate_response(prompt)
        print(f"Generated response: {response}")  # Debug: Log the generated response
        return response
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return f"Error: {str(e)}"


@app.get("/", response_class=HTMLResponse)
async def read_root():
    return FileResponse(os.path.join(current_dir, "webui", "index.html"))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(current_dir, "webui", "favicon.ico"))


@app.post("/poll")
async def poll(request: Request):
    data = await request.json()
    context = data.get("context", "")
    log_from = data.get("log_from", 0)

    if context not in chat_contexts:
        chat_contexts[context] = {"messages": [], "paused": False}

    context_data = chat_contexts[context]
    new_messages = context_data["messages"][log_from:]

    return JSONResponse(
        {
            "ok": True,
            "context": context,
            "log_version": len(context_data["messages"]),
            "logs": new_messages,
            "paused": context_data["paused"],
            "contexts": [{"id": ctx, "no": idx + 1} for idx, ctx in enumerate(chat_contexts.keys())],
        }
    )


@app.post("/msg")
async def message(request: Request):
    data = await request.json()
    text = data.get("text", "")
    context = data.get("context", "")

    if context not in chat_contexts:
        chat_contexts[context] = {"messages": [], "paused": False}

    # Generate a response using the agent
    response = await generate_agent_response(text)

    # Add user message and agent response to the context
    chat_contexts[context]["messages"].extend([{"type": "user", "content": text}, {"type": "agent", "content": response}])

    print(f"Sending response: {response}")  # Debug: Log the response being sent

    return JSONResponse({"ok": True})


@app.post("/pause")
async def pause(request: Request):
    data = await request.json()
    paused = data.get("paused", False)
    context = data.get("context", "")

    if context not in chat_contexts:
        raise HTTPException(status_code=404, detail="Context not found")

    chat_contexts[context]["paused"] = paused
    return JSONResponse({"ok": True})


@app.post("/reset")
async def reset(request: Request):
    data = await request.json()
    context = data.get("context", "")

    if context not in chat_contexts:
        raise HTTPException(status_code=404, detail="Context not found")

    chat_contexts[context]["messages"] = []
    chat_contexts[context]["paused"] = False
    return JSONResponse({"ok": True})


@app.post("/remove")
async def remove(request: Request):
    data = await request.json()
    context = data.get("context", "")

    if context not in chat_contexts:
        raise HTTPException(status_code=404, detail="Context not found")

    del chat_contexts[context]
    return JSONResponse({"ok": True})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            response = await generate_agent_response(data)
            await websocket.send_text(response)
    except WebSocketDisconnect:
        print("WebSocket disconnected.")


@app.get("/get_available_models")
async def get_available_models_endpoint():
    models_list = get_available_models()
    current_models = {
        "chat": getattr(agent.config.chat_model, "model", None),
        "utility": getattr(agent.config.utility_model, "model", None),
        "embedding": getattr(agent.config.embeddings_model, "model", None),
    }
    return JSONResponse({"models": models_list, "current_models": current_models})


@app.post("/update_model")
async def update_model(request: Request):
    data = await request.json()
    role = data.get("role")
    model_name = data.get("model_name")

    if role not in ["chat", "utility", "embedding"]:
        return JSONResponse({"ok": False, "message": f"Invalid role: {role}"}, status_code=400)

    try:
        # Update the agent's configuration
        if role == "chat":
            agent.config.chat_model = get_model_by_name(model_name)
        elif role == "utility":
            agent.config.utility_model = get_model_by_name(model_name)
        elif role == "embedding":
            agent.config.embeddings_model = get_embedding_model_by_name(model_name)

        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
