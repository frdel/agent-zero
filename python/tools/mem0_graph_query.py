from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.helpers.settings import get_settings
from python.helpers.print_style import PrintStyle
import json

class Mem0GraphQuery(Tool):
    """
    Advanced graph-based memory query tool for exploring entity relationships and semantic connections.
    Uses Neo4j graph database to perform complex queries across memory relationships.
    """
    
    async def execute(self, query="", relationship_type="", entity_type="", limit=10, depth=2, **kwargs):
        """
        Query the graph memory database for entities and relationships
        
        Args:
            query: Natural language query or Cypher query to search for
            relationship_type: Specific relationship type to filter by (optional)
            entity_type: Specific entity type to filter by (optional)  
            limit: Maximum number of results to return (default: 10)
            depth: Maximum relationship depth to traverse (default: 2)
        """
        settings = get_settings()
        
        # Check if mem0 backend is enabled and graph memory is enabled
        if (settings.get("memory_backend") != "mem0" or 
            not settings.get("mem0_enabled", False) or
            not settings.get("mem0_enable_graph_memory", False)):
            
            return Response(
                message="Graph memory is not enabled. Please enable mem0 backend and graph memory in settings.",
                break_loop=False
            )
        
        if not query:
            return Response(
                message="Please provide a query to search the graph memory.",
                break_loop=False
            )
        
        try:
            from python.helpers.memory_mem0 import Mem0Memory
            mem0_db = await Mem0Memory.get(self.agent)
            
            if not mem0_db.mem0_client:
                return Response(
                    message="Failed to connect to mem0 graph database.",
                    break_loop=False
                )
            
            # Perform graph-based search
            search_params = {
                "query": query,
                "user_id": mem0_db.user_id,
                "limit": int(limit)
            }
            
            # Add relationship and entity type filters if specified
            if relationship_type:
                search_params["filters"] = search_params.get("filters", {})
                search_params["filters"]["relationship_type"] = relationship_type
                
            if entity_type:
                search_params["filters"] = search_params.get("filters", {})
                search_params["filters"]["entity_type"] = entity_type
            
            # Execute graph search
            results = await mem0_db._retry_api_call(
                lambda: mem0_db.mem0_client.search(**search_params),
                f"Graph memory search for: {query}"
            )
            
            if not results:
                return Response(
                    message=f"No graph memories found for query: '{query}'",
                    break_loop=False
                )
            
            # Format results with graph-specific information
            formatted_results = []
            
            for idx, result in enumerate(results[:int(limit)]):
                memory_data = result.get("memory", result)
                
                # Extract graph-specific metadata
                metadata = memory_data.get("metadata", {})
                entities = metadata.get("entities", [])
                relationships = metadata.get("relationships", [])
                
                formatted_result = {
                    "id": memory_data.get("id", f"unknown_{idx}"),
                    "content": memory_data.get("text", memory_data.get("content", "No content")),
                    "score": result.get("score", 0.0),
                    "entities": entities,
                    "relationships": relationships,
                    "created_at": metadata.get("created_at"),
                    "updated_at": metadata.get("updated_at"),
                    "user_id": memory_data.get("user_id", mem0_db.user_id)
                }
                
                formatted_results.append(formatted_result)
            
            # Build comprehensive response
            response_parts = [
                f"Found {len(formatted_results)} graph memories for query: '{query}'",
                ""
            ]
            
            for idx, result in enumerate(formatted_results, 1):
                response_parts.extend([
                    f"**Memory #{idx}** (ID: {result['id']}) - Score: {result['score']:.3f}",
                    f"Content: {result['content']}",
                ])
                
                # Show entities if present
                if result['entities']:
                    entity_list = []
                    for entity in result['entities']:
                        if isinstance(entity, dict):
                            label = entity.get('label', entity.get('name', str(entity)))
                            entity_type = entity.get('type', 'Unknown')
                            entity_list.append(f"{label} ({entity_type})")
                        else:
                            entity_list.append(str(entity))
                    response_parts.append(f"Entities: {', '.join(entity_list)}")
                
                # Show relationships if present
                if result['relationships']:
                    rel_list = []
                    for rel in result['relationships']:
                        if isinstance(rel, dict):
                            rel_type = rel.get('type', rel.get('relationship', 'Unknown'))
                            source = rel.get('source', rel.get('from', ''))
                            target = rel.get('target', rel.get('to', ''))
                            if source and target:
                                rel_list.append(f"{source} --[{rel_type}]--> {target}")
                            else:
                                rel_list.append(str(rel_type))
                        else:
                            rel_list.append(str(rel))
                    response_parts.append(f"Relationships: {', '.join(rel_list)}")
                
                # Add timestamp information
                if result['created_at']:
                    response_parts.append(f"Created: {result['created_at']}")
                if result['updated_at'] and result['updated_at'] != result['created_at']:
                    response_parts.append(f"Updated: {result['updated_at']}")
                    
                response_parts.append("")  # Empty line between results
            
            # Add summary information
            if relationship_type:
                response_parts.append(f"Filtered by relationship type: {relationship_type}")
            if entity_type:
                response_parts.append(f"Filtered by entity type: {entity_type}")
            
            response_parts.append(f"Search performed with depth: {depth}, limit: {limit}")
            
            return Response(
                message="\n".join(response_parts),
                break_loop=False
            )
            
        except ImportError:
            return Response(
                message="mem0ai package not installed. Install with: pip install 'mem0ai[graph]'",
                break_loop=False
            )
        except Exception as e:
            error_msg = f"Graph memory search failed: {str(e)}"
            PrintStyle.error(error_msg)
            
            # Provide helpful error messages for common issues
            if "neo4j" in str(e).lower():
                error_msg += "\nHint: Check Neo4j connection settings and ensure Neo4j service is running."
            elif "graph" in str(e).lower():
                error_msg += "\nHint: Ensure graph memory is properly configured in settings."
            
            return Response(
                message=error_msg,
                break_loop=False
            )