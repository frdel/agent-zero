### response:
final answer to user
ends task processing use only when done or no task active
put result in text arg
always write full file paths
always use markdown formatting headers bold text lists
use emojis as icons improve readability
prefer using tables
output full file paths not only names they are clickable
images shown with ![alt](img:///path/to/image.png)
all math and variables wrap with latex notation delimiters <latex>x = ...</latex>, use only single line latex do formatting in markdown
usage:
~~~json
{
    "thoughts": [
        "...",
    ],
    "tool_name": "response",
    "tool_args": {
        "text": "Answer to the user",
    }
}
~~~