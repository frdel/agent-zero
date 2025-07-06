### content_personalizer:
adapt educational content based on student learning profile and preferences
personalizes explanations examples and complexity for engineering students
usage:
~~~json
{
    "thoughts": [
        "This student is a visual learner in mechanical engineering",
        "Let me personalize this explanation about stress analysis"
    ],
    "tool_name": "content_personalizer",
    "tool_args": {
        "action": "personalize_explanation",
        "content": "Stress analysis involves calculating forces...",
        "student_profile": {
            "learning_style": {"primary": "visual"},
            "engineering_field": "mechanical",
            "complexity_tolerance": 7
        },
        "topic": "stress_analysis"
    }
}
~~~

~~~json
{
    "thoughts": [
        "Student seems confused, let me simplify this explanation"
    ],
    "tool_name": "content_personalizer",
    "tool_args": {
        "action": "adjust_complexity",
        "content": "The algorithm complexity...",
        "complexity_adjustment": -2,
        "current_level": 8
    }
}
~~~
