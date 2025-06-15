import os
import json
import glob
import aiohttp
from aiohttp import ClientConnectorError, ClientResponseError

from python.helpers.api import ApiHandler, Request, Response
from python.helpers import settings, log, dotenv
from models import get_ollama_base_url, get_lmstudio_base_url # Added get_lmstudio_base_url

# Common model extensions for GPT4All
GPT4ALL_MODEL_EXTENSIONS = ["*.bin", "*.gguf"]

class OllamaListModelsHandler(ApiHandler):
    @classmethod
    def get_route(cls):
        return "/api/ollama/models"

    async def process(self, req: Request, res: Response):
        ollama_base_url = get_ollama_base_url()
        models_api_url = f"{ollama_base_url}/api/tags"
        formatted_models = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(models_api_url) as response:
                    response.raise_for_status()  # Raise an exception for HTTP errors
                    data = await response.json()

                    if "models" in data and isinstance(data["models"], list):
                        for model_info in data["models"]:
                            if "name" in model_info:
                                model_name = model_info["name"]
                                formatted_models.append({"value": model_name, "label": model_name})
                        res.json(formatted_models)
                    else:
                        log.error(f"Ollama API response format unexpected: {data}")
                        res.error("Unexpected response format from Ollama API", 500)
        except ClientConnectorError:
            log.error(f"Could not connect to Ollama server at {ollama_base_url}. Is Ollama running?")
            # Return empty list or a specific error message for the UI
            res.json([]) # Or res.error("Ollama server not reachable", 503)
        except ClientResponseError as e:
            log.error(f"Error from Ollama API: {e.status} {e.message}")
            res.error(f"Ollama API error: {e.message}", e.status)
        except json.JSONDecodeError:
            log.error("Failed to decode JSON response from Ollama API")
            res.error("Invalid JSON response from Ollama API", 500)
        except Exception as e:
            log.error(f"An unexpected error occurred while fetching Ollama models: {e}")
            res.error(f"An unexpected error occurred: {str(e)}", 500)

class GPT4AllListModelsHandler(ApiHandler):
    @classmethod
    def get_route(cls):
        return "/api/gpt4all/models"

    def process(self, req: Request, res: Response):
        gpt4all_model_path = dotenv.get_dotenv_value("GPT4ALL_MODEL_PATH")
        formatted_models = []

        if not gpt4all_model_path:
            log.warning("GPT4ALL_MODEL_PATH environment variable is not set. Cannot list GPT4All models.")
            res.json([])
            return

        try:
            if os.path.isfile(gpt4all_model_path):
                # If the path is a direct file, list only that file
                filename = os.path.basename(gpt4all_model_path)
                # Check if the file extension is one of the known model types
                if any(filename.endswith(ext.replace("*","")) for ext in GPT4ALL_MODEL_EXTENSIONS):
                     formatted_models.append({"value": filename, "label": filename})
                else:
                    log.warning(f"GPT4ALL_MODEL_PATH points to a file, but it does not have a recognized model extension: {filename}")
            elif os.path.isdir(gpt4all_model_path):
                # If the path is a directory, scan for model files
                for ext in GPT4ALL_MODEL_EXTENSIONS:
                    # Ensure path separator is correct for glob
                    search_path = os.path.join(gpt4all_model_path, ext)
                    for model_file in glob.glob(search_path):
                        filename = os.path.basename(model_file)
                        formatted_models.append({"value": filename, "label": filename})
                if not formatted_models:
                    log.info(f"No GPT4All models found in directory: {gpt4all_model_path} with extensions {GPT4ALL_MODEL_EXTENSIONS}")
            else:
                log.warning(f"GPT4ALL_MODEL_PATH '{gpt4all_model_path}' is not a valid file or directory.")

            res.json(formatted_models)

        except Exception as e:
            log.error(f"Error listing GPT4All models from path '{gpt4all_model_path}': {e}")
            res.error(f"An unexpected error occurred while listing GPT4All models: {str(e)}", 500)


class LMStudioListModelsHandler(ApiHandler):
    @classmethod
    def get_route(cls):
        return "/api/lmstudio/models"

    async def process(self, req: Request, res: Response):
        lm_studio_base_url = get_lmstudio_base_url()
        # LM Studio uses an OpenAI compatible API, endpoint is typically /v1/models
        models_api_url = f"{lm_studio_base_url}/v1/models"
        formatted_models = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(models_api_url) as response:
                    response.raise_for_status()  # Raise an exception for HTTP errors
                    data = await response.json()

                    # Expected structure: {"data": [{"id": "model-name-1", ...}, ...]}
                    if "data" in data and isinstance(data["data"], list):
                        for model_info in data["data"]:
                            if "id" in model_info: # LM Studio uses "id" for model name
                                model_id = model_info["id"]
                                formatted_models.append({"value": model_id, "label": model_id})
                        res.json(formatted_models)
                    else:
                        log.error(f"LM Studio API response format unexpected: {data}")
                        res.error("Unexpected response format from LM Studio API", 500)
        except ClientConnectorError:
            log.error(f"Could not connect to LM Studio server at {lm_studio_base_url}. Is it running?")
            res.json([]) # Return empty list for UI consistency
        except ClientResponseError as e:
            log.error(f"Error from LM Studio API: {e.status} {e.message}")
            res.error(f"LM Studio API error: {e.message}", e.status)
        except json.JSONDecodeError:
            log.error("Failed to decode JSON response from LM Studio API")
            res.error("Invalid JSON response from LM Studio API", 500)
        except Exception as e:
            log.error(f"An unexpected error occurred while fetching LM Studio models: {e}")
            res.error(f"An unexpected error occurred: {str(e)}", 500)
