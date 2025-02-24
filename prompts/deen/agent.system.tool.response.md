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
        "...",
    ],
    "tool_name": "response",
    "tool_args": {
        "text": "Answer to the user",
        "type": "text"
    }
}
~~~

**Audio Response Example:**
~~~json
{
    "thoughts": [
        "User requested Quran audio...",
        "Preparing audio response with metadata..."
    ],
    "tool_name": "response",
    "tool_args": {
        "text": "description of the audio with url",
        "type": "audio",
        "data": {
            "url": "absolute_path_or_url_to_audio",
            "metadata": {
                "title": "Audio title",
                "duration": "Duration in seconds",
                "format": "mp3|wav|ogg",
                "bitrate": "128kbps",
                "language": "ISO 639-1 code",
                "reciter": "Reciter name if applicable"
            }
        }
    }
}
~~~

**Schema Requirements:**

1. Text Response:
- Required: text, type="text"
- Optional: data=null

2. Audio Response:
- Required: text, type="audio", data (with url and metadata)
- Metadata must include: title, format
- Optional metadata: duration, bitrate, language, reciter

**Important Notes:** 
- Always specify response type explicitly
- Include data object for audio responses
- Use complete file paths for audio URLs
- Include relevant thoughts explaining the response
- Text field is always required regardless of type