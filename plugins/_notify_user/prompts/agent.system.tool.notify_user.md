### notify_user
send a notification for chats that run on their own for a longer time
notifications are non-blocking: they inform an absent user, never ask for a decision, never wait
send only when the user's picture of the work became false or stale: a strategy, plan, or assumption the user has seen was dropped, replaced, or contradicted
never send about starting, resuming, continuing, or attempting work
task end and goal completion go to the final response, never here
before sending, name what changed in the user's picture of the work and what comes next; if either is missing, do not send
if your last notification already covered this change, do not send again
if another agent delegated this work, do not send; report back to it instead
write the message so it makes sense without the chat open
notifications supplement, never replace, the final response
args: `message` required, short self-contained message in plain language
`type`: `info`, `progress`, `success`, `warning`, `error`; defaults to `info`
`priority`: `normal` or `high`; omit for `high`
`title`: optional short label
`detail`: optional longer supporting text
example:
~~~json
{
  "thoughts": ["Staging is unreachable, so the plan changed."],
  "headline": "Notifying strategy change",
  "tool_name": "notify_user",
  "tool_args": {
    "title": "Strategy changed",
    "message": "Staging unreachable; using recorded fixtures instead."
  }
}
~~~
