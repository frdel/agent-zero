### zakat_questionnaire_tool:
Interactive questionnaire tool to gather information needed for Zakat calculation.
used for zakat calculation if user wants to calculate zakat

Features:
- Asks questions in provided language
- Collects all necessary asset information
- Validates responses
- Automatically triggers Zakat calculation when complete
- Try to guide user with suggestion with each question

Usage:
Start with no parameters to begin questionnaire:
~~~json
{
    "thoughts": [
        "Need to gather information for Zakat calculation",
        "Will start questionnaire from beginning"
    ],
    "tool_name": "zakat_questionnaire_tool",
    "tool_args": {
        "current_question": 0,
        "answers": {},
        "language": "bn"
    }
}
~~~

Continue with previous answers:
~~~json
{
    "thoughts": [
        "Continuing questionnaire",
        "Processing answer and moving to next question"
    ],
    "tool_name": "zakat_questionnaire_tool",
    "tool_args": {
        "current_question": 1,
        "answers": {
            "gold_price": "8500"
        },
        "language": "bn"
    }
}
~~~ 