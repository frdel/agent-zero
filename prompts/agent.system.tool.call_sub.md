### call_subordinate

you can use subordinates for subtasks
subordinates can be scientist coder engineer etc
message field: always describe role, task details goal overview for new subordinate
delegate specific subtasks not entire task
reset arg usage:
  "true": spawn new subordinate
  "false": continue existing subordinate
if superior, orchestrate
respond to existing subordinates using call_subordinate tool with reset false
profile arg usage: select from available profiles for specialized subordinates, leave empty for default

example usage
~~~json
{
    "thoughts": [
        "The result seems to be ok but...",
        "I will ask a coder subordinate to fix...",
    ],
    "tool_name": "call_subordinate",
    "tool_args": {
        "profile": "",
        "message": "...",
        "reset": "true"
    }
}
~~~

**available profiles:**
{{agent_profiles}}