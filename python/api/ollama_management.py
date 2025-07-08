import httpx
from flask import Blueprint, jsonify, request, Response, stream_with_context
import json

from python.helpers import settings
from models import get_ollama_base_url

import httpx
from flask import Blueprint, jsonify, request, Response, stream_with_context
import json

from python.helpers import settings
from models import get_ollama_base_url
from python.helpers.auth_decorators import requires_auth

ollama_management_bp = Blueprint("ollama_management", __name__, url_prefix="/api/ollama")

def get_actual_ollama_base_url():
    # This function ensures we get the most current base URL,
    # especially if settings can be changed dynamically.
    # For now, using the one from models.py which reads .env or defaults.
    return get_ollama_base_url()

@ollama_management_bp.route("/models", methods=["GET"])
@requires_auth
async def list_ollama_models():
    """
    Lists locally available Ollama models.
    Proxies the request to the Ollama service's /api/tags endpoint.
    """
    ollama_base_url = get_actual_ollama_base_url()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ollama_base_url}/api/tags")
            response.raise_for_status()  # Raise an exception for bad status codes
            return jsonify(response.json())
    except httpx.RequestError as e:
        return jsonify({"error": f"Failed to connect to Ollama service: {str(e)}"}), 500
    except httpx.HTTPStatusError as e:
        return jsonify({"error": f"Ollama service returned an error: {str(e)}", "details": e.response.text}), e.response.status_code
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@ollama_management_bp.route("/pull", methods=["POST"])
@requires_auth
async def pull_ollama_model():
    """
    Pulls a model from the Ollama library.
    Proxies the request to the Ollama service's /api/pull endpoint.
    Streams the response back to the client.
    """
    data = request.get_json()
    if not data or "model_name" not in data:
        return jsonify({"error": "model_name is required"}), 400

    model_name = data["model_name"]
    stream = data.get("stream", True) # Default to streaming if not specified

    ollama_base_url = get_actual_ollama_base_url()

    async def event_stream():
        try:
            async with httpx.AsyncClient(timeout=None) as client: # Adjust timeout as needed for large downloads
                async with client.stream("POST", f"{ollama_base_url}/api/pull", json={"name": model_name, "stream": stream}) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_text():
                        # Ensure each chunk is a separate line for SSE
                        for line in chunk.splitlines():
                            if line:
                                yield f"data: {line}\n\n"
            yield f"data: {json.dumps({'status': 'completed pull process'})}\n\n" # Signal completion from proxy
        except httpx.RequestError as e:
            yield f"data: {json.dumps({'error': f'Failed to connect to Ollama service: {str(e)}'})}\n\n"
        except httpx.HTTPStatusError as e:
            error_details = e.response.text
            try:
                error_json = json.loads(error_details) # Ollama might return JSON error
            except json.JSONDecodeError:
                error_json = error_details
            yield f"data: {json.dumps({'error': f'Ollama service returned an error: {str(e)}', 'details': error_json})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': f'An unexpected error occurred during pull: {str(e)}'})}\n\n"

    return Response(stream_with_context(event_stream()), content_type="text/event-stream")

@ollama_management_bp.route("/status", methods=["GET"])
@requires_auth
async def get_ollama_status():
    """
    Checks the status of the Ollama service by trying to hit its root or version endpoint.
    """
    ollama_base_url = get_actual_ollama_base_url()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client: # 5 second timeout
            # Ollama root returns "Ollama is running"
            # /api/version is another option: response = await client.get(f"{ollama_base_url}/api/version")
            response = await client.get(ollama_base_url)
            response.raise_for_status()
            if response.text == "Ollama is running":
                 return jsonify({"status": "running", "message": "Ollama service is responsive.", "url": ollama_base_url})
            return jsonify({"status": "unknown", "message": "Ollama service is up but returned unexpected content.", "details": response.text, "url": ollama_base_url})
    except httpx.TimeoutException:
        return jsonify({"status": "error", "message": "Connection to Ollama service timed out.", "url": ollama_base_url}), 503
    except httpx.RequestError as e:
        return jsonify({"status": "error", "message": f"Failed to connect to Ollama service: {str(e)}", "url": ollama_base_url}), 503
    except httpx.HTTPStatusError as e:
        return jsonify({"status": "error", "message": f"Ollama service returned an error: {str(e)}", "details": e.response.text, "url": ollama_base_url}), e.response.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}", "url": ollama_base_url}), 500
