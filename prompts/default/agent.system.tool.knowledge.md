### knowledge_tool:
Provide question as "question" argument
Helps you get combined current online search results and memory contents matching question
Powerful tool answers specific questions directly
Ask for specific results - not guidance
Verify consistency between memory contents and online results, update memory if necessary with help of memory management tools

#### Usage:
~~~json
{
    "observations": [
        "...",
    ],
    "thoughts": [
        "...",
    ],
    "reflection": ["..."],
    "tool_name": "knowledge_tool",
    "tool_args": {
        "question": "How to...",
    }
}
~~~
