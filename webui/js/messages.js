// copy button
import { openImageModal } from "./image_modal.js";
import { marked } from "../vendor/marked/marked.esm.js";
import { getAutoScroll } from "/index.js";
import { store as _messageResizeStore } from "/components/messages/resize/message-resize-store.js"; // keep here, required in html
import { store as attachmentsStore } from "/components/chat/attachments/attachmentsStore.js";

const chatHistory = document.getElementById("chat-history");

let messageGroup = null;

// Scroll position manager for smooth autoscroll
class ScrollPositionManager {
  constructor() {
    this.positions = new Map();
    this.autoscrollDisabled = false;
    this.scrollableSelectors = ['.msg-content', '.kvps-val'];
    this.monitoringInterval = null; // Added for continuous monitoring
  }

  // Store scroll positions for all scrollable elements in a message
  storeMessageScrollPositions(messageContainer) {
    if (!messageContainer) return;

    const messageId = messageContainer.id;
    const positions = {};

    // Store main message content scroll position
    const msgContent = messageContainer.querySelector('.msg-content');
    if (msgContent && msgContent.scrollHeight > msgContent.clientHeight) {
      positions.msgContent = {
        scrollTop: msgContent.scrollTop,
        scrollHeight: msgContent.scrollHeight,
        clientHeight: msgContent.clientHeight,
        isAtBottom: this.isAtBottom(msgContent)
      };
    }

    // Store message body scroll position (for terminal messages)
    const msgBody = messageContainer.querySelector('.message-body');
    if (msgBody && msgBody.scrollHeight > msgBody.clientHeight) {
      positions.msgBody = {
        scrollTop: msgBody.scrollTop,
        scrollHeight: msgBody.scrollHeight,
        clientHeight: msgBody.clientHeight,
        isAtBottom: this.isAtBottom(msgBody)
      };
    }

    // Store KVP scroll positions
    const kvpValues = messageContainer.querySelectorAll('.kvps-val');
    kvpValues.forEach((kvp, index) => {
      if (kvp.scrollHeight > kvp.clientHeight) {
        positions[`kvp_${index}`] = {
          scrollTop: kvp.scrollTop,
          scrollHeight: kvp.scrollHeight,
          clientHeight: kvp.clientHeight,
          isAtBottom: this.isAtBottom(kvp)
        };
      }
    });

    this.positions.set(messageId, positions);
  }

  // Restore scroll positions for a message
  restoreMessageScrollPositions(messageContainer) {
    if (!messageContainer) return;

    const messageId = messageContainer.id;
    const positions = this.positions.get(messageId);
    if (!positions) return;

    // Use a small delay to ensure DOM is fully updated
    setTimeout(() => {
      // Restore main message content scroll
      if (positions.msgContent) {
        const msgContent = messageContainer.querySelector('.msg-content');
        if (msgContent) {
          if (this.autoscrollDisabled || !positions.msgContent.isAtBottom) {
            // User had scrolled up, restore their position
            msgContent.scrollTop = positions.msgContent.scrollTop;
          } else {
            // User was at bottom, keep at bottom (autoscroll)
            msgContent.scrollTop = msgContent.scrollHeight;
          }
        }
      }

      // Restore message body scroll position (for terminal messages)
      if (positions.msgBody) {
        const msgBody = messageContainer.querySelector('.message-body');
        if (msgBody) {
          if (this.autoscrollDisabled || !positions.msgBody.isAtBottom) {
            // User had scrolled up, restore their position
            msgBody.scrollTop = positions.msgBody.scrollTop;
          } else {
            // User was at bottom, keep at bottom (autoscroll)
            msgBody.scrollTop = msgBody.scrollHeight;
          }
        }
      }

      // Restore KVP scroll positions
      const kvpValues = messageContainer.querySelectorAll('.kvps-val');
      kvpValues.forEach((kvp, index) => {
        const posKey = `kvp_${index}`;
        if (positions[posKey]) {
          if (this.autoscrollDisabled || !positions[posKey].isAtBottom) {
            // User had scrolled up, restore their position
            kvp.scrollTop = positions[posKey].scrollTop;
          } else {
            // User was at bottom, keep at bottom (autoscroll)
            kvp.scrollTop = kvp.scrollHeight;
          }
        }
      });
    }, 10); // Small delay to ensure DOM is ready
  }

