### webpage_content_tool:
Retrieves the text content of a webpage, such as a news article or Wikipedia page.
Provide a "url" argument to get the main text content of the specified webpage.
This tool is useful for gathering information from online sources.
Always provide a full, valid URL including the protocol (http:// or https://).

**Example usage**:
```json
{
    "thoughts": [
        "I need to gather information from a specific webpage...",
        "I will use the webpage_content_tool to fetch the content...",
    ],
    "tool_name": "webpage_content_tool",
    "tool_args": {
        "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
    }
}
```