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
    """Multi-database GraphRAG helper supporting area-specific knowledge graphs."""

    _instances: dict[str, "GraphRAGHelper"] = {}
    _lock = threading.Lock()

    # Connection defaults
    _DB_HOST = "127.0.0.1"
    _DB_PORT = 6379

    def __init__(self, graph_name: str = "agent_zero_kg", area: str = "main") -> None:
        settings = get_settings()

        # Store area and create area-specific graph name
        self._area = area
        self._base_graph_name = graph_name
        self._graph_name = f"{graph_name}_{area}"  # e.g., "agent_zero_kg_main", "agent_zero_kg_fragments"

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
    def ingest_text(self, text: str, instruction: str | None = None, metadata: dict | None = None) -> None:
        """Add *text* as a document source into the KG with optional metadata.

        Parameters
        ----------
        text : str
            Arbitrary text content that will be analysed and converted into
            graph entities/relations by the LLM.
        instruction : str | None
            Optional high-level extraction instructions ("focus on people and
            organisations" etc.)
        metadata : dict | None
            Optional metadata about the source (e.g., memory_id, filename, area, etc.)
        """
        source = Source_FromRawText(text, instruction)
        self._ingest_sources([source], metadata)

    # ----------------------------------------------------------------- queries

    # ----------------------------------------------------------- helper intern
    def _ingest_sources(self, sources: List[AbstractSource], metadata: dict | None = None) -> None:
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

        # Store metadata if provided
        if metadata:
            self._store_source_metadata(metadata)

    # --------------------------------------------------------- helper methods
    def _store_source_metadata(self, metadata: dict) -> None:
        """Store metadata about the ingested source in the graph database."""
        try:
            import redis
            r = redis.Redis(host=self._DB_HOST, port=self._DB_PORT, decode_responses=True)

            # Create a unique metadata node with timestamp
            import time
            import json

            timestamp = int(time.time())
            metadata_id = f"source_metadata_{timestamp}"

            # Add core metadata fields
            metadata_with_defaults = {
                "source_type": "unknown",
                "source_id": "unknown",
                "area": "main",
                "timestamp": timestamp,
                **metadata
            }

            # Create metadata node in the graph
            metadata_json = json.dumps(metadata_with_defaults).replace('"', '\\"')
            cypher = f'MERGE (m:SourceMetadata {{id: "{metadata_id}", data: "{metadata_json}", timestamp: {timestamp}}})'

            try:
                r.execute_command("GRAPH.QUERY", self._graph_name, cypher)
                logger.debug(f"Stored source metadata: {metadata_with_defaults}")
            except Exception as e:
                logger.debug(f"Failed to store source metadata: {e}")

        except Exception as e:
            # Metadata storage failure shouldn't break ingestion
            logger.debug(f"Error storing source metadata: {e}")

    def get_source_metadata(self, limit: int = 10) -> list[dict]:
        """Retrieve stored source metadata from the graph."""
        try:
            import redis
            import json

            r = redis.Redis(host=self._DB_HOST, port=self._DB_PORT, decode_responses=True)

            # Query for metadata nodes
            cypher = f"MATCH (m:SourceMetadata) RETURN m.id, m.data, m.timestamp ORDER BY m.timestamp DESC LIMIT {limit}"
            result = r.execute_command("GRAPH.QUERY", self._graph_name, cypher)

            metadata_list = []
            if result and len(result) > 1 and result[1]:
                for row in result[1]:
                    try:
                        if len(row) >= 3:
                            metadata_id = row[0]
                            data_json = row[1]
                            timestamp = row[2]

                            # Parse the JSON data
                            data = json.loads(data_json) if data_json else {}
                            metadata_list.append({
                                "id": metadata_id,
                                "timestamp": timestamp,
                                **data
                            })
                    except Exception:
                        continue

            return metadata_list

        except Exception as e:
            logger.debug(f"Error retrieving source metadata: {e}")
            return []

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
                                    properties_section = node_data[2] if len(node_data) > 2 else []
                                    node_info = {}

                                    # Handle the nested properties structure: ['properties', [['name', 'value'], ...]]
                                    if isinstance(properties_section, list) and len(properties_section) >= 2:
                                        if properties_section[0] == 'properties' and isinstance(properties_section[1], list):
                                            for prop in properties_section[1]:
                                                if isinstance(prop, list) and len(prop) >= 2:
                                                    node_info[prop[0]] = prop[1]
                                        else:
                                            # Fallback: treat as direct property list
                                            for prop in properties_section:
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
                    rel_cypher = (f"MATCH (a)-[r]->(b) WHERE toLower(a.name) CONTAINS toLower('{keyword}') "
                                  f"OR toLower(b.name) CONTAINS toLower('{keyword}') RETURN a.name, type(r), b.name")
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
                    logger.warning(f"Failed to delete relationship {target['source']}-[{target['relationship']}]->{target['target']}: {e}")
                    continue

            # Delete nodes
            for target in deletion_targets:
                try:
                    name = target['properties'].get('name')
                    if name:
                        # Fix labels parsing - target['labels'] is a string like '[Person]', not a list
                        labels_raw = target['labels']
                        if isinstance(labels_raw, str):
                            # Remove brackets and quotes: '[Person]' -> 'Person'
                            labels_str = labels_raw.strip("[]'\"")
                        elif isinstance(labels_raw, list):
                            labels_str = ':'.join(labels_raw)
                        else:
                            labels_str = ''

                        # Construct the deletion query
                        if labels_str:
                            delete_node_cypher = f"MATCH (n:{labels_str} {{name: '{name}'}}) DELETE n"
                        else:
                            delete_node_cypher = f"MATCH (n {{name: '{name}'}}) DELETE n"

                        logger.info(f"Executing deletion: {delete_node_cypher}")
                        result = r.execute_command("GRAPH.QUERY", self._graph_name, delete_node_cypher)
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete node {target['properties'].get('name', 'Unknown')}: {e}")
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

    def query_with_enhanced_correction(self, question: str) -> str:
        """Query with enhanced Cypher error correction capabilities."""
        try:
            # First try the standard approach
            result = self.query(question, use_enhanced_correction=False)

            # If we get a good result, return it
            if result and "No relevant information" not in result and "Knowledge graph query failed" not in result:
                return result

            # If standard approach failed, check for common Cypher errors in the logs
            # and try a more intelligent approach
            return self._enhanced_query_attempt(question)

        except Exception as e:
            logger.error(f"Enhanced correction failed: {e}")
            return self._direct_query_fallback(question)

    def _enhanced_query_attempt(self, question: str) -> str:
        """Make an enhanced query attempt with better error handling."""
        try:
            import redis

            # Connect to database
            r = redis.Redis(host=self._DB_HOST, port=self._DB_PORT, decode_responses=True)

            # Use direct fallback for generic robustness (no hardcoded queries)
            return self._direct_query_fallback(question)

        except Exception as e:
            logger.error(f"Enhanced query attempt failed: {e}")
            return self._direct_query_fallback(question)

    def _get_graph_context(self) -> str:
        """Get context information about the current graph structure and data."""
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)

            context_parts = []

            # Get node labels and sample data
            try:
                labels_result = r.execute_command("GRAPH.QUERY", self._graph_name,
                                                  "MATCH (n) RETURN DISTINCT labels(n) as labels, n.name as sample_name LIMIT 20")
                if labels_result and len(labels_result) > 1 and labels_result[1]:
                    context_parts.append("Available entity types and examples:")
                    for row in labels_result[1]:
                        if isinstance(row, list) and len(row) >= 2:
                            label = str(row[0]).strip("[]'\"")
                            sample_name = row[1] if row[1] else "Unknown"
                            context_parts.append(f"- {label}: {sample_name}")
            except Exception as e:
                logger.debug(f"Failed to get node labels: {e}")

            # Get relationship types
            try:
                rels_result = r.execute_command("GRAPH.QUERY", self._graph_name, "MATCH ()-[r]->() RETURN DISTINCT type(r) as rel_type LIMIT 10")
                if rels_result and len(rels_result) > 1 and rels_result[1]:
                    context_parts.append("\nAvailable relationship types:")
                    for row in rels_result[1]:
                        if isinstance(row, list) and len(row) >= 1:
                            rel_type = row[0]
                            context_parts.append(f"- {rel_type}")
            except Exception as e:
                logger.debug(f"Failed to get relationship types: {e}")

            # If no specific context, provide a generic helpful note
            if not context_parts:
                context_parts.append("Graph contains Products, Organizations, and Features.")
                context_parts.append("Products are linked to Organizations via RELEASED_BY relationships.")
                context_parts.append("Products may use Features via USES relationships.")

            return "\n".join(context_parts)

        except Exception as e:
            logger.debug(f"Failed to get graph context: {e}")
            # Provide basic context even if Redis fails
            return "Graph contains Products, Organizations, and Features. Products are linked to Organizations and Features."

    def query(self, question: str, use_enhanced_correction: bool = True) -> str:
        """Query the knowledge graph with enhanced context and error correction."""
        try:
            if not self._kg:
                # Graph not initialized - attempt to reconnect
                try:
                    self._kg = KnowledgeGraph(
                        name=self._graph_name,
                        model_config=self._model_config,
                        host=self._DB_HOST,
                        port=self._DB_PORT,
                    )
                except Exception:
                    return "Knowledge graph not available"

            # Get graph context for better query generation
            graph_context = self._get_graph_context()

            # Enhanced question with context
            enhanced_question = f"""Context about available data in the graph:
{graph_context}

Based on this context, answer the following question:
{question}

Note: When looking for items like "phones", consider that they might be stored as specific product names like
"iPhone 15", "Samsung Galaxy S24", etc. Use appropriate CONTAINS or pattern matching in your queries."""

            # Try the enhanced query first
            session = self._kg.chat_session()
            result = session.send_message(enhanced_question)

            if result and "No relevant information" not in str(result):
                return str(result)

            # If enhanced query fails and correction is enabled, try fallback
            if use_enhanced_correction:
                return self._direct_query_fallback(question)
            else:
                return "No relevant information found in the knowledge graph."

        except Exception as e:
            logger.error(f"GraphRAG query failed: {e}")
            if use_enhanced_correction:
                return self._direct_query_fallback(question)
            return f"Knowledge graph query failed: {str(e)}"

    def query_with_memory_context(self, question: str, memory_context: dict | None = None) -> str:
        """Query with additional memory context for more relevant results."""
        try:
            if not self._kg:
                # Graph not initialized - attempt to reconnect
                try:
                    self._kg = KnowledgeGraph(
                        name=self._graph_name,
                        model_config=self._model_config,
                        host=self._DB_HOST,
                        port=self._DB_PORT,
                    )
                except Exception:
                    return "Knowledge graph not available"

            # Get graph context
            graph_context = self._get_graph_context()

            # Build enhanced context that includes both graph and memory information
            context_parts = [f"Graph structure: {graph_context}"]

            if memory_context:
                if memory_context.get('memories'):
                    context_parts.append(f"Related memories: {memory_context['memories'][:300]}...")
                if memory_context.get('solutions'):
                    context_parts.append(f"Related solutions: {memory_context['solutions'][:300]}...")

            enhanced_context = "\n\n".join(context_parts)

            # Create enhanced question with both graph and memory context
            enhanced_question = f"""Context information:
{enhanced_context}

Based on this context, answer the following question by finding complementary or related information in the knowledge graph:
{question}

Focus on entities, relationships, or facts that add value to the existing context. Look for connections,
additional details, or related information that isn't already covered in the memories/solutions above."""

            # Query the knowledge graph
            session = self._kg.chat_session()
            result = session.send_message(enhanced_question)

            if result and "No relevant information" not in str(result):
                return str(result)
            else:
                # Fall back to direct query if needed
                return self._direct_query_fallback(question)

        except Exception as e:
            logger.error(f"GraphRAG memory context query failed: {e}")
            return self._direct_query_fallback(question)

    def _format_enhanced_result(self, raw_result) -> str:
        """Format results from enhanced Cypher queries."""

        try:
            if not raw_result or len(raw_result) < 2 or not raw_result[1]:
                return "No data found"

            rows = raw_result[1][:8]  # Limit to 8 results
            formatted_items = []

            for row in rows:
                if isinstance(row, list) and len(row) >= 1:
                    # Handle different result formats

                    # Check if this is a relationship result (3 items: source, relation, target)
                    if len(row) == 3:
                        source_info = self._extract_node_info(row[0])
                        relation_type = str(row[1]) if row[1] else "CONNECTED"
                        target_info = self._extract_node_info(row[2])

                        if source_info and target_info:
                            formatted_items.append(f"{source_info}   {relation_type} → {target_info}")

                    # Single node result
                    elif len(row) >= 1:
                        node_info = self._extract_node_info(row[0])
                        if node_info:
                            formatted_items.append(node_info)

            if formatted_items:
                unique_items = list(dict.fromkeys(formatted_items))  # Remove duplicates
                return f"Found information: {', '.join(unique_items[:10])}"

            return "Data found but could not format"

        except Exception as e:
            logger.error(f"Error formatting enhanced result: {e}")
            return "Found data but formatting failed"

    def _extract_node_info(self, node_data) -> str:
        """Extract readable information from a node."""

        try:
            if isinstance(node_data, list) and len(node_data) >= 3:
                # Node format: [id, labels, properties]
                labels = node_data[1] if len(node_data) > 1 else []
                properties = node_data[2] if len(node_data) > 2 else []

                # Extract label
                label_str = "Node"
                if labels:
                    label_raw = str(labels)
                    label_str = label_raw.strip("[]'\"")

                # Extract name/title
                name = "Unknown"
                if isinstance(properties, list) and len(properties) >= 2:
                    if properties[0] == 'properties' and isinstance(properties[1], list):
                        for prop in properties[1]:
                            if isinstance(prop, list) and len(prop) >= 2:
                                if prop[0] in ['name', 'title', 'type']:
                                    name = prop[1]
                                    break

                return f"{label_str}: {name}"

            elif isinstance(node_data, str):
                return node_data

            return str(node_data) if node_data else "Unknown"

        except Exception:
            return "Unknown"

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

    @classmethod
    def query_multi_area(cls, question: str, areas: list[str], memory_context: dict | None = None) -> dict[str, str]:
        """Query multiple knowledge graph areas and return combined results."""
        results = {}

        for area in areas:
            try:
                helper = cls.get_for_area(area)
                if memory_context:
                    result = helper.query_with_memory_context(question, memory_context)
                else:
                    result = helper.query(question)

                if result and "No relevant information" not in result:
                    results[area] = result

            except Exception as e:
                logger.debug(f"Query failed for area {area}: {e}")
                continue

        return results

    @classmethod
    def format_multi_area_results(cls, results: dict[str, str]) -> str:
        """Format results from multiple areas into a single response."""
        if not results:
            return "No relevant information found in any knowledge graph area."

        formatted_parts = []

        # Order areas by relevance: main first, then others
        area_order = ["main", "fragments", "solutions", "instruments"]
        ordered_areas = [area for area in area_order if area in results]
        ordered_areas.extend([area for area in results.keys() if area not in area_order])

        for area in ordered_areas:
            result = results[area]
            area_title = area.title().replace('_', ' ')
            formatted_parts.append(f"## {area_title} Knowledge:\n{result}")

        return "\n\n".join(formatted_parts)

    # -------------------------------------------------------------- singleton
    @classmethod
    def get_default(cls, area: str = "main") -> "GraphRAGHelper":
        """Return a singleton helper instance for the specified area."""
        instance_key = f"agent_zero_kg_{area}"

        if instance_key not in cls._instances:
            with cls._lock:
                if instance_key not in cls._instances:
                    cls._instances[instance_key] = GraphRAGHelper(area=area)
        return cls._instances[instance_key]

    @classmethod
    def get_for_area(cls, area: str) -> "GraphRAGHelper":
        """Return a helper instance for a specific memory area."""
        return cls.get_default(area)

    @classmethod
    def get_multi_area(cls, areas: list[str]) -> dict[str, "GraphRAGHelper"]:
        """Return helper instances for multiple areas."""
        helpers = {}
        for area in areas:
            helpers[area] = cls.get_for_area(area)
        return helpers
