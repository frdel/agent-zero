# Problem
Generate sound effects using procedural audio generation techniques

# Usage (Recommended for All)
Run the wrapper script for maximum compatibility:
```
bash /a0/instruments/default/sound_effects/sound_effects.sh "<prompt>"
```
- This script will handle all environment setup, venv creation, and dependency installation for both GPU and CPU sound generation.
- You do **not** need to worry about which Python to use or whether the venv exists.
- The generated sound will be saved to `/root/generated_sounds/` with a timestamped filename.

# Examples
```
# Generate a bird sound
bash /a0/instruments/default/sound_effects/sound_effects.sh "A high-pitched bird chirping in the morning"

# Generate water sound
bash /a0/instruments/default/sound_effects/sound_effects.sh "Heavy rain falling on a tin roof"

# Generate impact sound
bash /a0/instruments/default/sound_effects/sound_effects.sh "A loud crash in an empty room"

# Generate ambient sound
bash /a0/instruments/default/sound_effects/sound_effects.sh "Busy city street with traffic"
```

# Supported Sound Types
- Nature sounds (birds, water, wind, thunder, rain)
- Impact sounds (hits, crashes, explosions)
- Ambient sounds (crowd, city, forest, ocean)
- Mechanical sounds (engines, machines, clocks)
- Character sounds (footsteps, breathing, voice)

# Notes for Automation/Agents
- Always invoke the shell script as shown above.
- Do **not** call the Python script directly; the shell script ensures reliability and compatibility across all environments.
- The prompt should be a natural language description of the desired sound.
- Duration can be adjusted with the `--duration` parameter (default: 2.0 seconds).

# Sound Effects Generator

A tool for generating various types of sound effects using procedural audio generation techniques.

## Features

- Generate natural sounds (bird calls, water, wind, etc.)
- Create impact sounds (hits, crashes, explosions)
- Generate ambient sounds (crowd noise, city sounds)
- Customizable duration and parameters
- High-quality audio output

## Categories

### Nature Sounds
- Bird calls
- Water
- Wind
- Thunder
- Rain

### Mechanical Sounds
- Engine
- Machine
- Clock
- Door
- Vehicle

### Impact Sounds
- Hit
- Crash
- Explosion
- Break
- Fall

### Ambient Sounds
- Crowd
- City
- Forest
- Ocean
- Wind

### Character Sounds
- Footstep
- Breathing
- Voice
- Movement

## Usage

```python
from sound_effects import SoundEffectsGenerator

# Initialize the generator
generator = SoundEffectsGenerator()

# Generate a bird call
bird_sound = generator.generate_sound_effect('nature', 'bird_call', duration=2.0)

# Generate water sound
water_sound = generator.generate_sound_effect('nature', 'water', duration=3.0)

# Generate impact sound
impact_sound = generator.generate_sound_effect('impact', 'hit', duration=1.0, intensity=0.8)
```

## Parameters

- `category`: The main category of the sound effect
- `subcategory`: The specific type of sound within the category
- `duration`: Length of the sound in seconds
- Additional parameters vary by sound type (e.g., `frequency` for bird calls, `intensity` for impacts)

## Output

Generated sounds are saved as WAV files in the `output` directory with the naming format:
`{category}_{subcategory}_{duration}s.wav` 