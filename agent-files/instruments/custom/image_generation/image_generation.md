# Problem
Generate an image locally using Stable Diffusion

# Solution
1. Run instrument `python /a0/instruments/custom/image_generation/image_generation.py "<prompt>"` with your desired prompt
2. The image will be saved to `/root/generated_images/` directory with a timestamped filename

# Arguments
- Required: A descriptive prompt (in quotes) for what you want in the image
- Optional arguments:
  - `--model MODEL_ID` - different model (default: CompVis/stable-diffusion-v1-4)
  - `--steps STEPS` - inference steps (default: 50)
  - `--size WIDTHxHEIGHT` - image dimensions (default: 512x512)
  - `--seed SEED` - random seed for reproducibility
  - `--cpu-only` - force CPU mode
  - `--fix-torch-cuda` - fix CUDA compatibility issues
  - `--fix-xformers` - fix memory optimization issues

# Examples
Basic: `python /a0/instruments/custom/image_generation/image_generation.py "a cat under a tree"`
Advanced: `python /a0/instruments/custom/image_generation/image_generation.py "sunset cityscape" --steps 75 --size 768x512`
Fix GPU issues: `python /a0/instruments/custom/image_generation/image_generation.py "dragon" --fix-torch-cuda --fix-xformers`

# Tips
- Use `--cpu-only` if GPU issues persist (will be slower)
- For highest quality, use more steps (50-100)
- If seeing CUDA/GPU errors, use the fix flags
- First-time use downloads models (may take several minutes)

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