  // Check global scroll state and update autoscroll disabled flag
  checkGlobalScrollState() {
    // Check main chat history - this is the primary indicator for disabling autoscroll
    const chatHistory = document.getElementById("chat-history");
    if (chatHistory && !this.isAtBottom(chatHistory, 20)) {
      this.autoscrollDisabled = true;
      return;
    }

    // Check chat input area - also important for disabling autoscroll
    const chatInput = document.getElementById("chat-input");
    if (chatInput && !this.isAtBottom(chatInput, 20)) {
      this.autoscrollDisabled = true;
      return;
    }

    // Individual message scroll positions don't disable autoscroll globally
    // They only affect their own scrolling behavior
    // This allows users to scroll up in individual messages while keeping autoscroll enabled

    // If we get here, main areas are at bottom, enable autoscroll
    this.autoscrollDisabled = false;
  }

  // Improved method to check if element is scrolled to bottom with better tolerance
  isAtBottom(element, tolerance = 10) {
    if (!element) return true;

    // Get current scroll position and dimensions
    const scrollTop = element.scrollTop;
    const scrollHeight = element.scrollHeight;
    const clientHeight = element.clientHeight;

    // Calculate how far from bottom we are
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

    // Return true if we're within tolerance of the bottom
    return distanceFromBottom <= tolerance;
  }

  // Enhanced method to check if user is at bottom of all scrollable areas
  // This method is more robust during active content generation
  isUserAtBottomOfAllScrollableAreas() {
    // Check main chat history
    const chatHistory = document.getElementById("chat-history");
    if (chatHistory && !this.isAtBottom(chatHistory, 20)) {
      return false;
    }

    // Check chat input area
    const chatInput = document.getElementById("chat-input");
    if (chatInput && !this.isAtBottom(chatInput, 20)) {
      return false;
    }

    // Check all message content areas
    const allMsgContent = document.querySelectorAll('.msg-content');
    for (const element of allMsgContent) {
      if (!this.isAtBottom(element, 20)) {
        return false;
      }
    }

    // Check all message body areas (terminal messages)
    const allMsgBody = document.querySelectorAll('.message-body');
    for (const element of allMsgBody) {
      if (!this.isAtBottom(element, 20)) {
        return false;
      }
    }

    // Check all KVP areas
    const allKvpValues = document.querySelectorAll('.kvps-val');
    for (const element of allKvpValues) {
      if (!this.isAtBottom(element, 20)) {
        return false;
      }
    }

    return true;
  }

  // Continuous monitoring method for re-enabling autoscroll during active content generation
  startContinuousMonitoring() {
    // Clear any existing monitoring
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
    }

