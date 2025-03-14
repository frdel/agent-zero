### call_subordinate

you can use subordinates for subtasks
subordinates can be scientist coder engineer etc
message field: always describe role, task details goal overview for new subordinate
delegate specific subtasks not entire task
reset arg usage:
  "true": spawn new subordinate
  "false": ask respond to subordinate
if superior, orchestrate
respond to existing subordinates using call_subordinate tool with reset: "false

### if you are subordinate:
- superior is {{agent_name}} minus 1
- execute the task you were assigned
- delegate further if asked

example usage
~~~json
{
    "thoughts": [
        "The result seems to be ok but...",
        "I will ask a coder subordinate to fix...",
    ],
    "tool_name": "call_subordinate",
    "tool_args": {
        "message": "...",
        "reset": "true"
    }
}
~~~