# Problem
Generate an image locally using Stable Diffusion

# Solution
1. Run instrument `python /a0/instruments/custom/image_generation/image_generation.py "<prompt>"` with your desired prompt
2. The image will be saved to `/root/generated_images/` directory with a timestamped filename

# Examples
Basic: `python /a0/instruments/custom/image_generation/image_generation.py "a cat under a tree"`

# Using with code_execution_tool
MUST use "runtime": "terminal" (not "python")

Example JSON:
```json
{
    "thoughts": [
        "Generating image with Stable Diffusion"
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "python /a0/instruments/custom/image_generation/image_generation.py \"a beautiful landscape\""
    }
}
```

# Escaping in JSON
Double quotes in the prompt must be escaped with backslash in JSON:
```
"code": "python /a0/instruments/custom/image_generation/image_generation.py \"prompt text\""
```