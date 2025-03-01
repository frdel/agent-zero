### zakat_questionnaire_tool:
Interactive questionnaire tool to gather information needed for Zakat calculation.
Used for zakat calculation if user wants to calculate zakat in a guided manner.

NOTE: This questionnaire is optional for token optimization. Users can directly use the zakat_calculator_tool with their assets and liabilities information. For users who successfully calculated zakat or want to cancel, use the zakat_calculator_tool with status="success" or status="cancel" parameter.

Features:
- Asks questions in provided language (Bengali or English)
- Collects all necessary asset information
- Validates responses
- Automatically triggers Zakat calculation when complete
- Dynamically determines next questions based on answers provided
- Supports all asset types recognized by the calculator, including agricultural and mining assets
- Allows entry of gold/silver by either weight or value

Questionnaire Flow:
1. First asks configuration questions (gold/silver prices)
2. Then asks about various assets:
   - Cash and bank deposits
   - Loans given to others
   - Investments and shares
   - Precious metals (gold/silver by weight or value)
   - Trade goods
   - Agricultural assets (if applicable)
   - Mining resources (if applicable)
   - Investment properties
   - Other income
3. Finally asks about liabilities (debts, expenses)

Response Format:
The tool returns an object with:
- `text`: The question text to display to the user
- `type`: The type of response expected ("text" or "multiple_choice")
- `question_id`: The ID of the current question (for internal use)
- `options`: Array of options (only for multiple_choice questions)

When complete, it returns a dictionary with instructions to call the zakat_calculator_tool.

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
        "answers": {},
        "language": "bn"  // or "en" for English
    }
}
~~~

Continue with user's answer:
~~~json
{
    "thoughts": [
        "Continuing questionnaire",
        "User provided answer '8500' for gold price"
    ],
    "tool_name": "zakat_questionnaire_tool",
    "tool_args": {
        "answers": {
            "gold_price": "8500",  // add the answer with the question_id
            // include all previous answers
        },
        "language": "bn"
    }
}
~~~

For multiple choice questions, provide the index of the selected option (starting from 0):
~~~json
{
    "thoughts": [
        "User selected to provide gold information by weight"
    ],
    "tool_name": "zakat_questionnaire_tool",
    "tool_args": {
        "answers": {
            "gold_price": "8500",
            "gold_input_type": "0",  // 0 = weight, 1 = value
            // include all previous answers
        },
        "language": "bn"
    }
}
~~~

IMPORTANT REMINDER:
1. Always add each new answer to the "answers" object using the question_id
2. Display the text field from the response to the user and wait for their input
3. For multiple choice questions, show the options and get the selected index
4. The tool automatically determines which question to ask next based on the answers dictionary and handles conditional logic 