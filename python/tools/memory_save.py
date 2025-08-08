from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.helpers import settings


class MemorySave(Tool):

    async def execute(self, text="", area="", **kwargs):

        if not area:
            area = Memory.Area.MAIN.value

        metadata = {"area": area, **kwargs}

        db = await Memory.get(self.agent)
        id = await db.insert_text(text, metadata)

        # Ingest into GraphRAG after successful memory save (if enabled)
        graph_status = False
        try:
            set = settings.get_settings()
            if set.get("use_graphrag", True):
                graph_status = await self._ingest_to_graphrag(text, area, None)
        except Exception:
            # GraphRAG failure shouldn't break memory saving
            pass

        # Prepare result message
        base_result = self.agent.read_prompt("fw.memory_saved.md", memory_id=id)

        if graph_status:
            result = f"{base_result}\n\nAlso added to knowledge graph with structured entity and relationship extraction."
        else:
            result = base_result

        return Response(message=result, break_loop=False)

    async def _ingest_to_graphrag(self, text: str, area: str, memory_id: str | None = None) -> bool:
        """Ingest memory text into GraphRAG knowledge graph with metadata."""
        try:
            from python.helpers.graphrag_helper import GraphRAGHelper

            # Get area-specific instruction for better entity extraction
            area_instructions = {
                Memory.Area.FRAGMENTS.value: "Focus on extracting people, facts, events, and relationships from memory fragments",
                Memory.Area.MAIN.value: "Focus on extracting key concepts, entities, and important information",
                Memory.Area.SOLUTIONS.value: "Focus on extracting problem-solving approaches, methods, and technical solutions",
                Memory.Area.INSTRUMENTS.value: "Focus on extracting tools, technologies, and instruments used"
            }

            instruction = area_instructions.get(area, "Focus on extracting entities and relationships")

            # Create metadata for memory source tracking
            import time
            metadata = {
                "source_type": "memory_manual",
                "source_id": memory_id or f"manual_{int(time.time())}",
                "memory_id": memory_id,
                "area": area,
                "tool": "memory_save",
                "agent_id": self.agent.config.agent_name if hasattr(self.agent.config, 'agent_name') else "unknown"
            }

            # Get GraphRAG helper for the specified area and ingest
            helper = GraphRAGHelper.get_for_area(area)
            helper.ingest_text(text, instruction, metadata)

            return True

        except Exception:
            # Silently fail - GraphRAG integration shouldn't break memory saving
            return False
