import httpx
from flask import Blueprint, jsonify
from python.helpers import dotenv
from python.helpers.auth_decorators import requires_auth # Assuming this is the shared auth decorator

openrouter_proxy_bp = Blueprint("openrouter_proxy", __name__, url_prefix="/api/openrouter")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"

def get_openrouter_api_key():
    # Consistent with how models.py retrieves it
    return (
        dotenv.get_dotenv_value("API_KEY_OPENROUTER")
        or dotenv.get_dotenv_value("OPENROUTER_API_KEY")
        or None # Ensure it returns None if not found, to be checked
    )

def is_free_model(model_data: dict) -> bool:
    """Checks if a model is free based on its pricing information."""
    pricing = model_data.get("pricing", {})
    # Check if prompt and completion prices are zero or very close to zero (represented as strings)
    prompt_price = pricing.get("prompt", "1") # Default to non-free if not present
    completion_price = pricing.get("completion", "1") # Default to non-free if not present
    request_price = pricing.get("request", "1") # Some models might only have a request price

    try:
        # Convert to float for comparison, handle potential conversion errors for malformed data
        is_prompt_free = float(prompt_price) == 0.0
        is_completion_free = float(completion_price) == 0.0
        # A model is free if both prompt and completion are free.
        # Or if it has a $0 request cost and $0 prompt/completion (though typically request cost is for specific free models)
        # For simplicity, we primarily check prompt and completion.
        # Some truly free models might list "0" or "0.0" or "0.0000000"
        if float(request_price) == 0.0 and is_prompt_free and is_completion_free:
            return True # Free per-request models

        return is_prompt_free and is_completion_free
    except ValueError:
        return False # If price is not a valid number, assume not free

@openrouter_proxy_bp.route("/models", methods=["GET"])
@requires_auth
async def list_openrouter_models():
    """
    Fetches models from OpenRouter, filters for free ones, and returns them.
    """
    api_key = get_openrouter_api_key()
    if not api_key:
        return jsonify({"error": "OpenRouter API key is not configured in .env"}), 500

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": dotenv.get_dotenv_value("OPENROUTER_REFERRER") or "http://localhost:50080", # Optional but good practice
        "X-Title": dotenv.get_dotenv_value("OPENROUTER_X_TITLE") or "Agent Zero", # Optional
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(OPENROUTER_API_URL, headers=headers)
            response.raise_for_status()
            all_models_data = response.json()

        if "data" not in all_models_data or not isinstance(all_models_data["data"], list):
            return jsonify({"error": "Invalid response structure from OpenRouter API"}), 500

        free_models = []
        for model in all_models_data["data"]:
            if isinstance(model, dict) and is_free_model(model):
                free_models.append({
                    "id": model.get("id"),
                    "name": model.get("name"),
                    "description": model.get("description", ""),
                    "context_length": model.get("context_length"),
                    "pricing": model.get("pricing") # Include pricing for transparency
                })

        return jsonify({"models": free_models})

    except httpx.RequestError as e:
        return jsonify({"error": f"Failed to connect to OpenRouter API: {str(e)}"}), 500
    except httpx.HTTPStatusError as e:
        return jsonify({"error": f"OpenRouter API returned an error: {str(e)}", "details": e.response.text}), e.response.status_code
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
