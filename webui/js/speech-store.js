import { createStore } from "./AlpineStore.js";
import { updateChatInput, sendMessage } from "../index.js";

const Status = {
  INACTIVE: "inactive",
  ACTIVATING: "activating", 
  LISTENING: "listening",
  RECORDING: "recording",
  WAITING: "waiting",
  PROCESSING: "processing",
};

// Create the speech store
export const speechStore = createStore('speech', {
  // STT Settings
  stt_model_size: "tiny",
  stt_language: "en", 
  stt_silence_threshold: 0.05,
  stt_silence_duration: 1000,
  stt_waiting_timeout: 2000,
  
  // TTS Settings
  tts_enabled: false,
  
  // TTS State
  isSpeaking: false,
  currentAudio: null,
  audioContext: null,
  userHasInteracted: false,
  
  // STT State
  microphoneInput: null,
  micStatus: Status.INACTIVE,
  
  // Initialize speech functionality
  async init() {
    await this.loadSettings();
    this.setupBrowserTTS();
    this.setupUserInteractionHandling();
  },

  // Load settings from server
  async loadSettings() {
    try {
      const response = await fetchApi("/settings_get", { method: "POST" });
      const data = await response.json();
      const speechSection = data.settings.sections.find(s => s.title === "Speech");

      if (speechSection) {
        speechSection.fields.forEach(field => {
          if (this.hasOwnProperty(field.id)) {
            this[field.id] = field.value;
          }
        });
      }
    } catch (error) {
      window.toastFetchError("Failed to load speech settings", error);
      console.error("Failed to load speech settings:", error);
    }
  },

  // Setup browser TTS
  setupBrowserTTS() {
    this.synth = window.speechSynthesis;
    this.browserUtterance = null;
  },

  // Setup user interaction handling for autoplay policy
  setupUserInteractionHandling() {
    const enableAudio = () => {
      if (!this.userHasInteracted) {
        this.userHasInteracted = true;
        console.log("User interaction detected - audio playback enabled");
        
        // Create a dummy audio context to "unlock" audio
        try {
          this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
          this.audioContext.resume();
        } catch (e) {
          console.log("AudioContext not available");
        }
      }
    };

    // Listen for any user interaction
    const events = ['click', 'touchstart', 'keydown', 'mousedown'];
    events.forEach(event => {
      document.addEventListener(event, enableAudio, { once: true, passive: true });
    });
  },

  // Main speak function
  async speak(text) {
    if (!this.tts_enabled) return;
    if (this.isSpeaking) return;

    text = this.cleanText(text);
    if (!text.trim()) return;

    if (!this.userHasInteracted) {
      this.showAudioPermissionPrompt();
      return;
    }

    try {
      await this.speakWithKokoro(text);
    } catch (error) {
      console.error("TTS error:", error);
      this.speakWithBrowser(text);
    }
  },

  // Show a prompt to user to enable audio
  showAudioPermissionPrompt() {
    if (window.toast) {
      window.toast("Click anywhere to enable audio playback", "info", 5000);
    } else {
      console.log("Please click anywhere on the page to enable audio playback");
    }
  },

  // Browser TTS
  speakWithBrowser(text) {
    this.browserUtterance = new SpeechSynthesisUtterance(text);
    this.browserUtterance.onstart = () => { this.isSpeaking = true; };
    this.browserUtterance.onend = () => { this.isSpeaking = false; };
    this.synth.speak(this.browserUtterance);
  },

  // Kokoro TTS
  async speakWithKokoro(text) {
    try {
      const response = await sendJsonData("/synthesize", { text });
      
      if (response.success) {
        if (response.audio_parts) {
          // Multiple chunks - play sequentially
          for (const audioPart of response.audio_parts) {
            await this.playAudio(audioPart);
            await new Promise(resolve => setTimeout(resolve, 100)); // Brief pause
          }
        } else if (response.audio) {
          // Single audio
          await this.playAudio(response.audio);
        }
      } else {
        console.error("Kokoro TTS error:", response.error);
        this.speakWithBrowser(text);
      }
    } catch (error) {
      console.error("Kokoro TTS error:", error);
      this.speakWithBrowser(text);
    }
  },


  // Play base64 audio
  async playAudio(base64Audio) {
    return new Promise((resolve, reject) => {
      const audio = new Audio();
      
      audio.onplay = () => { 
        this.isSpeaking = true; 
      };
      audio.onended = () => { 
        this.isSpeaking = false;
        this.currentAudio = null;
        resolve();
      };
      audio.onerror = (error) => {
        this.isSpeaking = false;
        this.currentAudio = null;
        reject(error);
      };

      audio.src = `data:audio/wav;base64,${base64Audio}`;
      this.currentAudio = audio;
      
      audio.play().catch(error => {
        this.isSpeaking = false;
        this.currentAudio = null;
        
        if (error.name === 'NotAllowedError') {
          this.showAudioPermissionPrompt();
          this.userHasInteracted = false;
        }
        reject(error);
      });
    });
  },

  // Stop all speech
  stop() {
    if (this.synth?.speaking) {
      this.synth.cancel();
    }
    
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio.currentTime = 0;
      this.currentAudio = null;
    }
    
    this.isSpeaking = false;
  },

  // Clean text for TTS
  cleanText(text) {
    return text
      .replace(/([\u2700-\u27BF]|[\uE000-\uF8FF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|[\u2011-\u26FF]|\uD83E[\uDD10-\uDDFF])/g, "")
      .replace(/https?:\/\/[^\s]+/g, "")
      .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g, "")
      .replace(/\s+/g, " ")
      .trim();
  },

  // Initialize microphone input
  async initMicrophone() {
    if (this.microphoneInput) return this.microphoneInput;
    
    this.microphoneInput = new MicrophoneInput(
      async (text, isFinal) => {
        if (isFinal) {
          updateChatInput(text);
          if (!this.microphoneInput.messageSent) {
            this.microphoneInput.messageSent = true;
            await sendMessage();
          }
        }
      }
    );
    
    this.micStatus = Status.ACTIVATING;
    const initialized = await this.microphoneInput.initialize();
    return initialized ? this.microphoneInput : null;
  },

  // Toggle microphone
  async toggleMicrophone() {
    const hasPermission = await this.requestMicrophonePermission();
    if (!hasPermission) return;

    if (!this.microphoneInput && !(await this.initMicrophone())) {
      return;
    }

    this.micStatus = this.micStatus === Status.INACTIVE || this.micStatus === Status.ACTIVATING
      ? Status.LISTENING 
      : Status.INACTIVE;
  },

  // Request microphone permission
  async requestMicrophonePermission() {
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      return true;
    } catch (err) {
      console.error("Error accessing microphone:", err);
      toast("Microphone access denied. Please enable microphone access in your browser settings.", "error");
      return false;
    }
  }
});

