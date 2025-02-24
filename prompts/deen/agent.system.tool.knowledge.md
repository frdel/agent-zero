### knowledge_tool:
Powerful tool to provide direct answers to specific questions by combining memory and optional online sources.

**Features:**
- Searches memory database by default
- Optional online Islamic sources search when requested for verified answers
- If you use online sources, you must provide the source name
- Ensures proper UTF-8 encoding of all text
- Validates Islamic authenticity when using online sources
- Provides citations and references

**Input Handling:**
- Preserves UTF-8 character encoding
- Maintains proper text formatting
- Supports multilingual content through Unicode

**Example usage without online search**:
~~~json
{
    "thoughts": [
        "Searching memory database",
        "Checking stored Islamic knowledge"
    ],
    "tool_name": "knowledge_tool",
    "tool_args": {
        "question": "Your question here in any language"
    }
}
~~~

**Example usage with online search**:
~~~json
{
    "thoughts": [
        "Need current information from Islamic sources",
        "Will verify memory with online references"
    ],
    "tool_name": "knowledge_tool",
    "tool_args": {
        "question": "Your question here in any language",
        "use_online": true
    }
}
~~~

**Response Format:**
- Preserves original text formatting
- Maintains proper character encoding
- Includes both memory and online sources when requested
- Provides clear citations

**Best Practices:**
- Always validate UTF-8 encoding
- Check for proper rendering of special characters
- Verify citations maintain proper formatting
- Double-check text integrity