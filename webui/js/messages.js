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

// Function to determine optimal message height state - simplified with smooth transitions
function determineMessageState(msg, retryCount = 0) {
  // Avoid infinite retry loops
  const MAX_RETRIES = 10;
  // If this is the last agent/response message and streaming, always expanded
  const isAgentOrResponse = msg.classList.contains('message-agent') || msg.classList.contains('message-agent-response');
  const allAgentMsgs = Array.from(document.querySelectorAll('.message-agent, .message-agent-response'));
  const isLastAgentMsg = isAgentOrResponse && allAgentMsgs.length > 0 && allAgentMsgs[allAgentMsgs.length - 1] === msg;
  if (msg.classList.contains('message-temp') && isLastAgentMsg) {
    const stack = new Error().stack.split('\n').slice(1, 4).join(' | ');
    console.log(`[BORDER-DEBUG] determineMessageState: last streaming agent/response, forcing expanded | classList=${msg.className} | stack=${stack}`);
    return Promise.resolve('expanded');
  }
  if (msg.classList.contains('message-temp')) {
    // Streaming messages are always expanded
    const stack = new Error().stack.split('\n').slice(1, 4).join(' | ');
    console.log(`[BORDER-DEBUG] determineMessageState: message-temp, forcing expanded | classList=${msg.className} | stack=${stack}`);
    return Promise.resolve('expanded');
  }
  if (msg.classList.contains('state-lock')) {
    // Locked messages are always compact
    const stack = new Error().stack.split('\n').slice(1, 4).join(' | ');
    console.log(`[BORDER-DEBUG] determineMessageState: state-lock, forcing compact | classList=${msg.className} | stack=${stack}`);
    return Promise.resolve('compact');
  }
  // Only proceed if the element is attached and visible
  if (!msg.isConnected || msg.offsetParent === null) {
    console.log(`[DEBUG] determineMessageState: element not in DOM or not visible, skipping | classList=${msg.className}`);
    return Promise.resolve('expanded');
  }
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      try {
        // Patch: Add a temporary class that mimics expanded state border/padding for measurement
        const beforeClassList = Array.from(msg.classList).join(' ');
        const beforeMaxHeight = msg.style.maxHeight;
        const beforeOverflow = msg.style.overflow;
        const beforeOverflowY = msg.style.overflowY;
        const beforeBorderLeft = msg.style.borderLeft;
        // Save current state
        const wasCompact = msg.classList.contains('message-compact');
        const wasExpanded = msg.classList.contains('message-expanded');
        // DO NOT remove compact/expanded, just add measuring-message
        msg.classList.add('measuring-message');
        msg.style.maxHeight = 'none';
        msg.style.overflow = 'visible';
        msg.style.overflowY = 'visible';
        msg.offsetHeight;
        const totalHeight = msg.scrollHeight || 0;
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
        // Restore previous state
        msg.classList.remove('measuring-message');
        msg.style.maxHeight = beforeMaxHeight;
        msg.style.overflow = beforeOverflow;
        msg.style.overflowY = beforeOverflowY;
        const afterClassList = Array.from(msg.classList).join(' ');
        const afterMaxHeight = msg.style.maxHeight;
        const afterOverflow = msg.style.overflow;
        const afterOverflowY = msg.style.overflowY;
        const afterBorderLeft = msg.style.borderLeft;
        if (finalHeight === 0) {
          if (retryCount < MAX_RETRIES) {
            console.log(`[DEBUG] determineMessageState: height=0, retrying next frame (${retryCount + 1}) | classList=${afterClassList}`);
            requestAnimationFrame(() => {
              determineMessageState(msg, retryCount + 1).then(resolve);
            });
          } else {
            console.warn(`[WARN] determineMessageState: height=0 after ${MAX_RETRIES} retries, defaulting to expanded | classList=${afterClassList}`);
            resolve('expanded');
          }
          return;
        }
        const threshold = 400;
        const willBeCompact = finalHeight > threshold;
        console.log(`[DEBUG] determineMessageState: before classList=${beforeClassList}, after classList=${afterClassList}, before maxHeight=${beforeMaxHeight}, after maxHeight=${afterMaxHeight}, before overflow=${beforeOverflow}, after overflow=${afterOverflow}, before overflowY=${beforeOverflowY}, after overflowY=${afterOverflowY}, before borderLeft=${beforeBorderLeft}, after borderLeft=${afterBorderLeft}, finalHeight=${finalHeight}, willBeCompact=${willBeCompact}`);
        console.log(`[BORDER-DEBUG] determineMessageState: borderLeft=${msg.style.borderLeft} | classList=${msg.className}`);
        if (willBeCompact) {
          resolve('compact');
        } else {
          resolve('expanded');
        }
      } catch (error) {
        console.warn('Error determining message state:', error);
        resolve('expanded');
      }
    });
  });
}

