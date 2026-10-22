# Wait

Provides the `wait` tool, which pauses agent execution until a duration (`seconds`, `minutes`, `hours`, `days`) or an ISO `until` timestamp is reached.

Waiting is intervention-aware: pauses extend the target time for duration waits, and remaining time is streamed to the log while waiting.
