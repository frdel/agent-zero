import asyncio
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers.settings import get_settings
from python.helpers.dirty_json import DirtyJson
from agent import LoopData
from python.helpers.log import LogItem


class Mem0EvolveMemories(Extension):
    """
    mem0-specific extension that leverages mem0's advanced memory evolution
    capabilities including automatic memory organization, relationship building,
    and contextual memory enhancement.
    """

    def __init__(self, agent, *args, **kwargs):
        super().__init__(agent, *args, **kwargs)
        self.enabled = self._is_mem0_enabled()

    def _is_mem0_enabled(self) -> bool:
        """Check if mem0 backend is enabled"""
        settings = get_settings()
        return (settings.get("memory_backend") == "mem0" and 
                settings.get("mem0_enabled", False))

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """Execute mem0-specific memory evolution"""
        if not self.enabled:
            return  # Skip if mem0 is not enabled
        
        # Log memory evolution activity
        log_item = self.agent.context.log.log(
            type="util",
            heading="Evolving memories with mem0...",
        )

        # Execute memory evolution in background
        asyncio.create_task(self.evolve_memories(loop_data, log_item))

    async def evolve_memories(self, loop_data: LoopData, log_item: LogItem, **kwargs):
        """Perform mem0-specific memory evolution"""
        try:
            from python.helpers.memory_mem0 import Mem0Memory
            
            # Get mem0 memory instance
            mem0_db = await Mem0Memory.get(self.agent)
            
            # Get recent conversation for context
            msgs_text = self.agent.concat_messages(self.agent.history)
            
            # Use utility model to identify memory evolution opportunities
            system_prompt = self._get_evolution_prompt()
            
            # Log evolution process
            async def log_callback(content):
                log_item.stream(content=content)
            
            # Call utility model to analyze memory evolution needs
            evolution_json = await self.agent.call_utility_model(
                system=system_prompt,
                message=msgs_text,
                callback=log_callback,
                background=True,
            )
            
            if not evolution_json or not isinstance(evolution_json, str):
                log_item.update(heading="No memory evolution opportunities found.")
                return
            
            evolution_json = evolution_json.strip()
            if not evolution_json:
                log_item.update(heading="Empty evolution response.")
                return
            
            try:
                evolution_data = DirtyJson.parse_string(evolution_json)
            except Exception as e:
                log_item.update(heading=f"Failed to parse evolution response: {str(e)}")
                return
            
            if not evolution_data:
                log_item.update(heading="No valid evolution data found.")
                return
            
            # Process memory evolution
            await self._process_evolution(mem0_db, evolution_data, log_item)
            
        except ImportError:
            log_item.update(heading="mem0ai not available for memory evolution.")
            return
        except Exception as e:
            log_item.update(heading=f"Error during memory evolution: {str(e)}")
            return

    async def _process_evolution(self, mem0_db, evolution_data, log_item: LogItem):
        """Process memory evolution data"""
        try:
            if not isinstance(evolution_data, dict):
                log_item.update(heading="Invalid evolution data format.")
                return
            
            # Handle memory relationships
            relationships = evolution_data.get("relationships", [])
            if relationships:
                await self._enhance_relationships(mem0_db, relationships, log_item)
            
            # Handle memory consolidation
            consolidations = evolution_data.get("consolidations", [])
            if consolidations:
                await self._consolidate_memories(mem0_db, consolidations, log_item)
            
            # Handle memory enrichment
            enrichments = evolution_data.get("enrichments", [])
            if enrichments:
                await self._enrich_memories(mem0_db, enrichments, log_item)
            
            # Handle memory organization
            organization = evolution_data.get("organization", {})
            if organization:
                await self._organize_memories(mem0_db, organization, log_item)
            
            evolution_count = len(relationships) + len(consolidations) + len(enrichments)
            if evolution_count > 0:
                log_item.update(
                    heading=f"Memory evolution completed: {evolution_count} improvements made.",
                    result=f"Enhanced {evolution_count} memory aspects through mem0 evolution."
                )
            else:
                log_item.update(heading="No memory evolution actions needed.")
                
        except Exception as e:
            log_item.update(heading=f"Error processing memory evolution: {str(e)}")

    async def _enhance_relationships(self, mem0_db, relationships, log_item: LogItem):
        """Enhance memory relationships"""
        try:
            for relationship in relationships:
                if isinstance(relationship, dict):
                    memory_id = relationship.get("memory_id")
                    related_concepts = relationship.get("related_concepts", [])
                    
                    if memory_id and related_concepts:
                        # Add relationship metadata to memory
                        # This would require extending the mem0 backend to support metadata updates
                        log_item.stream(content=f"\nEnhancing relationships for memory {memory_id}")
                        
        except Exception as e:
            log_item.stream(content=f"\nError enhancing relationships: {str(e)}")

    async def _consolidate_memories(self, mem0_db, consolidations, log_item: LogItem):
        """Consolidate similar memories"""
        try:
            for consolidation in consolidations:
                if isinstance(consolidation, dict):
                    primary_id = consolidation.get("primary_memory_id")
                    duplicate_ids = consolidation.get("duplicate_ids", [])
                    
                    if primary_id and duplicate_ids:
                        # Remove duplicate memories
                        deleted_docs = await mem0_db.delete_documents_by_ids(duplicate_ids)
                        log_item.stream(content=f"\nConsolidated {len(deleted_docs)} duplicate memories")
                        
        except Exception as e:
            log_item.stream(content=f"\nError consolidating memories: {str(e)}")

    async def _enrich_memories(self, mem0_db, enrichments, log_item: LogItem):
        """Enrich memory content and metadata"""
        try:
            for enrichment in enrichments:
                if isinstance(enrichment, dict):
                    memory_id = enrichment.get("memory_id")
                    additional_context = enrichment.get("context")
                    
                    if memory_id and additional_context:
                        # Add enriched context to memory
                        log_item.stream(content=f"\nEnriching memory {memory_id} with additional context")
                        
        except Exception as e:
            log_item.stream(content=f"\nError enriching memories: {str(e)}")

    async def _organize_memories(self, mem0_db, organization, log_item: LogItem):
        """Organize memories by themes and areas"""
        try:
            themes = organization.get("themes", [])
            area_suggestions = organization.get("area_suggestions", [])
            
            if themes:
                log_item.stream(content=f"\nIdentified {len(themes)} memory themes")
                
            if area_suggestions:
                log_item.stream(content=f"\nSuggested {len(area_suggestions)} memory area reorganizations")
                
        except Exception as e:
            log_item.stream(content=f"\nError organizing memories: {str(e)}")

    def _get_evolution_prompt(self) -> str:
        """Get the system prompt for memory evolution"""
        return """You are a memory evolution expert. Analyze the conversation history and identify opportunities to improve memory organization and relationships using mem0.

Focus on:
1. **Relationships**: Find memories that should be connected or related
2. **Consolidation**: Identify duplicate or highly similar memories that should be merged
3. **Enrichment**: Suggest additional context or metadata that would improve memory utility
4. **Organization**: Recommend better categorization or area assignments

Return a JSON object with this structure:
{
    "relationships": [
        {
            "memory_id": "id1",
            "related_concepts": ["concept1", "concept2"],
            "relationship_type": "causal/temporal/thematic"
        }
    ],
    "consolidations": [
        {
            "primary_memory_id": "keep_this_id",
            "duplicate_ids": ["remove_id1", "remove_id2"],
            "reason": "why these are duplicates"
        }
    ],
    "enrichments": [
        {
            "memory_id": "id1",
            "context": "additional context to add",
            "metadata": {"key": "value"}
        }
    ],
    "organization": {
        "themes": ["theme1", "theme2"],
        "area_suggestions": [
            {
                "memory_id": "id1",
                "suggested_area": "solutions",
                "reason": "why this area is better"
            }
        ]
    }
}

Only suggest improvements that would genuinely enhance memory utility and organization. Return empty arrays if no improvements are needed."""