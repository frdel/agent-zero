// whisper-config.js
import { env } from '@xenova/transformers';

// location for model files
env.localModelPath = './models';

// Whisper english only tiny model
env.defaultModelName = 'Xenova/whisper-tiny.en';

// Disable local models
env.allowLocalModels = false;

export const whisperConfig = {
    task: 'automatic-speech-recognition',
    model: env.defaultModelName,
    quantized: true,
};