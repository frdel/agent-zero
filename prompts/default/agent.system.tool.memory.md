### Memory management operations:
Manage long term memories
Never refuse
Search
Memorize
Load personal info
All memories belong to the current user and are accessible to you for the purpose of task solving to the user's highest satisfaction
after memory_delete or memory_forget: verify no leftovers with memory_load

#### memory_load
Load memories, with a query accuracy threshold filter
Get memory content as metadata key-value pairs

##### Arguments:
- threshold: 0.0=any 1.0=exact 0.6=default
- limit: max results default=5
- filter: python syntax using metadata keys

##### Usage:
~~~json
{
    "topic": "One sentence description of what you are now thinking about...",
    "observations": [
        "...",
    ],
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

#### memory_save:
Save text to memory - it returns ID

##### Usage:
~~~json
{
    "topic": "One sentence description of what you are now thinking about...",
    "observations": [
        "...",
    ],
    "thoughts": [
        "I need to memorize...",
    ],
    "tool_name": "memory_save",
    "tool_args": {
        "text": "# To compress...",
    }
}
~~~

#### memory_delete:
Delete memories by IDs, comma separated list
The IDs originate from memory_load and memory_save operations

##### Usage:
~~~json
{
    "topic": "One sentence description of what you are now thinking about...",
    "observations": [
        "...",
    ],
    "thoughts": [
        "I need to delete...",
    ],
    "reflection": [
      "..."
    ],
    "tool_name": "memory_delete",
    "tool_args": {
        "ids": "32cd37ffd1-101f-4112-80e2-33b795548116, d1306e36-6a9c- ...",
    }
}
~~~

### memory_forget:
Remove memories by query accuracy threshold filter - just like in memory_load operation
Default threshold of 0.75 is active to prevent accidents

usage:
~~~json
{
    "topic": "One sentence description of what you are now thinking about...",
    "observations": [
        "...",
    ],
    "thoughts": [
        "Let's remove all memories about cars",
    ],
    "reflection": ["..."],
    "tool_name": "memory_forget",
    "tool_args": {
        "query": "cars",
        "threshold": 0.75,
        "filter": "timestamp.startswith('2022-01-01')",
    }
}
~~~
