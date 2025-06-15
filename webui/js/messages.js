// copy button
import { openImageModal } from "./image_modal.js";

function createCopyButton() {
  const button = document.createElement("button");
  button.className = "copy-button";
  button.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
    <path d="m4 16-2-2v-10c0-1.1.9-2 2-2h10l2 2"/>
  </svg>`;

  button.addEventListener("click", async function (e) {
    e.stopPropagation();
    const container = this.closest(".msg-content, .kvps-row, .message-text");
    let textToCopy;

    if (container.classList.contains("kvps-row")) {
      textToCopy = container.querySelector(".kvps-val").textContent;
    } else if (container.classList.contains("message-text")) {
      textToCopy = container.querySelector("span").textContent;
    } else {
      textToCopy = container.querySelector("span").textContent;
    }

    try {
      await navigator.clipboard.writeText(textToCopy);
      const originalHTML = button.innerHTML;
      button.classList.add("copied");
      button.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20,6 9,17 4,12"/>
      </svg>`;
      setTimeout(() => {
        button.classList.remove("copied");
        button.innerHTML = originalHTML;
      }, 2000);
    } catch (err) {
      console.error("Failed to copy text:", err);
    }
  });

  return button;
}

function addCopyButtonToElement(element) {
  if (!element.querySelector(".copy-button")) {
    const button = createCopyButton();
    element.appendChild(button);
  }
}

function createControlButton(label, title, handler) {
  const btn = document.createElement("button");
  btn.className = "message-button";
  btn.textContent = label;
  btn.title = title;
  btn.setAttribute("aria-label", title);
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    handler();
  });
  return btn;
}

// Legacy function - replaced by injectConsoleControls for all message types
function injectMessageControls(messageDiv) {
  // This function is deprecated - all messages now use injectConsoleControls
  console.warn("injectMessageControls is deprecated, use injectConsoleControls instead");
}

