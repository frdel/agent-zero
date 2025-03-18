# Problem
Generate AI music from a text prompt

# Solution
1. If folder is specified, cd to it
2. Run instrument "bash /a0/instruments/custom/music_generation/music_generation.sh <prompt> [options]" with your desired text prompt
3. Wait for the generation to complete

## Available Options:
- `--duration <seconds>` - Length of music in seconds (default: 30, max: 30-120 depending on model)
- `--model <size>` - Model size: small, medium, large, melody (default: medium)
- `--genre <genre>` - Specific genre (e.g., rock, jazz, classical)
- `--bpm <number>` - Beats per minute
- `--seed <number>` - Random seed for reproducibility
- `--output-dir <path>` - Directory to save generated music (default: /root/generated_music)

## Examples:
```
bash /a0/instruments/custom/music_generation/music_generation.sh "An upbeat electronic dance track with synth arpeggios" --duration 45
```

```
bash /a0/instruments/custom/music_generation/music_generation.sh "A smooth jazz piece with piano and saxophone" --model medium --genre jazz
```

```
bash /a0/instruments/custom/music_generation/music_generation.sh "Epic orchestral soundtrack with dramatic strings and percussion" --model large
```
