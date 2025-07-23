## Advanced mem0 Memory Tools:
Enhanced memory management with AI-powered organization, user context, and graph relationships

### mem0_save:
Advanced memory saving with metadata and area selection
Supports enriched metadata, automatic organization, and memory evolution
- area: memory area classification (main/fragments/solutions/instruments)
- metadata: custom key-value pairs for enhanced organization
usage:
~~~json
{
    "thoughts": [
        "I'll save this with enhanced mem0 features and metadata",
    ],
    "headline": "Saving information with mem0 advanced features",
    "tool_name": "mem0_save",
    "tool_args": {
        "text": "User prefers Python for data analysis projects and uses pandas extensively",
        "area": "main",
        "metadata": {"category": "preferences", "skill_level": "intermediate"}
    }
}
~~~

### mem0_query:
Enhanced memory querying with user context and relationship awareness
Provides intelligent search with automatic context integration
- query: search query with natural language support
- limit: max results (default: 5)
- area: filter by memory area (optional)
- include_relations: include graph relationships (default: false)
usage:
~~~json
{
    "thoughts": [
        "Let me search with mem0's enhanced capabilities for better context",
    ],
    "headline": "Advanced memory search with context",
    "tool_name": "mem0_query",
    "tool_args": {
        "query": "user programming preferences and data tools",
        "limit": 10,
        "include_relations": true
    }
}
~~~

### mem0_relate:
Create and manage relationships between memories
Enables building knowledge graphs of connected information
- memory_ids: list of memory IDs to relate
- relationship_type: type of relationship (related_to/caused_by/part_of/etc)
- description: optional description of the relationship
usage:
~~~json
{
    "thoughts": [
        "I'll create relationships between these related memories",
    ],
    "headline": "Creating memory relationships",
    "tool_name": "mem0_relate",
    "tool_args": {
        "memory_ids": ["uuid1", "uuid2"],
        "relationship_type": "related_to",
        "description": "Both are user's preferred programming tools"
    }
}
~~~

### mem0_graph_query:
Query the knowledge graph for complex relationships
Find connected memories and relationship patterns
- entity: central entity to explore
- relationship_type: filter by relationship type (optional)
- depth: traversal depth (default: 2)
- limit: max results (default: 10)
usage:
~~~json
{
    "thoughts": [
        "I'll explore the knowledge graph around this concept",
    ],
    "headline": "Querying memory knowledge graph",
    "tool_name": "mem0_graph_query",
    "tool_args": {
        "entity": "Python programming",
        "depth": 3,
        "limit": 15
    }
}
~~~

### mem0_graph_visualize:
Visualize memory relationships as ASCII art graph
Shows connections between memories in readable format
- center_entity: entity to center the visualization around
- max_nodes: maximum nodes to display (default: 20)
- output_format: visualization format (ascii/json/summary)
usage:
~~~json
{
    "thoughts": [
        "Let me visualize the memory relationships around this topic",
    ],
    "headline": "Visualizing memory graph structure",
    "tool_name": "mem0_graph_visualize",
    "tool_args": {
        "center_entity": "user preferences",
        "max_nodes": 15,
        "output_format": "ascii"
    }
}
~~~

### mem0_services:
Manage mem0 services (QDrant, Neo4j, OpenMemory MCP)
Check status, start/stop services, view diagnostics
- action: status/start/stop/restart/diagnostics
- services: specific services (optional, defaults to all)
usage:
~~~json
{
    "thoughts": [
        "Let me check the status of mem0 services",
    ],
    "headline": "Checking mem0 service status",
    "tool_name": "mem0_services",
    "tool_args": {
        "action": "status"
    }
}
~~~

### mem0_forget:
Advanced memory deletion with mem0 features
Supports user context and relationship cleanup
- query: memories to forget (uses AI to understand context)
- confirm: require confirmation for safety (default: true)
usage:
~~~json
{
    "thoughts": [
        "I'll use mem0's advanced forget to remove specific memories",
    ],
    "headline": "Forgetting memories with mem0",
    "tool_name": "mem0_forget",
    "tool_args": {
        "query": "outdated programming preferences from 2020",
        "confirm": true
    }
}
~~~

### mem0_migrate:
Migrate memories between storage backends
Transfer from FAISS to mem0 or vice versa
- direction: faiss_to_mem0 or mem0_to_faiss
- preserve_metadata: keep original metadata (default: true)
- batch_size: migration batch size (default: 50)
usage:
~~~json
{
    "thoughts": [
        "I'll migrate the existing memories to mem0 for enhanced features",
    ],
    "headline": "Migrating memories to mem0 backend",
    "tool_name": "mem0_migrate",
    "tool_args": {
        "direction": "faiss_to_mem0",
        "preserve_metadata": true
    }
}
~~~