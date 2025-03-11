### response:
The final answer to user is contained in the "text" argument
Ends task processing - use this tool ONLY when done, no task active OR you need feedback from user
Put the text (for example final task result) in text arg
Always write full file paths if local files are mentioned
Use full sentences and language matching the user's request
Consider any directions from the user about the form and contents of the response before answering

#### Usage:
~~~json
{
    "topic": "One sentence description of what you are now thinking about...",
    "observations": [
        "...",
    ],
    "thoughts": [
        "...",
    ],
    "reflection": ["..."],
    "tool_name": "response",
    "tool_args": {
        "text": "Answer to the user",
    }
}
~~~
