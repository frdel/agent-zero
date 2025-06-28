### call_subordinate

you can use subordinates for subtasks
subordinates can be specialized roles
message field: always describe task details goal overview important details for new subordinate
delegate specific subtasks not entire task
reset arg usage:
  "true": spawn new subordinate
  "false": continue current conversation
prompt_profile defines subordinate specialization

#### if you are superior
- identify new tasks which your main task's completion depends upon
- break down your main task into subtasks if possible. If the task can not be split execute it yourself
- only let saubtasks and new depended upon tasks of your main task be handled by subordinates
- never forward your entire task to a subordinate to avoid endless delegation loops

#### if you are subordinate:
- superior is {{agent_name}} minus 1
- execute the task you were assigned
- delegate further if asked
- break down tasks and delegate if necessary
- do not delegate tasks you can accomplish yourself without refining them
- only subtasks of your current main task are allowed to be delegated. Never delegate your entire task ro prevent endless loops.

#### Arguments:
- message (string): always describe task details goal overview important details for new subordinate
- reset (boolean): true: spawn new subordinate, false: continue current conversation
- prompt_profile (string): defines specialization, only available prompt profiles below, can omit when reset false

##### Prompt Profiles available
{{prompt_profiles}}

#### example usage
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

~~~json
{
    "thoughts": [
        "The response is missing...",
        "I will ask a subordinate to add...",
    ],
    "tool_name": "call_subordinate",
    "tool_args": {
        "message": "...",
        "reset": "false",
    }
}
~~~