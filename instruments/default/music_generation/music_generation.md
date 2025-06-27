# Problem
Generate music locally using MusicGen (transformers) with robust venv, CPU/GPU, and heartbeat support

# Usage (Recommended for All)
Run the wrapper script for maximum compatibility:
```
bash /a0/instruments/default/music_generation/music_generation.sh "<prompt>"
```
- This script will handle all environment setup, venv creation, and dependency installation for both GPU and CPU workflows.
- You do **not** need to worry about which Python to use or whether the venv exists.
- The generated music will be saved to `/root/generated_music/` with a timestamped filename (WAV format).

# Example
```
bash /a0/instruments/default/music_generation/music_generation.sh "An upbeat electronic track with a catchy melody"
```

# Notes for Automation/Agents
- Always invoke the shell script as shown above.
- Do **not** call the Python script directly; the shell script ensures reliability and compatibility across all environments.
- Output files are WAV format by default, saved in `/root/generated_music/`.

# Options
- `--seed <int>`: Set a random seed for reproducibility
- `--output-dir <path>`: Change the output directory (default: `/root/generated_music`)
- `--duration <seconds>`: Set music duration (if supported by the model)

# How It Works
1. Checks for NVIDIA GPU and CUDA libraries
2. Sets up a dedicated venv at `/opt/instruments_venv` if needed
3. Installs all required dependencies (PyTorch, transformers, etc.)
4. Runs the music generation Python script with heartbeat monitoring
5. Outputs a WAV file in `/root/generated_music/` with a timestamped filename

# Troubleshooting
- If you have a GPU but music is generated on CPU, check the terminal output for CUDA/PyTorch warnings.
- If you see dependency errors, try deleting `/opt/instruments_venv` and rerunning the script.
- The first run may take several minutes to download models and set up the environment.
- For best results, use clear, descriptive prompts (e.g., "A relaxing piano melody with gentle strings").