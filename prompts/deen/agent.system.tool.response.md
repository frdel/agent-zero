### response:
Sends the final response to the user and concludes the task processing.

**Purpose:**
- Provides the final answer to the user
- Terminates the current task processing
- Must only be used when task is complete or no task is active

**Response Types:**
1. Text Response (Default)
2. Audio Response (If quran_audio_tool is used)
3. JSON Response

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
        "type": "text|audio|json",
        
        // Audio Response Schema (Optional)
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

        // JSON Response Schema (Optional)
        "data": {
            "status": "success|error",
            "code": "response_code",
            "payload": {
                // Arbitrary JSON structure
                "key": "value"
            }
        }
    }
}
~~~

**Important Notes:** 
- tools args text and type are required
- Always use complete file paths
- Include relevant thoughts explaining the response
- Only one 'data' structure should be present based on type
- When quran_audio_tool is used, response type must be "audio" with corresponding audio data structure
- When text contains audio file path, response type must be "audio" with corresponding audio data structure