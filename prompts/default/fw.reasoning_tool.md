The agent (You) requested to perform deep multistep reasoning about:

!!! {{query}}

Analyze this task bit by bit and think step-by-step before answering.
Don't forget to follow correct formatting of your response as valid JSON!

# Response format:
~~~json
{
    "topic": "One sentence description of what you are now thinking about...",
    "observations": ["...", "..."],
    "thoughts": ["...", "..."],
    "reflection": ["...", "..."],
    "tool_name": "tool_name",
    "tool_args": {
        "argument1": "value1",
        "argument2": "value2"
    }
}
~~~
