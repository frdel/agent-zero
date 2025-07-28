import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum

from langchain_core.documents import Document

from python.helpers.memory import Memory
from python.helpers.dirty_json import DirtyJson
from python.helpers.log import LogItem
from python.helpers.print_style import PrintStyle
from python.tools.memory_load import DEFAULT_THRESHOLD as DEFAULT_MEMORY_THRESHOLD
from agent import Agent


class ConsolidationAction(Enum):
    """Actions that can be taken during memory consolidation."""
    MERGE = "merge"
    REPLACE = "replace"
    KEEP_SEPARATE = "keep_separate"
    UPDATE = "update"
    SKIP = "skip"


@dataclass
class ConsolidationConfig:
    """Configuration for memory consolidation behavior."""
    similarity_threshold: float = DEFAULT_MEMORY_THRESHOLD
    max_similar_memories: int = 10
    consolidation_sys_prompt: str = "memory.consolidation.sys.md"
    consolidation_msg_prompt: str = "memory.consolidation.msg.md"
    max_llm_context_memories: int = 5
    keyword_extraction_sys_prompt: str = "memory.keyword_extraction.sys.md"
    keyword_extraction_msg_prompt: str = "memory.keyword_extraction.msg.md"
    processing_timeout_seconds: int = 60
    # Add safety threshold for REPLACE actions
    replace_similarity_threshold: float = 0.9  # Higher threshold for replacement safety


@dataclass
class ConsolidationResult:
    """Result of memory consolidation analysis."""
    action: ConsolidationAction
    memories_to_remove: List[str] = field(default_factory=list)
    memories_to_update: List[Dict[str, Any]] = field(default_factory=list)
    new_memory_content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""


@dataclass
class MemoryAnalysisContext:
    """Context for LLM memory analysis."""
    new_memory: str
    similar_memories: List[Document]
    area: str
    timestamp: str
    existing_metadata: Dict[str, Any]


