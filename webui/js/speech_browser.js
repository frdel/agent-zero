import { pipeline, read_audio } from './transformers@3.0.2.js';
import { updateChatInput, sendMessage } from '../index.js';

const microphoneButton = document.getElementById('microphone-button');
let microphoneInput = null;
let isProcessingClick = false;

const Status = {
    INACTIVE: 'inactive',
    ACTIVATING: 'activating',
    LISTENING: 'listening',
    RECORDING: 'recording',
    WAITING: 'waiting',
    PROCESSING: 'processing'
};

class MicrophoneInput {
    constructor(updateCallback, options = {}) {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.lastChunk = [];
        this.updateCallback = updateCallback;
        this.messageSent = false;

        // Audio analysis properties
        this.audioContext = null;
        this.mediaStreamSource = null;
        this.analyserNode = null;
        this._status = Status.INACTIVE;

        // Timing properties
        this.lastAudioTime = null;
        this.waitingTimer = null;
        this.silenceStartTime = null;
        this.hasStartedRecording = false;
        this.analysisFrame = null;

        this.options = {
            modelSize: 'tiny',
            language: 'en',
            silenceThreshold: 0.15,
            silenceDuration: 1000,
            waitingTimeout: 2000,
            minSpeechDuration: 500,
            ...options
        };
    }

    get status() {
        return this._status;
    }

    set status(newStatus) {
        if (this._status === newStatus) return;

        const oldStatus = this._status;
        this._status = newStatus;
        console.log(`Mic status changed from ${oldStatus} to ${newStatus}`);

        // Update UI
        microphoneButton.classList.remove(`mic-${oldStatus.toLowerCase()}`);
        microphoneButton.classList.add(`mic-${newStatus.toLowerCase()}`);
        microphoneButton.setAttribute('data-status', newStatus);

        // Handle state-specific behaviors
        this.handleStatusChange(oldStatus, newStatus);
    }

    handleStatusChange(oldStatus, newStatus) {

        //last chunk kept only for transition to recording status
        if (newStatus != Status.RECORDING) { this.lastChunk = null; }

        switch (newStatus) {
            case Status.INACTIVE:
                this.handleInactiveState();
                break;
            case Status.LISTENING:
                this.handleListeningState();
                break;
            case Status.RECORDING:
                this.handleRecordingState();
                break;
            case Status.WAITING:
                this.handleWaitingState();
                break;
            case Status.PROCESSING:
                this.handleProcessingState();
                break;
        }
    }

    handleInactiveState() {
        this.stopRecording();
        this.stopAudioAnalysis();
        if (this.waitingTimer) {
            clearTimeout(this.waitingTimer);
            this.waitingTimer = null;
        }
    }

    handleListeningState() {
        this.stopRecording();
        this.audioChunks = [];
        this.hasStartedRecording = false;
        this.silenceStartTime = null;
        this.lastAudioTime = null;
        this.messageSent = false;
        this.startAudioAnalysis();
    }

    handleRecordingState() {
        if (!this.hasStartedRecording && this.mediaRecorder.state !== 'recording') {
            this.hasStartedRecording = true;
            this.mediaRecorder.start(1000);
            console.log('Speech started');
        }
        if (this.waitingTimer) {
            clearTimeout(this.waitingTimer);
            this.waitingTimer = null;
        }
    }

    handleWaitingState() {
        // Don't stop recording during waiting state
        this.waitingTimer = setTimeout(() => {
            if (this.status === Status.WAITING) {
                this.status = Status.PROCESSING;
            }
        }, this.options.waitingTimeout);
    }

    handleProcessingState() {
        this.stopRecording();
        this.process();
    }

    stopRecording() {
        if (this.mediaRecorder?.state === 'recording') {
            this.mediaRecorder.stop();
            this.hasStartedRecording = false;
        }
    }

