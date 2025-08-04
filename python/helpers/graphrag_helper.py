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
import logging
from typing import Optional, List

from python.helpers.dotenv import load_dotenv

# Ensure environment variables (.env) are loaded *before* litellm validation
load_dotenv()

from graphrag_sdk.models.litellm import LiteModel  # type: ignore
from graphrag_sdk.model_config import KnowledgeGraphModelConfig  # type: ignore
from graphrag_sdk.kg import KnowledgeGraph  # type: ignore
from graphrag_sdk.ontology import Ontology  # type: ignore
from graphrag_sdk.source import Source_FromRawText, AbstractSource  # type: ignore

logger = logging.getLogger(__name__)

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
        """Ask *question* against the KnowledgeGraph and return the answer with enhanced error handling."""
        # Always try to ensure KG is initialized first
        if self._kg is None:
            # Check if graph data exists using direct query
            if not self._check_graph_has_data():
                raise RuntimeError("Knowledge graph is not initialised – ingest data first.")

            # Try to initialize KG connection to existing graph
            try:
                from graphrag_sdk import KnowledgeGraph
                self._kg = KnowledgeGraph(
                    name=self._graph_name,
                    model_config=self._model_config,
                    host=self._DB_HOST,
                    port=self._DB_PORT,
                )
                logger.info("✅ GraphRAG SDK connection established")
            except Exception as e:
                error_message = str(e)
                logger.debug(f"GraphRAG SDK connection failed: {error_message}")

                # Check if it's a schema compatibility issue
                if "Invalid attribute type" in error_message or "AttributeType" in error_message:
                    # Try clearing just the schema metadata first
                    self._clear_schema_metadata()

                    # Try to connect again
                    try:
                        self._kg = KnowledgeGraph(
                            name=self._graph_name,
                            model_config=self._model_config,
                            host=self._DB_HOST,
                            port=self._DB_PORT,
                        )
                        logger.info("✅ GraphRAG SDK connection established after schema cleanup")

                    except Exception as e2:
                        logger.debug(f"GraphRAG SDK still failed after cleanup: {e2}")
                        # If schema metadata clearing didn't work, fall back to direct query
                        return self._direct_query_fallback(question)

                else:
                    # If SDK connection fails, use direct database fallback
                    return self._direct_query_fallback(question)

        try:
            # Add a simple timeout to prevent hanging on retry loops
            import signal
            import time

            def timeout_handler(signum, frame):
                raise TimeoutError("GraphRAG SDK query timed out")

            # Set a 30-second timeout for GraphRAG SDK queries
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)

            try:
                session = self._kg.chat_session()
                result = session.send_message(question)
            finally:
                signal.alarm(0)  # Cancel the timeout

            # Check if the result is valid
            if isinstance(result, dict):
                # GraphRAG SDK returns response in "response" key, not "answer"
                answer = result.get("response") or result.get("answer")
                if answer and self._is_valid_result(str(answer)):
                    return str(answer)
                elif answer:  # If we have an answer but validation failed, still return it
                    return str(answer)
                else:
                    # If no response/answer key, fall back to the old logic
                    answer = str(result)
                    if self._is_valid_result(answer):
                        return answer

            # If result is not a dict, validate it directly
            elif result and self._is_valid_result(str(result)):
                return str(result)

            # If invalid or problematic result, try fallback
            return self._query_with_fallbacks(question)

        except TimeoutError:
            logger.warning("GraphRAG SDK query timed out, using fallback")
            return self._query_with_fallbacks(question)

        except Exception as e:
            error_message = str(e)

            # Handle specific GraphRAG SDK errors
            if any(error_phrase in error_message for error_phrase in [
                "does not connect",
                "Make sure the relation direction is correct",
                "Failed to generate Cypher query",
                "Invalid attribute type",
                "AttributeType"
            ]):
                # Reset KG instance and try fallback
                self._kg = None
                return self._query_with_fallbacks(question)

            # For other errors, also try fallback
            return self._query_with_fallbacks(question)

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

    def delete_knowledge(self, query: str, preview: bool = True) -> str:
        """Delete knowledge from the knowledge graph based on a query.

        Args:
            query: Natural language description of what to delete
            preview: If True, only shows what would be deleted without actually deleting

        Returns:
            str: Description of what was or would be deleted
        """
        try:
            import redis
            r = redis.Redis(host=self._DB_HOST, port=self._DB_PORT, decode_responses=True)
            r.ping()

            # Extract keywords to identify what to delete
            keywords = self._extract_keywords(query)

            # Generate Cypher queries to find matching data
            deletion_targets = []

            # Strategy 1: Find entities by name containing keywords
            for keyword in keywords:
                try:
                    find_cypher = f"MATCH (n) WHERE toLower(n.name) CONTAINS toLower('{keyword}') RETURN n, labels(n)"
                    result = r.execute_command("GRAPH.QUERY", self._graph_name, find_cypher)

                    if result and result[1]:  # Has data
                        for row in result[1]:
                            if isinstance(row, list) and len(row) >= 2:
                                node_data = row[0]
                                labels = row[1]

                                if isinstance(node_data, list) and len(node_data) >= 3:
                                    properties = node_data[2] if len(node_data) > 2 else []
                                    node_info = {}
                                    if isinstance(properties, list):
                                        for prop in properties:
                                            if isinstance(prop, list) and len(prop) >= 2:
                                                node_info[prop[0]] = prop[1]

                                    deletion_targets.append({
                                        'type': 'node',
                                        'labels': labels,
                                        'properties': node_info,
                                        'keyword': keyword
                                    })

                except Exception as e:
                    continue

            # Strategy 2: Find relationships involving those entities
            relationship_targets = []
            for keyword in keywords:
                try:
                    rel_cypher = f"MATCH (a)-[r]->(b) WHERE toLower(a.name) CONTAINS toLower('{keyword}') OR toLower(b.name) CONTAINS toLower('{keyword}') RETURN a.name, type(r), b.name"
                    result = r.execute_command("GRAPH.QUERY", self._graph_name, rel_cypher)

                    if result and result[1]:
                        for row in result[1]:
                            if isinstance(row, list) and len(row) >= 3:
                                relationship_targets.append({
                                    'type': 'relationship',
                                    'source': row[0],
                                    'relationship': row[1],
                                    'target': row[2],
                                    'keyword': keyword
                                })
                except Exception as e:
                    continue

            if not deletion_targets and not relationship_targets:
                return f"No matching data found for deletion query: '{query}'"

            # Generate summary of what would be deleted
            summary_parts = []

            if deletion_targets:
                nodes_summary = []
                for target in deletion_targets[:5]:  # Limit to first 5 for readability
                    name = target['properties'].get('name', 'Unknown')
                    labels = target['labels'][0] if target['labels'] else 'Node'
                    nodes_summary.append(f"{labels}: {name}")

                if len(deletion_targets) > 5:
                    nodes_summary.append(f"... and {len(deletion_targets) - 5} more nodes")

                summary_parts.append(f"Nodes: {', '.join(nodes_summary)}")

            if relationship_targets:
                rel_summary = []
                for target in relationship_targets[:5]:  # Limit to first 5 for readability
                    rel_summary.append(f"{target['source']}-[{target['relationship']}]->{target['target']}")

                if len(relationship_targets) > 5:
                    rel_summary.append(f"... and {len(relationship_targets) - 5} more relationships")

                summary_parts.append(f"Relationships: {', '.join(rel_summary)}")

            summary = "; ".join(summary_parts)

            if preview:
                return f"DELETION PREVIEW:\nThe following would be deleted: {summary}\n\nTo confirm deletion, set confirm=True"

            # Actually perform the deletion
            deleted_count = 0

            # Delete relationships first (to avoid constraint violations)
            for target in relationship_targets:
                try:
                    delete_rel_cypher = f"MATCH (a {{name: '{target['source']}'}})-[r:{target['relationship']}]->(b {{name: '{target['target']}'}}) DELETE r"
                    result = r.execute_command("GRAPH.QUERY", self._graph_name, delete_rel_cypher)
                    deleted_count += 1
                except Exception as e:
                    continue

            # Delete nodes
            for target in deletion_targets:
                try:
                    name = target['properties'].get('name')
                    if name:
                        labels_str = ':'.join(target['labels']) if target['labels'] else ''
                        delete_node_cypher = f"MATCH (n{':' + labels_str if labels_str else ''} {{name: '{name}'}}) DELETE n"
                        result = r.execute_command("GRAPH.QUERY", self._graph_name, delete_node_cypher)
                        deleted_count += 1
                except Exception as e:
                    continue

            return f"DELETION COMPLETED:\nSuccessfully deleted {deleted_count} items from the knowledge graph.\nDeleted: {summary}"

        except Exception as e:
            return f"Failed to delete knowledge: {e}"

    def reset_graph_schema(self) -> str:
        """Reset the graph to resolve schema conflicts.

        Returns:
            str: Status message about the reset operation
        """
        try:
            import redis
            r = redis.Redis(host=self._DB_HOST, port=self._DB_PORT, decode_responses=True)
            r.ping()

            # Delete the graph completely to reset schema
            try:
                r.execute_command("GRAPH.DELETE", self._graph_name)
            except Exception as e:
                pass  # May not exist

            # Reset the KG instance to force re-initialization
            self._kg = None

            return f"Knowledge graph schema has been reset. The graph '{self._graph_name}' is now empty and ready for fresh data ingestion."

        except Exception as e:
            return f"Failed to reset graph schema: {e}"

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from a deletion query."""
        import re

        keywords = []

        # Extract quoted terms (most specific)
        quoted_terms = re.findall(r'"([^"]*)"', query) + re.findall(r"'([^']*)'", query)
        keywords.extend(quoted_terms)

        # Extract capitalized words (likely entity names)
        capitalized_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
        keywords.extend(capitalized_words)

        # Extract technical terms
        tech_patterns = [
            r'\b\w*(?:Language|language)\b',
            r'\b\w*(?:Framework|framework)\b',
            r'\b\w*(?:Library|library)\b',
            r'\b\w*(?:Tool|tool|Tools)\b',
            r'\b\w*(?:API|api)\b',
            r'\b\w*(?:SDK|sdk)\b'
        ]
        for pattern in tech_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            keywords.extend(matches)

        # Remove duplicates and short terms
        unique_keywords = list(set([kw.strip() for kw in keywords if kw.strip() and len(kw.strip()) > 2]))

        return unique_keywords

    def _check_graph_has_data(self) -> bool:
        """Check if the graph database has any data."""
        try:
            import redis
            r = redis.Redis(host=self._DB_HOST, port=self._DB_PORT, decode_responses=True)
            r.ping()

            # Simple check for any nodes in the graph
            result = r.execute_command("GRAPH.QUERY", self._graph_name, "MATCH (n) RETURN count(n) LIMIT 1")
            if result and len(result) > 1 and result[1]:
                count = result[1][0][0] if result[1] and result[1][0] else 0
                return count > 0
            return False
        except Exception:
            return False

    def _clear_schema_metadata(self) -> None:
        """Clear GraphRAG SDK schema metadata that might be corrupted."""
        try:
            import redis
            r = redis.Redis(host=self._DB_HOST, port=self._DB_PORT, decode_responses=True)
            r.ping()

            # Clear GraphRAG SDK metadata keys that might contain corrupted schema
            schema_key = f"{{{self._graph_name}}}_schema"
            telemetry_key = f"telemetry{{{self._graph_name}}}"

            try:
                r.delete(schema_key)
            except Exception:
                pass

            try:
                r.delete(telemetry_key)
            except Exception:
                pass

        except Exception:
            pass

    def _is_valid_result(self, answer: str) -> bool:
        """Check if the query result is valid and useful."""
        if not answer or len(answer.strip()) < 3:
            return False

        # Check for common error patterns
        error_patterns = [
            "failed to generate",
            "does not connect",
            "relation direction",
            "invalid attribute",
            "no data found"
        ]

        answer_lower = answer.lower()
        for pattern in error_patterns:
            if pattern in answer_lower:
                return False

        return True

    def _query_with_fallbacks(self, question: str) -> str:
        """Try alternative query strategies when the main GraphRAG SDK fails."""
        try:
            # Try direct database fallback
            return self._direct_query_fallback(question)
        except Exception as e:
            return f"Unable to query the knowledge graph: {e}"


    def _direct_query_fallback(self, question: str) -> str:
        """Direct database query fallback when GraphRAG SDK fails."""
        try:
            import redis
            r = redis.Redis(host=self._DB_HOST, port=self._DB_PORT, decode_responses=True)
            r.ping()

            # Extract keywords from the question
            keywords = self._extract_keywords(question)

            if not keywords:
                # If no keywords, try to get any data by searching for common properties
                keywords = [""]

            results = []

            # Strategy 1: Find nodes by name containing keywords
            for keyword in keywords:
                try:
                    if keyword:
                        cypher = f"MATCH (n) WHERE toLower(n.name) CONTAINS toLower('{keyword}') RETURN n, labels(n) LIMIT 5"
                    else:
                        cypher = "MATCH (n) RETURN n, labels(n) LIMIT 5"

                    result = r.execute_command("GRAPH.QUERY", self._graph_name, cypher)

                    if result and result[1]:
                        for row in result[1]:
                            if isinstance(row, list) and len(row) >= 2:
                                node_data = row[0]
                                labels = row[1]

                                if isinstance(node_data, list) and len(node_data) >= 3:
                                    # Properties are in format ['properties', [['name', 'value'], ...]]
                                    properties_section = node_data[2] if len(node_data) > 2 else []
                                    node_info = {}
                                    if isinstance(properties_section, list) and len(properties_section) >= 2:
                                        if properties_section[0] == 'properties' and isinstance(properties_section[1], list):
                                            for prop in properties_section[1]:
                                                if isinstance(prop, list) and len(prop) >= 2:
                                                    node_info[prop[0]] = prop[1]

                                    # Labels are in format '[Person]' (string) - need to clean them
                                    if labels:
                                        label_raw = str(labels)
                                        # Remove brackets and quotes: '[Person]' -> 'Person'
                                        label_str = label_raw.strip("[]'\"")
                                    else:
                                        label_str = "Node"
                                    name = node_info.get('name', 'Unknown')
                                    results.append(f"{label_str}: {name}")

                except Exception as e:
                    continue

            if results:
                unique_results = list(set(results))

                # Try to get relationship information for found entities
                enhanced_results = []
                for result in unique_results[:5]:  # Limit to avoid too much data
                    enhanced_results.append(result)

                    # Extract entity name from result (format: "Label: Name")
                    if ":" in result:
                        entity_name = result.split(":", 1)[1].strip()

                        try:
                            # Find relationships for this entity
                            rel_query = f"MATCH (n)-[r]-(m) WHERE n.name = '{entity_name}' OR n.title = '{entity_name}' RETURN type(r), m, labels(m) LIMIT 3"
                            rel_result = r.execute_command("GRAPH.QUERY", self._graph_name, rel_query)

                            if rel_result and rel_result[1]:
                                for rel_row in rel_result[1]:
                                    if isinstance(rel_row, list) and len(rel_row) >= 3:
                                        rel_type = rel_row[0]
                                        connected_node = rel_row[1]
                                        connected_labels = rel_row[2]

                                        # Parse connected entity
                                        if isinstance(connected_node, list) and len(connected_node) >= 3:
                                            conn_props_section = connected_node[2]
                                            conn_info = {}
                                            if isinstance(conn_props_section, list) and len(conn_props_section) >= 2:
                                                if conn_props_section[0] == 'properties':
                                                    for prop in conn_props_section[1]:
                                                        if isinstance(prop, list) and len(prop) >= 2:
                                                            conn_info[prop[0]] = prop[1]

                                            conn_label = str(connected_labels).strip("[]'\"")
                                            conn_name = conn_info.get('name', conn_info.get('title', conn_info.get('description', 'Unknown')))
                                            enhanced_results.append(f"  {rel_type} → {conn_label}: {conn_name}")
                        except Exception:
                            continue

                return f"Found information: {', '.join(enhanced_results[:15])}"
            else:
                # If no specific matches, try to get any available data with relationships
                try:
                    any_data_result = r.execute_command("GRAPH.QUERY", self._graph_name, "MATCH (n) RETURN n, labels(n) LIMIT 5")
                    if any_data_result and any_data_result[1]:
                        any_results = []
                        for row in any_data_result[1]:
                            if isinstance(row, list) and len(row) >= 2:
                                node_data = row[0]
                                labels = row[1]

                                if isinstance(node_data, list) and len(node_data) >= 3:
                                    # Properties are in format ['properties', [['name', 'value'], ...]]
                                    properties_section = node_data[2] if len(node_data) > 2 else []
                                    node_info = {}
                                    if isinstance(properties_section, list) and len(properties_section) >= 2:
                                        if properties_section[0] == 'properties' and isinstance(properties_section[1], list):
                                            for prop in properties_section[1]:
                                                if isinstance(prop, list) and len(prop) >= 2:
                                                    node_info[prop[0]] = prop[1]

                                    # Labels are in format '[Person]' (string) - need to clean them
                                    if labels:
                                        label_raw = str(labels)
                                        # Remove brackets and quotes: '[Person]' -> 'Person'
                                        label_str = label_raw.strip("[]'\"")
                                    else:
                                        label_str = "Node"
                                    name = node_info.get('name', node_info.get('title', 'Unknown'))
                                    any_results.append(f"{label_str}: {name}")

                        if any_results:
                            return f"Available data in graph: {', '.join(any_results[:10])}"

                except Exception:
                    pass

                return "No relevant information found in the knowledge graph."

        except Exception as e:
            return f"Knowledge graph query failed: {e}"

    # -------------------------------------------------------------- singleton
    @classmethod
    def get_default(cls) -> "GraphRAGHelper":
        """Return a singleton helper instance shared across the application."""
        if cls._default_instance is None:
            with cls._lock:
                if cls._default_instance is None:
                    cls._default_instance = GraphRAGHelper()
        return cls._default_instance