    // Start monitoring every 100ms to check if user has scrolled to bottom
    this.monitoringInterval = setInterval(() => {
      if (this.autoscrollDisabled) {
        // Check if main chat history is at bottom - this is the primary indicator
        const chatHistory = document.getElementById("chat-history");
        const isMainHistoryAtBottom = chatHistory && this.isAtBottom(chatHistory, 20);

        // Check if chat input is at bottom
        const chatInput = document.getElementById("chat-input");
        const isChatInputAtBottom = chatInput && this.isAtBottom(chatInput, 20);

        // If main chat history is at bottom, re-enable autoscroll regardless of individual message positions
        if (isMainHistoryAtBottom && isChatInputAtBottom) {
          this.reEnableAutoscrollIfAtBottom();
        }
      }
    }, 100);
  }

  // Stop continuous monitoring
  stopContinuousMonitoring() {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
    }
  }

  // Set up scroll listeners for a message container
  setupScrollListeners(messageContainer) {
    if (!messageContainer) return;

    // Add scroll listeners to detect user scrolling within messages
    // These don't disable autoscroll globally, they just manage their own scroll behavior
    const msgContent = messageContainer.querySelector('.msg-content');
    if (msgContent) {
      msgContent.addEventListener('scroll', () => {
        // Individual message scroll doesn't disable global autoscroll
        // It only affects the scroll behavior of this specific element
        if (this.isAtBottom(msgContent, 20)) {
          // If user scrolls back to bottom of this message, they might want autoscroll
          this.reEnableAutoscrollIfAtBottom();
        }
      });
    }

    // Add scroll listeners for message-body elements (terminal messages)
    const msgBody = messageContainer.querySelector('.message-body');
    if (msgBody) {
      msgBody.addEventListener('scroll', () => {
        // Individual message scroll doesn't disable global autoscroll
        // It only affects the scroll behavior of this specific element
        if (this.isAtBottom(msgBody, 20)) {
          // If user scrolls back to bottom of this message, they might want autoscroll
          this.reEnableAutoscrollIfAtBottom();
        }
      });
    }

    const kvpValues = messageContainer.querySelectorAll('.kvps-val');
    kvpValues.forEach(kvp => {
      kvp.addEventListener('scroll', () => {
        // Individual KVP scroll doesn't disable global autoscroll
        // It only affects the scroll behavior of this specific element
        if (this.isAtBottom(kvp, 20)) {
          // If user scrolls back to bottom of this KVP, they might want autoscroll
          this.reEnableAutoscrollIfAtBottom();
        }
      });
    });
  }

  // Set up scroll listeners for global elements (chat history, chat input)
  setupGlobalScrollListeners() {
    // Set up scroll listener for main chat history
    const chatHistory = document.getElementById("chat-history");
    if (chatHistory) {
      chatHistory.addEventListener('scroll', () => {
        if (!this.isAtBottom(chatHistory)) {
          this.disableAutoscroll();
          // Start continuous monitoring when autoscroll is disabled
          this.startContinuousMonitoring();
        } else {
          this.reEnableAutoscrollIfAtBottom();
        }
      });
    }

    // Set up scroll listener for chat input
    const chatInput = document.getElementById("chat-input");
    if (chatInput) {
      chatInput.addEventListener('scroll', () => {
        if (!this.isAtBottom(chatInput)) {
          this.disableAutoscroll();
          // Start continuous monitoring when autoscroll is disabled
          this.startContinuousMonitoring();
        } else {
          this.reEnableAutoscrollIfAtBottom();
        }
      });
    }
  }

  // Enhanced method to re-enable autoscroll when user scrolls to bottom
  reEnableAutoscrollIfAtBottom() {
    // Check if main chat history is at bottom - this is the primary indicator
    const chatHistory = document.getElementById("chat-history");
    const isMainHistoryAtBottom = chatHistory && this.isAtBottom(chatHistory, 20);

    // Check if chat input is at bottom
    const chatInput = document.getElementById("chat-input");
    const isChatInputAtBottom = chatInput && this.isAtBottom(chatInput, 20);

    // If main chat history is at bottom, re-enable autoscroll regardless of individual message positions
    // This allows users to scroll up in individual messages but still have autoscroll when they scroll down the main history
    if (isMainHistoryAtBottom && isChatInputAtBottom) {
      this.autoscrollDisabled = false;
      // Stop continuous monitoring when autoscroll is re-enabled
      this.stopContinuousMonitoring();
      // Scroll all elements to bottom when autoscroll is enabled
      this.scrollAllToBottom();
      // Update the main autoscroll state
      if (window.updateAfterScroll) {
        window.updateAfterScroll();
      }
    }
  }

  // Method to scroll all scrollable elements to the bottom
  scrollAllToBottom() {
    // Scroll main chat history to bottom
    const chatHistory = document.getElementById("chat-history");
    if (chatHistory) {
      chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    // Scroll chat input to bottom
    const chatInput = document.getElementById("chat-input");
    if (chatInput) {
      chatInput.scrollTop = chatInput.scrollHeight;
    }

    // Scroll all message content areas to bottom
    const allMsgContent = document.querySelectorAll('.msg-content');
    allMsgContent.forEach(element => {
      if (element.scrollHeight > element.clientHeight) {
        element.scrollTop = element.scrollHeight;
      }
    });

    // Scroll all message body areas (terminal messages) to bottom
    const allMsgBody = document.querySelectorAll('.message-body');
    allMsgBody.forEach(element => {
      if (element.scrollHeight > element.clientHeight) {
        element.scrollTop = element.scrollHeight;
      }
    });

    // Scroll all KVP areas to bottom
    const allKvpValues = document.querySelectorAll('.kvps-val');
    allKvpValues.forEach(element => {
      if (element.scrollHeight > element.clientHeight) {
        element.scrollTop = element.scrollHeight;
      }
    });
  }

  // Disable autoscroll globally
  disableAutoscroll() {
    this.autoscrollDisabled = true;
    // Start continuous monitoring when autoscroll is disabled
    this.startContinuousMonitoring();
    // Don't call window.toggleAutoScroll here to avoid circular dependency
    // The main autoscroll state will be updated via scrollChanged function
  }

  // Enable autoscroll
  enableAutoscroll() {
    this.autoscrollDisabled = false;
    // Stop continuous monitoring when autoscroll is enabled
    this.stopContinuousMonitoring();
    // Automatically scroll to bottom when autoscroll is enabled
    this.scrollAllToBottom();
  }
}

// Global scroll position manager instance
const scrollManager = new ScrollPositionManager();

// Export scroll manager for use in other modules
export function getScrollManager() {
  return scrollManager;
}

