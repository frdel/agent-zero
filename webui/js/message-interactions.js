// Message Interactions Handler for Touch/Pointer Devices
import { getInputType } from "./device.js";

// Track which messages currently have visible action buttons
const visibleActionStates = new WeakSet();

// Initialize interaction handlers for touch devices
export function initializeMessageInteractions() {
    const inputType = getInputType();
    
    if (inputType === "touch") {
        setupTouchInteractions();
    }
    // Pointer devices use hover states from CSS, no JS needed
}

// Set up touch device interactions
function setupTouchInteractions() {
    // Use event delegation on the chat history container
    const chatHistory = document.getElementById("chat-history");
    if (!chatHistory) return;
    
    // Handle touch interactions for showing/hiding action buttons
    chatHistory.addEventListener("click", handleTouchInteraction, { passive: false });
    
    // Handle clicks outside messages to hide action buttons
    document.addEventListener("click", handleOutsideClick, { passive: true });
    
    // Prevent text selection when tapping action buttons area
    chatHistory.addEventListener("selectstart", handleSelectStart, { passive: false });
}

// Handle touch interactions on messages
function handleTouchInteraction(e) {
    // Find the closest message container
    const messageContainer = e.target.closest(".msg-content, .kvps-row, .message-text");
    if (!messageContainer) return;
    
    // If clicking on action buttons, let them handle their own events
    if (e.target.closest(".action-buttons")) {
        return;
    }
    
    // Toggle action buttons visibility
    toggleActionButtons(messageContainer, e);
}

// Handle clicks outside of messages to hide action buttons
function handleOutsideClick(e) {
    // If clicking on a message or action button, don't hide
    if (e.target.closest(".msg-content, .kvps-row, .message-text, .action-buttons")) {
        return;
    }
    
    // Hide all visible action buttons
    hideAllActionButtons();
}

// Prevent text selection when interacting with action area
function handleSelectStart(e) {
    // Allow text selection unless we're in the action buttons area
    const actionButtons = e.target.closest(".action-buttons");
    const messageContainer = e.target.closest(".msg-content, .kvps-row, .message-text");
    
    if (actionButtons) {
        e.preventDefault();
        return false;
    }
    
    // If a message has visible action buttons, prevent selection to avoid conflicts
    if (messageContainer && visibleActionStates.has(messageContainer)) {
        // Allow selection after a short delay to distinguish from tap-to-show-buttons
        setTimeout(() => {
            if (visibleActionStates.has(messageContainer)) {
                // Still visible, user might want to select text
                return true;
            }
        }, 200);
    }
}

// Toggle action buttons visibility for a message
export function toggleActionButtons(messageContainer, event = null) {
    if (!messageContainer) return;
    
    const isCurrentlyVisible = visibleActionStates.has(messageContainer);
    
    if (isCurrentlyVisible) {
        hideActionButtons(messageContainer);
    } else {
        // Hide all other visible action buttons first
        hideAllActionButtons();
        
        // Show action buttons for this message
        showActionButtons(messageContainer);
    }
    
    // Prevent event bubbling to avoid triggering document click handler
    if (event) {
        event.stopPropagation();
    }
}

// Show action buttons for a message
export function showActionButtons(messageContainer) {
    if (!messageContainer) return;
    
    messageContainer.classList.add("show-actions");
    visibleActionStates.add(messageContainer);
    
    // Add a slight delay to prevent immediate hiding from document click
    setTimeout(() => {
        messageContainer.setAttribute("data-actions-visible", "true");
    }, 50);
}

// Hide action buttons for a message
export function hideActionButtons(messageContainer) {
    if (!messageContainer) return;
    
    messageContainer.classList.remove("show-actions");
    messageContainer.removeAttribute("data-actions-visible");
    visibleActionStates.delete(messageContainer);
}

// Hide all visible action buttons
export function hideAllActionButtons() {
    const chatHistory = document.getElementById("chat-history");
    if (!chatHistory) return;
    
    // Find all messages with visible action buttons
    const visibleMessages = chatHistory.querySelectorAll(".show-actions");
    visibleMessages.forEach(message => {
        hideActionButtons(message);
    });
}

// Setup interaction for a specific message (called when message is created)
export function setupMessageInteraction(messageContainer) {
    if (!messageContainer) return;
    
    const inputType = getInputType();
    
    if (inputType === "touch") {
        // For touch devices, add click handler
        messageContainer.addEventListener("click", (e) => {
            // Only handle if not clicking on action buttons
            if (!e.target.closest(".action-buttons")) {
                toggleActionButtons(messageContainer, e);
            }
        }, { passive: false });
        
        // Prevent context menu on long press for action area
        messageContainer.addEventListener("contextmenu", (e) => {
            if (e.target.closest(".action-buttons")) {
                e.preventDefault();
            }
        });
    }
    
    // For both touch and pointer devices, handle keyboard navigation
    setupKeyboardNavigation(messageContainer);
}

// Set up keyboard navigation for accessibility
function setupKeyboardNavigation(messageContainer) {
    const actionButtons = messageContainer.querySelector(".action-buttons");
    if (!actionButtons) return;
    
    const buttons = actionButtons.querySelectorAll(".action-button");
    
    buttons.forEach((button, index) => {
        button.setAttribute("tabindex", "0");
        
        button.addEventListener("keydown", (e) => {
            switch (e.key) {
                case "Enter":
                case " ":
                    e.preventDefault();
                    button.click();
                    break;
                case "ArrowLeft":
                    e.preventDefault();
                    const prevButton = buttons[index - 1] || buttons[buttons.length - 1];
                    prevButton.focus();
                    break;
                case "ArrowRight":
                    e.preventDefault();
                    const nextButton = buttons[index + 1] || buttons[0];
                    nextButton.focus();
                    break;
                case "Escape":
                    hideActionButtons(messageContainer);
                    messageContainer.focus();
                    break;
            }
        });
    });
}

// Debounced scroll handler to manage viewport sticky buttons
let scrollTimeout;
export function handleScroll() {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
        // Check if any viewport-sticky buttons should be hidden
        const stickyButtons = document.querySelectorAll(".action-buttons.viewport-sticky");
        stickyButtons.forEach(buttons => {
            const parent = buttons.closest(".msg-content, .kvps-row, .message-text");
            if (parent) {
                const rect = parent.getBoundingClientRect();
                const isVisible = rect.top < window.innerHeight && rect.bottom > 0;
                
                if (isVisible) {
                    buttons.classList.remove("viewport-sticky");
                }
            }
        });
    }, 100);
}

// Initialize scroll handler
export function initializeScrollHandler() {
    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("resize", handleScroll, { passive: true });
}

// Cleanup function
export function cleanupMessageInteractions() {
    window.removeEventListener("scroll", handleScroll);
    window.removeEventListener("resize", handleScroll);
    
    const chatHistory = document.getElementById("chat-history");
    if (chatHistory) {
        chatHistory.removeEventListener("click", handleTouchInteraction);
        chatHistory.removeEventListener("selectstart", handleSelectStart);
    }
    
    document.removeEventListener("click", handleOutsideClick);
    
    // Clear visible states
    visibleActionStates.clear?.();
}