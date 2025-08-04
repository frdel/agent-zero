### graphrag_delete

Delete specific knowledge from the GraphRAG knowledge graph using natural language queries
removes entities and relationships based on keywords and patterns
useful for cleaning up outdated or incorrect information
requires explicit confirmation to prevent accidental data loss

#### When to use
- Remove outdated or incorrect information from the knowledge graph
- Clean up specific entities or relationships
- Delete knowledge related to specific topics or domains
- Maintain data quality by removing obsolete content

#### Parameters
- `query` (str): Natural language description of what to delete (e.g., "Python programming language", "outdated framework information")
- `confirm` (bool): Safety confirmation flag. Must be set to `true` to actually delete. Default is `false` for preview mode.

#### Important Notes
⚠️ **WARNING**: This tool will permanently delete data from the knowledge graph. This action cannot be undone.

Always use `confirm: false` first to preview what would be deleted, then set `confirm: true` if you want to proceed.

#### Usage Examples

1. Preview deletion (safe, shows what would be deleted):

~~~json
{
    "thoughts": [
        "I need to see what would be deleted for Python-related content",
        "Let me preview the deletion first before confirming"
    ],
    "headline": "Previewing deletion of Python-related knowledge",
    "tool_name": "graphrag_delete",
    "tool_args": {
        "query": "Python programming language",
        "confirm": false
    }
}
~~~

2. Confirm deletion after preview:

~~~json
{
    "thoughts": [
        "The preview looks correct, I want to delete this outdated information",
        "I'll confirm the deletion now"
    ],
    "headline": "Deleting outdated Python information from knowledge graph",
    "tool_name": "graphrag_delete",
    "tool_args": {
        "query": "Python programming language",
        "confirm": true
    }
}
~~~

3. Delete framework-related information:

~~~json
{
    "thoughts": [
        "I need to remove all information about deprecated frameworks",
        "This will help keep the knowledge graph current"
    ],
    "headline": "Removing deprecated framework information",
    "tool_name": "graphrag_delete",
    "tool_args": {
        "query": "deprecated frameworks Angular.js jQuery",
        "confirm": true
    }
}
~~~

The tool will find entities and relationships containing the specified keywords and remove them from the graph.
