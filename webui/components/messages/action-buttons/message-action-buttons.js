// Message Action Buttons Component
import { store as speechStore } from "/components/chat/speech/speech-store.js";

// Extract text content based on container type
function extractTextContent(container) {
    if (container.classList.contains("kvps-row")) {
        return container.querySelector(".kvps-val")?.innerText || "";
    } else if (container.classList.contains("message-text")) {
        // User messages use <pre> elements, not <span>
        return container.querySelector("pre")?.innerText || container.querySelector("span")?.innerText || "";
    } else {
        // Other message types use <span> elements
        return container.querySelector("span")?.innerText || "";
    }
}

// Copy text with fallback for local development
async function copyToClipboard(text, button) {
    try {
        // Try modern clipboard API first
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            showCopyFeedback(button, true);
        } else {
            // Fallback for local development or non-HTTPS
            const textarea = document.createElement("textarea");
            textarea.value = text;
            textarea.style.position = "fixed";
            textarea.style.left = "-999999px";
            document.body.appendChild(textarea);
            textarea.select();
            
            try {
                document.execCommand("copy");
                showCopyFeedback(button, true);
            } catch (err) {
                console.error("Fallback copy failed:", err);
                showCopyFeedback(button, false);
            } finally {
                document.body.removeChild(textarea);
            }
        }
    } catch (err) {
        console.error("Copy failed:", err);
        showCopyFeedback(button, false);
    }
}

// Show visual feedback for copy action
function showCopyFeedback(button, success) {

    
    if (success) {

        button.classList.add("success");
    } else {
        button.classList.add("error");
    }
    
    setTimeout(() => {
        button.classList.remove("success", "error");
    }, 2000);
}

// Speak text using speech store
async function speakContent(text, button) {
    try {
        // Validate input text
        if (!text || typeof text !== 'string' || text.trim().length === 0) {
            console.warn("TTS: No valid text to speak");
            return;
        }
        
        // Update button state
        button.classList.add("speaking");
        const icon = button.querySelector(".material-symbols-outlined");
        const originalIcon = icon.textContent;
        
        // Check if already speaking
        if (speechStore.isSpeaking) {
            // Stop speaking using the correct speech store method
            if (speechStore.stop) {
                speechStore.stop();
            } else {
                // Fallback if stop doesn't exist
                speechSynthesis.cancel();
            }
            icon.textContent = originalIcon;
            button.classList.remove("speaking");
            return;
        }
        
        // Clean and speak text
        const cleanedText = speechStore.cleanText ? speechStore.cleanText(text.trim()) : text.trim();
        
        // Validate cleaned text
        if (!cleanedText || cleanedText.length === 0) {
            console.warn("TTS: Text was empty after cleaning");
            button.classList.remove("speaking");
            return;
        }
        
        // Update icon to show speaking state
        icon.textContent = "stop_circle";
        
        // Start speaking - use the speak function from speech store
        if (speechStore.speak) {
            await speechStore.speak(cleanedText);
        } else {
            // Fallback to browser TTS if speech store doesn't have speak function
            const utterance = new SpeechSynthesisUtterance(cleanedText);
            utterance.lang = 'en-US'; // Ensure English language
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;
            
            // Handle utterance events
            utterance.onend = () => {
                icon.textContent = originalIcon;
                button.classList.remove("speaking");
            };
            
            utterance.onerror = (event) => {
                console.error("TTS utterance error:", event.error);
                icon.textContent = originalIcon;
                button.classList.remove("speaking");
            };
            
            speechSynthesis.speak(utterance);
            return; // Don't reset button state immediately for browser TTS
        }
        
        // Reset button state when done (for speech store)
        icon.textContent = originalIcon;
        button.classList.remove("speaking");
        
    } catch (err) {
        console.error("Speech failed:", err);
        button.classList.remove("speaking");
        
        // Reset icon
        const icon = button.querySelector(".material-symbols-outlined");
        if (icon) {
            icon.textContent = "volume_up";
        }
        
        // Show error feedback
        button.classList.add("error");
        
        setTimeout(() => {
            button.classList.remove("error");
        }, 2000);
    }
}

// Create action buttons for a message or KVP
export function createActionButtons() {
    const container = document.createElement("div");
    container.className = "action-buttons";
    
    // Copy button
    const copyButton = document.createElement("button");
    copyButton.className = "action-button copy-action";
    copyButton.setAttribute("aria-label", "Copy text");
    copyButton.innerHTML = `
        <span class="material-symbols-outlined">content_copy</span>
    `;
    
    // Speak button
    const speakButton = document.createElement("button");
    speakButton.className = "action-button speak-action";
    speakButton.setAttribute("aria-label", "Speak text");
    speakButton.innerHTML = `
        <span class="material-symbols-outlined">volume_up</span>
    `;
    
    // Add event listeners
    copyButton.addEventListener("click", async function(e) {
        e.stopPropagation();
        const messageContainer = this.closest(".msg-content, .kvps-row, .message-text");
        const textToCopy = extractTextContent(messageContainer);
        await copyToClipboard(textToCopy, this);
    });
    
    speakButton.addEventListener("click", async function(e) {
        e.stopPropagation();
        const messageContainer = this.closest(".msg-content, .kvps-row, .message-text");
        const textToSpeak = extractTextContent(messageContainer);
        await speakContent(textToSpeak, this);
    });
    
    // Add buttons to container
    container.appendChild(copyButton);
    container.appendChild(speakButton);
    
    return container;
}

// Add action buttons to an element
export function addActionButtonsToElement(element) {
    // Remove any existing action buttons first
    const existingButtons = element.querySelector(".action-buttons");
    if (existingButtons) {
        existingButtons.remove();
    }
    
    
    // Create and add new action buttons
    const actionButtons = createActionButtons();
    element.appendChild(actionButtons);
    
    // Set up intersection observer for viewport detection
    setupViewportObserver(element);
}

// Set up intersection observer for keeping buttons in viewport
function setupViewportObserver(element) {
    const actionButtons = element.querySelector(".action-buttons");
    if (!actionButtons) return;
    
    // Create observer for viewport detection
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const buttons = entry.target.querySelector(".action-buttons");
            if (buttons && !entry.isIntersecting) {

            } else if (buttons) {

            }
        });
    }, {
        root: null,
        rootMargin: "-50px 0px",
        threshold: 0
    });
    
    // Start observing
    observer.observe(element);
    
    // Store observer reference for cleanup
    element._actionButtonsObserver = observer;
}

// Cleanup function to disconnect observer
export function cleanupActionButtons(element) {
    if (element._actionButtonsObserver) {
        element._actionButtonsObserver.disconnect();
        delete element._actionButtonsObserver;
    }
}