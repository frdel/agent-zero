### graphrag_query

Query the GraphRAG knowledge graph using natural language questions
retrieves relevant information from ingested documents and data
uses semantic search and relationship traversal for comprehensive answers
requires prior data ingestion via graphrag_ingest tool
usage:

1. Query biographical information:

~~~json
{
    "thoughts": [
        "I need to find information about Einstein that was previously ingested",
        "Let me query the knowledge graph for biographical details"
    ],
    "headline": "Querying knowledge graph for Einstein's biography",
    "tool_name": "graphrag_query",
    "tool_args": {
        "message": "What scientific achievements did Einstein accomplish?"
    }
}
~~~

2. Query technical documentation:

~~~json
{
    "thoughts": [
        "I need to understand how the UserService API works",
        "The knowledge graph should have this information from ingested docs"
    ],
    "headline": "Querying API documentation in knowledge graph",
    "tool_name": "graphrag_query",
    "tool_args": {
        "message": "What parameters does the createUser function accept and what validations does it perform?"
    }
}
~~~

3. Query project information:

~~~json
{
    "thoughts": [
        "I need to check what decisions were made in recent meetings",
        "Let me query the knowledge graph for project updates"
    ],
    "headline": "Retrieving project decisions from knowledge graph",
    "tool_name": "graphrag_query",
    "tool_args": {
        "message": "What are the current action items and deadlines for Project Alpha?"
    }
}
~~~

4. Query relationships and connections:

~~~json
{
    "thoughts": [
        "I want to understand the connections between different concepts",
        "The knowledge graph excels at showing relationships"
    ],
    "headline": "Exploring concept relationships in knowledge graph",
    "tool_name": "graphrag_query",
    "tool_args": {
        "message": "How are the different microservices components related to each other?"
    }
}
~~~

**Parameters:**
- **message** (required): Natural language question or query about the stored knowledge

**Notes:**
- Knowledge graph must contain data (use graphrag_ingest first)
- Supports complex questions about relationships and connections
- Leverages semantic search for relevant information retrieval
- Returns comprehensive answers based on graph structure and content
- Works best with specific, focused questions rather than broad queries
