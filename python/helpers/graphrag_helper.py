"""GraphRag integration helper.

This helper bridges Agent Zero's litellm powered model stack with the GraphRAG
SDK so that knowledge graphs can be created, populated and queried using the
same model configuration that is already defined in Agent Zero `settings`.

Key features
------------
1. Uses the same chat model as configured for the agent (provider/name/api_base)
   so NO additional model credentials have to be configured – they are read
   from the existing .env file by litellm.
2. Creates a FalkorDB-backed `KnowledgeGraph` on the local Redis/FalkorDB
   instance (default `localhost:6379`).
3. Automatically bootstraps a *dynamic ontology* from the first ingested
   sources. Subsequent ingestions extend the existing ontology.
4. Simple, synchronous public methods:
     • `ingest_text(text[, instruction])`
     • `query(question) -> str`

A **singleton** instance is exposed via `GraphRAGHelper.get_default()` so tools
can share the same underlying KnowledgeGraph connection.
"""
from __future__ import annotations

import os
import threading
from typing import Optional, List

from python.helpers.dotenv import load_dotenv

# Ensure environment variables (.env) are loaded *before* litellm validation
load_dotenv()

from graphrag_sdk.models.litellm import LiteModel  # type: ignore
from graphrag_sdk.model_config import KnowledgeGraphModelConfig  # type: ignore
from graphrag_sdk.kg import KnowledgeGraph  # type: ignore
from graphrag_sdk.ontology import Ontology  # type: ignore
from graphrag_sdk.source import Source_FromRawText, AbstractSource  # type: ignore

from python.helpers.settings import get_settings  # Agent Zero settings helper


