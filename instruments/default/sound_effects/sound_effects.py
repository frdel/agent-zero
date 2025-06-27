#!/usr/bin/env python3

import argparse
import os
import sys
import torch
import soundfile as sf
from datetime import datetime
from diffusers import AudioLDMPipeline

# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = "/opt/instruments_venv"
DEFAULT_OUTPUT_DIR = "/root/generated_sounds"
MODEL_ID = "cvssp/audioldm-s-full-v2"

# Load the pipeline globally (so it's not reloaded for every call)
def load_pipeline():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = AudioLDMPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.float16 if device == "cuda" else torch.float32)
    pipe = pipe.to(device)
    return pipe

pipe = None

def generate_sound_effect(prompt, duration=5.0, num_inference_steps=150, guidance_scale=5.0, seed=None, output_path=None):
    global pipe
    if pipe is None:
        pipe = load_pipeline()
    generator = None
    if seed is not None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        generator = torch.Generator(device).manual_seed(seed)
    # Generate audio
    kwargs = dict(
        prompt=prompt,
        num_inference_steps=num_inference_steps,
        audio_length_in_s=duration,
        generator=generator
    )
    # Only add guidance_scale if supported
    if 'guidance_scale' in pipe.__call__.__code__.co_varnames:
        kwargs['guidance_scale'] = guidance_scale
    result = pipe(**kwargs).audios
    # Take the first waveform, convert to numpy, and save
    output = result[0]
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(DEFAULT_OUTPUT_DIR, f"sound_{timestamp}.wav")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # AudioLDM outputs 16kHz mono audio
    sf.write(output_path, output, 16000)
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Generate sound effects from text prompts using AudioLDM.")
    parser.add_argument("prompt", type=str, help="Description of the sound to generate (e.g., 'a bird chirping in the morning', 'heavy rain falling', 'a car engine starting')")
    parser.add_argument("--duration", type=float, default=5.0, help="Duration of the sound in seconds (default 5, max 10)")
    parser.add_argument("--output", type=str, default=None, help="Output WAV file path")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--steps", type=int, default=150, help="Number of inference steps (higher = better quality, slower)")
    parser.add_argument("--guidance-scale", type=float, default=5.0, help="Guidance scale for prompt adherence (higher = more literal, default 5.0)")
    args = parser.parse_args()

    output_path = args.output
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(DEFAULT_OUTPUT_DIR, f"sound_{timestamp}.wav")

    print(f"🔊 Generating sound effect for prompt: '{args.prompt}'")
    print(f"   Duration: {args.duration}s | Output: {output_path}")
    print(f"   Steps: {args.steps} | Guidance scale: {args.guidance_scale}")
    path = generate_sound_effect(
        prompt=args.prompt,
        duration=args.duration,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance_scale,
        seed=args.seed,
        output_path=output_path
    )
    print(f"✅ Sound effect saved to: {path}")
    print("ℹ️ Output is 16kHz mono. For higher resolution, consider upsampling with a tool like sox or ffmpeg.")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 