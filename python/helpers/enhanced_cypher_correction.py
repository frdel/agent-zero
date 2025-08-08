"""
Enhanced Cypher Correction for GraphRAG
========================================

Provides intelligent Cypher query correction by analyzing errors
and giving specific guidance to the LLM for fixing syntax and logic issues.
"""

import re
import logging
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

class CypherErrorCorrector:
    """Intelligent Cypher error correction system."""

    def __init__(self, agent):
        self.agent = agent
        self.max_correction_attempts = 3

    async def correct_cypher_with_guidance(
        self,
        original_question: str,
        failed_cypher: str,
        error_message: str,
        ontology: Dict,
        attempt_number: int = 1
    ) -> Optional[str]:
        """
        Attempt to correct a failed Cypher query by providing specific guidance to the LLM.

        Args:
            original_question: The original natural language question
            failed_cypher: The Cypher query that failed
            error_message: The specific error message from the database
            ontology: The current graph ontology (entities and relationships)
            attempt_number: Current attempt number (for limiting retries)

        Returns:
            Corrected Cypher query or None if unable to correct
        """

        if attempt_number > self.max_correction_attempts:
            logger.warning(f"Max correction attempts ({self.max_correction_attempts}) reached")
            return None

        # Analyze the error and generate specific correction guidance
        correction_guidance = self._analyze_error_and_generate_guidance(
            failed_cypher, error_message, ontology
        )

        if not correction_guidance:
            logger.warning(f"Could not generate correction guidance for error: {error_message}")
            return None

        # Create a prompt for the LLM to correct the Cypher
        correction_prompt = self._build_correction_prompt(
            original_question, failed_cypher, error_message, correction_guidance, ontology
        )

        try:
            # Call the LLM to generate a corrected Cypher query
            corrected_cypher = await self.agent.call_utility_model(
                system="You are a Cypher query expert. Your task is to fix broken Cypher queries based on specific error guidance.",
                message=correction_prompt,
                background=True
            )

            # Clean up the response (remove code blocks, etc.)
            corrected_cypher = self._clean_cypher_response(corrected_cypher)

            if corrected_cypher and corrected_cypher != failed_cypher:
                logger.info(f"Generated corrected Cypher (attempt {attempt_number}): {corrected_cypher}")
                return corrected_cypher
            else:
                logger.warning(f"LLM returned same or empty Cypher on attempt {attempt_number}")
                return None

        except Exception as e:
            logger.error(f"Error during Cypher correction attempt {attempt_number}: {e}")
            return None

    def _analyze_error_and_generate_guidance(
        self,
        failed_cypher: str,
        error_message: str,
        ontology: Dict
    ) -> Optional[str]:
        """Analyze the specific error and generate targeted guidance for correction."""

        error_lower = error_message.lower()

        # Pattern 1: Relationship direction errors
        if "does not connect" in error_lower and "make sure the relation direction is correct" in error_lower:
            return self._generate_relationship_direction_guidance(failed_cypher, error_message, ontology)

        # Pattern 2: UNION query errors
        elif "union must have the same column names" in error_lower:
            return self._generate_union_correction_guidance(failed_cypher)

        # Pattern 3: Invalid property access
        elif "property" in error_lower and ("does not exist" in error_lower or "not found" in error_lower):
            return self._generate_property_correction_guidance(failed_cypher, ontology)

        # Pattern 4: Syntax errors
        elif "syntax error" in error_lower or "invalid" in error_lower:
            return self._generate_syntax_correction_guidance(failed_cypher, error_message)

        # Pattern 5: Multiple statement errors
        elif "more than one statement" in error_lower:
            return "The query contains multiple statements. Use only a single Cypher statement. Remove any semicolons and combine into one query."

        # General error
        else:
            return f"Fix this Cypher error: {error_message}. Focus on: 1) Correct relationship directions, 2) Valid property names, 3) Proper syntax."

    def _generate_relationship_direction_guidance(
        self,
        failed_cypher: str,
        error_message: str,
        ontology: Dict
    ) -> str:
        """Generate specific guidance for relationship direction errors."""

        # Extract the problematic relationship from the error message
        relation_match = re.search(r'Relation (\w+) does not connect (\w+) to (\w+)', error_message)

        if relation_match:
            relation_name = relation_match.group(1)
            wrong_source = relation_match.group(2)
            wrong_target = relation_match.group(3)

            # Find the correct direction from ontology
            correct_direction = None
            if 'relations' in ontology:
                for rel in ontology['relations']:
                    if rel.get('label') == relation_name:
                        correct_source = rel.get('source', {}).get('label', 'Unknown')
                        correct_target = rel.get('target', {}).get('label', 'Unknown')
                        correct_direction = f"({correct_source})-[:{relation_name}]->({correct_target})"
                        break

            guidance = f"RELATIONSHIP DIRECTION ERROR: The relationship '{relation_name}' cannot connect {wrong_source} to {wrong_target}."

            if correct_direction:
                guidance += f" The correct direction is: {correct_direction}"

            # List all valid relationships for reference
            valid_relations = []
            if 'relations' in ontology:
                for rel in ontology['relations'][:5]:  # Limit to first 5
                    source = rel.get('source', {}).get('label', 'Unknown')
                    target = rel.get('target', {}).get('label', 'Unknown')
                    rel_name = rel.get('label', 'Unknown')
                    valid_relations.append(f"({source})-[:{rel_name}]->({target})")

            if valid_relations:
                guidance += f"\n\nValid relationships: {', '.join(valid_relations)}"

            guidance += "\n\nCorrect the relationship direction in your Cypher query."
            return guidance

        return "Fix the relationship direction error. Check the ontology for correct source->target patterns."

    def _generate_union_correction_guidance(self, failed_cypher: str) -> str:
        """Generate guidance for UNION query errors."""

        return """UNION QUERY ERROR: All sub-queries in a UNION must return the same column names.

WRONG:
MATCH (a:NodeA) RETURN a
UNION
MATCH (b:NodeB) RETURN b

CORRECT:
MATCH (n:NodeA) RETURN n
UNION
MATCH (n:NodeB) RETURN n

OR use a single query instead:
MATCH (n) WHERE n:NodeA OR n:NodeB RETURN n

Fix your query to use consistent column names or avoid UNION entirely."""

    def _generate_property_correction_guidance(self, failed_cypher: str, ontology: Dict) -> str:
        """Generate guidance for property access errors."""

        # Extract available properties from ontology
        available_properties = set()
        if 'entities' in ontology:
            for entity in ontology['entities']:
                if 'attributes' in entity:
                    for attr in entity['attributes']:
                        if 'name' in attr:
                            available_properties.add(attr['name'])

        guidance = "PROPERTY ERROR: You're trying to access a property that doesn't exist."

        if available_properties:
            props_list = ', '.join(sorted(available_properties)[:10])  # Limit to 10
            guidance += f"\n\nAvailable properties: {props_list}"

        guidance += "\n\nUse only properties that exist in the ontology. Common properties are 'name', 'title', 'type'."

        return guidance

    def _generate_syntax_correction_guidance(self, failed_cypher: str, error_message: str) -> str:
        """Generate guidance for syntax errors."""

        common_fixes = [
            "Ensure all parentheses are properly matched: ()",
            "Check that all quotes are properly closed: 'text' or \"text\"",
            "Verify relationship syntax: -[:RELATIONSHIP_NAME]->",
            "Make sure MATCH, WHERE, RETURN keywords are used correctly",
            "Remove any trailing semicolons",
            "Use proper variable names (letters, numbers, underscores only)"
        ]

        return f"SYNTAX ERROR: {error_message}\n\nCommon fixes:\n" + "\n".join(f"- {fix}" for fix in common_fixes)

    def _build_correction_prompt(
        self,
        original_question: str,
        failed_cypher: str,
        error_message: str,
        correction_guidance: str,
        ontology: Dict
    ) -> str:
        """Build a comprehensive prompt for the LLM to correct the Cypher query."""

        # Format ontology information
        ontology_summary = self._format_ontology_summary(ontology)

        prompt = f"""You need to fix a broken Cypher query. Here are the details:

ORIGINAL QUESTION: {original_question}

FAILED CYPHER QUERY:
{failed_cypher}

ERROR MESSAGE: {error_message}

SPECIFIC CORRECTION GUIDANCE:
{correction_guidance}

CURRENT ONTOLOGY:
{ontology_summary}

TASK: Generate a corrected Cypher query that:
1. Answers the original question
2. Fixes the specific error mentioned
3. Uses only valid entities, relationships, and properties from the ontology
4. Follows proper Cypher syntax

Return ONLY the corrected Cypher query, nothing else. Do not include explanations or code blocks."""

        return prompt

    def _format_ontology_summary(self, ontology: Dict) -> str:
        """Format ontology information for the prompt."""

        summary_parts = []

        # Entities
        if 'entities' in ontology:
            entities = []
            for entity in ontology['entities'][:5]:  # Limit to 5
                label = entity.get('label', 'Unknown')
                attributes = []
                if 'attributes' in entity:
                    for attr in entity['attributes'][:3]:  # Limit to 3 attributes
                        attr_name = attr.get('name', 'unknown')
                        attributes.append(attr_name)

                if attributes:
                    entities.append(f"{label} ({', '.join(attributes)})")
                else:
                    entities.append(label)

            if entities:
                summary_parts.append(f"Entities: {', '.join(entities)}")

        # Relationships
        if 'relations' in ontology:
            relations = []
            for rel in ontology['relations'][:5]:  # Limit to 5
                source = rel.get('source', {}).get('label', 'Unknown')
                target = rel.get('target', {}).get('label', 'Unknown')
                rel_name = rel.get('label', 'Unknown')
                relations.append(f"({source})-[:{rel_name}]->({target})")

            if relations:
                summary_parts.append(f"Relationships: {', '.join(relations)}")

        return "\n".join(summary_parts) if summary_parts else "No ontology available"

    def _clean_cypher_response(self, response: str) -> Optional[str]:
        """Clean the LLM response to extract just the Cypher query."""

        if not response:
            return None

        # Remove code blocks
        response = re.sub(r'```(?:cypher|sql)?\s*\n', '', response, flags=re.IGNORECASE)
        response = re.sub(r'```', '', response)

        # Remove common prefixes
        response = re.sub(r'^(corrected query|here\'s the corrected|fixed query):\s*', '', response, flags=re.IGNORECASE)

        # Clean up whitespace
        response = response.strip()

        # Take only the first line if multiple lines
        lines = response.split('\n')
        if lines:
            response = lines[0].strip()

        # Basic validation - should start with a Cypher keyword
        cypher_keywords = ['MATCH', 'CREATE', 'MERGE', 'WITH', 'UNWIND', 'RETURN']
        if any(response.upper().startswith(keyword) for keyword in cypher_keywords):
            return response

        return None


