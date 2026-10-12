### response:
final answer to user
ends task processing use only when done or no task active
args: `text`
output full file paths not only names to be clickable
file links: only two render as working links: a bare absolute path in plain text, or a markdown link using the file scheme [label](file:///absolute/path.ext); never link local files as [label](/a0/...) - that root-relative href has no server route and 404s
default to balanced, concise answers: informative but tight, not terse and not verbose.
usage:
~~~json
{
    "thoughts": [
        "...",
    ],
    "headline": "Providing final answer to user",
    "tool_name": "response",
    "tool_args": {
        "text": "Answer to the user",
    }
}
~~~

{{ include "agent.system.response_tool_tips.md" }}
