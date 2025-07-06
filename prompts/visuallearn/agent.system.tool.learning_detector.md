### learning_style_detector:
detect and track student learning styles through interaction analysis and surveys
stores findings in long-term memory for personalization
usage:
~~~json
{
    "thoughts": [
        "I need to understand how this student learns best",
        "Let me analyze their interaction patterns"
    ],
    "tool_name": "learning_style_detector",
    "tool_args": {
        "action": "analyze_interaction",
        "interaction_data": {
            "visual_requests": 3,
            "audio_requests": 1,
            "code_requests": 4,
            "simplify_requests": 1
        }
    }
}
~~~

~~~json
{
    "thoughts": [
        "This is a new student, let me offer an optional survey"
    ],
    "tool_name": "learning_style_detector", 
    "tool_args": {
        "action": "survey"
    }
}
~~~
