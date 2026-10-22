### a2a_chat
chat with a remote FastA2A-compatible agent; remote context is preserved automatically per `agent_url`
args: `agent_url`, `message`, optional `attachments[]`, optional `reset`
- `agent_url`: base url, accepts `host:port`, `http://host:port`, or a full `/a2a` url
- `message`: text to send to the remote agent
- `attachments[]`: optional absolute uris or paths to send with the message
- `reset`: json boolean; use `true` to start a fresh conversation with the same `agent_url`
do not send `context_id`; the tool handles that internally
example:
~~~json
{
  "thoughts": ["I need to ask a remote agent and keep the session for follow-up."],
  "headline": "Contacting remote FastA2A agent",
  "tool_name": "a2a_chat",
  "tool_args": {
    "agent_url": "http://weather.example.com:8000/a2a",
    "message": "What's the forecast for Berlin today?",
    "attachments": [],
    "reset": false
  }
}
~~~
