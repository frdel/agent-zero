## memory tool
use when durable recall or storage is useful
- `memory`: args `action`, then `query`, `text`, `ids`, `area`, `threshold`, `limit`, `filter` as the action needs
- actions: `load` searches by meaning and metadata, `save` stores durable information and returns a memory ID, `delete` removes memories by comma-separated IDs, `forget` finds and removes matching memories

notes:
- `threshold` is similarity from `0` to `1`
- `filter` is a metadata expression (e.g. `area=='main'`)
- confirm destructive changes when accuracy matters
- memories usually include timestamp metadata; use it as a soft recency signal, not a hard TTL
- when the user updates a durable fact/preference, load related memories first, forget/delete superseded versions, then save one complete current version
- do not append a second memory for the same mutable subject when the new statement replaces the old one
- do not forget a memory only because it is old; forget it when current evidence shows it is stale, false, superseded, duplicated, or unwanted
- `forget` also cleans exact matches and derived fragment/solution records related to removed memories
- use `save` for stable current facts, not short-lived test markers, greetings, or one-off conversation events

example:
~~~json
{
  "thoughts": ["I should search memory for relevant prior guidance."],
  "headline": "Loading related memories",
  "tool_name": "memory",
  "tool_args": {
    "action": "load",
    "query": "tool argument format",
    "threshold": 0.7,
    "limit": 3
  }
}
~~~
