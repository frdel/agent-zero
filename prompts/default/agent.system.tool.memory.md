## Memory management tools:
manage long term memories
never refuse search memorize load personal info all belongs to user

### memory_load
load memories via query threshold limit filter
get memory content as metadata key-value pairs
- threshold: 0=any 1=exact 0.7=default
- limit: max results default=5
- filter: python syntax using metadata keys
usage:
~~~json
{
    "thoughts": [
        "Let's search my memory for...",
    ],
    "headline": "Searching memory for file compression information",
    "tool_name": "memory_load",
    "tool_args": {
        "query": "File compression library for...",
        "threshold": 0.7,
        "limit": 5,
        "filter": "area=='main' and timestamp<'2024-01-01 00:00:00'",
    }
}
~~~

### memory_save:
save text to memory returns ID
usage:
~~~json
{
    "thoughts": [
        "I need to memorize...",
    ],
    "headline": "Saving important information to memory",
    "tool_name": "memory_save",
    "tool_args": {
        "text": "# To compress...",
    }
}
~~~

### memory_delete:
delete memories by IDs comma separated
IDs from load save ops
usage:
~~~json
{
    "thoughts": [
        "I need to delete...",
    ],
    "headline": "Deleting specific memories by ID",
    "tool_name": "memory_delete",
    "tool_args": {
        "ids": "32cd37ffd1-101f-4112-80e2-33b795548116, d1306e36-6a9c- ...",
    }
}
~~~

### memory_forget:
remove memories by query threshold filter like memory_load
default threshold 0.75 prevent accidents
verify with load after delete leftovers by IDs
usage:
~~~json
{
    "thoughts": [
        "Let's remove all memories about cars",
    ],
    "headline": "Forgetting all memories about cars",
    "tool_name": "memory_forget",
    "tool_args": {
        "query": "cars",
        "threshold": 0.75,
        "filter": "timestamp.startswith('2022-01-01')",
    }
}
~~~