export function setMessage(id, type, heading, content, temp, kvps = null) {
  // Search for the existing message container by id
  let messageContainer = document.getElementById(`message-${id}`);
  let isNewMessage = false;

  if (messageContainer) {
    // Store current scroll positions before updating
    scrollManager.storeMessageScrollPositions(messageContainer);

    // Don't clear innerHTML - we'll do incremental updates
    // messageContainer.innerHTML = "";
  } else {
    // Create a new container if not found
    isNewMessage = true;
    const sender = type === "user" ? "user" : "ai";
    messageContainer = document.createElement("div");
    messageContainer.id = `message-${id}`;
    messageContainer.classList.add("message-container", `${sender}-container`);
    // if (temp) messageContainer.classList.add("message-temp");
  }

  const handler = getHandler(type);
  handler(messageContainer, id, type, heading, content, temp, kvps);

  // If this is a new message, handle DOM insertion
  if (isNewMessage && !document.getElementById(`message-${id}`)) {
    // message type visual grouping
    const groupTypeMap = {
      user: "right",
      info: "mid",
      warning: "mid",
      error: "mid",
      rate_limit: "mid",
      util: "mid",
      hint: "mid",
      // anything else is "left"
    };

    //force new group on these types
    const groupStart = {
      agent: true,
      // anything else is false
    };

    const groupType = groupTypeMap[type] || "left";

    // here check if messageGroup is still in DOM, if not, then set it to null (context switch)
    if(messageGroup && !document.getElementById(messageGroup.id))
      messageGroup = null;

    if (
      !messageGroup || // no group yet exists
      groupStart[type] || // message type forces new group
      groupType != messageGroup.getAttribute("data-group-type") // message type changes group
    ) {
      messageGroup = document.createElement("div");
      messageGroup.id = `message-group-${id}`;
      messageGroup.classList.add(`message-group`, `message-group-${groupType}`);
      messageGroup.setAttribute("data-group-type", groupType);
    }

    messageGroup.appendChild(messageContainer);
    chatHistory.appendChild(messageGroup);

    // Set up scroll listeners for new message
    scrollManager.setupScrollListeners(messageContainer);
  } else {
    // For existing messages, restore scroll positions after DOM update
    setTimeout(() => {
      scrollManager.restoreMessageScrollPositions(messageContainer);
    }, 0);
  }
}

function createCopyButton() {
  const button = document.createElement("button");
  button.className = "copy-button";
  button.textContent = "Copy";

  button.addEventListener("click", async function (e) {
    e.stopPropagation();
    const container = this.closest(".msg-content, .kvps-row, .message-text");
    let textToCopy;

    if (container.classList.contains("kvps-row")) {
      textToCopy = container.querySelector(".kvps-val").innerText;
    } else if (container.classList.contains("message-text")) {
      textToCopy = container.querySelector("span").innerText;
    } else {
      textToCopy = container.querySelector("span").innerText;
    }

    try {
      await navigator.clipboard.writeText(textToCopy);
      const originalText = button.textContent;
      button.classList.add("copied");
      button.textContent = "Copied!";
      setTimeout(() => {
        button.classList.remove("copied");
        button.textContent = originalText;
      }, 2000);
    } catch (err) {
      console.error("Failed to copy text:", err);
    }
  });

  return button;
}