function injectConsoleControls(messageDiv, command, type) {
  const controls = document.createElement("div");
  controls.className = "message-controls console-controls";

  // Function to get current states from localStorage (always fresh)
  const getCurrentStates = () => ({
    isHidden: localStorage.getItem(`msgHidden_${type}`) === 'true',
    isFullHeight: localStorage.getItem(`msgFullHeight_${type}`) === 'true'
  });

  // Function to determine optimal message height state - simplified with smooth transitions
  const determineMessageState = (msg) => {
    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        try {
          // Ensure message is in natural state for accurate measurement
          const originalMaxHeight = msg.style.maxHeight;
          const originalOverflow = msg.style.overflow;
          const originalOverflowY = msg.style.overflowY;
          
          // Temporarily remove height constraints for accurate measurement
          msg.style.maxHeight = 'none';
          msg.style.overflow = 'visible';
          msg.style.overflowY = 'visible';
          
          // Also temporarily remove any state classes for pure measurement
          const wasCompact = msg.classList.contains('message-compact');
          const wasExpanded = msg.classList.contains('message-expanded');
          msg.classList.remove('message-compact', 'message-expanded');
          
          // Force reflow to get accurate height
          msg.offsetHeight;
          
          // Get total message height including all content
          const totalHeight = msg.scrollHeight || 0;
          
          // Also check the content specifically for tool messages
          let contentHeight = 0;
          const scrollableContent = msg.querySelector('.scrollable-content');
          const kvpsTable = msg.querySelector('.msg-kvps');
          
          if (scrollableContent) {
            contentHeight = Math.max(contentHeight, scrollableContent.scrollHeight || 0);
          }
          if (kvpsTable) {
            contentHeight = Math.max(contentHeight, kvpsTable.scrollHeight || 0);
          }
          
          const finalHeight = Math.max(totalHeight, contentHeight);
          
          // Restore original state
          msg.style.maxHeight = originalMaxHeight;
          msg.style.overflow = originalOverflow;
          msg.style.overflowY = originalOverflowY;
          
          // Restore classes if they were there
          if (wasCompact) msg.classList.add('message-compact');
          if (wasExpanded) msg.classList.add('message-expanded');
          
          console.log(`📏 Message height analysis: total=${totalHeight}px, content=${contentHeight}px, final=${finalHeight}px`);
          
          // More conservative threshold - only add scrollbars for truly tall content
          if (finalHeight > 350) {
            console.log('📏 Case: >350px → Compact scroll');
            resolve('compact');
          } else {
            console.log('📏 Case: ≤350px → Natural (no scroll)');
            resolve('natural');
          }
          
        } catch (error) {
          console.warn('Error determining message state:', error);
          resolve('natural');
        }
      });
    });
  };

  // Debounced state update to prevent flashing during streaming
  const stateUpdateTimeouts = new Map();
  
  const debouncedStateUpdate = (messageElement, delay = 100) => {
    const messageId = messageElement.id || messageElement.className || Math.random().toString();
    
    // Clear existing timeout for this message
    if (stateUpdateTimeouts.has(messageId)) {
      clearTimeout(stateUpdateTimeouts.get(messageId));
    }
    
    // Set new timeout
    const timeoutId = setTimeout(async () => {
      try {
        const newState = await determineMessageState(messageElement);
        // Apply state smoothly
        messageElement.style.transition = 'max-height 0.2s ease-out, opacity 0.15s ease-in-out';
        
        // Remove existing state classes
        messageElement.classList.remove("message-compact", "message-expanded");
        
        // Apply new state
        if (newState === 'compact') {
          messageElement.classList.add("message-compact");
        }
        
        stateUpdateTimeouts.delete(messageId);
      } catch (error) {
        console.warn('Error in debounced state update:', error);
        stateUpdateTimeouts.delete(messageId);
      }
    }, delay);
    
    stateUpdateTimeouts.set(messageId, timeoutId);
  };

  // Global observer for streaming message updates
  if (!window.streamingObserver) {
    window.streamingObserver = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'childList' || mutation.type === 'characterData') {
          const target = mutation.target;
          
          // Find the closest message element
          let messageElement = target.closest('.message');
          if (!messageElement && target.classList && target.classList.contains('message')) {
            messageElement = target;
          }
          
          // If this is a streaming message (has message-temp class), debounce the update
          if (messageElement && messageElement.classList.contains('message-temp')) {
            debouncedStateUpdate(messageElement, 150); // Longer delay for streaming
          }
        }
      });
    });
    
    // Start observing the chat history for streaming updates
    const chatHistory = document.getElementById('chat-history');
    if (chatHistory) {
      window.streamingObserver.observe(chatHistory, {
        childList: true,
        subtree: true,
        characterData: true
      });
    }
  }

  // Function to apply state to ALL messages of this type
  const updateAllMessagesOfType = async () => {
    const { isHidden, isFullHeight } = getCurrentStates();
    const messageSelector = getMessageSelectorForType(type);
    const allMessagesOfType = document.querySelectorAll(messageSelector);
    
    for (const msg of allMessagesOfType) {
      // Remove all state classes (including legacy ones)
      msg.classList.remove(
        "message-collapsed", "message-compact", "message-expanded",
        "message-scroll", "message-smart-scroll", "message-upper-overflow", "message-auto" // Legacy classes
      );
      
      // Apply current state
      if (isHidden) {
        msg.classList.add("message-collapsed");
        // Add preview for hidden content
        addContentPreview(msg, type);
      } else {
        // Remove preview when showing content
        removeContentPreview(msg);
        
        // Check user preferences - ALWAYS re-read from localStorage for real-time updates
        const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
        
        if (isFixedHeightGlobal) {
          // Global fixed height mode ON - messages use smart height by default
          if (isFullHeight) {
            // User explicitly wants full expansion - same as when fixed height is OFF
            msg.classList.add("message-expanded");
            // Force truly expanded state like when fixed height is off - use !important styles
            msg.style.setProperty('max-height', 'none', 'important');
            msg.style.setProperty('overflow-y', 'visible', 'important');
            msg.style.setProperty('overflow-x', 'auto', 'important');
            // Ensure no scrollbar space is reserved
            msg.style.setProperty('scrollbar-gutter', 'auto', 'important');
            
            // Also clear constraints from any nested scrollable content
            const scrollableContent = msg.querySelector('.scrollable-content');
            if (scrollableContent) {
              scrollableContent.style.setProperty('max-height', 'none', 'important');
              scrollableContent.style.setProperty('overflow-y', 'visible', 'important');
              scrollableContent.style.setProperty('overflow-x', 'visible', 'important');
            }
            
            // Clear constraints from any nested content areas
            const msgContent = msg.querySelector('.msg-content');
            if (msgContent) {
              msgContent.style.setProperty('max-height', 'none', 'important');
              msgContent.style.setProperty('overflow-y', 'visible', 'important');
            }
          } else {
            // Default behavior - apply intelligent height management
            try {
              // Force a small delay to ensure DOM is stable, then re-measure
              await new Promise(resolve => setTimeout(resolve, 10));
              const optimalState = await determineMessageState(msg);
              switch (optimalState) {
                case 'natural':
                  // No class needed - natural height, but ensure clean state
                  msg.style.maxHeight = 'none';
                  msg.style.overflowY = 'visible';
                  break;
                case 'compact':
                  msg.classList.add("message-compact");
                  // Ensure proper compact state
                  msg.style.maxHeight = '400px';
                  msg.style.overflowY = 'auto';
                  break;
                default:
                  // Fallback to compact
                  msg.classList.add("message-compact");
                  msg.style.maxHeight = '400px';
                  msg.style.overflowY = 'auto';
              }
            } catch (error) {
              console.warn('Error applying message state:', error);
              msg.classList.add("message-compact");
              msg.style.maxHeight = '400px';
              msg.style.overflowY = 'auto';
            }
          }
        } else {
          // Global fixed height mode OFF - messages are expanded by default
          if (isFullHeight) {
            // User override to compact mode
            try {
              await new Promise(resolve => setTimeout(resolve, 10));
              const optimalState = await determineMessageState(msg);
              if (optimalState === 'compact' || isFullHeight) {
                msg.classList.add("message-compact");
                msg.style.maxHeight = '400px';
                msg.style.overflowY = 'auto';
              } else {
                // Natural state but user wanted compact, so force compact
                msg.classList.add("message-compact");
                msg.style.maxHeight = '400px';
                msg.style.overflowY = 'auto';
              }
            } catch (error) {
              console.warn('Error re-evaluating message state:', error);
              msg.classList.add("message-compact");
              msg.style.maxHeight = '400px';
              msg.style.overflowY = 'auto';
            }
          } else {
            // Default behavior - fully expanded like natural state
            msg.classList.add("message-expanded");
            msg.style.setProperty('max-height', 'none', 'important');
            msg.style.setProperty('overflow-y', 'visible', 'important');
            msg.style.setProperty('overflow-x', 'auto', 'important');
            msg.style.setProperty('scrollbar-gutter', 'auto', 'important');
            
            // Also clear constraints from any nested scrollable content
            const scrollableContent = msg.querySelector('.scrollable-content');
            if (scrollableContent) {
              scrollableContent.style.setProperty('max-height', 'none', 'important');
              scrollableContent.style.setProperty('overflow-y', 'visible', 'important');
              scrollableContent.style.setProperty('overflow-x', 'visible', 'important');
            }
            
            // Clear constraints from any nested content areas
            const msgContent = msg.querySelector('.msg-content');
            if (msgContent) {
              msgContent.style.setProperty('max-height', 'none', 'important');
              msgContent.style.setProperty('overflow-y', 'visible', 'important');
            }
          }
        }
      }
    }

    // Update ALL button visual states for this type
    updateAllButtonStatesForType(type);
  };

  // Add content preview functionality
  const addContentPreview = (msg, msgType) => {
    // Remove existing preview
    const existingPreview = msg.querySelector('.content-preview');
    if (existingPreview) existingPreview.remove();

    // Get meaningful content for preview
    let previewText = '';
    const scrollableContent = msg.querySelector('.scrollable-content');
    const msgContent = msg.querySelector('.msg-content');
    const kvpsRows = msg.querySelectorAll('.kvps-row');
    
    if (msgType === 'code_exe') {
      // For code execution, show last output line
      if (scrollableContent && msgContent) {
        const textContent = msgContent.textContent || msgContent.innerText || '';
        const lines = textContent.trim().split('\n').filter(line => line.trim());
        previewText = lines.length > 0 ? `Last: ${lines[lines.length - 1].trim()}` : 'No output';
      }
    } else if (msgType === 'agent') {
      // For blue agent messages, try to get meaningful content from kvps first
      if (kvpsRows.length > 0) {
        // Look for thoughts, text, or other meaningful content
        for (const row of kvpsRows) {
          const keyCell = row.querySelector('.kvps-key');
          const valCell = row.querySelector('.kvps-val');
          if (keyCell && valCell) {
            const key = keyCell.textContent.toLowerCase();
            const val = valCell.textContent.trim();
            
            // Prioritize thoughts, text, or tool name
            if (key.includes('thought') || key.includes('text') || key.includes('tool')) {
              if (val && val.length > 0 && !val.startsWith('{') && !val.startsWith('[')) {
                previewText = val.length > 80 ? val.substring(0, 80) + '...' : val;
                break;
              }
            }
          }
        }
        
        // If no meaningful kvp content found, use first non-JSON kvp
        if (!previewText) {
          for (const row of kvpsRows) {
            const valCell = row.querySelector('.kvps-val');
            if (valCell) {
              const val = valCell.textContent.trim();
              if (val && val.length > 0 && !val.startsWith('{') && !val.startsWith('[')) {
                previewText = val.length > 80 ? val.substring(0, 80) + '...' : val;
                break;
              }
            }
          }
        }
      }
      
      // Fallback to regular content if no kvps
      if (!previewText && scrollableContent && msgContent) {
        const textContent = msgContent.textContent || msgContent.innerText || '';
        const lines = textContent.trim().split('\n').filter(line => line.trim());
        const firstLine = lines[0] || '';
        if (firstLine && !firstLine.startsWith('{') && !firstLine.startsWith('[')) {
          previewText = firstLine.length > 80 ? firstLine.substring(0, 80) + '...' : firstLine;
        }
      }
      
      // Final fallback
      if (!previewText) {
        previewText = 'Agent message content';
      }
    } else if (msgType === 'response') {
      // For green agent response messages, show beginning of message content
      if (scrollableContent && msgContent) {
        const textContent = msgContent.textContent || msgContent.innerText || '';
        const lines = textContent.trim().split('\n').filter(line => line.trim());
        const firstLine = lines[0] || '';
        previewText = firstLine.length > 80 ? firstLine.substring(0, 80) + '...' : firstLine;
      }
      
      // Fallback
      if (!previewText) {
        previewText = 'Agent response content';
      }
    } else {
      // For other types, show first meaningful line
      if (scrollableContent && msgContent) {
        const textContent = msgContent.textContent || msgContent.innerText || '';
        const lines = textContent.trim().split('\n').filter(line => line.trim());
        const firstLine = lines[0] || '';
        previewText = firstLine.length > 80 ? firstLine.substring(0, 80) + '...' : firstLine;
      }
    }

    if (previewText) {
      const preview = document.createElement('div');
      preview.className = 'content-preview';
      preview.textContent = previewText;
      msg.appendChild(preview);
    }
  };

  const removeContentPreview = (msg) => {
    const preview = msg.querySelector('.content-preview');
    if (preview) preview.remove();
  };

  // Toggle hide/show content - ALWAYS read from localStorage
  const toggleVisibility = () => {
    const currentState = localStorage.getItem(`msgHidden_${type}`) === 'true';
    const newState = !currentState;
    localStorage.setItem(`msgHidden_${type}`, newState);
    updateAllMessagesOfType();
  };

  // Toggle height - ALWAYS read from localStorage
  const toggleHeight = () => {
    const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
    const currentState = localStorage.getItem(`msgFullHeight_${type}`) === 'true';
    
    // Logic for toggling depends on global mode:
    // - When global fixed height is ON: toggle between compact (false) and expanded (true)  
    // - When global fixed height is OFF: toggle between expanded (false) and compact (true)
    const newState = !currentState;
    localStorage.setItem(`msgFullHeight_${type}`, newState);
    
    console.log(`🔧 Toggle height for ${type}: ${currentState} -> ${newState} (global fixed: ${isFixedHeightGlobal})`);
    updateAllMessagesOfType();
  };

  // Copy message content
  const copyMessage = () => {
    let textToCopy = '';
    
    // Get text content from the message, excluding hidden copy buttons
    const msgContent = messageDiv.querySelector('.msg-content');
    const msgText = messageDiv.querySelector('.message-text');
    const scrollableContent = messageDiv.querySelector('.scrollable-content');
    
    if (msgContent) {
      // Clone the element to avoid modifying original
      const clone = msgContent.cloneNode(true);
      // Remove any copy buttons and inline copy icons
      clone.querySelectorAll('.copy-button, .inline-copy-icon').forEach(el => el.remove());
      textToCopy = clone.textContent || clone.innerText || '';
    } else if (msgText) {
      const clone = msgText.cloneNode(true);
      clone.querySelectorAll('.copy-button, .inline-copy-icon').forEach(el => el.remove());
      textToCopy = clone.textContent || clone.innerText || '';
    } else if (scrollableContent) {
      const clone = scrollableContent.cloneNode(true);
      clone.querySelectorAll('.copy-button, .inline-copy-icon').forEach(el => el.remove());
      textToCopy = clone.textContent || clone.innerText || '';
    }
    
    if (textToCopy.trim()) {
      navigator.clipboard.writeText(textToCopy.trim()).then(() => {
        // Flash the copy button to show success
        const copyBtn = messageDiv.querySelector('.message-copy-btn');
        if (copyBtn) {
          copyBtn.style.color = '#10b981';
          setTimeout(() => {
            updateButtonState(copyBtn, false, type, 'copy');
          }, 500);
        }
      }).catch(err => {
        console.error('Failed to copy text: ', err);
      });
    }
  };

  // Create modern SVG buttons
  const hideBtn = createModernButton('hide', toggleVisibility);
  const heightBtn = createModernButton('height', toggleHeight);
  const copyBtn = createModernButton('copy', copyMessage);

  hideBtn.classList.add('message-hide-btn');
  heightBtn.classList.add('message-height-btn');
  copyBtn.classList.add('message-copy-btn');

  // Store type on buttons for global state updates
  hideBtn.dataset.type = type;
  heightBtn.dataset.type = type;
  copyBtn.dataset.type = type;

  // Update ALL buttons of this type across all messages
  const updateAllButtonStatesForType = (msgType) => {
    const { isHidden, isFullHeight } = getCurrentStates();
    const allHideButtons = document.querySelectorAll(`.message-hide-btn[data-type="${msgType}"]`);
    const allHeightButtons = document.querySelectorAll(`.message-height-btn[data-type="${msgType}"]`);
    const allCopyButtons = document.querySelectorAll(`.message-copy-btn[data-type="${msgType}"]`);
    
    allHideButtons.forEach(btn => updateButtonState(btn, isHidden, msgType, 'hide'));
    allHeightButtons.forEach(btn => updateButtonState(btn, isFullHeight, msgType, 'height'));
    allCopyButtons.forEach(btn => updateButtonState(btn, false, msgType, 'copy'));
  };

  controls.append(hideBtn, heightBtn, copyBtn);

  let headerDiv = messageDiv.querySelector('.message-header');
  if (!headerDiv) {
    headerDiv = document.createElement('div');
    headerDiv.classList.add('message-header');
    const existingHeading = messageDiv.querySelector('h4');
    if (existingHeading) headerDiv.appendChild(existingHeading);
    messageDiv.prepend(headerDiv);
  }
  headerDiv.appendChild(controls);

  // Only add console summary for actual console/code execution messages
  if (type === 'code_exe' && command && command.trim().length > 0) {
    const summary = document.createElement("pre");
    summary.className = "console-summary";
    summary.textContent = command.split("\n")[0];
    messageDiv.insertBefore(summary, controls.nextSibling);
  }

  // Initialize button states immediately to prevent empty buttons
  const { isHidden, isFullHeight } = getCurrentStates();
  updateButtonState(hideBtn, isHidden, type, 'hide');
  updateButtonState(heightBtn, isFullHeight, type, 'height');
  updateButtonState(copyBtn, false, type, 'copy');

  // Initialize button states and apply to messages - delay to ensure DOM is ready
  setTimeout(() => {
    updateAllMessagesOfType();
  }, 100);
}

