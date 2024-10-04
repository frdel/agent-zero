### knowledge_tool:
Provide a "question" argument to retrieve information from online sources and memory. Prioritize asking for direct answers over guidance. 
Verify memory information against online sources.
**Example usage**:
~~~json
{
    "thoughts": [
        "I need to gather information about...",
        "First I will search...",
        "Then I will...",
    ],
    "tool_name": "knowledge_tool",
    "tool_args": {
        "question": "How to...",
    }
}
~~~