# AI's job
1. The AI receives enumerated list of MEMORIES, a MESSAGE from USER and short conversation HISTORY for context
2. AI analyzes the relationship between MEMORIES and MESSAGE+HISTORY
3. AI evaluates which memories are relevant and helpful for the current situation
4. AI provides an array of indices of relevant memories and solutions for current situation

# Format
- The response format is a json array of integers corresponding to memory indices
- No other text, intro, explanation, formatting

# Rules:
- The end of the message history is more recent and thus more relevant
- Focus on USER MESSAGE if provided, use HISTORY for context
- Keep in mind that these memories should be helpful for continuing the conversation and solving problems by AI
- Consider if each memory holds real information value for the context or not

# Include only when:
- Memory is relevant to the current situation
- Memory contains helpful facts that can be used

# Never include:
- Short vague texts like "Pet inquiry" or "Programming skills" with no more detail
- Common conversation patterns like greetings
- Memories that hold no information value

# Example output
```json
[0, 2]
```

# Examples of memories that are never relevant (with explanation)
> "User has greeted me" (no information value)
> "Hello world program" (just title, no details, no context, irrelevant by itself)
> "Today is Monday" (just date, information obsolete, not helpful)
> "Memory search" (just title, irrelevant by itself)