// Microphone Input Class (simplified for store integration)
class MicrophoneInput {
  constructor(updateCallback) {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.lastChunk = [];
    this.updateCallback = updateCallback;
    this.messageSent = false;
    this.audioContext = null;
    this.mediaStreamSource = null;
    this.analyserNode = null;
    this._status = Status.INACTIVE;
    this.lastAudioTime = null;
    this.waitingTimer = null;
    this.silenceStartTime = null;
    this.hasStartedRecording = false;
    this.analysisFrame = null;
  }

  get status() {
    return this._status;
  }

  set status(newStatus) {
    if (this._status === newStatus) return;
    
    const oldStatus = this._status;
    this._status = newStatus;
    speechStore.micStatus = newStatus;
    console.log(`Mic status changed from ${oldStatus} to ${newStatus}`);

    this.handleStatusChange(oldStatus, newStatus);
  }

  async initialize() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 }
      });

      this.mediaRecorder = new MediaRecorder(stream);
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0 && (this.status === Status.RECORDING || this.status === Status.WAITING)) {
          if (this.lastChunk) {
            this.audioChunks.push(this.lastChunk);
            this.lastChunk = null;
          }
          this.audioChunks.push(event.data);
        } else if (this.status === Status.LISTENING) {
          this.lastChunk = event.data;
        }
      };

      this.setupAudioAnalysis(stream);
      return true;
    } catch (error) {
      console.error("Microphone initialization error:", error);
      toast("Failed to access microphone. Please check permissions.", "error");
      return false;
    }
  }

  handleStatusChange(oldStatus, newStatus) {
    if (newStatus != Status.RECORDING) {
      this.lastChunk = null;
    }

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
    if (!this.hasStartedRecording && this.mediaRecorder.state !== "recording") {
      this.hasStartedRecording = true;
      this.mediaRecorder.start(1000);
      console.log("Speech started");
    }
    if (this.waitingTimer) {
      clearTimeout(this.waitingTimer);
      this.waitingTimer = null;
    }
  }

  handleWaitingState() {
    this.waitingTimer = setTimeout(() => {
      if (this.status === Status.WAITING) {
        this.status = Status.PROCESSING;
      }
    }, speechStore.stt_waiting_timeout);
  }

  handleProcessingState() {
    this.stopRecording();
    this.process();
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

      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        const amplitude = (dataArray[i] - 128) / 128;
        sum += amplitude * amplitude;
      }
      const rms = Math.sqrt(sum / dataArray.length);
      const now = Date.now();

      // Update status based on audio level (ignore if TTS is speaking)
      if (rms > this.densify(speechStore.stt_silence_threshold)) {
        this.lastAudioTime = now;
        this.silenceStartTime = null;

        if ((this.status === Status.LISTENING || this.status === Status.WAITING) && !speechStore.isSpeaking && !speechStore.isGenerating) {
          this.status = Status.RECORDING;
        }
      } else if (this.status === Status.RECORDING) {
        if (!this.silenceStartTime) {
          this.silenceStartTime = now;
        }

        const silenceDuration = now - this.silenceStartTime;
        if (silenceDuration >= speechStore.stt_silence_duration) {
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

  stopRecording() {
    if (this.mediaRecorder?.state === "recording") {
      this.mediaRecorder.stop();
      this.hasStartedRecording = false;
    }
  }

  densify(x) {
    return Math.exp(-5 * (1 - x));
  }

  async process() {
    if (this.audioChunks.length === 0) {
      this.status = Status.LISTENING;
      return;
    }

    const audioBlob = new Blob(this.audioChunks, { type: "audio/wav" });
    const base64 = await this.convertBlobToBase64Wav(audioBlob);

    try {
      const result = await sendJsonData("/transcribe", { audio: base64 });
      const text = this.filterResult(result.text || "");

      if (text) {
        console.log("Transcription:", result.text);
        await this.updateCallback(result.text, true);
      }
    } catch (error) {
      window.toastFetchError("Transcription error", error);
      console.error("Transcription error:", error);
    } finally {
      this.audioChunks = [];
      this.status = Status.LISTENING;
    }
  }

  convertBlobToBase64Wav(audioBlob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64Data = reader.result.split(",")[1];
        resolve(base64Data);
      };
      reader.onerror = (error) => reject(error);
      reader.readAsDataURL(audioBlob);
    });
  }

  filterResult(text) {
    text = text.trim();
    let ok = false;
    while (!ok) {
      if (!text) break;
      if (text[0] === "{" && text[text.length - 1] === "}") break;
      if (text[0] === "(" && text[text.length - 1] === ")") break;
      if (text[0] === "[" && text[text.length - 1] === "]") break;
      ok = true;
    }
    if (ok) return text;
    else console.log(`Discarding transcription: ${text}`);
  }
}

// Initialize speech store
window.speechStore = speechStore;

// Event listeners
document.addEventListener("settings-updated", () => speechStore.loadSettings());
document.addEventListener("DOMContentLoaded", () => speechStore.init());