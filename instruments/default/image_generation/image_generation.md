# Problem
Generate an image locally using Stable Diffusion

# Usage (Recommended for All)
Run the wrapper script for maximum compatibility:
```
bash /a0/instruments/default/image_generation/image_generation.sh "<prompt>"
```
- This script will handle all environment setup, venv creation, and dependency installation for both GPU and CPU images.
- You do **not** need to worry about which Python to use or whether the venv exists.
- The generated image will be saved to `/root/generated_images/` with a timestamped filename.

# Example
```
bash /a0/instruments/default/image_generation/image_generation.sh "a cat under a tree"
```

# Notes for Automation/Agents
- Always invoke the shell script as shown above.
- Do **not** call the Python script directly; the shell script ensures reliability and compatibility across all environments.