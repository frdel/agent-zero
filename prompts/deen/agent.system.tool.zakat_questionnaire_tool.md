### zakat_questionnaire_tool:
Interactive questionnaire tool to gather information needed for Zakat calculation.
Used for zakat calculation if user wants to calculate zakat.

Features:
- Asks questions in provided language (Bengali or English)
- Collects all necessary asset information
- Validates responses
- Automatically triggers Zakat calculation when complete

Questionnaire Flow:
1. First asks configuration questions (gold/silver prices)
2. Then asks about assets (cash, investments, property, etc.)
3. Finally asks about liabilities (debts, expenses)

Response Format:
The tool returns the question directly as a string to be shown to the user.
When complete, it returns a dictionary with instructions to call the zakat_calculator_tool.

IMPORTANT: The tool now includes a hint at the end of each question with the exact current_question value to use for the next question. Always use this exact value to avoid skipping questions.

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
        "language": "bn"  // or "en" for English
    }
}
~~~

Continue with user's answer and move to next question:
~~~json
{
    "thoughts": [
        "Continuing questionnaire",
        "User provided answer '8500' for gold price",
        "Moving to next question using the specified current_question value"
    ],
    "tool_name": "zakat_questionnaire_tool",
    "tool_args": {
        "current_question": 1,  // Use EXACTLY the value provided in the previous question
        "answers": {
            "gold_price": "8500"  // include previous answers
        },
        "language": "bn"
    }
}
~~~

IMPORTANT REMINDER:
1. DO NOT skip questions - follow the exact current_question value provided at the end of each question
2. Display the message directly to the user and wait for their response
3. Add each answer to the "answers" object with the appropriate question ID 