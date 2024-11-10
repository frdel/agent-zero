import { pipeline, read_audio } from './transformers@3.0.2.js';
import { updateChatInput, sendMessage } from './index.js';

const microphoneButton = document.getElementById('microphone-button');
let microphoneInput = null;
let isProcessingClick = false;

class MicrophoneInput {
    /**
     * Voice Input Handler with Whisper Transcription
     * 
     * Whisper Model Size Configuration:
     * - 'tiny':   Smallest model, fastest, lowest accuracy (~32MB)
     *   - Best for: Quick prototyping, low-resource environments
     *   - Pros: Very fast, low memory usage
     *   - Cons: Lowest transcription accuracy
     * 
     * - 'base':   Small model, good balance of speed and accuracy (~74MB)
     *   - Best for: General-purpose voice input
     *   - Pros: Reasonable accuracy, moderate resource usage
     *   - Cons: Less accurate than larger models
     * 
     * - 'small':  Medium-sized model, better accuracy (~244MB)
     *   - Best for: More precise transcription needs
     *   - Pros: Improved accuracy over base model
     *   - Cons: Slower, more memory-intensive
     * 
     * - 'medium': Large model with high accuracy (~769MB)
     *   - Best for: Professional transcription, multi-language support
     *   - Pros: Very high accuracy
     *   - Cons: Significant computational resources required
     * 
     * - 'large':  Largest model, highest accuracy (~1.5GB)
     *   - Best for: Professional, multi-language transcription
     *   - Pros: Highest possible accuracy
     *   - Cons: Slowest, most resource-intensive
     * 
     * Recommended Default: 'base' for most web applications
     */
    constructor(updateCallback, options = {}) {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.updateCallback = updateCallback;
        this.isFinalizing = false;
        this.messageSent = false; // move messageSent into class

        // New properties for silence detection
        this.audioContext = null;
        this.mediaStreamSource = null;
        this.analyserNode = null;
        this.silenceTimer = null;
        this.silenceThreshold = options.silenceThreshold || 0.01; // Adjust as needed
        this.silenceDuration = options.silenceDuration || 2000;   // Duration in milliseconds

        this.options = {
            modelSize: 'tiny',
            language: 'en',
            chunkDuration: 3000,
            ...options
        };
    }

    async initialize() {
        try {

            this.transcriber = await pipeline(`automatic-speech-recognition`, `Xenova/whisper-${this.options.modelSize}.${this.options.language}`);

            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    channelCount: 1
                }
            });

            // Configure MediaRecorder
            this.mediaRecorder = new MediaRecorder(stream);

            // Handle audio data availability
            this.mediaRecorder.ondataavailable = async (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                    // await this.processAudioChunk(event.data);
                }
            };

            // Handle recording stop
            this.mediaRecorder.onstop = async () => {
                await this.finalizeRecording();
            };

            // Set up AudioContext and AnalyserNode for silence detection
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.mediaStreamSource = this.audioContext.createMediaStreamSource(stream);
            this.analyserNode = this.audioContext.createAnalyser();
            this.analyserNode.minDecibels = -90;
            this.analyserNode.maxDecibels = -10;
            this.analyserNode.smoothingTimeConstant = 0.85;

            this.mediaStreamSource.connect(this.analyserNode);
        } catch (error) {
            console.error('Microphone initialization error:', error);
            toast('Failed to access microphone. Please check permissions.', 'error');
        }
    }

    startSilenceDetection() {
        const dataArray = new Uint8Array(this.analyserNode.fftSize);
        const checkSilence = () => {
            this.analyserNode.getByteTimeDomainData(dataArray);

            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                const amplitude = (dataArray[i] - 128) / 128;
                sum += amplitude * amplitude;
            }
            const rms = Math.sqrt(sum / dataArray.length);

            if (rms < this.silenceThreshold) {
                if (!this.silenceTimer) {
                    this.silenceTimer = setTimeout(() => {
                        if (this.isRecording) {
                            console.log('Silence detected. Stopping recording.');
                            this.stopRecording();
                            microphoneButton.classList.remove('recording');
                            microphoneButton.classList.remove('mic-pulse');
                        }
                    }, this.silenceDuration);
                }
            } else {
                if (this.silenceTimer) {
                    clearTimeout(this.silenceTimer);
                    this.silenceTimer = null;
                }
            }

            if (this.isRecording) {
                requestAnimationFrame(checkSilence);
            }
        };

        if (this.isRecording) {
            requestAnimationFrame(checkSilence);
        }
    }

    startRecording() {
        if (this.mediaRecorder && this.audioContext) {
            this.isRecording = true;
            this.audioChunks = [];
            this.messageSent = false;
            this.mediaRecorder.start(this.options.chunkDuration);
            this.audioContext.resume();
            this.startSilenceDetection();
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.isRecording = false;
            if (!this.isFinalizing) {
                this.isFinalizing = true;
                this.mediaRecorder.stop();
                this.audioContext.suspend();
                if (this.silenceTimer) {
                    clearTimeout(this.silenceTimer);
                    this.silenceTimer = null;
                }
            }
        }
    }


    async finalizeRecording() {
        if (this.isFinalizing) {
            this.isFinalizing = false;

            if (this.audioChunks.length > 0) {

                const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                const audioUrl = URL.createObjectURL(audioBlob);
                const samplingRate = 16000; // Adjust as needed for the model
                const audioData = await read_audio(audioUrl, samplingRate);
                URL.revokeObjectURL(audioUrl);

                // Transcribe the audio
                const result = await this.transcriber(audioData);

                if (result.text) {
                    console.log('Final transcription received:', result.text);
                    await this.updateCallback(result.text, true);
                } else {
                    console.warn('Final transcription returned empty text.');
                }


                // Release the object URL after use

                // const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                // this.audioChunks = [];  // Clear for next recording

                // const reader = new FileReader();
                // reader.onloadend = async () => {
                //     const base64Data = reader.result.split(',')[1];

                //     try {
                //         const response = await fetch('/transcribe', {
                //             method: 'POST',
                //             headers: {
                //                 'Content-Type': 'application/json'
                //             },
                //             body: JSON.stringify({
                //                 audio_data: base64Data,
                //                 model_size: this.options.modelSize,
                //                 language: this.options.language,
                //                 is_final: true
                //             })
                //         });

                //         const result = await response.json();

                //         if (result.text) {
                //             console.log('Final transcription received:', result.text);
                //             await this.updateCallback(result.text, true);
                //         } else {
                //             console.warn('Final transcription returned empty text.');
                //         }
                //     } catch (transcribeError) {
                //         console.error('Final transcription error:', transcribeError);
                //         toast('Final transcription failed.', 'error');
                //     } finally {
                //         // Reset the microphone button state
                //         microphoneButton.classList.remove('recording');
                //         microphoneButton.classList.remove('mic-pulse');
                //         microphoneButton.style.backgroundColor = '';
                //     }
                // };
                // reader.readAsDataURL(audioBlob);
            }
        }
    }
}

