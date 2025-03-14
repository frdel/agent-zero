# Problem
Generate an image locally using Stable Diffusion

# Solution
1. Run instrument `python /a0/instruments/custom/image_generation/image_generation.py "<prompt>"` with your desired prompt
2. The image will be saved to `/root/generated_images/` directory with a timestamped filename
3. Wait for the confirmation message with the saved image path

# Arguments
- Required: A descriptive prompt (in quotes) for what you want in the image
- Optional arguments can be added after the prompt:
  - `--model MODEL_ID` to specify a different model (default: CompVis/stable-diffusion-v1-4)
  - `--steps STEPS` to set the number of inference steps (default: 50)
  - `--size WIDTHxHEIGHT` to set custom dimensions (default: 512x512)
  - `--seed SEED` to use a specific seed for reproducibility

# Examples
- Basic usage: `python /a0/instruments/custom/image_generation/image_generation.py "a Turkish angora white cat under a live oak tree"`
- With options: `python /a0/instruments/custom/image_generation/image_generation.py "a futuristic cityscape at sunset" --steps 75 --size 768x512`

# Dependencies
- This instrument requires the Hugging Face diffusers library and PyTorch
- Dependencies will be installed automatically if not present
- First-time use may take longer due to model downloading 

# Using with code_execution_tool
When executing this instrument through code_execution_tool, you MUST use "runtime": "terminal"
DO NOT use "runtime": "python" which will cause syntax errors with the command

## Example Tool Usage
```json
{
    "thoughts": [
        "Generating image with Stable Diffusion"
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "python /a0/instruments/custom/image_generation/image_generation.py \"prompt text\""
    }
}
```

# Note on Escaping
When using terminal runtime, ensure proper escaping of double quotes in the prompt:
- Correct: `"runtime": "terminal", "code": "python /a0/instruments/custom/image_generation/image_generation.py \"prompt text\""`
- Incorrect: `"runtime": "python", "code": "python /a0/instruments/custom/image_generation/image_generation.py \"prompt text\""`

# Troubleshooting
- If you see "SyntaxError: invalid syntax", you're using "runtime": "python" instead of "terminal"
- If the image fails to generate, make sure all dependencies are installed
- For first-time use, be patient as the model download may take several minutes
- If the output directory doesn't exist, it will be created automatically 