function addCopyButtonToElement(element) {
  if (!element.querySelector(".copy-button")) {
    element.appendChild(createCopyButton());
  }
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
  mainClass = "",
  kvps = null,
  messageClasses = [],
  contentClasses = [],
  latex = false,
  markdown = false,
  resizeBtns = true
) {
  // Find existing message div or create new one
  let messageDiv = messageContainer.querySelector(".message");
  if (!messageDiv) {
    messageDiv = document.createElement("div");
    messageDiv.classList.add("message");
    messageContainer.appendChild(messageDiv);
  }

  // Update message classes
  messageDiv.className = `message ${mainClass} ${messageClasses.join(' ')}`;

  // Handle heading
  if (heading) {
    let headingElement = messageDiv.querySelector(".msg-heading");
    if (!headingElement) {
      headingElement = document.createElement("div");
      headingElement.classList.add("msg-heading");
      messageDiv.insertBefore(headingElement, messageDiv.firstChild);
    }

    let headingH4 = headingElement.querySelector("h4");
    if (!headingH4) {
      headingH4 = document.createElement("h4");
      headingElement.appendChild(headingH4);
    }
    headingH4.innerHTML = convertIcons(escapeHTML(heading));

    if (resizeBtns) {
      let minMaxBtn = headingElement.querySelector(".msg-min-max-btns");
      if (!minMaxBtn) {
        minMaxBtn = document.createElement("div");
        minMaxBtn.classList.add("msg-min-max-btns");
        minMaxBtn.innerHTML = `
          <a href="#" class="msg-min-max-btn" @click.prevent="$store.messageResize.minimizeMessageClass('${mainClass}', $event)"><span class="material-symbols-outlined" x-text="$store.messageResize.getSetting('${mainClass}').minimized ? 'expand_content' : 'minimize'"></span></a>
          <a href="#" class="msg-min-max-btn" x-show="!$store.messageResize.getSetting('${mainClass}').minimized" @click.prevent="$store.messageResize.maximizeMessageClass('${mainClass}', $event)"><span class="material-symbols-outlined" x-text="$store.messageResize.getSetting('${mainClass}').maximized ? 'expand' : 'expand_all'"></span></a>
        `;
        headingElement.appendChild(minMaxBtn);
      }
    }
  } else {
    // Remove heading if it exists but heading is null
    const existingHeading = messageDiv.querySelector(".msg-heading");
    if (existingHeading) {
      existingHeading.remove();
    }
  }

  // Find existing body div or create new one
  let bodyDiv = messageDiv.querySelector(".message-body");
  if (!bodyDiv) {
    bodyDiv = document.createElement("div");
    bodyDiv.classList.add("message-body");
    messageDiv.appendChild(bodyDiv);
  }

  // Handle KVPs incrementally
  drawKvpsIncremental(bodyDiv, kvps, false);

  // Handle content
  if (content && content.trim().length > 0) {
    if (markdown) {
      let contentDiv = bodyDiv.querySelector(".msg-content");
      if (!contentDiv) {
        contentDiv = document.createElement("div");
        contentDiv.classList.add("msg-content", ...contentClasses);
        bodyDiv.appendChild(contentDiv);

        // Set up scroll listener for new content div
        contentDiv.addEventListener('scroll', () => {
          // Individual message scroll doesn't disable global autoscroll
          // It only affects the scroll behavior of this specific element
          if (scrollManager.isAtBottom(contentDiv, 20)) {
            // If user scrolls back to bottom of this message, they might want autoscroll
            scrollManager.reEnableAutoscrollIfAtBottom();
          }
        });
      } else {
        // Update classes
        contentDiv.className = `msg-content ${contentClasses.join(' ')}`;
      }

      let spanElement = contentDiv.querySelector("span");
      if (!spanElement) {
        spanElement = document.createElement("span");
        contentDiv.appendChild(spanElement);
      }

      let processedContent = content;
      processedContent = convertImageTags(processedContent);
      processedContent = convertImgFilePaths(processedContent);
      processedContent = marked.parse(processedContent, { breaks: true });
      processedContent = convertPathsToLinks(processedContent);
      processedContent = addBlankTargetsToLinks(processedContent);
      spanElement.innerHTML = processedContent;

      // KaTeX rendering for markdown
      if (latex) {
        spanElement.querySelectorAll("latex").forEach((element) => {
          katex.render(element.innerHTML, element, {
            throwOnError: false,
          });
        });
      }

      // Ensure copy button exists
      if (!contentDiv.querySelector(".copy-button")) {
        addCopyButtonToElement(contentDiv);
      }
      adjustMarkdownRender(contentDiv);
    } else {
      let preElement = bodyDiv.querySelector(".msg-content");
      if (!preElement) {
        preElement = document.createElement("pre");
        preElement.classList.add("msg-content", ...contentClasses);
        preElement.style.whiteSpace = "pre-wrap";
        preElement.style.wordBreak = "break-word";
        bodyDiv.appendChild(preElement);

        // Set up scroll listener for new pre element
        preElement.addEventListener('scroll', () => {
          // Individual message scroll doesn't disable global autoscroll
          // It only affects the scroll behavior of this specific element
          if (scrollManager.isAtBottom(preElement, 20)) {
            // If user scrolls back to bottom of this message, they might want autoscroll
            scrollManager.reEnableAutoscrollIfAtBottom();
          }
        });
      } else {
        // Update classes
        preElement.className = `msg-content ${contentClasses.join(' ')}`;
      }

      let spanElement = preElement.querySelector("span");
      if (!spanElement) {
        spanElement = document.createElement("span");
        preElement.appendChild(spanElement);

        // Add click handler for small screens (only once)
        spanElement.addEventListener("click", () => {
          copyText(spanElement.textContent, spanElement);
        });
      }

      spanElement.innerHTML = convertHTML(content);

      // Ensure copy button exists
      if (!preElement.querySelector(".copy-button")) {
        addCopyButtonToElement(preElement);
      }
    }
  } else {
    // Remove content if it exists but content is empty
    const existingContent = bodyDiv.querySelector(".msg-content");
    if (existingContent) {
      existingContent.remove();
    }
  }

  if (followUp) {
    messageContainer.classList.add("message-followup");
  }

  // Don't force scroll here - let the scroll manager handle it
  // The scroll manager will decide whether to autoscroll based on user's scroll state

  return messageDiv;
}

