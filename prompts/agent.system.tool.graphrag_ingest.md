### graphrag_ingest

Ingest textual information into the GraphRAG knowledge graph for later retrieval
processes text to extract entities, relationships, and create searchable knowledge base
use for documents, research data, code documentation, meeting notes, specifications
builds dynamic ontology automatically from ingested content
usage:

1. Ingest document or text content:

~~~json
{
    "thoughts": [
        "I need to store this information in the knowledge graph",
        "This will help me remember and query this data later",
        "Let me ingest this text into GraphRAG"
    ],
    "headline": "Ingesting document content into knowledge graph",
    "tool_name": "graphrag_ingest",
    "tool_args": {
        "text": "Albert Einstein was a German-born theoretical physicist who developed the theory of relativity. He received the Nobel Prize in Physics in 1921 for his explanation of the photoelectric effect.",
        "instruction": "Focus on biographical information and scientific achievements"
    }
}
~~~

2. Ingest code documentation:

~~~json
{
    "thoughts": [
        "I should store this API documentation for future reference",
        "The knowledge graph will help me understand the relationships between functions"
    ],
    "headline": "Storing API documentation in knowledge graph",
    "tool_name": "graphrag_ingest",
    "tool_args": {
        "text": "The UserService class provides methods for user management. The createUser() method accepts name, email, and role parameters. It validates the email format and checks for duplicate emails before creating the user record.",
        "instruction": "Extract API functions, parameters, and validation rules"
    }
}
~~~

3. Ingest research or meeting notes:

~~~json
{
    "thoughts": [
        "These meeting notes contain important decisions and action items",
        "Storing them in the knowledge graph will help track project progress"
    ],
    "headline": "Ingesting meeting notes into knowledge graph",
    "tool_name": "graphrag_ingest",
    "tool_args": {
        "text": "Project Alpha review meeting on March 15th. Team decided to migrate to microservices architecture. Sarah will lead the database migration by end of Q2. Budget approved for additional cloud infrastructure.",
        "instruction": "Focus on decisions, action items, deadlines, and responsible persons"
    }
}
~~~

**Parameters:**
- **text** (required): The textual content to ingest and process
- **instruction** (optional): Specific guidance on what information to extract or focus on

**Notes:**
- Text is automatically processed to extract entities and relationships
- Ontology is built dynamically based on the content
- Use specific instructions to guide entity extraction for specialized domains
- Successfully ingested content becomes queryable via graphrag_query tool
