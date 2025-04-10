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
        "code": "python /a0/instruments/custom/video_generation/video_generation.py \"A majestic eagle soaring through mountain peaks, cinematic, golden hour lighting\" --duration 3"
    }
}
```

## Notes
- First run downloads models (~1-2GB)
- Generation takes 2-10 minutes
- Output includes MP4 video and thumbnail
- Automatically adapts to available GPU memory
