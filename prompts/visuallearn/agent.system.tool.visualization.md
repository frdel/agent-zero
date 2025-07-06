### visualization_bridge:
integrate with VisuaLearn visualization engine for engineering concepts
detect visualizable content and suggest interactive simulations
generate links to visualization engine with student context
usage:
~~~json
{
    "thoughts": [
        "The student is learning about bubble sort",
        "This would be perfect for an interactive visualization"
    ],
    "tool_name": "visualization_bridge",
    "tool_args": {
        "action": "suggest_visualization",
        "concept": "bubble_sort",
        "learning_style": "visual",
        "student_level": "intermediate"
    }
}
~~~

~~~json
{
    "thoughts": [
        "Let me check what concepts in this explanation can be visualized"
    ],
    "tool_name": "visualization_bridge",
    "tool_args": {
        "action": "detect_visualizable",
        "content": "bubble sort algorithm works by repeatedly stepping through the list",
        "subject_area": "computer_science"
    }
}
~~~
