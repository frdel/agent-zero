### graphrag_reset

Reset the GraphRAG knowledge graph schema when experiencing compatibility issues
clears the entire knowledge graph and resets its schema
resolves schema conflicts and AttributeType errors
use with caution as this deletes all existing graph data

#### When to use
- When getting "Invalid attribute type" errors from GraphRAG
- When the knowledge graph schema becomes corrupted
- When you need to start fresh with a clean knowledge graph
- When schema conflicts prevent proper data access

#### Parameters
- `confirm` (bool): Safety confirmation flag. Must be set to `true` to actually perform the reset.

#### Important Notes
⚠️ **WARNING**: This tool will permanently delete ALL data from the knowledge graph. This action cannot be undone.

Only use this tool when:
1. You're experiencing persistent schema compatibility issues
2. The knowledge graph is not functioning properly due to schema conflicts
3. You want to start completely fresh with ingestion

After using this tool, you'll need to re-ingest all your knowledge using the GraphRAG ingestion tool.

#### Usage Examples

1. Reset graph due to schema conflicts:

~~~json
{
    "thoughts": [
        "I'm getting 'Invalid attribute type' errors from GraphRAG",
        "The knowledge graph schema seems corrupted",
        "I need to reset it to resolve these compatibility issues"
    ],
    "headline": "Resetting knowledge graph schema due to compatibility issues",
    "tool_name": "graphrag_reset",
    "tool_args": {
        "confirm": true
    }
}
~~~

2. Start fresh with clean knowledge graph:

~~~json
{
    "thoughts": [
        "I want to start over with a completely clean knowledge graph",
        "This will clear all existing data and schema",
        "After reset I can re-ingest information with a fresh schema"
    ],
    "headline": "Clearing knowledge graph for fresh start",
    "tool_name": "graphrag_reset",
    "tool_args": {
        "confirm": true
    }
}
~~~

The tool will provide confirmation when the reset is complete and the graph is ready for fresh data.
