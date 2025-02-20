### reasoning_tool:
Reasoning tool is used to perform a reasoning step. This way the agent can continue reasoning about the task in another round of observations, thoughts and reflections.
This tool should be used as many times as needed to successfully conduct the agent's reasoning process until a result has best quality possible
It is a tool the agent should use to correct its own reasoning mistakes or to expand understanding of the query

#### Arguments:
*   query (string) : Imperative prompt in second person with clear instructions for the reasoning plan, result requirements and goals
*   reasoning_effort (Literal["low" | "medium" | "high"]): "low", "medium" or "high". It controls how many tokens the agent is allowed to use for thinking. Use the lowest needed value. Higher reasoning effort has higher material cost for the user but it also gives deeper/better reasoning results. Try to prefer "low" over "medium" and "medium" over "high" if possible.

!!! #### Important notes:
!!! *   When solving complex reasoning tasks and puzzles, use the "reasoning_tool" to be able to iterate on your own observations, thoughts and reflections, to refine your reasoning as often as necessary and to solve the task to the highest satisfaction.

#### Usage:
~~~json
{
    "observations": [
        "...",
    ],
    "thoughts": [
        "...",
    ],
    "reflection": [
        "...",
        "This is new, I need to update my observations and think it through again. But it's easy, got to think just a little more."
    ],
    "tool_name": "reasoning_tool",
    "tool_args": {
        "query": "Imperative prompt in second person with clear instructions for the reasoning plan, result requirements and goals",
        "reasoning_effort" : "low"
    }
}
~~~

~~~json
{
    "observations": [
        "...",
    ],
    "thoughts": [
        "...",
    ],
    "reflection": [
        "...",
        "Wait, i think I made a mistake in my reasoning, I need to update my observations and think it through again. I need to think really hard"
    ],
    "tool_name": "reasoning_tool",
    "tool_args": {
        "query": "Imperative prompt in second person with clear instructions for the reasoning plan, result requirements and goals",
        "reasoning_effort" : "high"

    }
}
~~~

~~~json
{
    "observations": [
        "...",
    ],
    "thoughts": [
        "...",
    ],
    "reflection": [
        "...",
        "Wait, i think I made a mistake in my reasoning, I need to update my observations and think it through again"
    ],
    "tool_name": "reasoning_tool",
    "tool_args": {
        "query": "Imperative prompt in second person with clear instructions for the reasoning plan, result requirements and goals",
        "reasoning_effort" : "medium"

    }
}
~~~
