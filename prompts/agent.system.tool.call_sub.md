### a2a_subordinate

you can use subordinates for subtasks using A2A protocol
subordinates can be coder, analyst, researcher, tester, writer etc
message field: always describe role, task details goal overview for new subordinate
delegate specific subtasks not entire task
reset arg usage:
  "true": spawn new subordinate
  "false": continue existing subordinate
if superior, orchestrate multiple subordinates in parallel
respond to existing subordinates using a2a_subordinate tool with reset false

example usage
~~~json
{
    "thoughts": [
        "The result seems to be ok but...",
        "I will ask a coder subordinate to fix...",
    ],
    "tool_name": "a2a_subordinate",
    "tool_args": {
        "profile": "",
        "message": "...",
        "role": "coder",
        "reset": "true"
    }
}
~~~

**available profiles:**
{{agent_profiles}}