// Simplified Message Action Buttons - Keeping the Great Look & Feel
import { store as speechStore } from "/components/chat/speech/speech-store.js";

// Extract text content from different message types
function getTextContent(element) {
    if (element.classList.contains("kvps-row")) {
        return element.querySelector(".kvps-val")?.innerText || "";
    } else if (element.classList.contains("message-text")) {
        return element.querySelector("pre")?.innerText || element.querySelector("span")?.innerText || "";
    } else {
        return element.querySelector("span")?.innerText || "";
    }
}

// Create and add action buttons to element
export function addActionButtonsToElement(element) {
    // Skip if buttons already exist
    if (element.querySelector(".action-buttons")) return;
    
    // Create container with same styling as original
    const container = document.createElement("div");
    container.className = "action-buttons";
    
    // Copy button - matches original design
    const copyBtn = document.createElement("button");
    copyBtn.className = "action-button copy-action";
    copyBtn.setAttribute("aria-label", "Copy text");
    copyBtn.innerHTML = '<span class="material-symbols-outlined">content_copy</span>';
    
    copyBtn.onclick = async (e) => {
        e.stopPropagation();
        const text = getTextContent(element);
        const icon = copyBtn.querySelector(".material-symbols-outlined");
        
        try {
            // Try modern clipboard API
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
            } else {
                // Fallback for local dev
                const textarea = document.createElement("textarea");
                textarea.value = text;
                textarea.style.position = "fixed";
                textarea.style.left = "-999999px";
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand("copy");
                document.body.removeChild(textarea);
            }
            
            // Visual feedback - matches original
            icon.textContent = "check";
            copyBtn.classList.add("success");
            setTimeout(() => {
                icon.textContent = "content_copy";
                copyBtn.classList.remove("success");
            }, 2000);
            
        } catch (err) {
            console.error("Copy failed:", err);
            icon.textContent = "error";
            copyBtn.classList.add("error");
            setTimeout(() => {
                icon.textContent = "content_copy";
                copyBtn.classList.remove("error");
            }, 2000);
        }
    };
    
    // Speak button - matches original design
    const speakBtn = document.createElement("button");
    speakBtn.className = "action-button speak-action";
    speakBtn.setAttribute("aria-label", "Speak text");
    speakBtn.innerHTML = '<span class="material-symbols-outlined">volume_up</span>';
    
    speakBtn.onclick = async (e) => {
        e.stopPropagation();
        const text = getTextContent(element);
        const icon = speakBtn.querySelector(".material-symbols-outlined");
        
        if (!text || text.trim().length === 0) return;
        
        try {
            // Check if already speaking and stop it
            if (speechStore.isSpeaking) {
                if (speechStore.stop) speechStore.stop();
                else speechSynthesis.cancel();
                return;
            }
            
            // Visual feedback - matches original
            speakBtn.classList.add("speaking");
            icon.textContent = "stop_circle";
            
            // Use speech store if available, otherwise browser TTS
            if (speechStore?.speak) {
                const cleanedText = speechStore.cleanText ? speechStore.cleanText(text) : text;
                await speechStore.speak(cleanedText);
            } else {
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.lang = 'en-US';
                utterance.onend = () => {
                    icon.textContent = "volume_up";
                    speakBtn.classList.remove("speaking");
                };
                speechSynthesis.speak(utterance);
                return; // Don't reset immediately for browser TTS
            }
            
            // Reset for speech store
            icon.textContent = "volume_up";
            speakBtn.classList.remove("speaking");
            
        } catch (err) {
            console.error("Speech failed:", err);
            icon.textContent = "volume_up";
            speakBtn.classList.remove("speaking");
        }
    };
    
    container.append(copyBtn, speakBtn);
    element.appendChild(container);
}