export function addBlankTargetsToLinks(str) {
  const doc = new DOMParser().parseFromString(str, 'text/html');

  doc.querySelectorAll('a').forEach(anchor => {
    const href = anchor.getAttribute('href') || '';
    if (href.startsWith('#') || href.trim().toLowerCase().startsWith('javascript')) return;
    if (!anchor.hasAttribute('target') || anchor.getAttribute('target') === '') {
      anchor.setAttribute('target', '_blank');
    }

    const rel = (anchor.getAttribute('rel') || '').split(/\s+/).filter(Boolean);
    if (!rel.includes('noopener')) rel.push('noopener');
    if (!rel.includes('noreferrer')) rel.push('noreferrer');
    anchor.setAttribute('rel', rel.join(' '));
  });
  return doc.body.innerHTML;
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
  _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    false,
    "message-default",
    kvps,
    ["message-ai"],
    ["msg-json"],
    false,
    false
  );
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

  _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    false,
    "message-agent",
    kvpsFlat,
    ["message-ai"],
    ["msg-json"],
    false,
    false
  );
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
  _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    true,
    "message-agent-response",
    null,
    ["message-ai"],
    [],
    true,
    true
  );
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
    content,
    temp,
    true,
    "message-agent-delegation",
    kvps,
    ["message-ai", "message-agent"],
    [],
    true,
    false
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
  headingElement.classList.add("msg-heading");
  headingElement.innerHTML =
    `${heading} <span class='icon material-symbols-outlined'>person</span>`;
  messageDiv.appendChild(headingElement);

  if (content && content.trim().length > 0) {
    const textDiv = document.createElement("div");
    textDiv.classList.add("message-text");

    // Create a span for the content
    const spanElement = document.createElement("pre");
    spanElement.innerHTML = escapeHTML(content);
    textDiv.appendChild(spanElement);

    // Add click handler
    textDiv.addEventListener("click", () => {
      copyText(content, textDiv);
    });

    addCopyButtonToElement(textDiv);
    messageDiv.appendChild(textDiv);
  }

  // Handle attachments
  if (kvps && kvps.attachments && kvps.attachments.length > 0) {
    const attachmentsContainer = document.createElement("div");
    attachmentsContainer.classList.add("attachments-container");

    kvps.attachments.forEach((attachment) => {
      const attachmentDiv = document.createElement("div");
      attachmentDiv.classList.add("attachment-item");

      const displayInfo = attachmentsStore.getAttachmentDisplayInfo(attachment);

      if (displayInfo.isImage) {
        attachmentDiv.classList.add("image-type");

        const img = document.createElement("img");
        img.src = displayInfo.previewUrl;
        img.alt = displayInfo.filename;
        img.classList.add("attachment-preview");
        img.style.cursor = "pointer";


        attachmentDiv.appendChild(img);
      } else {
        // Render as file tile with title and icon
        attachmentDiv.classList.add("file-type");

        // File icon
        if (displayInfo.previewUrl && displayInfo.previewUrl !== displayInfo.filename) {
          const iconImg = document.createElement("img");
          iconImg.src = displayInfo.previewUrl;
          iconImg.alt = `${displayInfo.extension} file`;
          iconImg.classList.add("file-icon");
          attachmentDiv.appendChild(iconImg);
        }

        // File title
        const fileTitle = document.createElement("div");
        fileTitle.classList.add("file-title");
        fileTitle.textContent = displayInfo.filename;

        attachmentDiv.appendChild(fileTitle);
      }

      attachmentDiv.addEventListener('click', displayInfo.clickHandler);

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
  _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    true,
    "message-tool",
    kvps,
    ["message-ai"],
    ["msg-output"],
    false,
    false
  );
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
  _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    true,
    "message-code-exe",
    null,
    ["message-ai"],
    [],
    false,
    false
  );
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
  _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    true,
    "message-browser",
    kvps,
    ["message-ai"],
    ["msg-json"],
    false,
    false
  );
}

export function drawMessageAgentPlain(
  mainClass,
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
    mainClass,
    kvps,
    [],
    [],
    false,
    false
  );
  messageContainer.classList.add("center-container");
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
  return drawMessageAgentPlain(
    "message-info",
    messageContainer,
    id,
    type,
    heading,
    content,
    temp,
    kvps
  );
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
    "message-util",
    kvps,
    [],
    ["msg-json"],
    false,
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
  return drawMessageAgentPlain(
    "message-warning",
    messageContainer,
    id,
    type,
    heading,
    content,
    temp,
    kvps
  );
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
  return drawMessageAgentPlain(
    "message-error",
    messageContainer,
    id,
    type,
    heading,
    content,
    temp,
    kvps
  );
}