// Global map to debounce scroll-to-bottom per message
const pendingScrollAnimationFrame = new Map();

function ensureScrollTracking(messageElement) {
  if (!messageElement || messageElement.dataset.scrollTrackingInitialized === "true") {
    return; // Already initialized
  }

  // Do not set up scroll tracking for streaming messages
  if (messageElement.classList.contains('message-temp')) {
    return;
  }

  // Initialize user scroll tracking
  messageElement.dataset.userScrolled = "false";
  messageElement.dataset.scrollTrackingInitialized = "true";

  // Add scroll listener for unified scrolling
  const scrollHandler = () => {
    const hasScrolling = messageElement.classList.contains('message-compact') || 
                        messageElement.scrollHeight > messageElement.clientHeight;
    if (hasScrolling) {
      const nearBottom = messageElement.scrollTop + messageElement.clientHeight >= messageElement.scrollHeight - 10;
      messageElement.dataset.userScrolled = nearBottom ? "false" : "true";
      const borderLeft = messageElement.style.borderLeft;
      const overflowY = messageElement.style.overflowY;
      const classList = Array.from(messageElement.classList).join(' ');
      console.log(`[SCROLL] ensureScrollTracking: ${messageElement.id || messageElement.className} scroll event | nearBottom=${nearBottom} | userScrolled=${messageElement.dataset.userScrolled} | scrollTop=${messageElement.scrollTop} | height=${messageElement.scrollHeight} | overflowY=${overflowY} | borderLeft=${borderLeft} | classList=${classList}`);
    }
  };
  messageElement.removeEventListener("scroll", scrollHandler);
  messageElement.addEventListener("scroll", scrollHandler);

  const borderLeft = messageElement.style.borderLeft;
  const overflowY = messageElement.style.overflowY;
  const classList = Array.from(messageElement.classList).join(' ');
  console.log(`[SCROLL] ensureScrollTracking: initialized for ${messageElement.id || messageElement.className} | scrollTop=${messageElement.scrollTop} | height=${messageElement.scrollHeight} | overflowY=${overflowY} | borderLeft=${borderLeft} | classList=${classList}`);

  // Only auto-scroll to bottom if compact and not user scrolled, and not streaming
  if (messageElement.classList.contains('message-compact') && !messageElement.classList.contains('message-temp')) {
    if (pendingScrollAnimationFrame.has(messageElement)) {
      cancelAnimationFrame(pendingScrollAnimationFrame.get(messageElement));
    }
    const rafId = requestAnimationFrame(() => {
      if (messageElement.scrollHeight === 0) {
        // Try again next frame if not rendered yet
        ensureScrollTracking(messageElement);
        return;
      }
      if (messageElement.dataset.userScrolled !== 'true') {
        messageElement.scrollTop = messageElement.scrollHeight;
        messageElement.dataset.userScrolled = "false";
      }
      const borderLeft2 = messageElement.style.borderLeft;
      const overflowY2 = messageElement.style.overflowY;
      const classList2 = Array.from(messageElement.classList).join(' ');
      pendingScrollAnimationFrame.delete(messageElement);
      console.log(`[SCROLL] ensureScrollTracking: auto-scroll to bottom for ${messageElement.id || messageElement.className} | scrollTop=${messageElement.scrollTop} | height=${messageElement.scrollHeight} | overflowY=${overflowY2} | borderLeft=${borderLeft2} | classList=${classList2}`);
    });
    pendingScrollAnimationFrame.set(messageElement, rafId);
  }
}

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

  // Debounced state update to prevent flashing during streaming
  const stateUpdateTimeouts = new Map();
  
  // Patch: Only allow state/scroll updates for streaming message during streaming
  // Accept a force parameter to override the guard for user actions
  function debouncedStateUpdate(messageElement, delay = 100, force = false) {
    // If not the streaming message, skip during streaming (unless forced by user action)
    const isStreaming = document.querySelector('.message-temp');
    // Allow code_exe messages to update state even if streaming
    if (!force && isStreaming && !messageElement.classList.contains('message-temp')) {
      if (!messageElement.classList.contains('message-code-exe')) {
        console.log(`[GUARD] debouncedStateUpdate: Skipping ${messageElement.id || messageElement.className} because another message is streaming.`);
        return;
      }
    }
    if (!force && (messageElement.classList.contains('message-temp') || messageElement.classList.contains('state-lock'))) {
      console.log(`[GUARD] debouncedStateUpdate: Skipping ${messageElement.id || messageElement.className} because it is streaming or locked.`);
      return;
    }
    const messageId = messageElement.id || messageElement.className || Math.random().toString();
    if (stateUpdateTimeouts.has(messageId)) {
      clearTimeout(stateUpdateTimeouts.get(messageId));
    }
    lockMessageState(messageElement);
    const prevUserScrolled = messageElement.dataset.userScrolled;
    const timeoutId = setTimeout(async () => {
      try {
        let messageType = 'default';
        if (messageElement.classList.contains('message-code-exe')) messageType = 'code_exe';
        else if (messageElement.classList.contains('message-tool')) messageType = 'tool';
        else if (messageElement.classList.contains('message-agent-response')) messageType = 'response';
        else if (messageElement.classList.contains('message-agent')) messageType = 'agent';
        else if (messageElement.classList.contains('message-browser')) messageType = 'browser';
        else if (messageElement.classList.contains('message-error')) messageType = 'error';
        else if (messageElement.classList.contains('message-warning')) messageType = 'warning';
        else if (messageElement.classList.contains('message-info')) messageType = 'info';
        const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
        const isFullHeight = localStorage.getItem(`msgFullHeight_${messageType}`) === 'true';
        if (!isFixedHeightGlobal || isFullHeight) {
          setMessageState(messageElement, 'expanded');
          messageElement.style.setProperty('height', 'auto', 'important');
          messageElement.style.setProperty('max-height', 'none', 'important');
          messageElement.style.setProperty('overflow-y', 'visible', 'important');
          messageElement.style.setProperty('overflow-x', 'auto', 'important');
          messageElement.style.setProperty('scrollbar-gutter', 'auto', 'important');
          const scrollableContent = messageElement.querySelector('.scrollable-content');
          if (scrollableContent) {
            scrollableContent.style.setProperty('max-height', 'none', 'important');
            scrollableContent.style.setProperty('overflow-y', 'visible', 'important');
            scrollableContent.style.setProperty('overflow-x', 'visible', 'important');
          }
          const msgContent = messageElement.querySelector('.msg-content');
          if (msgContent) {
            msgContent.style.setProperty('max-height', 'none', 'important');
            msgContent.style.setProperty('overflow-y', 'visible', 'important');
          }
          console.log(`[STATE] debouncedStateUpdate: ${messageId} set to expanded | scrollTop=${messageElement.scrollTop} | height=${messageElement.scrollHeight}`);
          unlockMessageState(messageElement);
          stateUpdateTimeouts.delete(messageId);
          return;
        }
        const newState = await determineMessageState(messageElement);
        setMessageState(messageElement, newState === 'compact' ? 'compact' : 'expanded');
        ensureScrollTracking(messageElement);
        if (prevUserScrolled !== undefined) {
          messageElement.dataset.userScrolled = prevUserScrolled;
        }
        console.log(`[STATE] debouncedStateUpdate: ${messageId} set to ${newState} | scrollTop=${messageElement.scrollTop} | height=${messageElement.scrollHeight}`);
        unlockMessageState(messageElement);
        stateUpdateTimeouts.delete(messageId);
      } catch (error) {
        unlockMessageState(messageElement);
        stateUpdateTimeouts.delete(messageId);
      }
    }, delay);
    stateUpdateTimeouts.set(messageId, timeoutId);
  }

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
          // But skip state changes for streaming messages
          if (messageElement && messageElement.classList.contains('message-temp')) {
            console.log('🔄 Streaming mutation detected for message');
            
            // Ensure scroll tracking is set up for streaming messages
            ensureScrollTracking(messageElement);
            
            // Do NOT call debouncedStateUpdate for streaming messages
            return;
          }
          
          // For non-streaming messages, allow debounced state update
          if (messageElement) {
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
  // Accept a force parameter to override the guard for user actions
  const updateAllMessagesOfType = async (force = false) => {
    const { isHidden, isFullHeight } = getCurrentStates();
    const messageSelector = getMessageSelectorForType(type);
    const allMessagesOfType = document.querySelectorAll(messageSelector);
    const isStreaming = document.querySelector('.message-temp');
    for (const msg of allMessagesOfType) {
      // --- Fix: Always allow hide/unhide to override streaming guard ---
      // Only skip if locked/streaming AND not a hide/unhide action
      if (!force && isStreaming && !msg.classList.contains('message-temp')) {
        if (!msg.classList.contains('message-code-exe')) {
          console.log(`[GUARD] updateAllMessagesOfType: Skipping ${msg.id || msg.className} because another message is streaming.`);
          continue;
        }
      }
      if (!force && (msg.classList.contains('message-temp') || msg.classList.contains('state-lock'))) {
        console.log(`[GUARD] updateAllMessagesOfType: Skipping ${msg.id || msg.className} because it is streaming or locked.`);
        continue;
      }
      const prevState = msg.classList.contains('message-compact') ? 'compact' : (msg.classList.contains('message-expanded') ? 'expanded' : 'none');
      if (isHidden) {
        msg.classList.add('message-collapsed');
        addContentPreview(msg, type);
        console.log(`[STATE] updateAllMessagesOfType: ${msg.id || msg.className} set to collapsed | prevState=${prevState}`);
      } else {
        // --- Fix: Always remove collapsed class when unhidden ---
        msg.classList.remove('message-collapsed');
      }
      removeContentPreview(msg);
      const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
      if (isFixedHeightGlobal) {
        if (isFullHeight) {
          setMessageState(msg, 'expanded');
          msg.style.setProperty('height', 'auto', 'important');
          msg.style.setProperty('max-height', 'none', 'important');
          msg.style.setProperty('overflow-y', 'visible', 'important');
          msg.style.setProperty('overflow-x', 'auto', 'important');
          msg.style.setProperty('scrollbar-gutter', 'auto', 'important');
          const scrollableContent = msg.querySelector('.scrollable-content');
          if (scrollableContent) {
            scrollableContent.style.setProperty('max-height', 'none', 'important');
            scrollableContent.style.setProperty('overflow-y', 'visible', 'important');
            scrollableContent.style.setProperty('overflow-x', 'visible', 'important');
          }
          const msgContent = msg.querySelector('.msg-content');
          if (msgContent) {
            msgContent.style.setProperty('max-height', 'none', 'important');
            msgContent.style.setProperty('overflow-y', 'visible', 'important');
          }
          console.log(`[STATE] updateAllMessagesOfType: ${msg.id || msg.className} set to expanded | prevState=${prevState} | scrollTop=${msg.scrollTop} | height=${msg.scrollHeight}`);
          // Only call determineMessageState when expanding, to allow auto-compact if needed
          try {
            await new Promise(resolve => setTimeout(resolve, 10));
            const optimalState = await determineMessageState(msg);
            setMessageState(msg, optimalState === 'compact' ? 'compact' : 'expanded');
            ensureScrollTracking(msg);
            console.log(`[STATE] updateAllMessagesOfType: ${msg.id || msg.className} set to ${optimalState} | prevState=${prevState} | scrollTop=${msg.scrollTop} | height=${msg.scrollHeight}`);
          } catch (error) {
            setMessageState(msg, 'compact');
            ensureScrollTracking(msg);
            console.log(`[STATE] updateAllMessagesOfType: ${msg.id || msg.className} fallback to compact | prevState=${prevState} | scrollTop=${msg.scrollTop} | height=${msg.scrollHeight}`);
          }
        } else {
          // User wants compact: force compact, do not call determineMessageState
          setMessageState(msg, 'compact');
          msg.style.setProperty('max-height', '400px', 'important');
          msg.style.setProperty('overflow-y', 'auto', 'important');
          msg.style.setProperty('overflow-x', 'auto', 'important');
          msg.style.setProperty('scrollbar-gutter', 'stable', 'important');
          ensureScrollTracking(msg);
          console.log(`[STATE] updateAllMessagesOfType: ${msg.id || msg.className} set to compact (user-forced) | prevState=${prevState} | scrollTop=${msg.scrollTop} | height=${msg.scrollHeight}`);
        }
      } else {
        setMessageState(msg, 'expanded');
        msg.style.setProperty('height', 'auto', 'important');
        msg.style.setProperty('max-height', 'none', 'important');
        msg.style.setProperty('overflow-y', 'visible', 'important');
        msg.style.setProperty('overflow-x', 'auto', 'important');
        msg.style.setProperty('scrollbar-gutter', 'auto', 'important');
        const scrollableContent = msg.querySelector('.scrollable-content');
        if (scrollableContent) {
          scrollableContent.style.setProperty('max-height', 'none', 'important');
          scrollableContent.style.setProperty('overflow-y', 'visible', 'important');
          scrollableContent.style.setProperty('overflow-x', 'visible', 'important');
        }
        const msgContent = msg.querySelector('.msg-content');
        if (msgContent) {
          msgContent.style.setProperty('max-height', 'none', 'important');
          msgContent.style.setProperty('overflow-y', 'visible', 'important');
        }
        console.log(`[STATE] updateAllMessagesOfType: ${msg.id || msg.className} set to expanded | prevState=${prevState} | scrollTop=${msg.scrollTop} | height=${msg.scrollHeight}`);
      }
    }
    updateAllButtonStatesForType(type);
    // After streaming ends, unlock all and reevaluate
    if (!isStreaming) {
      unlockAllMessageStates();
      allMessagesOfType.forEach(msg => {
        if (!msg.classList.contains('message-temp')) {
          reevaluateMessageStateAfterStreaming(msg);
        }
      });
    }
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
    updateAllMessagesOfType(true); // force update
  };

  // Toggle height - ALWAYS read from localStorage
  const toggleHeight = () => {
    const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
    const currentState = localStorage.getItem(`msgFullHeight_${type}`) === 'true';
    const newState = !currentState;
    localStorage.setItem(`msgFullHeight_${type}`, newState);
    console.log(`🔧 Toggle height for ${type}: ${currentState} -> ${newState} (global fixed: ${isFixedHeightGlobal})`);
    updateAllMessagesOfType(true); // force update
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
      // Collapsed/hidden state - show plus icon (maximize/expand)
      button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`;
      button.style.color = '#10b981'; // Green - click to show
      button.title = `Show all ${type} messages (expand)`;
    } else {
      // Visible state - show minus icon (minimize/collapse)
      button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/></svg>`;
      button.style.color = '#6b7280'; // Gray - click to hide
      button.title = `Hide all ${type} messages (collapse)`;
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
  setTimeout(() => {
    const allMessages = document.querySelectorAll('.message');
    allMessages.forEach(async (msg) => {
      if (msg.classList.contains('message-collapsed') || msg.classList.contains('message-temp') || msg.classList.contains('state-lock')) return;
      const controls = msg.querySelector('.message-controls');
      if (!controls) return;
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
      const isFullHeight = localStorage.getItem(`msgFullHeight_${messageType}`) === 'true';
      const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
      msg.style.maxHeight = '';
      msg.style.overflowY = '';
      msg.style.overflowX = 'auto';
      if (isFixedHeightGlobal) {
        if (!isFullHeight) {
          setTimeout(async () => {
            try {
              const optimalState = await determineMessageState(msg);
              setMessageState(msg, optimalState === 'compact' ? 'compact' : 'expanded');
              ensureScrollTracking(msg);
            } catch (error) {}
          }, 50);
        }
      } else {
        if (isFullHeight) {
          setMessageState(msg, 'compact');
          msg.style.maxHeight = '400px';
          msg.style.overflowY = 'auto';
        }
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
        // Skip streaming or locked messages
        if (msg.classList.contains('message-temp') || msg.classList.contains('state-lock')) continue;
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

  // Set up scroll tracking for the unified system
  // We need to find the parent message element and set up tracking there
  requestAnimationFrame(() => {
    const messageElement = wrapper.closest('.message');
    if (messageElement) {
      // Use the centralized scroll tracking function
      ensureScrollTracking(messageElement);
    }
  });

  // Legacy wrapper scroll handling (for backwards compatibility)
  wrapper.addEventListener("scroll", () => {
    updateIndicators();
    const nearBottom =
      wrapper.scrollTop + wrapper.clientHeight >= wrapper.scrollHeight - 1;
    wrapper.dataset.userScrolled = nearBottom ? "false" : "true";
  });

  // Initial scroll to bottom for legacy wrappers that still have scrolling
  requestAnimationFrame(() => {
    const computedStyle = window.getComputedStyle(wrapper);
    if (computedStyle.overflowY !== 'visible') {
      wrapper.scrollTop = wrapper.scrollHeight;
      wrapper.dataset.userScrolled = "false";
    }
    updateIndicators();
  });

  return wrapper;
}

function scrollToEndIfNeeded(wrapper) {
  if (!wrapper) return;
  const computedStyle = window.getComputedStyle(wrapper);
  if (computedStyle.overflowY === 'visible') {
    const messageElement = wrapper.closest('.message');
    if (messageElement && messageElement.classList.contains('message-compact')) {
      if (pendingScrollAnimationFrame.has(messageElement)) {
        cancelAnimationFrame(pendingScrollAnimationFrame.get(messageElement));
      }
      const rafId = requestAnimationFrame(() => {
        if (messageElement.scrollHeight === 0) {
          ensureScrollTracking(messageElement);
          return;
        }
        if (messageElement.dataset.userScrolled !== 'true') {
          messageElement.scrollTop = messageElement.scrollHeight;
          messageElement.dataset.userScrolled = "false";
        }
        pendingScrollAnimationFrame.delete(messageElement);
      });
      pendingScrollAnimationFrame.set(messageElement, rafId);
    }
    return;
  }
  if (wrapper.dataset.userScrolled === "true") return;
  if (pendingScrollAnimationFrame.has(wrapper)) {
    cancelAnimationFrame(pendingScrollAnimationFrame.get(wrapper));
  }
  const rafId = requestAnimationFrame(() => {
    if (wrapper.scrollHeight === 0) {
      scrollToEndIfNeeded(wrapper);
      return;
    }
    wrapper.scrollTop = wrapper.scrollHeight;
    wrapper.dispatchEvent(new Event("scroll"));
    pendingScrollAnimationFrame.delete(wrapper);
  });
  pendingScrollAnimationFrame.set(wrapper, rafId);
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
  if (temp) {
    messageDiv.classList.add("message-temp");
  }

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
  finalizeMessageState(div, 'default');
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
  // Immediately set state after render (no scroll changes)
  finalizeMessageState(div, 'agent');
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
  
  // PATCH: If state-lock is present, do not schedule delayed state update
  if (!messageDiv.classList.contains('message-temp') && !messageDiv.classList.contains('state-lock')) {
    const timeoutId = setTimeout(() => {
      if (messageDiv.classList.contains('message-temp') || messageDiv.classList.contains('state-lock')) {
        if (messageDiv.classList.contains('state-lock')) {
          console.log('[LOCK-DEBUG] drawMessageResponse: skipping delayed state update due to state-lock', messageDiv);
        }
        return;
      }
      const isFixedHeightGlobal = localStorage.getItem('fixedHeight') === 'true';
      const isFullHeight = localStorage.getItem('msgFullHeight_response') === 'true';
      if (isFixedHeightGlobal && !isFullHeight && !messageDiv.classList.contains('message-collapsed')) {
        determineMessageState(messageDiv).then(optimalState => {
          if (optimalState === 'compact') {
            messageDiv.classList.remove('message-expanded');
            messageDiv.classList.add('message-compact');
            ensureScrollTracking(messageDiv);
            console.log('📏 Applied compact to response message after creation');
          } else {
            messageDiv.classList.remove('message-compact');
            messageDiv.classList.add('message-expanded');
            ensureScrollTracking(messageDiv);
            console.log('📏 Applied expanded to response message after creation');
          }
        }).catch(error => {
          console.warn('Error evaluating response message state:', error);
        });
      }
      pendingStateTimeouts.delete(messageDiv);
    }, 150);
    pendingStateTimeouts.set(messageDiv, timeoutId);
  } else if (messageDiv.classList.contains('state-lock')) {
    console.log('[LOCK-DEBUG] drawMessageResponse: skipping initial delayed state update due to state-lock', messageDiv);
  }
  finalizeMessageState(messageDiv, 'response');
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
  finalizeMessageState(messageDiv, 'user');
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
  finalizeMessageState(div, 'tool');
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
  finalizeMessageState(div, 'code_exe');
  return div;
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
  finalizeMessageState(div, 'browser');
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

export function convertHTML(str) {
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

export function updateMessageContent(container, content) {
  const span = container.querySelector('.msg-content span') || container.querySelector('.scrollable-content span') || container.querySelector('.message span');
  if (span) {
    span.textContent = content;
    // Log border after content update
    const msg = container.querySelector('.message');
    if (msg) {
      console.log(`[BORDER-DEBUG] updateMessageContent: after content update | borderLeft=${msg.style.borderLeft} | classList=${msg.className}`);
      // If this is a code_exe message, re-run finalizeMessageState to allow compacting while streaming
      if (msg.classList.contains('message-code-exe')) {
        if (window.finalizeMessageState) {
          window.finalizeMessageState(msg, 'code_exe');
        }
        // --- Ensure scrollable-content always auto-scrolls to bottom in compact mode ---
        if (msg.classList.contains('message-compact')) {
          const scrollableContent = msg.querySelector('.scrollable-content');
          requestAnimationFrame(() => {
            if (scrollableContent) {
              scrollableContent.scrollTop = scrollableContent.scrollHeight;
              scrollableContent.dataset.userScrolled = "false";
            }
            // Also set on the message div itself as a fallback
            msg.scrollTop = msg.scrollHeight;
            msg.dataset.userScrolled = "false";
            console.log('🔽 (Forced) Auto-scrolled code_exe scrollable-content and message div to bottom after content update');
          });
        }
      }
    }
  }
}

// Helper to re-evaluate state after streaming ends
export async function reevaluateMessageStateAfterStreaming(messageDiv) {
  if (messageDiv.classList.contains('message-temp')) return;
  lockMessageState(messageDiv);
  if (pendingStateTimeouts.has(messageDiv)) {
    clearTimeout(pendingStateTimeouts.get(messageDiv));
    pendingStateTimeouts.delete(messageDiv);
  }
  // Only reevaluate this message, not others
  console.log(`[GUARD] reevaluateMessageStateAfterStreaming: Only reevaluating ${messageDiv.id || messageDiv.className} after streaming.`);
  const prevState = messageDiv.classList.contains('message-compact') ? 'compact' : (messageDiv.classList.contains('message-expanded') ? 'expanded' : 'none');
  try {
    const optimalState = await determineMessageState(messageDiv);
    setMessageState(messageDiv, optimalState === 'compact' ? 'compact' : 'expanded');
    ensureScrollTracking(messageDiv);
    if (messageDiv.dataset.userScrolled !== 'true') {
      messageDiv.scrollTop = messageDiv.scrollHeight;
      messageDiv.dataset.userScrolled = 'false';
    }
    console.log(`[STATE] reevaluateMessageStateAfterStreaming: ${messageDiv.id || messageDiv.className} set to ${optimalState} | prevState=${prevState} | scrollTop=${messageDiv.scrollTop} | height=${messageDiv.scrollHeight}`);
  } catch (error) {
    console.warn('Error re-evaluating message state after streaming:', error);
  }
  // unlockMessageState(messageDiv); // Do not unlock automatically
}

// Debugging function for console testing
window.debugScrolling = function() {
  console.log('🔍 Debugging scrolling for all messages:');
  
  const allMessages = document.querySelectorAll('.message');
  allMessages.forEach((msg, index) => {
    const container = msg.closest('.message-container');
    const messageId = container ? container.id : `unknown-${index}`;
    const classes = Array.from(msg.classList).join(' ');
    const hasScrollTracking = msg.dataset.scrollTrackingInitialized === "true";
    const userScrolled = msg.dataset.userScrolled;
    const scrollHeight = msg.scrollHeight;
    const clientHeight = msg.clientHeight;
    const scrollTop = msg.scrollTop;
    const isTemp = container ? container.classList.contains('message-temp') : false;
    
    console.log(`📋 Message ${messageId}:`);
    console.log(`  Classes: ${classes}`);
    console.log(`  Scroll tracking: ${hasScrollTracking}`);
    console.log(`  User scrolled: ${userScrolled}`);
    console.log(`  Dimensions: ${scrollHeight}h × ${clientHeight}ch (scrollTop: ${scrollTop})`);
    console.log(`  Is temp/streaming: ${isTemp}`);
    console.log(`  Can scroll: ${scrollHeight > clientHeight}`);
    
    // Check for content span
    const span = container ? container.querySelector('.msg-content span') : null;
    if (span) {
      console.log(`  Content length: ${span.innerHTML.length} chars`);
    } else {
      console.log(`  ⚠️ No content span found`);
    }
    
    console.log('---');
  });
  
  // Also check for any streaming messages
  const streamingMessages = document.querySelectorAll('.message-temp');
  console.log(`🔄 Found ${streamingMessages.length} streaming messages`);
  
  return {
    totalMessages: allMessages.length,
    streamingMessages: streamingMessages.length,
    compactMessages: document.querySelectorAll('.message-compact').length,
    expandedMessages: document.querySelectorAll('.message-expanded').length
  };
};

// Function to force auto-scroll on a specific message (for testing)
window.forceScrollMessage = function(messageId) {
  const container = document.getElementById(`message-${messageId}`);
  if (!container) {
    console.error(`Message ${messageId} not found`);
    return;
  }
  
  const messageDiv = container.querySelector('.message');
  if (!messageDiv) {
    console.error(`No .message div found in ${messageId}`);
    return;
  }
  
  console.log(`🔽 Force scrolling message ${messageId}`);
  messageDiv.scrollTop = messageDiv.scrollHeight;
  messageDiv.dataset.userScrolled = "false";
  console.log(`Scrolled to: ${messageDiv.scrollTop}/${messageDiv.scrollHeight}`);
};

// Function to force a message into compact mode (for testing)
window.forceCompactMessage = function(messageId) {
  const container = document.getElementById(`message-${messageId}`);
  if (!container) {
    console.error(`Message ${messageId} not found`);
    return;
  }
  
  const messageDiv = container.querySelector('.message');
  if (!messageDiv) {
    console.error(`No .message div found in ${messageId}`);
    return;
  }
  
  console.log(`📦 Force compact mode for message ${messageId}`);
  messageDiv.classList.remove('message-expanded');
  messageDiv.classList.add('message-compact');
  ensureScrollTracking(messageDiv);
  
  // Auto-scroll to bottom
  requestAnimationFrame(() => {
    messageDiv.scrollTop = messageDiv.scrollHeight;
    messageDiv.dataset.userScrolled = "false";
    console.log(`Auto-scrolled after forcing compact: ${messageDiv.scrollTop}/${messageDiv.scrollHeight}`);
  });
};

// Function to test streaming updates (for debugging)
window.testStreamingUpdate = function(messageId, newContent) {
  const container = document.getElementById(`message-${messageId}`);
  if (!container) {
    console.error(`Message ${messageId} not found`);
    return;
  }
  
  console.log(`🧪 Testing streaming update for message ${messageId}`);
  
  // Import the updateMessageContent function and test it
  if (window.msgs && window.msgs.updateMessageContent) {
    window.msgs.updateMessageContent(container, newContent || "Test streaming content that should auto-scroll to bottom when it gets long enough to trigger compact mode and scrolling behavior.");
  } else {
    // Fallback - call the function directly
    updateMessageContent(container, newContent || "Test streaming content that should auto-scroll to bottom when it gets long enough to trigger compact mode and scrolling behavior.");
  }
};

console.log('🛠️ Debug function available: window.debugScrolling()');

// Make messages functions available globally for debugging
window.msgs = {
  updateMessageContent,
  convertHTML,
  getHandler
};

// Add a global map to track pending state evaluators
const pendingStateTimeouts = new Map();

// Helper to lock state on a message
function lockMessageState(msg) {
  msg.classList.add('state-lock');
}
// Helper to unlock state on a message
function unlockMessageState(msg) {
  msg.classList.remove('state-lock');
}

// Helper to set message state safely
function setMessageState(msg, newState) {
  // Only update if the state is actually changing
  if (!msg.classList.contains(`message-${newState}`)) {
    msg.classList.remove('message-expanded', 'message-compact');
    msg.classList.add(`message-${newState}`);
  }
}

// Helper: Force a message to expanded state (removes compact, adds expanded)
function forceExpanded(msg) {
  msg.classList.remove('message-compact');
  msg.classList.add('message-expanded');
  msg.style.maxHeight = 'none';
  msg.style.overflowY = 'visible';
}

// Helper: Re-evaluate all agent-response messages except the last one
export function enforceLastAgentResponseExpanded() {
  const responses = Array.from(document.querySelectorAll('.message-agent-response'));
  if (responses.length === 0) return;
  // Last one stays expanded
  const last = responses[responses.length - 1];
  forceExpanded(last);
  // All previous can compact if needed
  for (let i = 0; i < responses.length - 1; i++) {
    const msg = responses[i];
    // Only re-evaluate if not collapsed or streaming
    if (!msg.classList.contains('message-collapsed') && !msg.classList.contains('message-temp')) {
      determineMessageState(msg).then(optimalState => {
        setMessageState(msg, optimalState === 'compact' ? 'compact' : 'expanded');
      });
    }
  }
}

// Helper to unlock all messages after streaming ends
function unlockAllMessageStates() {
  const lockedMessages = document.querySelectorAll('.state-lock');
  lockedMessages.forEach(msg => msg.classList.remove('state-lock'));
}

// New helper: finalize message state after render (no scroll changes)
function finalizeMessageState(messageDiv, type) {
  // Special handling for code_exe messages: compact while streaming if >400px
  if (type === 'code_exe' && messageDiv.classList.contains('message-temp')) {
    // If empty, skip
    if (!messageDiv || messageDiv.scrollHeight === 0) return;
    if (messageDiv.scrollHeight > 400) {
      setMessageState(messageDiv, 'compact');
      // Always scroll to bottom unless user has scrolled up
      if (messageDiv.dataset.userScrolled !== 'true') {
        messageDiv.scrollTop = messageDiv.scrollHeight;
        messageDiv.dataset.userScrolled = "false";
      }
      return;
    } else {
      setMessageState(messageDiv, 'expanded');
      return;
    }
  }
  // If streaming (other types), always expanded
  if (messageDiv.classList.contains('message-temp')) {
    setMessageState(messageDiv, 'expanded');
    return;
  }
  // If empty, skip
  if (!messageDiv || messageDiv.scrollHeight === 0) return;
  // Otherwise, determine optimal state
  determineMessageState(messageDiv).then(optimalState => {
    setMessageState(messageDiv, optimalState === 'compact' ? 'compact' : 'expanded');
    // Restore auto-scroll-to-bottom within message when compacted, unless user has scrolled up
    if (optimalState === 'compact' && messageDiv.dataset.userScrolled !== 'true') {
      messageDiv.scrollTop = messageDiv.scrollHeight;
      messageDiv.dataset.userScrolled = "false";
    }
  });
}
