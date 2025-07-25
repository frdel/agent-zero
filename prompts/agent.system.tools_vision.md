## "Multimodal (Vision) Agent Tools" available:

### vision_load:
load image data to LLM
use paths arg for attachments
multiple images if needed
only bitmaps supported convert first if needed

**Example usage**:
```json
{
    "thoughts": [
        "I need to see the image...",
    ],
    "headline": "Loading image for visual analysis",
    "tool_name": "vision_load",
    "tool_args": {
        "paths": ["/path/to/image.png"],
    }
}
```
