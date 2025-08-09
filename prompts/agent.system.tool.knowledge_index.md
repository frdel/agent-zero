### knowledge_index:

import external document into knowledge store as knowledge_source
always indexes into main area; visibility is controlled by owner
use for URLs or local files; prefer concise inputs and clear intents

- uri/url/path: document location (file://, http(s)://, absolute/relative path)
- owner (optional): set knowledge ownership; defaults to current profile (or "default")

usage:
```json
{
  "thoughts": [
    "I should ingest this PDF as private knowledge for my profile",
    "It will help future answers related to this topic"
  ],
  "headline": "Index external knowledge source",
  "tool_name": "knowledge_index",
  "tool_args": {
    "url": "https://example.com/guide.pdf"
  }
}
```

```json
{
  "thoughts": [
    "Index local markdown as global knowledge"
  ],
  "headline": "Index local file",
  "tool_name": "knowledge_index",
  "tool_args": {
    "path": "file:///home/user/notes/topic.md",
    "owner": "default"
  }
}
```