// Create modern button with proper SVG icons
function createModernButton(buttonType, handler) {
  const btn = document.createElement("button");
  btn.className = "message-button modern-button";
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    handler();
  });
  return btn;
}

// Update individual button state with proper icons and colors
function updateButtonState(button, isActive, type, buttonType) {
  button.classList.toggle('active', isActive);
  
  if (buttonType === 'hide') {
    if (isActive) {
      // Hidden state - show eye icon to indicate "click to show"
      button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>`;
      button.style.color = '#10b981'; // Green - click to show
      button.title = `Show all ${type} messages`;
    } else {
      // Visible state - show eye-off icon to indicate "click to hide"  
      button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>
        <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 11 8 11 8a13.16 13.16 0 0 1-1.67 2.68"/>
        <path d="M6.61 6.61A13.526 13.526 0 0 0 1 12s4 8 11 8a9.74 9.74 0 0 0 5.39-1.61"/>
        <line x1="2" y1="2" x2="22" y2="22"/>
      </svg>`;
      button.style.color = '#6b7280'; // Gray - click to hide
      button.title = `Hide all ${type} messages (show preview only)`;
    }
  } else if (buttonType === 'height') {
    const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
    
    // Logic: 
    // - When global fixed height is OFF: messages are expanded by default, show compress icon
    // - When global fixed height is ON and message type is not expanded: show expand icon  
    // - When message type is explicitly expanded (isActive=true): show compress icon
    
    if (!isFixedHeightGlobal) {
      // Global fixed height mode is OFF - messages are expanded by default
      if (isActive) {
        // User has set this type to compact mode - show expand icon
        button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15,3 21,3 21,9"/>
          <polyline points="9,21 3,21 3,15"/>
          <line x1="21" y1="3" x2="14" y2="10"/>
          <line x1="3" y1="21" x2="10" y2="14"/>
        </svg>`;
        button.style.color = '#f59e0b'; // Amber - expand available
        button.title = `Expand all ${type} messages (unlimited height)`;
      } else {
        // Default state - show compress icon (currently expanded)
        button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="4,14 10,14 10,20"/>
          <polyline points="20,10 14,10 14,4"/>
          <line x1="14" y1="10" x2="21" y2="3"/>
          <line x1="3" y1="21" x2="10" y2="14"/>
        </svg>`;
        button.style.color = '#10b981'; // Green - expanded, can compress
        button.title = `Set all ${type} messages to scroll height`;
      }
    } else {
      // Global fixed height mode is ON - messages are compact by default
      if (isActive) {
        // User has set this type to expanded mode - show compress icon
        button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="4,14 10,14 10,20"/>
          <polyline points="20,10 14,10 14,4"/>
          <line x1="14" y1="10" x2="21" y2="3"/>
          <line x1="3" y1="21" x2="10" y2="14"/>
        </svg>`;
        button.style.color = '#10b981'; // Green - expanded
        button.title = `Set all ${type} messages to scroll height`;
      } else {
        // Default state - show expand icon (currently compact)
        button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15,3 21,3 21,9"/>
          <polyline points="9,21 3,21 3,15"/>
          <line x1="21" y1="3" x2="14" y2="10"/>
          <line x1="3" y1="21" x2="10" y2="14"/>
        </svg>`;
        button.style.color = '#f59e0b'; // Amber - expand available
        button.title = `Expand all ${type} messages (unlimited height)`;
      }
    }
  } else if (buttonType === 'copy') {
    // Copy button - always same icon, no active state needed
    button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
    </svg>`;
    button.style.color = '#6b7280'; // Gray - default
    button.title = `Copy ${type} message content`;
  }
}

// Make updateButtonState globally available
window.updateButtonState = updateButtonState;

// Function to re-evaluate message states after new messages are added
window.reevaluateMessageStates = (delay = 200) => {
  console.log('🔄 Re-evaluating message states after new content');
  setTimeout(() => {
    // Get all messages that might need state updates
    const allMessages = document.querySelectorAll('.message');
    
    allMessages.forEach(async (msg) => {
      // Skip if message is already collapsed (hidden)
      if (msg.classList.contains('message-collapsed')) return;
      
      // Check if this message has controls (meaning it participates in our system)
      const controls = msg.querySelector('.message-controls');
      if (!controls) return;
      
      // Determine message type from classes
      let messageType = 'default';
      if (msg.classList.contains('message-agent')) messageType = 'agent';
      else if (msg.classList.contains('message-tool')) messageType = 'tool';
      else if (msg.classList.contains('message-code-exe')) messageType = 'code_exe';
      else if (msg.classList.contains('message-browser')) messageType = 'browser';
      else if (msg.classList.contains('message-info')) messageType = 'info';
      else if (msg.classList.contains('message-warning')) messageType = 'warning';
      else if (msg.classList.contains('message-error')) messageType = 'error';
      else if (msg.classList.contains('message-user')) messageType = 'user';
      else if (msg.classList.contains('message-agent-response')) messageType = 'response';
      
      // Get current preferences
      const isFullHeight = localStorage.getItem(`msgFullHeight_${messageType}`) === 'true';
      const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
      
      // Clear any existing inline styles that might interfere
      msg.style.maxHeight = '';
      msg.style.overflowY = '';
      msg.style.overflowX = 'auto';
      
      // Only re-evaluate if not manually overridden
      if (isFixedHeightGlobal) {
        if (!isFullHeight) {
          // Default smart behavior - re-evaluate
          msg.classList.remove('message-compact', 'message-expanded');
          
          // Re-evaluate after a short delay to ensure content is stable
          setTimeout(async () => {
            try {
              const optimalState = await determineMessageState(msg);
              if (optimalState === 'compact') {
                msg.classList.add('message-compact');
                msg.style.maxHeight = '400px';
                msg.style.overflowY = 'auto';
                console.log(`📏 Applied compact to ${messageType} message after re-evaluation`);
              } else {
                // Natural state
                msg.style.maxHeight = 'none';
                msg.style.overflowY = 'visible';
                console.log(`📏 Applied natural to ${messageType} message after re-evaluation`);
              }
            } catch (error) {
              console.warn('Error in re-evaluation:', error);
            }
          }, 50);
        }
        // If isFullHeight is true, keep the expanded override
      } else {
        // Fixed height off - only re-evaluate if user chose compact
        if (isFullHeight) {
          // User chose compact in expanded-by-default mode
          msg.classList.remove('message-compact', 'message-expanded');
          msg.classList.add('message-compact');
          msg.style.maxHeight = '400px';
          msg.style.overflowY = 'auto';
          console.log(`📏 Applied forced compact to ${messageType} message after re-evaluation`);
        }
        // If isFullHeight is false, keep the expanded default
      }
    });
  }, delay);
};

// Global function to trigger re-evaluation of all messages when fixed height setting changes
window.updateAllMessageStates = () => {
  console.log('🔄 Updating all message states for fixed height toggle');
  
  // RESET ALL INDIVIDUAL MESSAGE TYPE PREFERENCES - global preference has authority
  const messageTypes = ['agent', 'response', 'tool', 'code_exe', 'browser', 'info', 'warning', 'error', 'user', 'default'];
  
  console.log('🔄 Resetting all individual message type preferences to let global preference take authority');
  messageTypes.forEach(type => {
    // Clear individual message type preferences
    localStorage.removeItem(`msgFullHeight_${type}`);
    // Keep hide preferences since those are independent
    // localStorage.removeItem(`msgHidden_${type}`); // Don't reset hide preferences
  });
  
  // Trigger update for each message type with fresh preferences
  messageTypes.forEach(async (type) => {
    const messageSelector = getMessageSelectorForType(type);
    const messagesOfType = document.querySelectorAll(messageSelector);
    
    console.log(`📋 Found ${messagesOfType.length} messages of type ${type}`);
    
    if (messagesOfType.length > 0) {
      // Get fresh preferences after reset
      const { isHidden, isFullHeight } = {
        isHidden: localStorage.getItem(`msgHidden_${type}`) === 'true',
        isFullHeight: localStorage.getItem(`msgFullHeight_${type}`) === 'true' // This will be false now since we cleared it
      };
      
      for (const msg of messagesOfType) {
        // Remove all state classes and reset inline styles
        msg.classList.remove(
          "message-collapsed", "message-compact", "message-expanded",
          "message-scroll", "message-smart-scroll", "message-upper-overflow", "message-auto"
        );
        
        // Clear any inline styles that might interfere
        msg.style.maxHeight = '';
        msg.style.overflowY = '';
        msg.style.overflowX = 'auto'; // Keep horizontal scroll
        
        // Apply current state based on fresh localStorage read
        if (isHidden) {
          msg.classList.add("message-collapsed");
        } else {
          const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
          console.log(`🔧 Fixed height global setting: ${isFixedHeightGlobal} for ${type} (reset preferences)`);
          
          if (isFixedHeightGlobal) {
            // Global fixed height mode ON - since we reset preferences, use default smart behavior
            setTimeout(async () => {
              try {
                // Force reflow before measuring
                msg.offsetHeight;
                const optimalState = await determineMessageState(msg);
                msg.classList.remove("message-compact", "message-expanded");
                if (optimalState === 'compact') {
                  msg.classList.add("message-compact");
                  msg.style.maxHeight = '400px';
                  msg.style.overflowY = 'auto';
                  console.log(`📏 Applied compact to ${type} message (${msg.scrollHeight}px)`);
                } else {
                  // Natural state - no scrollbar needed
                  msg.style.maxHeight = 'none';
                  msg.style.overflowY = 'visible';
                  console.log(`📏 Applied natural to ${type} message (${msg.scrollHeight}px)`);
                }
              } catch (error) {
                console.warn('Error re-evaluating message state:', error);
                msg.classList.add("message-compact");
                msg.style.maxHeight = '400px';
                msg.style.overflowY = 'auto';
              }
            }, 50);
          } else {
            // Global fixed height mode OFF - since we reset preferences, use default expanded behavior
            msg.classList.add("message-expanded");
            msg.style.setProperty('max-height', 'none', 'important');
            msg.style.setProperty('overflow-y', 'visible', 'important');
            msg.style.setProperty('overflow-x', 'auto', 'important');
            msg.style.setProperty('scrollbar-gutter', 'auto', 'important');
            
            // Also clear constraints from any nested scrollable content
            const scrollableContent = msg.querySelector('.scrollable-content');
            if (scrollableContent) {
              scrollableContent.style.setProperty('max-height', 'none', 'important');
              scrollableContent.style.setProperty('overflow-y', 'visible', 'important');
              scrollableContent.style.setProperty('overflow-x', 'visible', 'important');
            }
            
            // Clear constraints from any nested content areas
            const msgContent = msg.querySelector('.msg-content');
            if (msgContent) {
              msgContent.style.setProperty('max-height', 'none', 'important');
              msgContent.style.setProperty('overflow-y', 'visible', 'important');
            }
            
            console.log(`📏 Applied expanded (global off) to ${type} message`);
          }
        }
      }
    }
  });
};

// Helper function to get CSS selector for message type
function getMessageSelectorForType(type) {
  switch (type) {
    case 'agent': return '.message-agent';
    case 'response': return '.message-agent-response';
    case 'tool': return '.message-tool';
    case 'code_exe': return '.message-code-exe';
    case 'browser': return '.message-browser';
    case 'info': return '.message-info';
    case 'warning': return '.message-warning';
    case 'error': return '.message-error';
    case 'user': return '.message-user';
    case 'default': return '.message-default';
    default: return `.message-${type}`;
  }
}

function wrapInScrollable(element, disableWrapping = false) {
  if (disableWrapping) return element;

  const wrapper = document.createElement("div");
  wrapper.classList.add("scrollable-content");

  const indTop = document.createElement("div");
  indTop.className = "scroll-indicator top";
  indTop.textContent = "\u25B2"; // ▲

  const indBottom = document.createElement("div");
  indBottom.className = "scroll-indicator bottom";
  indBottom.textContent = "\u25BC"; // ▼

  wrapper.appendChild(indTop);
  wrapper.appendChild(indBottom);
  wrapper.appendChild(element);

  function updateIndicators() {
    if (wrapper.scrollTop > 0) {
      wrapper.classList.add("show-top");
    } else {
      wrapper.classList.remove("show-top");
    }

    if (wrapper.scrollTop + wrapper.clientHeight < wrapper.scrollHeight - 1) {
      wrapper.classList.add("show-bottom");
    } else {
      wrapper.classList.remove("show-bottom");
    }
  }

  wrapper.addEventListener("scroll", () => {
    updateIndicators();
    const nearBottom =
      wrapper.scrollTop + wrapper.clientHeight >= wrapper.scrollHeight - 1;
    wrapper.dataset.userScrolled = nearBottom ? "false" : "true";
  });

  // Scroll to bottom initially
  requestAnimationFrame(() => {
    wrapper.scrollTop = wrapper.scrollHeight;
    wrapper.dataset.userScrolled = "false";
    updateIndicators();
  });

  return wrapper;
}

function scrollToEndIfNeeded(wrapper) {
  if (!wrapper || wrapper.dataset.userScrolled === "true") return;
  wrapper.scrollTop = wrapper.scrollHeight;
  wrapper.dispatchEvent(new Event("scroll"));
}

export function getHandler(type) {
  switch (type) {
    case "user":
      return drawMessageUser;
    case "agent":
      return drawMessageAgent;
    case "response":
      return drawMessageResponse;
    case "tool":
      return drawMessageTool;
    case "code_exe":
      return drawMessageCodeExe;
    case "browser":
      return drawMessageBrowser;
    case "warning":
      return drawMessageWarning;
    case "rate_limit":
      return drawMessageWarning;
    case "error":
      return drawMessageError;
    case "info":
      return drawMessageInfo;
    case "util":
      return drawMessageUtil;
    case "hint":
      return drawMessageInfo;
    default:
      return drawMessageDefault;
  }
}

// draw a message with a specific type
export function _drawMessage(
  messageContainer,
  heading,
  content,
  temp,
  followUp,
  kvps = null,
  messageClasses = [],
  contentClasses = [],
  latex = false,
  addControls = true
) {
  const messageDiv = document.createElement("div");
  messageDiv.classList.add("message", ...messageClasses);

  if (addControls) {
    // Determine message type from classes
    let messageType = 'default';
    if (messageClasses.includes('message-agent')) messageType = 'agent';
    else if (messageClasses.includes('message-tool')) messageType = 'tool';
    else if (messageClasses.includes('message-code-exe')) messageType = 'code_exe';
    else if (messageClasses.includes('message-browser')) messageType = 'browser';
    else if (messageClasses.includes('message-info')) messageType = 'info';
    else if (messageClasses.includes('message-warning')) messageType = 'warning';
    else if (messageClasses.includes('message-error')) messageType = 'error';
    else if (messageClasses.includes('message-user')) messageType = 'user';
    
    injectConsoleControls(messageDiv, '', messageType);
  }
  const skipScroll = messageClasses.includes("message-agent-response");

  if (heading) {
    const headingElement = document.createElement("h4");
    headingElement.textContent = heading;
    messageDiv.appendChild(headingElement);
  }

  drawKvps(messageDiv, kvps, latex);

  if (content && content.trim().length > 0) {
    const preElement = document.createElement("pre");
    preElement.classList.add("msg-content", ...contentClasses);
    preElement.style.whiteSpace = "pre-wrap";
    preElement.style.wordBreak = "break-word";

    const spanElement = document.createElement("span");
    spanElement.innerHTML = convertHTML(content);

    // Add click handler for small screens
    spanElement.addEventListener("click", () => {
      copyText(spanElement.textContent, spanElement);
    });

    preElement.appendChild(spanElement);
    addCopyButtonToElement(preElement);

    const wrapper = wrapInScrollable(preElement, skipScroll);
    messageDiv.appendChild(wrapper);

    // Render LaTeX math within the span
    if (window.renderMathInElement && latex) {
      renderMathInElement(spanElement, {
        delimiters: [{ left: "$", right: "$", display: true }],
        throwOnError: false,
      });
    }
  }

  messageContainer.appendChild(messageDiv);

  if (followUp) {
    messageContainer.classList.add("message-followup");
  }

  return messageDiv;
}

export function drawMessageDefault(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  const div = _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    false,
    kvps,
    ["message-ai", "message-default"],
    ["msg-json"],
    false,
    false  // addControls = false to prevent basic buttons
  );
  injectConsoleControls(div, content || "", 'default');
}

export function drawMessageAgent(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  let kvpsFlat = null;
  if (kvps) {
    kvpsFlat = { ...kvps, ...(kvps["tool_args"] || {}) };
    delete kvpsFlat["tool_args"];
  }

  const div = _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    false,
    kvpsFlat,
    ["message-ai", "message-agent"],
    ["msg-json"],
    false,
    false  // addControls = false to prevent basic buttons
  );
  injectConsoleControls(div, content || "", 'agent');
  
  // Re-evaluate this specific message after it's fully rendered
  setTimeout(() => {
    const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
    const isFullHeight = localStorage.getItem('msgFullHeight_agent') === 'true';
    
    if (isFixedHeightGlobal && !isFullHeight && !div.classList.contains('message-collapsed')) {
      determineMessageState(div).then(optimalState => {
        if (optimalState === 'compact') {
          div.classList.remove('message-expanded');
          div.classList.add('message-compact');
          console.log('📏 Applied compact to agent message after creation');
        }
      }).catch(error => {
        console.warn('Error evaluating agent message state:', error);
      });
    }
  }, 150);
}

export function drawMessageResponse(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  const messageDiv = _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    true,
    null,
    ["message-ai", "message-agent-response"],
    [],
    true,
    false  // addControls = false to prevent basic buttons
  );
  
  // Add proper controls for agent response messages
  injectConsoleControls(messageDiv, content || "", 'response');
  
  // Re-evaluate this specific message after it's fully rendered
  setTimeout(() => {
    const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
    const isFullHeight = localStorage.getItem('msgFullHeight_response') === 'true';
    
    if (isFixedHeightGlobal && !isFullHeight && !messageDiv.classList.contains('message-collapsed')) {
      determineMessageState(messageDiv).then(optimalState => {
        if (optimalState === 'compact') {
          messageDiv.classList.remove('message-expanded');
          messageDiv.classList.add('message-compact');
          console.log('📏 Applied compact to response message after creation');
        }
      }).catch(error => {
        console.warn('Error evaluating response message state:', error);
      });
    }
  }, 150);
  
  return messageDiv;
}

export function drawMessageDelegation(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  _drawMessage(
    messageContainer,
    heading,
    messageContent,
    temp,
    true,
    kvps,
    ["message-ai", "message-agent", "message-agent-delegation"],
    [],
    true
  );
}

export function drawMessageUser(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null,
  latex = false
) {
  const messageDiv = document.createElement("div");
  messageDiv.classList.add("message", "message-user");
  
  const headingElement = document.createElement("h4");
  headingElement.textContent = "User message";
  messageDiv.appendChild(headingElement);
  
  injectConsoleControls(messageDiv, content || "", 'user');

  if (content && content.trim().length > 0) {
    const textDiv = document.createElement("div");
    textDiv.classList.add("message-text");

    // Create a span for the content
    const spanElement = document.createElement("span");
    spanElement.innerHTML = convertHTML(content);
    textDiv.appendChild(spanElement);

    // Add click handler
    textDiv.addEventListener("click", () => {
      copyText(content, textDiv);
    });

    addCopyButtonToElement(textDiv);
    const wrapper = wrapInScrollable(textDiv, false);
    messageDiv.appendChild(wrapper);
  }

  // Handle attachments
  if (kvps && kvps.attachments && kvps.attachments.length > 0) {
    const attachmentsContainer = document.createElement("div");
    attachmentsContainer.classList.add("attachments-container");

    kvps.attachments.forEach((attachment) => {
      const attachmentDiv = document.createElement("div");
      attachmentDiv.classList.add("attachment-item");

      if (typeof attachment === "string") {
        // attachment is filename
        const filename = attachment;
        const extension = filename.split(".").pop().toUpperCase();

        attachmentDiv.classList.add("file-type");
        attachmentDiv.innerHTML = `
                    <div class="file-preview">
                        <span class="filename">${filename}</span>
                        <span class="extension">${extension}</span>
                    </div>
                `;
      } else if (attachment.type === "image") {
        // Existing logic for images
        const imgWrapper = document.createElement("div");
        imgWrapper.classList.add("image-wrapper");

        const img = document.createElement("img");
        img.src = attachment.url;
        img.alt = attachment.name;
        img.classList.add("attachment-preview");

        const fileInfo = document.createElement("div");
        fileInfo.classList.add("file-info");
        fileInfo.innerHTML = `
                    <span class="filename">${attachment.name}</span>
                    <span class="extension">${attachment.extension.toUpperCase()}</span>
                `;

        imgWrapper.appendChild(img);
        attachmentDiv.appendChild(imgWrapper);
        attachmentDiv.appendChild(fileInfo);
      } else {
        // Existing logic for non-image files
        attachmentDiv.classList.add("file-type");
        attachmentDiv.innerHTML = `
                    <div class="file-preview">
                        <span class="filename">${attachment.name}</span>
                        <span class="extension">${attachment.extension.toUpperCase()}</span>
                    </div>
                `;
      }

      attachmentsContainer.appendChild(attachmentDiv);
    });

    messageDiv.appendChild(attachmentsContainer);
  }

  messageContainer.appendChild(messageDiv);
}

export function drawMessageTool(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  const div = _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    true,
    kvps,
    ["message-ai", "message-tool"],
    ["msg-output"],
    false,
    false  // addControls = false to prevent basic buttons
  );
  injectConsoleControls(div, content || "", 'tool');
  
  // Re-evaluate this specific message after it's fully rendered
  setTimeout(() => {
    const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
    const isFullHeight = localStorage.getItem('msgFullHeight_tool') === 'true';
    
    if (isFixedHeightGlobal && !isFullHeight && !div.classList.contains('message-collapsed')) {
      determineMessageState(div).then(optimalState => {
        if (optimalState === 'compact') {
          div.classList.remove('message-expanded');
          div.classList.add('message-compact');
          console.log('📏 Applied compact to tool message after creation');
        }
      }).catch(error => {
        console.warn('Error evaluating tool message state:', error);
      });
    }
  }, 150);
}

export function drawMessageCodeExe(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  const div = _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    true,
    null,
    ["message-ai", "message-code-exe"],
    [],
    false,
    false
  );
  injectConsoleControls(div, content || "", 'code_exe');
}

export function drawMessageBrowser(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  const div = _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    true,
    kvps,
    ["message-ai", "message-browser"],
    ["msg-json"],
    false,
    false  // addControls = false to prevent basic buttons
  );
  injectConsoleControls(div, content || "", 'browser');
}

export function drawMessageAgentPlain(
  classes,
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  const div = _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    false,
    kvps,
    [...classes],
    [],
    false
  );
  messageContainer.classList.add("center-container");
  return div;
}

export function drawMessageInfo(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  const div = drawMessageAgentPlain(
    ["message-info"],
    messageContainer,
    id,
    type,
    heading,
    content,
    temp,
    kvps
  );
  injectConsoleControls(div, content || "", 'info');
  return div;
}

export function drawMessageUtil(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    false,
    kvps,
    ["message-util"],
    ["msg-json"],
    false
  );
  messageContainer.classList.add("center-container");
}

export function drawMessageWarning(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  const div = drawMessageAgentPlain(
    ["message-warning"],
    messageContainer,
    id,
    type,
    heading,
    content,
    temp,
    kvps
  );
  injectConsoleControls(div, content || "", 'warning');
  return div;
}

export function drawMessageError(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  const div = drawMessageAgentPlain(
    ["message-error"],
    messageContainer,
    id,
    type,
    heading,
    content,
    temp,
    kvps
  );
  injectConsoleControls(div, content || "", 'error');
  return div;
}

function drawKvps(container, kvps, latex) {
  if (kvps) {
    const table = document.createElement("table");
    table.classList.add("msg-kvps");
    for (let [key, value] of Object.entries(kvps)) {
      const row = table.insertRow();
      row.classList.add("kvps-row");
      if (key === "thoughts" || key === "reflection")
        row.classList.add("msg-thoughts");

      const th = row.insertCell();
      th.textContent = convertToTitleCase(key);
      th.classList.add("kvps-key");

      const td = row.insertCell();

      if (Array.isArray(value)) {
        for (const item of value) {
          addValue(item);
        }
      } else {
        addValue(value);
      }

      function addValue(value) {
        if (typeof value === "object") value = JSON.stringify(value, null, 2);

        if (typeof value === "string" && value.startsWith("img://")) {
          const imgElement = document.createElement("img");
          imgElement.classList.add("kvps-img");
          imgElement.src = value.replace("img://", "/image_get?path=");
          imgElement.alt = "Image Attachment";
          td.appendChild(imgElement);

          // Add click handler and cursor change
          imgElement.style.cursor = "pointer";
          imgElement.addEventListener("click", () => {
            openImageModal(imgElement.src, 1000);
          });

          td.appendChild(imgElement);
        } else {
          const pre = document.createElement("pre");
          pre.classList.add("kvps-val");

          if (row.classList.contains("msg-thoughts")) {
            pre.style.whiteSpace = "pre-wrap";
            pre.style.wordBreak = "break-word";
          } else {
            pre.style.whiteSpace = "pre";
            pre.style.overflowX = "auto";
          }

          const span = document.createElement("span");
          span.innerHTML = convertHTML(value);
          pre.appendChild(span);
          const wrap = wrapInScrollable(pre, container.classList.contains("message-agent-response"));
          td.appendChild(wrap);
          addCopyButtonToElement(td);

          // Add click handler
          span.addEventListener("click", () => {
            copyText(span.textContent, span);
          });

          if (window.renderMathInElement && latex) {
            renderMathInElement(span, {
              delimiters: [{ left: "$", right: "$", display: true }],
              throwOnError: false,
            });
          }
        }
      }
    }
    container.appendChild(table);
  }
}

function convertToTitleCase(str) {
  return str
    .replace(/_/g, " ") // Replace underscores with spaces
    .toLowerCase() // Convert the entire string to lowercase
    .replace(/\b\w/g, function (match) {
      return match.toUpperCase(); // Capitalize the first letter of each word
    });
}

function convertImageTags(content) {
  // Regular expression to match <image> tags and extract base64 content
  const imageTagRegex = /<image>(.*?)<\/image>/g;

  // Replace <image> tags with <img> tags with base64 source
  const updatedContent = content.replace(
    imageTagRegex,
    (match, base64Content) => {
      return `<img src="data:image/jpeg;base64,${base64Content}" alt="Image Attachment" style="max-width: 250px !important;"/>`;
    }
  );

  return updatedContent;
}

async function copyText(text, element) {
  try {
    await navigator.clipboard.writeText(text);
    element.classList.add("copied");
    setTimeout(() => {
      element.classList.remove("copied");
    }, 2000);
  } catch (err) {
    console.error("Failed to copy text:", err);
  }
}

function convertHTML(str) {
  if (typeof str !== "string") str = JSON.stringify(str, null, 2);

  let result = escapeHTML(str);
  result = convertPathsToLinks(result);
  result = convertImageTags(result);
  return result;
}

function escapeHTML(str) {
  const escapeChars = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  };
  return str.replace(/[&<>'"]/g, (char) => escapeChars[char]);
}

function convertPathsToLinks(str) {
  function generateLinks(match, ...args) {
    const parts = match.split("/");

    if (!parts[0]) parts.shift();
    let conc = "";
    let html = "";
    for (let part of parts) {
      conc += "/" + part;
      html += `/<a href="#" class="path-link" onclick="openFileLink('${conc}');">${part}</a>`;
    }
    return html;
  }

  const prefix = `(?:^|[ \`'"\\n]|&#39;|&quot;)`; // Use a non-capturing group for OR logic
  const folder = `[a-zA-Z0-9_\\/.\\-]`; // Characters allowed in folder chain
  const file = `[a-zA-Z0-9_\\-\\/]`; // Characters allowed in file names
  const suffix = `(?<!\\.)`;

  const regex = new RegExp(`(?<=${prefix})\\/${folder}*${file}${suffix}`, "g");

  return str.replace(regex, generateLinks);
}

// Removed broken inline copy system - using original copy buttons instead
