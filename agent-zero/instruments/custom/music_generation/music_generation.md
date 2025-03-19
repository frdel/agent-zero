# Video Generation

Generate AI videos from text prompts using local stable diffusion models.

## Usage

```bash
python /a0/instruments/custom/video_generation/video_generation.py "<prompt>" [options]
```

## Key Options
- `--duration <seconds>` - Length in seconds (default: 5, recommended: 3-5s for 8GB VRAM)
- `--width`/`--height` - Resolution (default: 512×512)
- `--seed` - For reproducible results
- `--output-dir` - Save location (default: /root/generated_videos)
- `--no-enhance` - Disable frame enhancement (smoother transitions)

## Prompt Tips
Best results include:
- Cinematic terms: "cinematic lighting", "photorealistic", "film grain"
- Camera movements: "slow pan", "aerial view"
- Lighting details: "golden hour", "dramatic shadows"

## Example for Agent

```json
{
    "thoughts": [
        "Need to generate a cinematic video of an eagle"
    ],
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "python /a0/instruments/custom/video_generation/video_generation.py \"A majestic eagle soaring through mountain peaks, cinematic lighting\" --duration 3"
    }
}
```

## How It Works
1. Generates a high-quality still image from your text prompt
2. Animates the image into a short video sequence
3. Enhances frame transitions for smoother motion
4. Outputs an MP4 file with accompanying thumbnail

## Notes
- First run downloads models (~2GB)
- Generation takes 2-10 minutes 
- Output includes MP4 video, thumbnail and metadata
- Automatically adapts to available GPU memory
- For 8GB VRAM, expect 12-20 frames (high quality but short duration)