export default MicrophoneInput;

async function initializeMicrophoneInput() {
    console.log('Initializing microphone input');

    microphoneInput = new MicrophoneInput(
        async (text, isFinal) => {
            if (isFinal) {
                console.log('Final transcription callback received:', text);
                updateChatInput(text)
                // chatInput.value = text;
                // adjustTextareaHeight();

                if (!microphoneInput.messageSent) {
                    microphoneInput.messageSent = true;
                    console.log('Sending message');
                    await sendMessage();
                }
            }
        },
        {
            modelSize: 'tiny',
            language: 'en',
            silenceThreshold: 0.07, // Adjust as needed
            silenceDuration: 2000,  // Adjust as needed
            onError: (error) => {
                console.error('Microphone input error:', error);
                toast('Microphone error: ' + error.message, 'error');
                // Reset recording state
                if (microphoneButton.classList.contains('recording')) {
                    microphoneButton.classList.remove('recording');
                }
            }
        }
    );

    await microphoneInput.initialize();
}


function toggleRecording() {
    console.log('toggleRecording called, isRecording:', microphoneInput.isRecording);

    if (microphoneInput.isRecording) {
        microphoneInput.stopRecording();
        microphoneButton.classList.remove('recording');
        // Add pulsing animation class
        microphoneButton.classList.remove('mic-pulse');
    } else {
        microphoneInput.startRecording();
        microphoneButton.classList.add('recording');
        // Add pulsing animation class
        microphoneButton.classList.add('mic-pulse');
    }

    // Add visual feedback
    microphoneButton.style.backgroundColor = microphoneInput.isRecording ? '#ff4444' : '';
    console.log('New recording state:', microphoneInput.isRecording);
}

// Some error handling for microphone input
async function requestMicrophonePermission() {
    try {
        await navigator.mediaDevices.getUserMedia({ audio: true });
        return true;
    } catch (err) {
        console.error('Error accessing microphone:', err);
        toast('Microphone access denied. Please enable microphone access in your browser settings.', 'error');
        return false;
    }
}
// microphoneButton click event listener modifier
microphoneButton.addEventListener('click', async () => {
    console.log('Microphone button clicked');
    if (isProcessingClick) {
        console.log('Click already being processed, ignoring');
        return;
    }
    isProcessingClick = true;

    const hasPermission = await requestMicrophonePermission();
    if (!hasPermission) return;

    if (!microphoneInput) {
        await initializeMicrophoneInput();
    }

    await toggleRecording();

    setTimeout(() => {
        isProcessingClick = false;
    }, 300); // Add a 300ms delay before allowing another click
});
