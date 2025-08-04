from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.helpers import settings


class MemoryDelete(Tool):

    async def execute(self, ids="", **kwargs):
        db = await Memory.get(self.agent)
        ids = [id.strip() for id in ids.split(",") if id.strip()]
        dels = await db.delete_documents_by_ids(ids=ids)

        # Delete corresponding data from GraphRAG
        await self._delete_from_graphrag(dels)

        result = self.agent.read_prompt("fw.memories_deleted.md", memory_count=len(dels))
        return Response(message=result, break_loop=False)

    async def _delete_from_graphrag(self, deleted_docs):
        """Delete entities from GraphRAG based on deleted memory documents."""
        try:
            from python.helpers.graphrag_helper import GraphRAGHelper

            # Extract entity names and keywords from deleted documents
            entities_to_delete = []
            for doc in deleted_docs:
                content = doc.page_content

                # Simple entity extraction - look for proper nouns and quoted terms
                import re

                # Find capitalized words (potential entity names)
                capitalized_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
                entities_to_delete.extend(capitalized_words)

                # Find quoted terms
                quoted_terms = re.findall(r'"([^"]+)"', content)
                entities_to_delete.extend(quoted_terms)

                # Find common entity patterns
                # Names after common patterns like "is a", "named", etc.
                name_patterns = re.findall(r'(?:is|was|named|called)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', content)
                entities_to_delete.extend(name_patterns)

            # Remove duplicates and clean up
            entities_to_delete = list(set([entity.strip() for entity in entities_to_delete if entity.strip()]))

            if entities_to_delete:
                # Use GraphRAG helper to delete entities (if enabled)
                set = settings.get_settings()
                if set.get("use_graphrag", True):
                    helper = GraphRAGHelper.get_default()
                    entities_query = " OR ".join(entities_to_delete)
                    helper.delete_knowledge(entities_query)

        except Exception:
            # GraphRAG deletion failure shouldn't break memory deletion
            pass
