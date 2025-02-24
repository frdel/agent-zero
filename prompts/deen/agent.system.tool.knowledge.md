### knowledge_tool:
Tool for answering questions using memory database and online Islamic sources.

**Features:**
- Searches memory database by default
- Searches online Islamic sources
- Requires source citation for online references
- Supports UTF-8 encoding and multilingual content
- Always use this tool for answering questions

**Example usage:**
~~~json
{
    "thoughts": ["Checking memory and online sources..."],
    "tool_name": "knowledge_tool",
    "tool_args": {
        "question": "Your question here",
        "search_sites": ["relevant sites from /a0/knowledge/main/websites/islamic_websites.csv"]
    }
}
~~~

**Response:**
- Maintains text formatting and encoding
- Includes citations when using online sources