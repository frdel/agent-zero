### call_subordinate

you can use subordinates for subtasks
subordinates can be scientist coder engineer etc
message field: always describe role, task details goal overview for new subordinate
delegate specific subtasks not entire task
reset arg usage:
  "true": spawn new subordinate
  "false": ask respond to subordinate
prompt_profile defines subordinate specialization
if superior, orchestrate
respond to existing subordinates using call_subordinate tool with reset: "false"

#### if you are subordinate:
- superior is {{agent_name}} minus 1
- execute the task you were assigned
- delegate further if asked

#### Arguments:
- message (string): The detailed task for the subordinate to accomplish
- reset (boolean): Whether to discard current subordinate dialog and spawn a fresh subordinate. If Fals, every subsequent call will continue the conversation with subordinate, if True new subordinate is spawned with the task.
- prompt_profile (string): Defines what prompt profile to use for the subordinate. This sets the behavior of the agent and his specialization (see list of profiles below for details). Choose a profile best suited for the task

##### Prompt Profiles (prompt_profile options)
{{prompt_profiles}}

#### example usage
~~~json
{
    "thoughts": [
        "The result seems to be ok but...",
        "I will ask a subordinate to fix...",
    ],
    "tool_name": "call_subordinate",
    "tool_args": {
        "message": "...",
        "reset": "true",
        "prompt_profile": "default",
    }
}
~~~

~~~json
{
    "thoughts": [
        "This task is challenging and requires a data analyst",
        "The research_agent profile supports data analysis",
    ],
    "tool_name": "call_subordinate",
    "tool_args": {
        "message": "...",
        "reset": "true",
        "prompt_profile": "research_agent",
    }
}
~~~
