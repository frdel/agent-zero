# Thoughts on Implementing Ollama and OpenRouter Integration

This document outlines the thought process, design decisions, and challenges encountered during the integration of Ollama and OpenRouter free-tier models into Agent Zero.

## Initial Planning & Exploration

*   **Goal**: Allow Agent Zero to use free local LLMs via Ollama and free-tier OpenRouter models.
*   **Codebase Exploration**:
    *   `python/helpers/call_llm.py`: Generic LLM call logic.
    *   `python/helpers/settings.py`: Manages settings, including model providers and UI generation. `convert_out` is key for UI.
    *   `webui/js/settings.js`: Frontend for settings.
    *   `models.py`: Defines `ModelProvider` enum and model instantiation logic. Crucially, Ollama and OpenRouter were already listed as providers and had basic Langchain model getters. This is a huge head start.
    *   `docker/run/docker-compose.yml`: Basic Docker setup for `agent-zero`.
*   **Ollama Research**:
    *   Official Docker image: `ollama/ollama`.
    *   Standard port: `11434`.
    *   Volume for models: `/root/.ollama`.
    *   API for local models: `GET /api/tags`.
    *   API for pulling models: `POST /api/pull`.
*   **OpenRouter Research**:
    *   API for all models: `GET https://openrouter.ai/api/v1/models`.
    *   Authentication: Bearer token.
    *   Free models: Identified by `pricing` fields being "0" in the API response.
    *   Rate limits for free models: 50/day (low credit), 1000/day (>= $10 credit).

## Detailed Plan Outline (Condensed)

1.  **Doc Framework**: Create `THOUGHTS.md`, `diff.md`.
2.  **Ollama Backend/Docker**:
    *   Add `ollama` service to `docker-compose.yml`.
    *   Adjust `OLLAMA_BASE_URL` to use Docker service name (`http://ollama:11434`).
    *   Create Agent Zero API endpoints (`/api/ollama/models`, `/api/ollama/pull`) to interact with Ollama's API.
3.  **Ollama Frontend**:
    *   Modify `settings.py` to add UI elements for Ollama (refresh list, pull model).
    *   Modify `settings.js` to call new Ollama endpoints and update UI.
4.  **OpenRouter API Key**: Ensure user's key is used.
5.  **OpenRouter Frontend (Autocomplete)**:
    *   Create Agent Zero API endpoint (`/api/openrouter/models`) to fetch, filter (free), and return OpenRouter models.
    *   Modify `settings.js` for autocomplete on model name input when OpenRouter is selected.
6.  **Documentation**: Update `THOUGHTS.md`, create `diff.md` (git diff).
7.  **Testing**: Thoroughly test both integrations and existing functionality.
8.  **Submission**.

## Ongoing Thoughts & Potential Challenges

*   **Ollama Model Pulling UI**: Implemented SSE streaming for `POST /api/ollama/pull` from the backend. The frontend JavaScript was updated to consume this stream and display progress messages. This provides better UX than a simple "Pulling..." message.
*   **Error Handling**: Added try-catch blocks in the new API endpoints (`ollama_management.py`, `openrouter_proxy.py`) and in the frontend JavaScript API calls to handle potential errors during HTTP requests or data processing. Error messages are returned as JSON or displayed as toasts.
*   **Security**:
    *   OpenRouter API key is handled via `.env` and the settings UI, which is consistent with other API keys in the project.
    *   The new Agent Zero backend endpoints proxying calls to Ollama and OpenRouter prevent exposure of any sensitive URLs or keys directly to the client.
    *   Authentication for new backend endpoints: Refactored the `requires_auth` decorator into a shared helper (`python/helpers/auth_decorators.py`) and applied it to all new API endpoints to maintain security consistency.
*   **Docker Networking**: `agent-zero` can resolve `ollama` service name due to Docker Compose's default networking. The `OLLAMA_BASE_URL` logic in `models.py` was updated to use `http://ollama:11434` when in Docker.
*   **User Experience (UX)**:
    *   The settings page will have new fields for Ollama management and OpenRouter autocomplete. Conditional display logic (to be implemented with `x-show` in HTML) is crucial to avoid clutter.
    *   Ollama fields are grouped under each model type (chat, util, embed) for contextual relevance.
    *   OpenRouter autocomplete aims to simplify model selection.
*   **`diff.md`**: A raw `git diff` output will be used for this.
*   **OpenRouter Autocomplete**:
    *   The JS logic fetches all free models once and then filters locally for suggestions, which should be performant enough for the expected number of free models.
    *   Suggestions are limited to the top 10 matches.
    *   The UI part (rendering the dropdown) will need careful implementation in the HTML/Alpine templates.
*   **Clarity of "Free"**:
    *   OpenRouter: The UI for autocomplete will implicitly list only free models. It would be good to add a small note in the UI near the OpenRouter model selection indicating that these are free but rate-limited.
    *   Ollama: Clearly "free" once downloaded. The UI allows pulling and listing local models.
*   **Conditional UI in Settings**:
    *   The backend (`settings.py`) now adds Ollama-specific fields to each relevant model section.
    *   The frontend (`settings.js`) includes a placeholder function `toggleOllamaFieldsVisibility` and logic in `handleProviderChange`. The actual show/hide mechanism will rely on Alpine.js `x-show` directives in the HTML template, binding to conditions like `settingsModalProxy.findFieldById(providerPrefix + '_provider').value === 'OLLAMA'`.
    *   Similarly, the OpenRouter autocomplete suggestion list would be shown/hidden based on `activeOpenRouterInputPrefix` and `currentOpenRouterSuggestions.length`.

## Key Implementation Details & Decisions

*   **Auth Decorator Refactoring**: Moved `requires_auth` to `python/helpers/auth_decorators.py` for better modularity and reusability across API endpoint files.
*   **Ollama API Interaction**: Used `httpx` for asynchronous HTTP requests from Agent Zero's backend to the Ollama service.
*   **SSE for Ollama Pull**: Implemented streaming for the `/api/ollama/pull` endpoint in `ollama_management.py` using `stream_with_context` and `text/event-stream` content type. The frontend `pullOllamaModel` function in `settings.js` uses `fetch` to consume this stream.
*   **API Key Management**: Relied on the existing robust API key management in `settings.py` and `dotenv.py` for the OpenRouter key.
*   **Modularity**: New backend logic for Ollama and OpenRouter was placed in separate files (`ollama_management.py`, `openrouter_proxy.py`) and registered as blueprints for better organization.

---
(More thoughts will be added as development progresses)
---
