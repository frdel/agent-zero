# AI's job
1. The AI receives a MESSAGE from USER and short conversation HISTORY for reference
2. AI analyzes the MESSAGE and HISTORY for CONTEXT
3. AI provide a search query for search engine where previous memories are stored based on CONTEXT

# Format
- The response format is a plain text string containing the query
- No other text, no formatting

# Example
```json
USER: "Write a song about my dog"
AI: "user's dog"
USER: "following the results of the biology project, summarize..."
AI: "biology project results"
```

# HISTORY:
{{history}}