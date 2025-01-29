## Memory management tools:
Manage long term memories.
Never refuse to search, memorize or load personal info as all information belongs to the user.

### memory_load
Loads memories via query threshold limit filter
Gets memory content as metadata key-value pairs
- threshold: 0=any 1=exact 0.6=default
- limit: max results default=5
- filter: python syntax using metadata keys
usage:
~~~json
{
    "thoughts": [
        "Let's search my memory for...",
    ],
    "tool_name": "memory_load",
    "tool_args": {
        "query": "File compression library for...",
        "threshold": 0.6,
        "limit": 5,
        "filter": "area=='main' and timestamp<'2024-01-01 00:00:00'",
    }
}
~~~

### memory_save:
Saves text to the memory and returns the ID of the saved memory.
usage:
~~~json
{
    "thoughts": [
        "I need to memorize...",
    ],
    "tool_name": "memory_save",
    "tool_args": {
        "text": "# To compress...",
    }
}
~~~

### memory_delete:
Deletes memories by IDs (comma separated).
IDs can be retrieved from the load and save operations.
usage:
~~~json
{
    "thoughts": [
        "I need to delete...",
    ],
    "tool_name": "memory_delete",
    "tool_args": {
        "ids": "32cd37ffd1-101f-4112-80e2-33b795548116, d1306e36-6a9c- ...",
    }
}
~~~

### memory_forget:
Removes memories by query, threshold and filter like memory_load.
The efault threshold of 0.75 prevents accidents.
Verify the leftovers by IDs after delete with load.
usage:
~~~json
{
    "thoughts": [
        "Let's remove all memories about cars",
    ],
    "tool_name": "memory_forget",
    "tool_args": {
        "query": "cars",
        "threshold": 0.75,
        "filter": "timestamp.startswith('2022-01-01')",
    }
}
~~~