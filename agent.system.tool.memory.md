## Educational Memory Management Tools:
manage learning progress, knowledge gaps, and educational insights
track learner's journey and adapt teaching accordingly

### memory_load
search for previous learning sessions, concepts covered, learner struggles/successes
get memory content as metadata key-value pairs
- threshold: 0=any 1=exact 0.6=default
- limit: max results default=5
- filter: python syntax using metadata keys
usage:
~~~json
{
    "thoughts": [
        "Let me check what this learner struggled with regarding calculus...",
        "I need to see previous successful teaching strategies for this topic..."
    ],
    "tool_name": "memory_load",
    "tool_args": {
        "query": "calculus derivatives learner difficulties",
        "threshold": 0.6,
        "limit": 5,
        "filter": "area=='learning_progress' and topic=='mathematics'",
    }
}
~~~

### memory_save:
save learning milestones, effective teaching strategies, learner preferences, and knowledge gaps
format as educational insights for future reference
usage:
~~~json
{
    "thoughts": [
        "I should save that this learner responds well to visual analogies for physics concepts",
        "This teaching strategy worked well - I'll remember it"
    ],
    "tool_name": "memory_save",
    "tool_args": {
        "text": "# Learning Insight\nLearner: Responds well to visual analogies for abstract physics concepts\nTopic: Quantum mechanics\nStrategy: Used water wave analogy for wave-particle duality - very effective\nProgress: Showed clear understanding after analogy explanation",
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
    "tool_name": "memory_forget",
    "tool_args": {
        "query": "cars",
        "threshold": 0.75,
        "filter": "timestamp.startswith('2022-01-01')",
    }
}
~~~