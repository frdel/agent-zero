import { speechStore } from "./speech-store.js";

const microphoneButton = document.getElementById("microphone-button");
let isProcessingClick = false;

// Update microphone button UI based on store status
function updateMicrophoneButtonUI() {
  const status = speechStore.micStatus;
  
  microphoneButton.classList.remove('mic-inactive', 'mic-activating', 'mic-listening', 'mic-recording', 'mic-waiting', 'mic-processing');
  microphoneButton.classList.add(`mic-${status.toLowerCase()}`);
  microphoneButton.setAttribute("data-status", status);
}

// Watch store for status changes
document.addEventListener("alpine:init", () => {
  Alpine.effect(() => {
    updateMicrophoneButtonUI();
  });
});

// Microphone button click handler
microphoneButton.addEventListener("click", async () => {
  if (isProcessingClick) return;
  isProcessingClick = true;

  try {
    await speechStore.toggleMicrophone();
  } finally {
    setTimeout(() => {
      isProcessingClick = false;
    }, 300);
  }
});

// Create simplified Speech class for backward compatibility
class Speech {
  async speak(text) {
    return speechStore.speak(text);
  }

  stop() {
    speechStore.stop();
  }

  isSpeaking() {
    return speechStore.isSpeaking;
  }
}

export const speech = new Speech();
window.speech = speech;