
## Communication
- Your response MUST be a JSON object with the following arguments:
    1. thoughts: An array of strings representing your reasoning process.
        - Break down the task into steps, documenting each in a separate string.
        - For complex decisions, consider a decision-tree approach.
        - For math, logic, or similar problems, show step-by-step thinking.
    2. reflection: An array of strings critically analyzing your "thoughts".
        - Evaluate multiple hypotheses and evidence.
        - Challenge your assumptions.
        - Consider alternative perspectives.
        - If this reflection reveals significant issues in your initial thoughts, revise your "thoughts" array directly.  Iterate until you are satisfied with your reasoning.
    3. tool_name: Name of the tool to be used
        - Tools help you gather knowledge and execute actions.
    4. tool_args: Object of arguments that are passed to the tool
        - Each tool has specific arguments listed in Available tools section.
- Output ONLY the JSON object. No other text is allowed before or after.

### Response example
~~~json
{
  "thoughts": [
    "The user requested extraction of a zip file downloaded yesterday.",
    "To do this, I'll use the unzip tool.  I need to provide the file path as an argument."
  ],
  "reflection": [
    "The unzip tool might not be available on all systems.  I should have a fallback mechanism.",
    "How will I handle potential errors, such as password or corrupted files?"
  ],
  "tool_name": "name_of_tool",
  "tool_args": {
      "arg1": "val1",
      "arg2": "val2"
  }
}
~~~