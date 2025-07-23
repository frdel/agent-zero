from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.helpers.settings import get_settings
from python.helpers.print_style import PrintStyle
import json

class Mem0GraphTraverse(Tool):
    """
    Traverse graph memory relationships to find connection paths between entities.
    Useful for discovering indirect relationships and knowledge paths.
    """
    
    async def execute(self, start_entity="", end_entity="", max_depth=3, relationship_types="", **kwargs):
        """
        Traverse graph memory to find paths between entities
        
        Args:
            start_entity: Starting entity or concept
            end_entity: Target entity or concept (optional - if not provided, explores from start_entity)
            max_depth: Maximum depth to traverse (default: 3)
            relationship_types: Comma-separated list of relationship types to follow (optional)
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
        
        if not start_entity:
            return Response(
                message="Please provide a starting entity to traverse from.",
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
            
            # Parse relationship types if provided
            allowed_rel_types = None
            if relationship_types:
                allowed_rel_types = [rt.strip() for rt in relationship_types.split(",")]
            
            # Perform traversal
            if end_entity:
                # Find paths between start and end entities
                paths = await self._find_paths_between_entities(
                    mem0_db, start_entity, end_entity, max_depth, allowed_rel_types
                )
                return self._format_path_results(start_entity, end_entity, paths, max_depth)
            else:
                # Explore outward from start entity
                exploration = await self._explore_from_entity(
                    mem0_db, start_entity, max_depth, allowed_rel_types
                )
                return self._format_exploration_results(start_entity, exploration, max_depth)
            
        except ImportError:
            return Response(
                message="mem0ai package not installed. Install with: pip install 'mem0ai[graph]'",
                break_loop=False
            )
        except Exception as e:
            error_msg = f"Graph traversal failed: {str(e)}"
            PrintStyle.error(error_msg)
            
            # Provide helpful error messages
            if "neo4j" in str(e).lower():
                error_msg += "\nHint: Check Neo4j connection settings and ensure Neo4j service is running."
            elif "graph" in str(e).lower():
                error_msg += "\nHint: Ensure graph memory is properly configured in settings."
            
            return Response(
                message=error_msg,
                break_loop=False
            )
    
    async def _find_paths_between_entities(self, mem0_db, start_entity, end_entity, max_depth, allowed_rel_types):
        """Find all paths between two entities"""
        # Search for memories containing both entities
        combined_query = f"{start_entity} {end_entity}"
        
        search_params = {
            "query": combined_query,
            "user_id": mem0_db.user_id,
            "limit": 50  # Get more results for path finding
        }
        
        results = await mem0_db._retry_api_call(
            lambda: mem0_db.mem0_client.search(**search_params),
            f"Path search between {start_entity} and {end_entity}"
        )
        
        if not results:
            return []
        
        # Build graph from results
        graph = self._build_graph_from_results(results)
        
        # Find paths using breadth-first search
        paths = self._find_shortest_paths(graph, start_entity, end_entity, max_depth, allowed_rel_types)
        
        return paths
    
    async def _explore_from_entity(self, mem0_db, start_entity, max_depth, allowed_rel_types):
        """Explore outward from a single entity"""
        search_params = {
            "query": start_entity,
            "user_id": mem0_db.user_id,
            "limit": 30
        }
        
        results = await mem0_db._retry_api_call(
            lambda: mem0_db.mem0_client.search(**search_params),
            f"Exploration from {start_entity}"
        )
        
        if not results:
            return {"levels": [], "entities": set(), "relationships": []}
        
        # Build graph from results
        graph = self._build_graph_from_results(results)
        
        # Perform level-by-level exploration
        exploration = self._explore_levels(graph, start_entity, max_depth, allowed_rel_types)
        
        return exploration
    
    def _build_graph_from_results(self, results):
        """Build a graph structure from search results"""
        graph = {}  # entity -> [(relationship, target_entity)]
        
        for result in results:
            memory_data = result.get("memory", result)
            metadata = memory_data.get("metadata", {})
            
            # Extract relationships
            for rel in metadata.get("relationships", []):
                if isinstance(rel, dict):
                    source = rel.get('source', rel.get('from', ''))
                    target = rel.get('target', rel.get('to', ''))
                    rel_type = rel.get('type', rel.get('relationship', 'RELATED_TO'))
                    
                    if source and target:
                        # Add forward relationship
                        if source not in graph:
                            graph[source] = []
                        graph[source].append((rel_type, target))
                        
                        # Add reverse relationship for traversal
                        if target not in graph:
                            graph[target] = []
                        graph[target].append((f"REVERSE_{rel_type}", source))
        
        return graph
    
    def _find_shortest_paths(self, graph, start, end, max_depth, allowed_rel_types):
        """Find shortest paths between start and end entities"""
        from collections import deque
        
        queue = deque([(start, [])])  # (current_entity, path)
        visited = set()
        paths = []
        
        while queue and len(paths) < 5:  # Limit to 5 paths max
            current_entity, path = queue.popleft()
            
            if len(path) >= max_depth:
                continue
                
            if current_entity == end and path:
                paths.append(path)
                continue
            
            state = (current_entity, len(path))
            if state in visited:
                continue
            visited.add(state)
            
            if current_entity in graph:
                for rel_type, next_entity in graph[current_entity]:
                    # Filter by relationship types if specified
                    if allowed_rel_types and rel_type not in allowed_rel_types:
                        # Also check without REVERSE_ prefix
                        clean_rel_type = rel_type.replace("REVERSE_", "")
                        if clean_rel_type not in allowed_rel_types:
                            continue
                    
                    new_path = path + [(current_entity, rel_type, next_entity)]
                    queue.append((next_entity, new_path))
        
        return paths
    
    def _explore_levels(self, graph, start_entity, max_depth, allowed_rel_types):
        """Explore graph level by level from start entity"""
        levels = []
        current_level = {start_entity}
        visited = {start_entity}
        all_relationships = []
        
        for depth in range(max_depth):
            if not current_level:
                break
                
            next_level = set()
            level_relationships = []
            
            for entity in current_level:
                if entity in graph:
                    for rel_type, target_entity in graph[entity]:
                        # Filter by relationship types if specified
                        if allowed_rel_types and rel_type not in allowed_rel_types:
                            clean_rel_type = rel_type.replace("REVERSE_", "")
                            if clean_rel_type not in allowed_rel_types:
                                continue
                        
                        if target_entity not in visited:
                            next_level.add(target_entity)
                            visited.add(target_entity)
                        
                        level_relationships.append((entity, rel_type, target_entity))
                        all_relationships.append((entity, rel_type, target_entity))
            
            if next_level:
                levels.append({
                    "depth": depth + 1,
                    "entities": list(next_level),
                    "relationships": level_relationships
                })
            
            current_level = next_level
        
        return {
            "levels": levels,
            "entities": visited,
            "relationships": all_relationships
        }
    
    def _format_path_results(self, start_entity, end_entity, paths, max_depth):
        """Format path finding results"""
        if not paths:
            return Response(
                message=f"No paths found between '{start_entity}' and '{end_entity}' within {max_depth} steps.",
                break_loop=False
            )
        
        response_parts = [
            f"**Paths from '{start_entity}' to '{end_entity}'**",
            f"Found {len(paths)} path(s) within {max_depth} steps:",
            ""
        ]
        
        for i, path in enumerate(paths, 1):
            response_parts.append(f"**Path #{i}** ({len(path)} steps):")
            
            path_str_parts = [start_entity]
            for source, rel_type, target in path:
                clean_rel_type = rel_type.replace("REVERSE_", "←")
                if "REVERSE_" in rel_type:
                    path_str_parts.append(f" ←[{clean_rel_type}]← {target}")
                else:
                    path_str_parts.append(f" →[{rel_type}]→ {target}")
            
            response_parts.append("".join(path_str_parts))
            response_parts.append("")
        
        return Response(
            message="\n".join(response_parts),
            break_loop=False
        )
    
    def _format_exploration_results(self, start_entity, exploration, max_depth):
        """Format exploration results"""
        if not exploration["levels"]:
            return Response(
                message=f"No connections found from '{start_entity}' within {max_depth} steps.",
                break_loop=False
            )
        
        response_parts = [
            f"**Graph Exploration from '{start_entity}'**",
            f"Explored {len(exploration['entities'])} entities across {len(exploration['levels'])} level(s):",
            ""
        ]
        
        for level in exploration["levels"]:
            depth = level["depth"]
            entities = level["entities"]
            relationships = level["relationships"]
            
            response_parts.extend([
                f"**Level {depth}** ({len(entities)} entities):",
                ""
            ])
            
            # Group relationships by source entity
            rel_groups = {}
            for source, rel_type, target in relationships:
                if source not in rel_groups:
                    rel_groups[source] = []
                clean_rel_type = rel_type.replace("REVERSE_", "←")
                if "REVERSE_" in rel_type:
                    rel_groups[source].append(f"←[{clean_rel_type}]← {target}")
                else:
                    rel_groups[source].append(f"→[{rel_type}]→ {target}")
            
            # Show relationships for each entity in this level
            for source, connections in list(rel_groups.items())[:10]:  # Limit display
                response_parts.append(f"  {source}:")
                for conn in connections[:5]:  # Limit connections per entity
                    response_parts.append(f"    {conn}")
                response_parts.append("")
            
            if len(rel_groups) > 10:
                response_parts.append(f"  ... and {len(rel_groups) - 10} more entities")
                response_parts.append("")
        
        # Add summary
        total_rels = len(exploration["relationships"])
        rel_types = set()
        for _, rel_type, _ in exploration["relationships"]:
            clean_rel_type = rel_type.replace("REVERSE_", "")
            rel_types.add(clean_rel_type)
        
        response_parts.extend([
            "**Summary:**",
            f"• Total entities discovered: {len(exploration['entities'])}",
            f"• Total relationships: {total_rels}",
            f"• Unique relationship types: {len(rel_types)}",
            ""
        ])
        
        if rel_types:
            response_parts.append(f"• Relationship types: {', '.join(sorted(rel_types))}")
        
        return Response(
            message="\n".join(response_parts),
            break_loop=False
        )