function drawKvps(container, kvps, latex) {
  if (kvps) {
    const table = document.createElement("table");
    table.classList.add("msg-kvps");
    for (let [key, value] of Object.entries(kvps)) {
      const row = table.insertRow();
      row.classList.add("kvps-row");
      if (key === "thoughts" || key === "reasoning")
        // TODO: find a better way to determine special class assignment
        row.classList.add("msg-thoughts");

      const th = row.insertCell();
      th.textContent = convertToTitleCase(key);
      th.classList.add("kvps-key");

      const td = row.insertCell();
      const tdiv = document.createElement("div");
      tdiv.classList.add("kvps-val");
      td.appendChild(tdiv);

      if (Array.isArray(value)) {
        for (const item of value) {
          addValue(item);
        }
      } else {
        addValue(value);
      }

      // autoscroll the KVP value if needed
      // if (getAutoScroll()) #TODO needs a better redraw system
      setTimeout(() => {
        tdiv.scrollTop = tdiv.scrollHeight;
      }, 0);

      function addValue(value) {
        if (typeof value === "object") value = JSON.stringify(value, null, 2);

        if (typeof value === "string" && value.startsWith("img://")) {
          const imgElement = document.createElement("img");
          imgElement.classList.add("kvps-img");
          imgElement.src = value.replace("img://", "/image_get?path=");
          imgElement.alt = "Image Attachment";
          tdiv.appendChild(imgElement);

          // Add click handler and cursor change
          imgElement.style.cursor = "pointer";
          imgElement.addEventListener("click", () => {
            openImageModal(imgElement.src, 1000);
          });
        } else {
          const pre = document.createElement("pre");
          const span = document.createElement("span");
          span.innerHTML = convertHTML(value);
          pre.appendChild(span);
          tdiv.appendChild(pre);
          addCopyButtonToElement(row);

          // Add click handler
          span.addEventListener("click", () => {
            copyText(span.textContent, span);
          });

          // KaTeX rendering for markdown
          if (latex) {
            span.querySelectorAll("latex").forEach((element) => {
              katex.render(element.innerHTML, element, {
                throwOnError: false,
              });
            });
          }
        }
      }

    }
    container.appendChild(table);
  }
}