    async initialize() {
        try {
            this.transcriber = await pipeline(
                'automatic-speech-recognition',
                `Xenova/whisper-${this.options.modelSize}.${this.options.language}`
            );

            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    channelCount: 1
                }
            });

            this.mediaRecorder = new MediaRecorder(stream);
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 &&
                    (this.status === Status.RECORDING || this.status === Status.WAITING)) {
                    if (this.lastChunk) {
                        this.audioChunks.push(this.lastChunk);
                        this.lastChunk = null;
                    }
                    this.audioChunks.push(event.data);
                    console.log('Audio chunk received, total chunks:', this.audioChunks.length);
                }
                else if (this.status === Status.LISTENING) {
                    this.lastChunk = event.data;
                }
            };

            this.setupAudioAnalysis(stream);
            return true;
        } catch (error) {

            console.error('Microphone initialization error:', error);
            window.toastFrontendError('Failed to access microphone. Please check permissions.', 'Microphone Error');
            return false;
        }
    }

    setupAudioAnalysis(stream) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        this.mediaStreamSource = this.audioContext.createMediaStreamSource(stream);
        this.analyserNode = this.audioContext.createAnalyser();
        this.analyserNode.fftSize = 2048;
        this.analyserNode.minDecibels = -90;
        this.analyserNode.maxDecibels = -10;
        this.analyserNode.smoothingTimeConstant = 0.85;
        this.mediaStreamSource.connect(this.analyserNode);
    }


    startAudioAnalysis() {
        const analyzeFrame = () => {
            if (this.status === Status.INACTIVE) return;

            const dataArray = new Uint8Array(this.analyserNode.fftSize);
            this.analyserNode.getByteTimeDomainData(dataArray);

            // Calculate RMS volume
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                const amplitude = (dataArray[i] - 128) / 128;
                sum += amplitude * amplitude;
            }
            const rms = Math.sqrt(sum / dataArray.length);

            const now = Date.now();

            // Update status based on audio level
            if (rms > this.options.silenceThreshold) {
                this.lastAudioTime = now;
                this.silenceStartTime = null;

                if (this.status === Status.LISTENING || this.status === Status.WAITING) {
                    if (!speech.isSpeaking()) // TODO? a better way to ignore agent's voice?
                        this.status = Status.RECORDING;
                }
            } else if (this.status === Status.RECORDING) {
                if (!this.silenceStartTime) {
                    this.silenceStartTime = now;
                }

                const silenceDuration = now - this.silenceStartTime;
                if (silenceDuration >= this.options.silenceDuration) {
                    this.status = Status.WAITING;
                }
            }

            this.analysisFrame = requestAnimationFrame(analyzeFrame);
        };

        this.analysisFrame = requestAnimationFrame(analyzeFrame);
    }

    stopAudioAnalysis() {
        if (this.analysisFrame) {
            cancelAnimationFrame(this.analysisFrame);
            this.analysisFrame = null;
        }
    }

    async process() {
        if (this.audioChunks.length === 0) {
            this.status = Status.LISTENING;
            return;
        }

        const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(audioBlob);



        try {
            const samplingRate = 16000;
            const audioData = await read_audio(audioUrl, samplingRate);
            const result = await this.transcriber(audioData);
            const text = this.filterResult(result.text || "")

            if (text) {
                console.log('Transcription:', result.text);
                await this.updateCallback(result.text, true);
            }
        } catch (error) {
            console.error('Transcription error:', error);
            window.toastFrontendError('Transcription failed.', 'Speech Recognition Error');
        } finally {
            URL.revokeObjectURL(audioUrl);
            this.audioChunks = [];
            this.status = Status.LISTENING;
        }
    }

    filterResult(text) {
        text = text.trim()
        let ok = false
        while (!ok) {
            if (!text) break
            if (text[0] === '{' && text[text.length - 1] === '}') break
            if (text[0] === '(' && text[text.length - 1] === ')') break
            if (text[0] === '[' && text[text.length - 1] === ']') break
            ok = true
        }
        if (ok) return text
        else console.log(`Discarding transcription: ${text}`)
    }
}



// Initialize and handle click events
async function initializeMicrophoneInput() {
    microphoneInput = new MicrophoneInput(
        async (text, isFinal) => {
            if (isFinal) {
                updateChatInput(text);
                if (!microphoneInput.messageSent) {
                    microphoneInput.messageSent = true;
                    await sendMessage();
                }
            }
        },
        {
            modelSize: 'tiny',
            language: 'en',
            silenceThreshold: 0.07,
            silenceDuration: 1000,
            waitingTimeout: 1500
        }
    );
    microphoneInput.status = Status.ACTIVATING;

    return await microphoneInput.initialize();
}

microphoneButton.addEventListener('click', async () => {
    if (isProcessingClick) return;
    isProcessingClick = true;

    const hasPermission = await requestMicrophonePermission();
    if (!hasPermission) return;

    try {
        if (!microphoneInput && !await initializeMicrophoneInput()) {
            return;
        }

        // Simply toggle between INACTIVE and LISTENING states
        microphoneInput.status =
            (microphoneInput.status === Status.INACTIVE || microphoneInput.status === Status.ACTIVATING) ? Status.LISTENING : Status.INACTIVE;
    } finally {
        setTimeout(() => {
            isProcessingClick = false;
        }, 300);
    }
});

// Some error handling for microphone input
async function requestMicrophonePermission() {
    try {
        await navigator.mediaDevices.getUserMedia({ audio: true });
        return true;
    } catch (err) {
        console.error('Error accessing microphone:', err);
        window.toastFrontendError('Microphone access denied. Please enable microphone access in your browser settings.', 'Microphone Error');
        return false;
    }
}


class Speech {
    constructor() {
        this.synth = window.speechSynthesis;
        this.utterance = null;
    }

    stripEmojis(str) {
        return str
            .replace(/([\u2700-\u27BF]|[\uE000-\uF8FF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|[\u2011-\u26FF]|\uD83E[\uDD10-\uDDFF])/g, '')
            .replace(/\s+/g, ' ')
            .trim();
    }

    speak(text) {
        console.log('Speaking:', text);
        // Stop any current utterance
        this.stop();

        // Remove emojis and create a new utterance
        text = this.stripEmojis(text);
        this.utterance = new SpeechSynthesisUtterance(text);

        // Speak the new utterance
        this.synth.speak(this.utterance);
    }

    stop() {
        if (this.isSpeaking()) {
            this.synth.cancel();
        }
    }

    isSpeaking() {
        return this.synth?.speaking || false;
    }
}

export const speech = new Speech();
window.speech = speech
