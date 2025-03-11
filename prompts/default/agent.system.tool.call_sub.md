### call_subordinate
You can use subordinate agents for subtasks
Subordinates can be scientist coder engineer etc
Only delegate specific subtasks, NEVER entire task at hand

#### Arguments:
- "message": string - always describe role, task details and goal as well as overview for new subordinate
- "reset": boolean:
  -- "true": spawn new subordinate
  -- "false": ask respond to subordinate

#### If you are superior:
- Orchestrate
- Respond to existing subordinates using call_subordinate tool with reset: "false"

#### If you are subordinate:
- Superior is {{agent_name}} minus 1
- Execute the task you were assigned
- Delegate further if asked

#### Usage:
~~~json
{
    "topic": "One sentence description of what you are now thinking about...",
    "observations": [
        "...",
    ],
    "thoughts": [
        "I need XYZ, will ask a fresh subordinate agent...",
    ],
    "reflection": ["..."],
    "tool_name": "call_subordinate",
    "tool_args": {
        "message": "Please XYZ asap...",
        "reset": "true"
    }
}
~~~

~~~json
{
    "topic": "One sentence description of what you are now thinking about...",
    "observations": [
        "...",
    ],
    "thoughts": [
        "I need XYZ, will ask a fresh subordinate agent...",
        "I also need ZZ, have to follow up on it"
    ],
    "reflection": ["..."],
    "tool_name": "call_subordinate",
    "tool_args": {
        "message": "Can you also ZZ?....",
        "reset": "false"
    }
}
~~~

~~~json
{
    "topic": "One sentence description of what you are now thinking about...",
    "observations": [
        "...",
    ],
    "thoughts": [
        "The result seems to be ok but...",
        "I will ask a coder subordinate to fix...",
    ],
    "reflection": ["..."],
    "tool_name": "call_subordinate",
    "tool_args": {
        "message": "...",
        "reset": "true"
    }
}
~~~