function drawKvpsIncremental(container, kvps, latex) {
  if (kvps) {
    // Find existing table or create new one
    let table = container.querySelector(".msg-kvps");
    if (!table) {
      table = document.createElement("table");
      table.classList.add("msg-kvps");
      container.appendChild(table);
    }

    // Get all current rows for comparison
    let existingRows = table.querySelectorAll(".kvps-row");
    const kvpEntries = Object.entries(kvps);

    // Update or create rows as needed
    kvpEntries.forEach(([key, value], index) => {
      let row = existingRows[index];

      if (!row) {
        // Create new row if it doesn't exist
        row = table.insertRow();
        row.classList.add("kvps-row");
      }

      // Update row classes
      row.className = "kvps-row";
      if (key === "thoughts" || key === "reasoning") {
        row.classList.add("msg-thoughts");
      }

      // Handle key cell
      let th = row.querySelector(".kvps-key");
      if (!th) {
        th = row.insertCell(0);
        th.classList.add("kvps-key");
      }
      th.textContent = convertToTitleCase(key);

      // Handle value cell
      let td = row.cells[1];
      if (!td) {
        td = row.insertCell(1);
      }

      let tdiv = td.querySelector(".kvps-val");
      if (!tdiv) {
        tdiv = document.createElement("div");
        tdiv.classList.add("kvps-val");
        td.appendChild(tdiv);

        // Set up scroll listener for new kvp value div
        tdiv.addEventListener('scroll', () => {
          // Individual KVP scroll doesn't disable global autoscroll
          // It only affects the scroll behavior of this specific element
          if (scrollManager.isAtBottom(tdiv, 20)) {
            // If user scrolls back to bottom of this KVP, they might want autoscroll
            scrollManager.reEnableAutoscrollIfAtBottom();
          }
        });
      }

      // Store current scroll position
      const currentScrollTop = tdiv.scrollTop;
      const isAtBottom = tdiv.scrollHeight - tdiv.scrollTop <= tdiv.clientHeight + 10;

      // Clear and rebuild content (for now - could be optimized further)
      tdiv.innerHTML = "";

      if (Array.isArray(value)) {
        for (const item of value) {
          addValue(item, tdiv);
        }
      } else {
        addValue(value, tdiv);
      }

      // Restore scroll position or autoscroll
      setTimeout(() => {
        if (!scrollManager.autoscrollDisabled && isAtBottom) {
          // User was at bottom, keep at bottom
          tdiv.scrollTop = tdiv.scrollHeight;
        } else if (!scrollManager.autoscrollDisabled) {
          // User was at bottom, keep at bottom (autoscroll)
          tdiv.scrollTop = tdiv.scrollHeight;
        } else {
          // Restore previous position only if user had scrolled up
          if (currentScrollTop > 0) {
            tdiv.scrollTop = currentScrollTop;
          }
        }
      }, 10);
    });

    // Remove extra rows if we have fewer kvps now
    while (existingRows.length > kvpEntries.length) {
      const lastRow = existingRows[existingRows.length - 1];
      lastRow.remove();
      existingRows = table.querySelectorAll(".kvps-row");
    }

    function addValue(value, tdiv) {
      if (typeof value === "object") value = JSON.stringify(value, null, 2);

      if (typeof value === "string" && value.startsWith("img://")) {
        const imgElement = document.createElement("img");
        imgElement.classList.add("kvps-img");
        imgElement.src = value.replace("img://", "/image_get?path=");
        imgElement.alt = "Image Attachment";
        tdiv.appendChild(imgElement);

        // Add click handler and cursor change
        imgElement.style.cursor = "pointer";
        imgElement.addEventListener("click", () => {
          openImageModal(imgElement.src, 1000);
        });
      } else {
        const pre = document.createElement("pre");
        const span = document.createElement("span");
        span.innerHTML = convertHTML(value);
        pre.appendChild(span);
        tdiv.appendChild(pre);

        // Only add copy button if it doesn't exist
        const row = tdiv.closest(".kvps-row");
        if (row && !row.querySelector(".copy-button")) {
          addCopyButtonToElement(row);
        }

        // Add click handler
        span.addEventListener("click", () => {
          copyText(span.textContent, span);
        });

        // KaTeX rendering for markdown
        if (latex) {
          span.querySelectorAll("latex").forEach((element) => {
            katex.render(element.innerHTML, element, {
              throwOnError: false,
            });
          });
        }
      }
    }
  } else {
    // Remove table if kvps is null/empty
    const existingTable = container.querySelector(".msg-kvps");
    if (existingTable) {
      existingTable.remove();
    }
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
  result = convertImageTags(result);
  result = convertPathsToLinks(result);
  return result;
}

function convertImgFilePaths(str) {
  return str.replace(/img:\/\//g, "/image_get?path=");
}

export function convertIcons(str) {
  return str.replace(
    /icon:\/\/([a-zA-Z0-9_]+)/g,
    '<span class="icon material-symbols-outlined">$1</span>'
  );
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
  function generateLinks(match) {
    const parts = match.split("/");
    if (!parts[0]) parts.shift(); // drop empty element left of first "
    let conc = "";
    let html = "";
    for (const part of parts) {
      conc += "/" + part;
      html += `/<a href="#" class="path-link" onclick="openFileLink('${conc}');">${part}</a>`;
    }
    return html;
  }

  const prefix = `(?:^|[> \`'"\\n]|&#39;|&quot;)`;
  const folder = `[a-zA-Z0-9_\\/.\\-]`;
  const file = `[a-zA-Z0-9_\\-\\/]`;
  const suffix = `(?<!\\.)`;
  const pathRegex = new RegExp(
    `(?<=${prefix})\\/${folder}*${file}${suffix}`,
    "g"
  );

  // skip paths inside html tags, like <img src="/path/to/image">
  const tagRegex = /(<(?:[^<>"']+|"[^"]*"|'[^']*')*>)/g;

  return str
    .split(tagRegex) // keep tags & text separate
    .map((chunk) => {
      // if it *starts* with '<', it's a tag -> leave untouched
      if (chunk.startsWith("<")) return chunk;
      // otherwise run your link-generation
      return chunk.replace(pathRegex, generateLinks);
    })
    .join("");
}

function adjustMarkdownRender(element) {
  // find all tables in the element
  const elements = element.querySelectorAll("table");

  // wrap each with a div with class message-markdown-table-wrap
  elements.forEach((el) => {
    const wrapper = document.createElement("div");
    wrapper.className = "message-markdown-table-wrap";
    el.parentNode.insertBefore(wrapper, el);
    wrapper.appendChild(el);
  });
}