class EnhancedGraphRAGHelper:
    """Enhanced GraphRAG helper with intelligent Cypher correction."""

    def __init__(self, base_helper, agent):
        self.base_helper = base_helper
        self.corrector = CypherErrorCorrector(agent)
        self.agent = agent

    async def query_with_cypher_correction(self, question: str) -> str:
        """
        Query with intelligent Cypher error correction.

        This method intercepts GraphRAG SDK calls and adds our own
        Cypher correction logic when the SDK fails.
        """

        try:
            # First try the normal GraphRAG query
            result = self.base_helper.query(question)

            # If we get a good result, return it
            if result and "No relevant information" not in result:
                return result

        except Exception as e:
            logger.debug(f"Standard GraphRAG query failed: {e}")

        # If standard query failed or returned no data, try enhanced correction
        return await self._query_with_manual_cypher_correction(question)

    async def _query_with_manual_cypher_correction(self, question: str) -> str:
        """
        Manually handle Cypher generation with correction logic.

        This bypasses the GraphRAG SDK's built-in Cypher generation
        and implements our own with better error handling.
        """

        try:
            # Get the current ontology
            ontology = self._get_current_ontology()

            if not ontology:
                logger.warning("No ontology available for Cypher generation")
                return self.base_helper._direct_query_fallback(question)

            # Generate initial Cypher query
            cypher_query = await self._generate_initial_cypher(question, ontology)

            if not cypher_query:
                logger.warning("Could not generate initial Cypher query")
                return self.base_helper._direct_query_fallback(question)

            # Try to execute the query with correction attempts
            return await self._execute_cypher_with_correction(
                question, cypher_query, ontology
            )

        except Exception as e:
            logger.error(f"Enhanced Cypher correction failed: {e}")
            return self.base_helper._direct_query_fallback(question)

    async def _generate_initial_cypher(self, question: str, ontology: Dict) -> Optional[str]:
        """Generate the initial Cypher query using the LLM."""

        ontology_summary = self.corrector._format_ontology_summary(ontology)

        prompt = f"""Generate a Cypher query to answer this question using the provided ontology.

QUESTION: {question}

ONTOLOGY:
{ontology_summary}

RULES:
1. Use only entities, relationships, and properties from the ontology
2. Respect relationship directions: (source)-[:RELATIONSHIP]->(target)
3. Use proper Cypher syntax
4. Return only the Cypher query, no explanations

CYPHER QUERY:"""

        try:
            cypher = await self.agent.call_utility_model(
                system="You are a Cypher query expert. Generate syntactically correct Cypher queries based on the given ontology.",
                message=prompt,
                background=True
            )

            return self.corrector._clean_cypher_response(cypher)

        except Exception as e:
            logger.error(f"Error generating initial Cypher: {e}")
            return None

    async def _execute_cypher_with_correction(
        self,
        question: str,
        cypher_query: str,
        ontology: Dict
    ) -> str:
        """Execute Cypher query with automatic correction on errors."""

        import redis

        try:
            r = redis.Redis(host=self.base_helper._DB_HOST, port=self.base_helper._DB_PORT, decode_responses=True)

            for attempt in range(1, self.corrector.max_correction_attempts + 2):  # +1 for initial attempt
                try:
                    logger.info(f"Executing Cypher (attempt {attempt}): {cypher_query}")

                    # Execute the query
                    result = r.execute_command("GRAPH.QUERY", self.base_helper._graph_name, cypher_query)

                    # If successful, process and return the result
                    if result and len(result) > 1 and result[1]:
                        formatted_result = self._format_cypher_result(result)
                        if formatted_result:
                            logger.info(f"Successful Cypher execution on attempt {attempt}")
                            return formatted_result

                    # If no data found, fall back
                    logger.warning(f"Cypher query returned no data on attempt {attempt}")
                    return self.base_helper._direct_query_fallback(question)

                except Exception as e:
                    error_message = str(e)
                    logger.warning(f"Cypher execution failed on attempt {attempt}: {error_message}")

                    # If this was the last attempt, fall back
                    if attempt >= self.corrector.max_correction_attempts + 1:
                        logger.error("Max correction attempts reached, falling back to direct query")
                        return self.base_helper._direct_query_fallback(question)

                    # Try to correct the query
                    corrected_cypher = await self.corrector.correct_cypher_with_guidance(
                        question, cypher_query, error_message, ontology, attempt
                    )

                    if corrected_cypher:
                        cypher_query = corrected_cypher
                        logger.info(f"Using corrected Cypher for attempt {attempt + 1}")
                    else:
                        logger.warning("Could not generate corrected Cypher, falling back")
                        return self.base_helper._direct_query_fallback(question)

        except Exception as e:
            logger.error(f"Critical error during Cypher execution: {e}")
            return self.base_helper._direct_query_fallback(question)

    def _get_current_ontology(self) -> Optional[Dict]:
        """Get the current graph ontology."""
        try:
            if hasattr(self.base_helper, '_kg') and self.base_helper._kg:
                return self.base_helper._kg._ontology._ontology
            return None
        except Exception:
            return None

    def _format_cypher_result(self, raw_result) -> Optional[str]:
        """Format raw Cypher result into a readable response."""
        try:
            if not raw_result or len(raw_result) < 2 or not raw_result[1]:
                return None

            # Use the existing formatting logic from the base helper
            return self.base_helper._direct_query_fallback._format_direct_result(raw_result)

        except Exception:
            # Fallback to simple formatting
            try:
                rows = raw_result[1][:5]  # Limit to 5 results
                formatted_rows = []

                for row in rows:
                    if isinstance(row, list) and row:
                        # Simple formatting for entities
                        formatted_rows.append(str(row[0]) if row[0] else "Unknown")

                return f"Found data: {', '.join(formatted_rows)}" if formatted_rows else None

            except Exception:
                return None
