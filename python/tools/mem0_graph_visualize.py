from python.helpers.memory import Memory
from python.helpers.tool import Tool, Response
from python.helpers.settings import get_settings
from python.helpers.print_style import PrintStyle
import json

class Mem0GraphVisualize(Tool):
    """
    Visualize memory relationships and entity connections in the graph database.
    Creates ASCII representations or structured data for graph visualization.
    """
    
    async def execute(self, entity="", max_relationships=20, include_properties=True, format="ascii", **kwargs):
        """
        Visualize graph memory relationships around an entity or concept
        
        Args:
            entity: Central entity or concept to visualize relationships around
            max_relationships: Maximum number of relationships to include (default: 20)
            include_properties: Whether to include entity properties in visualization (default: True)
            format: Output format - 'ascii', 'json', or 'summary' (default: 'ascii')
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
        
        if not entity:
            return Response(
                message="Please provide an entity or concept to visualize graph relationships around.",
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
            
            # Search for memories related to the entity
            search_params = {
                "query": entity,
                "user_id": mem0_db.user_id,
                "limit": int(max_relationships)
            }
            
            # Execute search to get related memories
            results = await mem0_db._retry_api_call(
                lambda: mem0_db.mem0_client.search(**search_params),
                f"Graph visualization search for: {entity}"
            )
            
            if not results:
                return Response(
                    message=f"No graph relationships found for entity: '{entity}'",
                    break_loop=False
                )
            
            # Extract entities and relationships from results
            entities = {}  # entity_name -> properties
            relationships = []  # list of (source, relationship, target) tuples
            
            for result in results:
                memory_data = result.get("memory", result)
                metadata = memory_data.get("metadata", {})
                
                # Extract entities
                for ent in metadata.get("entities", []):
                    if isinstance(ent, dict):
                        name = ent.get('label', ent.get('name', str(ent)))
                        properties = ent.copy() if include_properties else {}
                        if name not in entities:
                            entities[name] = properties
                    else:
                        entities[str(ent)] = {}
                
                # Extract relationships
                for rel in metadata.get("relationships", []):
                    if isinstance(rel, dict):
                        rel_type = rel.get('type', rel.get('relationship', 'RELATED_TO'))
                        source = rel.get('source', rel.get('from', ''))
                        target = rel.get('target', rel.get('to', ''))
                        if source and target:
                            relationships.append((source, rel_type, target))
            
            # Generate visualization based on format
            if format.lower() == "json":
                return self._format_json_visualization(entity, entities, relationships)
            elif format.lower() == "summary":
                return self._format_summary_visualization(entity, entities, relationships)
            else:  # ascii format
                return self._format_ascii_visualization(entity, entities, relationships, include_properties)
            
        except ImportError:
            return Response(
                message="mem0ai package not installed. Install with: pip install 'mem0ai[graph]'",
                break_loop=False
            )
        except Exception as e:
            error_msg = f"Graph visualization failed: {str(e)}"
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
    
    def _format_ascii_visualization(self, central_entity, entities, relationships, include_properties):
        """Generate ASCII art visualization of the graph"""
        response_parts = [
            f"**Graph Visualization for: {central_entity}**",
            "=" * 50,
            ""
        ]
        
        # Group relationships by source
        outgoing_rels = {}  # source -> [(relationship, target)]
        incoming_rels = {}  # target -> [(source, relationship)]
        
        for source, rel_type, target in relationships:
            # Outgoing relationships
            if source not in outgoing_rels:
                outgoing_rels[source] = []
            outgoing_rels[source].append((rel_type, target))
            
            # Incoming relationships
            if target not in incoming_rels:
                incoming_rels[target] = []
            incoming_rels[target].append((source, rel_type))
        
        # Find entities most related to our central entity
        central_entity_lower = central_entity.lower()
        central_entities = [name for name in entities.keys() 
                          if central_entity_lower in name.lower() or name.lower() in central_entity_lower]
        
        if not central_entities:
            central_entities = [list(entities.keys())[0]] if entities else [central_entity]
        
        for central in central_entities:
            response_parts.extend([
                f"🎯 **{central}**",
                ""
            ])
            
            # Show entity properties if requested
            if include_properties and central in entities and entities[central]:
                props = entities[central]
                if props:
                    prop_strs = []
                    for key, value in props.items():
                        if key not in ['label', 'name']:  # Don't repeat the name
                            prop_strs.append(f"{key}: {value}")
                    if prop_strs:
                        response_parts.append(f"   Properties: {', '.join(prop_strs)}")
                        response_parts.append("")
            
            # Show outgoing relationships
            if central in outgoing_rels:
                response_parts.append("   Outgoing Relationships:")
                for rel_type, target in outgoing_rels[central]:
                    response_parts.append(f"   ├── --[{rel_type}]--> {target}")
                response_parts.append("")
            
            # Show incoming relationships
            if central in incoming_rels:
                response_parts.append("   Incoming Relationships:")
                for source, rel_type in incoming_rels[central]:
                    response_parts.append(f"   ├── {source} --[{rel_type}]--> ")
                response_parts.append("")
        
        # Show other connected entities
        other_entities = [name for name in entities.keys() if name not in central_entities]
        if other_entities:
            response_parts.extend([
                "📊 **Other Connected Entities:**",
                ""
            ])
            
            for entity in other_entities[:10]:  # Limit to top 10 other entities
                connections = []
                if entity in outgoing_rels:
                    connections.extend([f"--[{rel}]--> {target}" for rel, target in outgoing_rels[entity][:3]])
                if entity in incoming_rels:
                    connections.extend([f"{source} --[{rel}]-->" for source, rel in incoming_rels[entity][:3]])
                
                if connections:
                    response_parts.append(f"   • {entity}")
                    for conn in connections[:3]:  # Show max 3 connections per entity
                        response_parts.append(f"     └─ {conn}")
                    response_parts.append("")
        
        # Add summary statistics
        response_parts.extend([
            "📈 **Graph Statistics:**",
            f"   • Total Entities: {len(entities)}",
            f"   • Total Relationships: {len(relationships)}",
            f"   • Unique Relationship Types: {len(set(rel for _, rel, _ in relationships))}",
            ""
        ])
        
        if len(relationships) > 0:
            # Show relationship type distribution
            rel_counts = {}
            for _, rel_type, _ in relationships:
                rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1
            
            response_parts.append("   Relationship Types:")
            for rel_type, count in sorted(rel_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                response_parts.append(f"     • {rel_type}: {count}")
        
        return Response(
            message="\n".join(response_parts),
            break_loop=False
        )
    
    def _format_json_visualization(self, central_entity, entities, relationships):
        """Generate JSON representation of the graph"""
        graph_data = {
            "central_entity": central_entity,
            "entities": entities,
            "relationships": [
                {"source": source, "relationship": rel_type, "target": target}
                for source, rel_type, target in relationships
            ],
            "statistics": {
                "entity_count": len(entities),
                "relationship_count": len(relationships),
                "unique_relationship_types": len(set(rel for _, rel, _ in relationships))
            }
        }
        
        return Response(
            message=f"Graph data for '{central_entity}':\n\n```json\n{json.dumps(graph_data, indent=2)}\n```",
            break_loop=False
        )
    
    def _format_summary_visualization(self, central_entity, entities, relationships):
        """Generate summary statistics of the graph"""
        response_parts = [
            f"**Graph Summary for: {central_entity}**",
            "",
            f"📊 Found {len(entities)} entities and {len(relationships)} relationships",
            ""
        ]
        
        if relationships:
            # Relationship type analysis
            rel_counts = {}
            for _, rel_type, _ in relationships:
                rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1
            
            response_parts.extend([
                "**Top Relationship Types:**",
                ""
            ])
            
            for rel_type, count in sorted(rel_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                response_parts.append(f"• {rel_type}: {count} connections")
            
            response_parts.append("")
            
            # Entity connection analysis
            entity_connections = {}
            for source, _, target in relationships:
                entity_connections[source] = entity_connections.get(source, 0) + 1
                entity_connections[target] = entity_connections.get(target, 0) + 1
            
            if entity_connections:
                response_parts.extend([
                    "**Most Connected Entities:**",
                    ""
                ])
                
                for entity, count in sorted(entity_connections.items(), key=lambda x: x[1], reverse=True)[:5]:
                    response_parts.append(f"• {entity}: {count} connections")
        
        return Response(
            message="\n".join(response_parts),
            break_loop=False
        )