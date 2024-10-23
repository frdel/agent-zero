// MicrophoneInput.js
import { pipeline } from "@xenova/transformers";
import { whisperConfig } from './whisper-config.js';

export class MicrophoneInput {
    constructor(onTranscriptionUpdate) {
        this.onTranscriptionUpdate = onTranscriptionUpdate;
        this.transcriber = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
    }

    async initialize() {
        this.transcriber = await pipeline(whisperConfig.task, whisperConfig.model, {
            quantized: whisperConfig.quantized
        });
    }

    async startRecording() {
        if (this.isRecording) return;

        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this.mediaRecorder = new MediaRecorder(stream);
        
        this.mediaRecorder.ondataavailable = (event) => {
            this.audioChunks.push(event.data);
        };

        this.mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
            const arrayBuffer = await audioBlob.arrayBuffer();
            const result = await this.transcriber(new Uint8Array(arrayBuffer), { chunk_length_s: 30, stride_length_s: 5 });
            this.onTranscriptionUpdate(result.text);
            this.audioChunks = [];
        };

        this.mediaRecorder.start(1000); // Capture audio in 1-second chunks
        this.isRecording = true;
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
        }
    }
}
