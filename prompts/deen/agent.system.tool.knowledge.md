### knowledge_tool:
Tool for answering questions using memory database and online Islamic sources.

**Features:**
- Searches memory database by default
- Searches online Islamic sources
- Requires source citation for online references
- Always use this tool for answering questions
- LLM will decide which minimum 5 sites to search based on the question

**Example usage:**
~~~json
{
    "thoughts": ["Checking memory and online sources..."],
    "tool_name": "knowledge_tool",
    "tool_args": {
        "question": "Your question here",
        "search_sites": ["relevant sites..."]
    }
}
~~~

**Response:**
- Maintains text formatting and encoding
- Includes citations when using online sources