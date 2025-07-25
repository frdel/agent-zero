### response:
final answer to user
ends task processing use only when done or no task active
put result in text arg
always use markdown formatting headers bold text lists
full message is automatically markdown do not wrap ~~~markdown
use emojis as icons improve readability
prefer using tables
focus nice structured output key selling point
output full file paths not only names to be clickable
images shown with ![alt](img:///path/to/image.png)
all math and variables wrap with latex notation delimiters <latex>x = ...</latex>, use only single line latex do formatting in markdown instead
speech: text and lists are spoken, tables and code blocks not, therefore use tables for files and technicals, use text and lists for plain english, do not include technical details in lists

usage:
~~~json
{
    "thoughts": [
        "...",
    ],
    "headline": "Explaining why...",
    "tool_name": "response",
    "tool_args": {
        "text": "Answer to the user",
    }
}
~~~