class MemoryConsolidator:
    """
    Intelligent memory consolidation system that uses LLM analysis to determine
    optimal memory organization and automatically consolidates related memories.
    """

    def __init__(self, agent: Agent, config: Optional[ConsolidationConfig] = None):
        self.agent = agent
        self.config = config or ConsolidationConfig()

    async def process_new_memory(
        self,
        new_memory: str,
        area: str,
        metadata: Dict[str, Any],
        log_item: Optional[LogItem] = None
    ) -> dict:
        """
        Process a new memory through the intelligent consolidation pipeline.

        Args:
            new_memory: The new memory content to process
            area: Memory area (MAIN, FRAGMENTS, SOLUTIONS, INSTRUMENTS)
            metadata: Initial metadata for the memory
            log_item: Optional log item for progress tracking

        Returns:
            dict: {"success": bool, "memory_ids": [str, ...]}
        """
        try:
            # Start processing with timeout
            processing_task = asyncio.create_task(
                self._process_memory_with_consolidation(new_memory, area, metadata, log_item)
            )

            result = await asyncio.wait_for(
                processing_task,
                timeout=self.config.processing_timeout_seconds
            )
            return result

        except asyncio.TimeoutError:
            PrintStyle().error(f"Memory consolidation timeout for area {area}")
            return {"success": False, "memory_ids": []}

        except Exception as e:
            PrintStyle().error(f"Memory consolidation error for area {area}: {str(e)}")
            return {"success": False, "memory_ids": []}

    async def _process_memory_with_consolidation(
        self,
        new_memory: str,
        area: str,
        metadata: Dict[str, Any],
        log_item: Optional[LogItem] = None
    ) -> dict:
        """Execute the full consolidation pipeline."""

        if log_item:
            log_item.update(progress="Starting intelligent memory consolidation...")

        # Step 1: Discover similar memories
        similar_memories = await self._find_similar_memories(new_memory, area, log_item)

        # this block always returns
        if not similar_memories:
            # No similar memories found, insert directly
            if log_item:
                log_item.update(
                    progress="No similar memories found, inserting new memory",
                    temp=True
                )
            try:
                db = await Memory.get(self.agent)
                if 'timestamp' not in metadata:
                    metadata['timestamp'] = self._get_timestamp()
                memory_id = await db.insert_text(new_memory, metadata)
                if log_item:
                    log_item.update(
                        result="Memory inserted successfully",
                        memory_ids=[memory_id],
                        consolidation_action="direct_insert"
                    )
                return {"success": True, "memory_ids": [memory_id]}
            except Exception as e:
                PrintStyle().error(f"Direct memory insertion failed: {str(e)}")
                if log_item:
                    log_item.update(result=f"Memory insertion failed: {str(e)}")
                return {"success": False, "memory_ids": []}

        if log_item:
            log_item.update(
                progress=f"Found {len(similar_memories)} similar memories, analyzing...",
                temp=True,
                similar_memories_count=len(similar_memories)
            )

        # Step 2: Validate that similar memories still exist (they might have been deleted by previous consolidations)
        if similar_memories:
            memory_ids_to_check = [doc.metadata.get('id') for doc in similar_memories if doc.metadata.get('id')]
            # Filter out None values and ensure all IDs are strings
            memory_ids_to_check = [str(id) for id in memory_ids_to_check if id is not None]
            db = await Memory.get(self.agent)
            still_existing = db.db.get_by_ids(memory_ids_to_check)
            existing_ids = {doc.metadata.get('id') for doc in still_existing}

            # Filter out deleted memories
            valid_similar_memories = [doc for doc in similar_memories if doc.metadata.get('id') in existing_ids]

            if len(valid_similar_memories) != len(similar_memories):
                deleted_count = len(similar_memories) - len(valid_similar_memories)
                if log_item:
                    log_item.update(
                        progress=f"Filtered out {deleted_count} deleted memories, {len(valid_similar_memories)} remain for analysis",
                        temp=True,
                        race_condition_detected=True,
                        deleted_similar_memories_count=deleted_count
                    )
                similar_memories = valid_similar_memories

        # If no valid similar memories remain after filtering, insert directly
        if not similar_memories:
            if log_item:
                log_item.update(
                    progress="No valid similar memories remain, inserting new memory",
                    temp=True
                )
            try:
                db = await Memory.get(self.agent)
                if 'timestamp' not in metadata:
                    metadata['timestamp'] = self._get_timestamp()
                memory_id = await db.insert_text(new_memory, metadata)
                if log_item:
                    log_item.update(
                        result="Memory inserted successfully (no valid similar memories)",
                        memory_ids=[memory_id],
                        consolidation_action="direct_insert_filtered"
                    )
                return {"success": True, "memory_ids": [memory_id]}
            except Exception as e:
                PrintStyle().error(f"Direct memory insertion failed: {str(e)}")
                if log_item:
                    log_item.update(result=f"Memory insertion failed: {str(e)}")
                return {"success": False, "memory_ids": []}

        # Step 3: Analyze with LLM (now with validated memories)
        analysis_context = MemoryAnalysisContext(
            new_memory=new_memory,
            similar_memories=similar_memories,
            area=area,
            timestamp=self._get_timestamp(),
            existing_metadata=metadata
        )

        consolidation_result = await self._analyze_memory_consolidation(analysis_context, log_item)

        if consolidation_result.action == ConsolidationAction.SKIP:
            if log_item:
                log_item.update(
                    progress="LLM analysis suggests skipping consolidation",
                    temp=True
                )
            try:
                db = await Memory.get(self.agent)
                if 'timestamp' not in metadata:
                    metadata['timestamp'] = self._get_timestamp()
                memory_id = await db.insert_text(new_memory, metadata)
                if log_item:
                    log_item.update(
                        result="Memory inserted (consolidation skipped)",
                        memory_ids=[memory_id],
                        consolidation_action="skip",
                        reasoning=consolidation_result.reasoning or "LLM analysis suggested skipping"
                    )
                return {"success": True, "memory_ids": [memory_id]}
            except Exception as e:
                PrintStyle().error(f"Skip consolidation insertion failed: {str(e)}")
                if log_item:
                    log_item.update(result=f"Memory insertion failed: {str(e)}")
                return {"success": False, "memory_ids": []}

        # Step 4: Apply consolidation decisions
        memory_ids = await self._apply_consolidation_result(
            consolidation_result,
            area,
            analysis_context.existing_metadata,  # Pass original metadata
            log_item
        )

        if log_item:
            if memory_ids:
                log_item.update(
                    result=f"Consolidation completed: {consolidation_result.action.value}",
                    memory_ids=memory_ids,
                    consolidation_action=consolidation_result.action.value,
                    reasoning=consolidation_result.reasoning or "No specific reasoning provided",
                    memories_processed=len(similar_memories) + 1  # +1 for new memory
                )
            else:
                log_item.update(
                    result=f"Consolidation failed: {consolidation_result.action.value}",
                    consolidation_action=consolidation_result.action.value,
                    reasoning=consolidation_result.reasoning or "Consolidation operation failed"
                )

        return {"success": bool(memory_ids), "memory_ids": memory_ids or []}

    async def _gather_consolidated_metadata(
        self,
        db: Memory,
        result: ConsolidationResult,
        original_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Gather and merge metadata from memories being consolidated to preserve important fields.
        This ensures critical metadata like priority, source, etc. is preserved during consolidation.
        """
        try:
            # Start with the new memory's metadata as base
            consolidated_metadata = dict(original_metadata)

            # Collect all memory IDs that will be involved in consolidation
            memory_ids = []

            # Add memories to be removed (MERGE, REPLACE actions)
            if result.memories_to_remove:
                memory_ids.extend(result.memories_to_remove)

            # Add memories to be updated (UPDATE action)
            if result.memories_to_update:
                for update_info in result.memories_to_update:
                    memory_id = update_info.get('id')
                    if memory_id:
                        memory_ids.append(memory_id)

            # Retrieve original memories to extract their metadata
            if memory_ids:
                original_memories = await db.db.aget_by_ids(memory_ids)

                # Merge ALL metadata fields from original memories
                for memory in original_memories:
                    memory_metadata = memory.metadata

                    # Process ALL metadata fields from the original memory
                    for field_name, field_value in memory_metadata.items():
                        if field_name not in consolidated_metadata:
                            # Field doesn't exist in consolidated metadata, add it
                            consolidated_metadata[field_name] = field_value
                        elif field_name in consolidated_metadata:
                            # Field exists in both - handle special merge cases
                            if field_name == 'tags' and isinstance(field_value, list) and isinstance(consolidated_metadata[field_name], list):
                                # Merge tags lists and remove duplicates
                                merged_tags = list(set(consolidated_metadata[field_name] + field_value))
                                consolidated_metadata[field_name] = merged_tags
                            # For all other fields, keep the new memory's value (don't overwrite)
                            # This preserves the new memory's metadata when there are conflicts

            return consolidated_metadata

        except Exception as e:
            # If metadata gathering fails, return original metadata as fallback
            PrintStyle(font_color="yellow").print(f"Failed to gather consolidated metadata: {str(e)}")
            return original_metadata

    async def _find_similar_memories(
        self,
        new_memory: str,
        area: str,
        log_item: Optional[LogItem] = None
    ) -> List[Document]:
        """
        Find similar memories using both semantic similarity and keyword matching.
        Now includes knowledge source awareness and similarity scores for validation.
        """
        db = await Memory.get(self.agent)

        # Step 1: Extract keywords/queries for enhanced search
        search_queries = await self._extract_search_keywords(new_memory, log_item)

        all_similar = []

        # Step 2: Semantic similarity search with scores
        semantic_similar = await db.search_similarity_threshold(
            query=new_memory,
            limit=self.config.max_similar_memories,
            threshold=self.config.similarity_threshold,
            filter=f"area == '{area}'"
        )
        all_similar.extend(semantic_similar)

        # Step 3: Keyword-based searches
        for query in search_queries:
            if query.strip():
                # Fix division by zero: ensure len(search_queries) > 0
                queries_count = max(1, len(search_queries))  # Prevent division by zero
                keyword_similar = await db.search_similarity_threshold(
                    query=query.strip(),
                    limit=max(3, self.config.max_similar_memories // queries_count),
                    threshold=self.config.similarity_threshold,
                    filter=f"area == '{area}'"
                )
                all_similar.extend(keyword_similar)

        # Step 4: Deduplicate by document ID and store similarity info
        seen_ids = set()
        unique_similar = []
        for doc in all_similar:
            doc_id = doc.metadata.get('id')
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                unique_similar.append(doc)

        # Step 5: Calculate similarity scores for replacement validation
        # Since FAISS doesn't directly expose similarity scores, use ranking-based estimation
        # CRITICAL: All documents must have similarity >= search_threshold since FAISS returned them
        # FIXED: Use conservative scoring that keeps all scores in safe consolidation range
        similarity_scores = {}
        total_docs = len(unique_similar)
        search_threshold = self.config.similarity_threshold
        safety_threshold = self.config.replace_similarity_threshold

        for i, doc in enumerate(unique_similar):
            doc_id = doc.metadata.get('id')
            if doc_id:
                # Convert ranking to similarity score with conservative distribution
                if total_docs == 1:
                    ranking_similarity = 1.0  # Single document gets perfect score
                else:
                    # Use conservative scoring: distribute between safety_threshold and 1.0
                    # This ensures all scores are suitable for consolidation
                    # First document gets 1.0, last gets safety_threshold (0.9 by default)
                    ranking_factor = 1.0 - (i / (total_docs - 1))
                    score_range = 1.0 - safety_threshold  # e.g., 1.0 - 0.9 = 0.1
                    ranking_similarity = safety_threshold + (score_range * ranking_factor)

                    # Ensure minimum score is search_threshold for logical consistency
                    ranking_similarity = max(ranking_similarity, search_threshold)

                similarity_scores[doc_id] = ranking_similarity

        # Step 6: Add similarity score to document metadata for LLM analysis
        for doc in unique_similar:
            doc_id = doc.metadata.get('id')
            estimated_similarity = similarity_scores.get(doc_id, 0.7)
            # Store for later validation
            doc.metadata['_consolidation_similarity'] = estimated_similarity

        # Step 7: Limit to max context for LLM
        limited_similar = unique_similar[:self.config.max_llm_context_memories]

        return limited_similar

    async def _extract_search_keywords(
        self,
        new_memory: str,
        log_item: Optional[LogItem] = None
    ) -> List[str]:
        """Extract search keywords/queries from new memory using utility LLM."""

        try:
            system_prompt = self.agent.read_prompt(
                self.config.keyword_extraction_sys_prompt,
            )

            message_prompt = self.agent.read_prompt(
                self.config.keyword_extraction_msg_prompt,
                memory_content=new_memory
            )

            # Call utility LLM to extract search queries
            keywords_response = await self.agent.call_utility_model(
                system=system_prompt,
                message=message_prompt,
                background=True
            )

            # Parse the response - expect JSON array of strings
            keywords_json = DirtyJson.parse_string(keywords_response.strip())

            if isinstance(keywords_json, list):
                return [str(k) for k in keywords_json if k]
            elif isinstance(keywords_json, str):
                return [keywords_json]
            else:
                return []

        except Exception as e:
            PrintStyle().warning(f"Keyword extraction failed: {str(e)}")
            # Fallback: use intelligent truncation for search
            # Take first 200 chars if short, or first sentence if longer, but cap at 200 chars
            if len(new_memory) <= 200:
                fallback_content = new_memory
            else:
                first_sentence = new_memory.split('.')[0]
                fallback_content = first_sentence[:200] if len(first_sentence) <= 200 else new_memory[:200]
            return [fallback_content.strip()]

    async def _analyze_memory_consolidation(
        self,
        context: MemoryAnalysisContext,
        log_item: Optional[LogItem] = None
    ) -> ConsolidationResult:
        """Use LLM to analyze memory consolidation options."""

        try:
            # Prepare similar memories text
            similar_memories_text = ""
            for i, doc in enumerate(context.similar_memories):
                timestamp = doc.metadata.get('timestamp', 'unknown')
                doc_id = doc.metadata.get('id', f'doc_{i}')
                similar_memories_text += f"ID: {doc_id}\nTimestamp: {timestamp}\nContent: {doc.page_content}\n\n"

            # Build system prompt
            system_prompt = self.agent.read_prompt(
                self.config.consolidation_sys_prompt,
            )

            # Build message prompt
            message_prompt = self.agent.read_prompt(
                self.config.consolidation_msg_prompt,
                new_memory=context.new_memory,
                similar_memories=similar_memories_text.strip(),
                area=context.area,
                current_timestamp=context.timestamp,
                new_memory_metadata=json.dumps(context.existing_metadata, indent=2)
            )

            analysis_response = await self.agent.call_utility_model(
                system=system_prompt,
                message=message_prompt,
                callback=None,
                background=True
            )

            # Parse LLM response
            result_json = DirtyJson.parse_string(analysis_response.strip())

            if not isinstance(result_json, dict):
                raise ValueError("LLM response is not a valid JSON object")

            # Parse consolidation result
            action_str = result_json.get('action', 'skip')
            try:
                action = ConsolidationAction(action_str.lower())
            except ValueError:
                action = ConsolidationAction.SKIP

            # Determine appropriate fallback for new_memory_content based on action
            if action in [ConsolidationAction.MERGE, ConsolidationAction.REPLACE]:
                # For MERGE/REPLACE, if no content provided, it's an error - don't use original
                default_content = ""
            else:
                # For KEEP_SEPARATE/UPDATE/SKIP, original memory is appropriate fallback
                default_content = context.new_memory

            return ConsolidationResult(
                action=action,
                memories_to_remove=result_json.get('memories_to_remove', []),
                memories_to_update=result_json.get('memories_to_update', []),
                new_memory_content=result_json.get('new_memory_content', default_content),
                metadata=result_json.get('metadata', {}),
                reasoning=result_json.get('reasoning', '')
            )

        except Exception as e:
            PrintStyle().warning(f"LLM consolidation analysis failed: {str(e)}")
            # Fallback: skip consolidation
            return ConsolidationResult(
                action=ConsolidationAction.SKIP,
                reasoning=f"Analysis failed: {str(e)}"
            )

    async def _apply_consolidation_result(
        self,
        result: ConsolidationResult,
        area: str,
        original_metadata: Dict[str, Any],  # Add original metadata parameter
        log_item: Optional[LogItem] = None
    ) -> list:
        """Apply the consolidation decisions to the memory database."""

        try:
            db = await Memory.get(self.agent)

            # Retrieve metadata from memories being consolidated to preserve important fields
            consolidated_metadata = await self._gather_consolidated_metadata(db, result, original_metadata)

            # Handle each action type specifically
            if result.action == ConsolidationAction.KEEP_SEPARATE:
                return await self._handle_keep_separate(db, result, area, consolidated_metadata, log_item)

            elif result.action == ConsolidationAction.MERGE:
                return await self._handle_merge(db, result, area, consolidated_metadata, log_item)

            elif result.action == ConsolidationAction.REPLACE:
                return await self._handle_replace(db, result, area, consolidated_metadata, log_item)

            elif result.action == ConsolidationAction.UPDATE:
                return await self._handle_update(db, result, area, consolidated_metadata, log_item)

            else:
                # Should not reach here, but handle gracefully
                PrintStyle().warning(f"Unknown consolidation action: {result.action}")
                return []

        except Exception as e:
            PrintStyle().error(f"Failed to apply consolidation result: {str(e)}")
            return []

    async def _handle_keep_separate(
        self,
        db: Memory,
        result: ConsolidationResult,
        area: str,
        original_metadata: Dict[str, Any],  # Add original metadata parameter
        log_item: Optional[LogItem] = None
    ) -> list:
        """Handle KEEP_SEPARATE action: Insert new memory without touching existing ones."""

        if not result.new_memory_content:
            return []

        # Prepare metadata for new memory
        # LLM metadata takes precedence over original metadata when there are conflicts
        final_metadata = {
            'area': area,
            'timestamp': self._get_timestamp(),
            'consolidation_action': result.action.value,
            **original_metadata,  # Original metadata first
            **result.metadata     # LLM metadata second (wins conflicts)
        }

        # do not include reasoning in memory
        # if result.reasoning:
        #     final_metadata['consolidation_reasoning'] = result.reasoning

        new_id = await db.insert_text(result.new_memory_content, final_metadata)
        return [new_id]

    async def _handle_merge(
        self,
        db: Memory,
        result: ConsolidationResult,
        area: str,
        original_metadata: Dict[str, Any],  # Add original metadata parameter
        log_item: Optional[LogItem] = None
    ) -> list:
        """Handle MERGE action: Combine memories, remove originals, insert consolidated version."""

        # Step 1: Remove original memories being merged
        if result.memories_to_remove:
            await db.delete_documents_by_ids(result.memories_to_remove)

        # Step 2: Insert consolidated memory
        if result.new_memory_content:
            # LLM metadata takes precedence over original metadata when there are conflicts
            final_metadata = {
                'area': area,
                'timestamp': self._get_timestamp(),
                'consolidation_action': result.action.value,
                'consolidated_from': result.memories_to_remove,
                **original_metadata,  # Original metadata first
                **result.metadata     # LLM metadata second (wins conflicts)
            }

            # do not include reasoning in memory
            # if result.reasoning:
            #     final_metadata['consolidation_reasoning'] = result.reasoning

            new_id = await db.insert_text(result.new_memory_content, final_metadata)
            return [new_id]
        else:
            return []

    async def _handle_replace(
        self,
        db: Memory,
        result: ConsolidationResult,
        area: str,
        original_metadata: Dict[str, Any],  # Add original metadata parameter
        log_item: Optional[LogItem] = None
    ) -> list:
        """Handle REPLACE action: Remove old memories, insert new version with similarity validation."""

        # Step 1: Validate similarity scores for replacement safety
        if result.memories_to_remove:
            # Get the memories to be removed and check their similarity scores
            memories_to_check = await db.db.aget_by_ids(result.memories_to_remove)

            unsafe_replacements = []
            for memory in memories_to_check:
                similarity = memory.metadata.get('_consolidation_similarity', 0.7)
                if similarity < self.config.replace_similarity_threshold:
                    unsafe_replacements.append({
                        'id': memory.metadata.get('id'),
                        'similarity': similarity,
                        'content_preview': memory.page_content[:100]
                    })

            # If we have unsafe replacements, either block them or require explicit confirmation
            if unsafe_replacements:
                PrintStyle().warning(
                    f"REPLACE blocked: {len(unsafe_replacements)} memories below "
                    f"similarity threshold {self.config.replace_similarity_threshold}, converting to KEEP_SEPARATE"
                )

                # Instead of replace, just insert the new memory (keep separate)
                if result.new_memory_content:
                    final_metadata = {
                        'area': area,
                        'timestamp': self._get_timestamp(),
                        'consolidation_action': 'keep_separate_safety',  # Indicate safety conversion
                        'original_action': 'replace',
                        'safety_reason': f'Similarity below threshold {self.config.replace_similarity_threshold}',
                        **original_metadata,
                        **result.metadata
                    }

                    # do not include reasoning in memory
                    # if result.reasoning:
                    #     final_metadata['consolidation_reasoning'] = result.reasoning

                    new_id = await db.insert_text(result.new_memory_content, final_metadata)
                    return [new_id]
                else:
                    return []

        # Step 2: Proceed with normal replacement if similarity checks pass
        if result.memories_to_remove:
            await db.delete_documents_by_ids(result.memories_to_remove)

        # Step 3: Insert replacement memory
        if result.new_memory_content:
            # LLM metadata takes precedence over original metadata when there are conflicts
            final_metadata = {
                'area': area,
                'timestamp': self._get_timestamp(),
                'consolidation_action': result.action.value,
                'replaced_memories': result.memories_to_remove,
                **original_metadata,  # Original metadata first
                **result.metadata     # LLM metadata second (wins conflicts)
            }

            # do not include reasoning in memory
            # if result.reasoning:
            #     final_metadata['consolidation_reasoning'] = result.reasoning

            new_id = await db.insert_text(result.new_memory_content, final_metadata)
            return [new_id]
        else:
            return []

    async def _handle_update(
        self,
        db: Memory,
        result: ConsolidationResult,
        area: str,
        original_metadata: Dict[str, Any],  # Add original metadata parameter
        log_item: Optional[LogItem] = None
    ) -> list:
        """Handle UPDATE action: Modify existing memories in place with additional information."""

        updated_count = 0
        updated_ids = []

        # Step 1: Update existing memories
        for update_info in result.memories_to_update:
            memory_id = update_info.get('id')
            new_content = update_info.get('new_content', '')

            if memory_id and new_content:
                # Validate that the memory exists before attempting to delete it
                existing_docs = await db.db.aget_by_ids([memory_id])
                if not existing_docs:
                    PrintStyle().warning(f"Memory ID {memory_id} not found during update, skipping")
                    continue

                # Delete old version and insert updated version
                await db.delete_documents_by_ids([memory_id])

                # LLM metadata takes precedence over original metadata when there are conflicts
                updated_metadata = {
                    'area': area,
                    'timestamp': self._get_timestamp(),
                    'consolidation_action': result.action.value,
                    'updated_from': memory_id,
                    **original_metadata,                    # Original metadata first
                    **update_info.get('metadata', {})       # LLM metadata second (wins conflicts)
                }

                new_id = await db.insert_text(new_content, updated_metadata)
                updated_count += 1
                updated_ids.append(new_id)

        # Step 2: Insert additional new memory if provided
        new_memory_id = None
        if result.new_memory_content:
            # LLM metadata takes precedence over original metadata when there are conflicts
            final_metadata = {
                'area': area,
                'timestamp': self._get_timestamp(),
                'consolidation_action': result.action.value,
                **original_metadata,  # Original metadata first
                **result.metadata     # LLM metadata second (wins conflicts)
            }

            # do not include reasoning in memory
            # if result.reasoning:
            #     final_metadata['consolidation_reasoning'] = result.reasoning

            new_memory_id = await db.insert_text(result.new_memory_content, final_metadata)
            updated_ids.append(new_memory_id)

        return updated_ids

    def _get_timestamp(self) -> str:
        """Get current timestamp in standard format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# Factory function for easy instantiation
def create_memory_consolidator(agent: Agent, **config_overrides) -> MemoryConsolidator:
    """
    Create a MemoryConsolidator with optional configuration overrides.

    Available configuration options:
    - similarity_threshold: Discovery threshold for finding related memories (default 0.7)
    - replace_similarity_threshold: Safety threshold for REPLACE actions (default 0.9)
    - max_similar_memories: Maximum memories to discover (default 10)
    - max_llm_context_memories: Maximum memories to send to LLM (default 5)
    - processing_timeout_seconds: Timeout for consolidation processing (default 30)
    """
    config = ConsolidationConfig(**config_overrides)
    return MemoryConsolidator(agent, config)
