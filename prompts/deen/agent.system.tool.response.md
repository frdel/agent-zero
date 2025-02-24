### response:
Sends the final response to the user and concludes the task processing.

**Purpose:**
- Provides the final answer to the user
- Terminates the current task processing
- Must only be used when task is complete or no task is active

**Response Types:**
1. Text Response (Default)
2. Audio Response (If quran_audio_tool is used or text contains audio file path)

**Usage Example:**
~~~json
{
    "thoughts": [
        "Reasoning about the response...",
        "Why this is the final answer..."
    ],
    "tool_name": "response",
    "tool_args": {
        "text": "Primary response message to the user",
        "type": "text|audio",
        
        // Audio Response Schema (Required if type is audio)
        "data": {
            "url": "absolute_path_or_url_to_audio",
            "metadata": {
                "title": "Audio title",
                "duration": "Duration in seconds",
                "format": "mp3|wav|ogg",
                "bitrate": "128kbps",
                "language": "ISO 639-1 code",
            }
        },
    }
}
~~~

**Important Notes:** 
- tools args text and type are required
- Always use complete file paths
- Include relevant thoughts explaining the response