class GraphRAGHelper:
    """Singleton helper around a GraphRAG `KnowledgeGraph`."""

    _default_instance: "GraphRAGHelper | None" = None
    _lock = threading.Lock()

    # Connection defaults
    _DB_HOST = "127.0.0.1"
    _DB_PORT = 6379

    def __init__(self, graph_name: str = "agent_zero_kg") -> None:
        settings = get_settings()

        # Build litellm model identifier
        provider = settings["chat_model_provider"].strip()
        model_name = settings["chat_model_name"].strip()

        # Build proper litellm model identifier
        # For openrouter, we need to use openrouter/ prefix so litellm routes correctly
        if provider.lower() == "openrouter":
            self._full_model_name = f"openrouter/{model_name}"
        else:
            self._full_model_name = f"{provider}/{model_name}"



        # Additional LiteLLM keyword arguments (api_base etc.)
        additional_params: dict = {}
        api_base = settings.get("chat_model_api_base", "")
        if api_base:
            additional_params["api_base"] = api_base
        # Merge custom kwargs from settings (already a dict)
        chat_kwargs = settings.get("chat_model_kwargs", {}) or {}
        # Convert string values to proper types for OpenRouter compatibility
        for key, value in chat_kwargs.items():
            if key == "temperature" and isinstance(value, str):
                try:
                    chat_kwargs[key] = float(value)
                except ValueError:
                    pass
        additional_params.update(chat_kwargs)

        # Ensure proper API key mapping for all providers
        self._setup_api_keys(provider)

        # Add provider-specific configurations
        if provider.lower() == "openrouter":
            additional_params["extra_headers"] = {
                "HTTP-Referer": "https://agent-zero.ai",
                "X-Title": "Agent Zero",
            }

        # Instantiate LiteModel (this validates presence of env keys)
        self._llm_model = LiteModel(model_name=self._full_model_name,
                                    additional_params=additional_params)

        # Re-use the same model for all GraphRAG tasks (extract, cypher, QA)
        self._model_config = KnowledgeGraphModelConfig.with_model(self._llm_model)

        self._graph_name = graph_name
        self._kg: Optional[KnowledgeGraph] = None

        # Try to connect to an existing graph (and its ontology).  If that
        # fails because the ontology is empty, we will lazily create the graph
        # on the first ingestion call.
        try:
            self._kg = KnowledgeGraph(
                name=self._graph_name,
                model_config=self._model_config,
                host=self._DB_HOST,
                port=self._DB_PORT,
            )
        except Exception:
            # Graph not created yet – defer creation until we have sources/ontology
            self._kg = None

    # ------------------------------------------------------------------ public
    def ingest_text(self, text: str, instruction: str | None = None) -> None:
        """Add *text* as a document source into the KG.

        Parameters
        ----------
        text : str
            Arbitrary text content that will be analysed and converted into
            graph entities/relations by the LLM.
        instruction : str | None
            Optional high-level extraction instructions ("focus on people and
            organisations" etc.)
        """
        source = Source_FromRawText(text, instruction)
        self._ingest_sources([source])

    # ----------------------------------------------------------------- queries
    def query(self, question: str) -> str:
        """Ask *question* against the KnowledgeGraph and return the answer."""
        if self._kg is None:
            raise RuntimeError("Knowledge graph is not initialised – ingest data first.")

        session = self._kg.chat_session()
        result = session.send_message(question)
        # `send_message` returns a dict {"answer": str, ...} according to SDK.
        # We'll try to pull the answer key first, else str(result).
        if isinstance(result, dict) and "answer" in result:
            return str(result["answer"])
        return str(result)

    # ----------------------------------------------------------- helper intern
    def _ingest_sources(self, sources: List[AbstractSource]) -> None:
        """Internal method that makes sure the KG exists and processes sources."""
        if self._kg is None:
            # Build ontology dynamically from the *first* batch of sources
            ontology = Ontology.from_sources(sources, model=self._llm_model)
            self._kg = KnowledgeGraph(
                name=self._graph_name,
                model_config=self._model_config,
                ontology=ontology,
                host=self._DB_HOST,
                port=self._DB_PORT,
            )
        # Add knowledge from sources into graph
        self._kg.process_sources(sources)

    # --------------------------------------------------------- helper methods
    def _setup_api_keys(self, provider: str) -> None:
        """Ensure the correct API keys are available for the specified provider.

        This method maps Agent Zero's .env API key naming conventions to the
        environment variables that litellm expects for each provider.
        """
        from python.helpers.dotenv import get_dotenv_value

        provider_lower = provider.lower()

        # Define the mapping from Agent Zero's API key naming to litellm's expected env vars
        api_key_mappings = {
            "openrouter": {
                "a0_keys": ["API_KEY_OPENROUTER", "OPENROUTER_API_KEY"],
                "litellm_keys": ["OPENROUTER_API_KEY"]
            },
            "openai": {
                "a0_keys": ["API_KEY_OPENAI", "OPENAI_API_KEY"],
                "litellm_keys": ["OPENAI_API_KEY"]
            },
            "anthropic": {
                "a0_keys": ["API_KEY_ANTHROPIC", "ANTHROPIC_API_KEY"],
                "litellm_keys": ["ANTHROPIC_API_KEY"]
            },
            "google": {
                "a0_keys": ["API_KEY_GOOGLE", "GOOGLE_API_KEY", "GEMINI_API_KEY"],
                "litellm_keys": ["GOOGLE_API_KEY", "GEMINI_API_KEY"]
            },
            "cohere": {
                "a0_keys": ["API_KEY_COHERE", "COHERE_API_KEY"],
                "litellm_keys": ["COHERE_API_KEY"]
            },
            "huggingface": {
                "a0_keys": ["API_KEY_HUGGINGFACE", "HUGGINGFACE_API_KEY"],
                "litellm_keys": ["HUGGINGFACE_API_KEY"]
            },
            "azure": {
                "a0_keys": ["API_KEY_AZURE", "AZURE_API_KEY"],
                "litellm_keys": ["AZURE_API_KEY"]
            }
        }

        # Get the mapping for this provider
        mapping = api_key_mappings.get(provider_lower)
        if not mapping:
            # For unknown providers, try common patterns
            mapping = {
                "a0_keys": [f"API_KEY_{provider.upper()}", f"{provider.upper()}_API_KEY"],
                "litellm_keys": [f"{provider.upper()}_API_KEY"]
            }

        # Find the API key from Agent Zero's naming conventions
        api_key = None
        for key_name in mapping["a0_keys"]:
            api_key = get_dotenv_value(key_name)
            if api_key and api_key != "None":
                break

        if not api_key:
            # No API key found - let litellm handle the error
            return

        # Set the API key for all environment variables that litellm might check
        for env_var in mapping["litellm_keys"]:
            os.environ[env_var] = api_key

        # Special case: For openrouter, also set OPENAI_API_KEY if the model name suggests OpenAI
        # This handles cases where model name is "openai/gpt-4" but provider is openrouter
        if provider_lower == "openrouter" and "/" in self._full_model_name:
            model_prefix = self._full_model_name.split("/")[1].split("/")[0]  # Extract "openai" from "openrouter/openai/gpt-4"
            if model_prefix in ["openai"]:
                os.environ["OPENAI_API_KEY"] = api_key

    # -------------------------------------------------------------- singleton
    @classmethod
    def get_default(cls) -> "GraphRAGHelper":
        """Return a singleton helper instance shared across the application."""
        if cls._default_instance is None:
            with cls._lock:
                if cls._default_instance is None:
                    cls._default_instance = GraphRAGHelper()
        return cls._default_instance
