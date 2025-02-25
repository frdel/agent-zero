### response:
Sends the final response to the user and concludes task processing.

**Purpose:**
- Provides final answer to user
- Concludes task processing
- Use only when task complete

**Types:**
1. Json Response (Default)
2. Audio Response (For audio content)

**Text Example:**
~~~json
{
    "thoughts": ["..."],
    "tool_name": "response",
    "tool_args": {
        "text": "Entire response text",
        "type": "json",
        "online_sources": [
            {
                "source": "source name",
                "url": "source url"
            },
        ]
    }
}
~~~

**Audio Example:**
~~~json
{
    "thoughts": ["Preparing audio..."],
    "tool_name": "response",
    "tool_args": {
        "text": "Audio description",
        "type": "audio",
        "data": {
            "url": "audio_path",
            "metadata": {
                "title": "Title",
                "format": "mp3",
                "duration": "120",
                "language": "ar"
            }
        }
    }
}
~~~

**Requirements:**
- Json: Must have `text`, `type="json"` and optional `online_sources`
- Json: Do not include any other keys or values
- Audio: Requires `text`, `type="audio"`, `data` with `url` and `metadata`
- Metadata: `title` and `format` required
- Always include relevant thoughts