// enhanced action buttons with copy and speech functionality
import { openImageModal } from "./image_modal.js";
import { marked } from "../vendor/marked/marked.esm.js";
import { getAutoScroll } from "/index.js";
import { store as _messageResizeStore } from "/components/messages/resize/message-resize-store.js"; // keep here, required in html
import { store as attachmentsStore } from "/components/chat/attachments/attachmentsStore.js";
import { store as speechStore } from "/components/chat/speech/speech-store.js";

const chatHistory = document.getElementById("chat-history");

let messageGroup = null;

export function setMessage(id, type, heading, content, temp, kvps = null) {
  // Search for the existing message container by id
  let messageContainer = document.getElementById(`message-${id}`);

  if (messageContainer) {
    // Don't re-render user messages
    // if (type === "user") {
    //   return; // Skip re-rendering
    // }
    // For other types, update the message
    messageContainer.innerHTML = "";
  } else {
    // Create a new container if not found
    const sender = type === "user" ? "user" : "ai";
    messageContainer = document.createElement("div");
    messageContainer.id = `message-${id}`;
    messageContainer.classList.add("message-container", `${sender}-container`);
    // if (temp) messageContainer.classList.add("message-temp");
  }

  const handler = getHandler(type);
  handler(messageContainer, id, type, heading, content, temp, kvps);

  // Add action buttons to all message content after rendering
  setTimeout(() => {
    const contentElements = messageContainer.querySelectorAll(".msg-content, .kvps-row");
    console.log(`[ActionButtons] Processing message ${id} type ${type}, found ${contentElements.length} content elements`);
    contentElements.forEach((element, index) => {
      console.log(`[ActionButtons] Element ${index}:`, element.className, element.textContent.slice(0, 50));
      if (!element.querySelector(".message-actions")) {
        console.log(`[ActionButtons] Adding action buttons to element ${index}`);
        addActionButtonsToElement(element);
      } else {
        console.log(`[ActionButtons] Action buttons already exist on element ${index}`);
      }
    });
  }, 50);

  // If the container was found, it was already in the DOM, no need to append again
  if (!document.getElementById(`message-${id}`)) {
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
  }
}

function createActionButtonGroup() {
  const container = document.createElement("div");
  container.className = "message-actions";
  container.setAttribute("role", "group");
  container.setAttribute("aria-label", "Message actions");

  // Copy button
  const copyButton = document.createElement("button");
  copyButton.className = "message-action-button copy-action";
  copyButton.innerHTML = '<span class="material-symbols-outlined">content_copy</span>';
  copyButton.setAttribute("aria-label", "Copy message");
  copyButton.setAttribute("title", "Copy to clipboard");
  copyButton.setAttribute("tabindex", "0");

  copyButton.addEventListener("click", async function (e) {
    e.stopPropagation();
    const textToCopy = extractTextFromContainer(this);

    try {
      await navigator.clipboard.writeText(textToCopy);
      const icon = copyButton.querySelector(".material-symbols-outlined");
      const originalIcon = icon.textContent;
      icon.textContent = "check";
      copyButton.classList.add("success");
      copyButton.setAttribute("aria-label", "Copied!");
      
      setTimeout(() => {
        icon.textContent = originalIcon;
        copyButton.classList.remove("success");
        copyButton.setAttribute("aria-label", "Copy message");
      }, 2000);
    } catch (err) {
      console.error("Failed to copy text:", err);
      copyButton.classList.add("error");
      setTimeout(() => {
        copyButton.classList.remove("error");
      }, 2000);
    }
  });

  // Speak button
  const speakButton = document.createElement("button");
  speakButton.className = "message-action-button speak-action";
  speakButton.innerHTML = '<span class="material-symbols-outlined">volume_up</span>';
  speakButton.setAttribute("aria-label", "Read message aloud");
  speakButton.setAttribute("title", "Text to speech");
  speakButton.setAttribute("tabindex", "0");

  // Track if this button is actively speaking
  let isThisButtonSpeaking = false;

  speakButton.addEventListener("click", async function (e) {
    e.stopPropagation();
    e.preventDefault();

    // Blur the button to prevent browser focus-related dropdowns
    this.blur();

    const icon = speakButton.querySelector(".material-symbols-outlined");

    // Check if currently speaking (pause icon is showing)
    if (icon.textContent === "pause" || isThisButtonSpeaking) {
      // Stop speaking - this is a pause/stop action
      isThisButtonSpeaking = false;
      icon.textContent = "volume_up";
      speakButton.setAttribute("aria-label", "Read message aloud");
      
      // Stop the speech completely
      speechStore.stop();
      
      // Reset all other speak buttons
      document.querySelectorAll('.speak-action .material-symbols-outlined').forEach(speakIcon => {
        if (speakIcon !== icon) {
          speakIcon.textContent = "volume_up";
          speakIcon.closest('.speak-action').setAttribute("aria-label", "Read message aloud");
        }
      });
      
      return; // Exit - this was a stop action, not a restart
    }

    // This is a start speaking action
    // First stop any other speaking and reset their buttons
    speechStore.stop();
    document.querySelectorAll('.speak-action .material-symbols-outlined').forEach(speakIcon => {
      speakIcon.textContent = "volume_up";
      speakIcon.closest('.speak-action').setAttribute("aria-label", "Read message aloud");
    });

    // Start speaking - pass the button element, not 'this' from the event handler
    const textToSpeak = extractTextFromContainer(speakButton);
    
    if (!textToSpeak.trim()) {
      console.warn("No text to speak");
      return;
    }

    try {
      isThisButtonSpeaking = true;
      icon.textContent = "pause";
      speakButton.setAttribute("aria-label", "Stop speaking");

      // Small delay to ensure UI updates
      await new Promise(resolve => setTimeout(resolve, 10));
      
      await speechStore.speak(textToSpeak);

      // Speech completed naturally
      if (isThisButtonSpeaking) {
        isThisButtonSpeaking = false;
        icon.textContent = "volume_up";
        speakButton.setAttribute("aria-label", "Read message aloud");
      }
    } catch (err) {
      console.error("Failed to speak text:", err);
      isThisButtonSpeaking = false;
      icon.textContent = "volume_up";
      speakButton.classList.add("error");
      setTimeout(() => {
        speakButton.classList.remove("error");
      }, 2000);
      speakButton.setAttribute("aria-label", "Read message aloud");
    }
  });

  container.appendChild(copyButton);
  container.appendChild(speakButton);
  
  return container;
}

function extractTextFromContainer(button) {
  // Get the action button container first
  const actionContainer = button.closest(".message-actions");
  if (!actionContainer) {
    console.error("Could not find message-actions container");
    return "";
  }
  
  // Get the parent element that contains both the content and the action buttons
  const parentElement = actionContainer.parentElement;
  if (!parentElement) {
    console.error("Could not find parent element");
    return "";
  }
  
  let textToExtract;

  // Check if this is a kvps row
  if (parentElement.classList.contains("kvps-row")) {
    // For kvps rows, we need to get the value from the second cell
    const kvpsVal = parentElement.querySelector(".kvps-val");
    if (kvpsVal) {
      // Get the actual value text, which might be in a pre/span element
      const preElement = kvpsVal.querySelector("pre");
      if (preElement) {
        textToExtract = preElement.innerText;
      } else {
        textToExtract = kvpsVal.innerText;
      }
    } else {
      textToExtract = "";
    }
  } else if (parentElement.classList.contains("msg-content") || parentElement.classList.contains("user-message-content")) {
    // Try to get text from pre element first (for user messages), then span, then the container itself
    const preElement = parentElement.querySelector("pre");
    const spanElement = parentElement.querySelector("span");
    
    if (preElement) {
      textToExtract = preElement.innerText;
    } else if (spanElement) {
      textToExtract = spanElement.innerText;
    } else {
      // Get text content but exclude the action buttons
      const clone = parentElement.cloneNode(true);
      const actionsInClone = clone.querySelector(".message-actions");
      if (actionsInClone) {
        actionsInClone.remove();
      }
      textToExtract = clone.innerText;
    }
  } else {
    console.warn("Unknown container type:", parentElement.className);
    textToExtract = parentElement.innerText;
  }

  return textToExtract || "";
}

function addActionButtonsToElement(element) {
  if (!element.querySelector(".message-actions")) {
    const actionGroup = createActionButtonGroup();
    element.appendChild(actionGroup);
    
    // Add viewport-aware positioning with sticky behavior
    function updateButtonPosition() {
      const rect = actionGroup.getBoundingClientRect();
      const containerRect = element.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const chatHistory = document.getElementById('chat-history');
      const chatHistoryRect = chatHistory ? chatHistory.getBoundingClientRect() : null;

      // Reset position classes
      actionGroup.classList.remove('position-left', 'position-bottom', 'position-sticky');

      // Get the effective bottom boundary (chat container or viewport, whichever is smaller)
      const effectiveBottom = chatHistoryRect ?
        Math.min(viewportHeight, chatHistoryRect.bottom) : viewportHeight;

      // Check if the container is partially out of viewport (for sticky behavior)
      if (containerRect.top < 0 && containerRect.bottom > 100) {
        // Container is scrolled partially out of view, make buttons sticky
        actionGroup.classList.add('position-sticky');
      } else {
        // Normal positioning checks
        if (rect.right > viewportWidth - 10) {
          actionGroup.classList.add('position-left');
        }

        // Check if buttons would be cut off at the bottom of chat container or viewport
        if (rect.bottom > effectiveBottom - 10) {
          actionGroup.classList.add('position-bottom');
        }

        // Special case: if message is very close to bottom of chat container,
        // ensure buttons stay within bounds
        if (chatHistoryRect && containerRect.bottom > chatHistoryRect.bottom - 60) {
          actionGroup.classList.add('position-bottom');
        }
      }
    }
    
    // Add device-specific behavior
    if (document.body.classList.contains("device-touch")) {
      // For touch devices, buttons are always visible (handled by CSS)
      // Just ensure proper positioning
      actionGroup.classList.add("visible");
      updateButtonPosition();

      // Add touch-friendly interaction
      element.addEventListener("touchstart", function(e) {
        // Only handle if not touching the buttons themselves
        if (!e.target.closest(".message-actions")) {
          // Hide all other visible action groups first
          document.querySelectorAll(".message-actions.visible").forEach(group => {
            if (group !== actionGroup) {
              group.classList.remove("visible");
            }
          });

          // Ensure this group is visible
          actionGroup.classList.add("visible");
          updateButtonPosition();
        }
      }, { passive: true });

      // Improve button responsiveness
      const buttons = actionGroup.querySelectorAll(".message-action-button");
      buttons.forEach(button => {
        // Add visual feedback for touch
        button.addEventListener("touchstart", function(e) {
          e.stopPropagation();
          this.style.transform = "scale(0.9)";
          this.style.background = "var(--color-accent)";
          this.style.color = "var(--color-background)";
          this.style.borderColor = "var(--color-accent)";
        }, { passive: true });

        button.addEventListener("touchend", function(e) {
          e.stopPropagation();
          // Reset visual state after a short delay
          setTimeout(() => {
            this.style.transform = "";
            this.style.background = "";
            this.style.color = "";
            this.style.borderColor = "";
          }, 150);
        }, { passive: true });

        button.addEventListener("touchcancel", function(e) {
          // Reset visual state if touch is cancelled
          this.style.transform = "";
          this.style.background = "";
          this.style.color = "";
          this.style.borderColor = "";
        }, { passive: true });

        // Ensure buttons are always clickable
        button.style.pointerEvents = "auto";
        button.style.touchAction = "manipulation";
      });

    } else {
      // For pointer devices, update position on hover
      element.addEventListener("mouseenter", function() {
        setTimeout(updateButtonPosition, 10);
      });
    }
    
    // Update position on window resize and scroll
    window.addEventListener("resize", updateButtonPosition);
    const chatHistory = document.getElementById("chat-history");
    if (chatHistory) {
      // Use throttled scroll handler for better performance
      let scrollTimeout;
      chatHistory.addEventListener("scroll", function() {
        if (scrollTimeout) clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(updateButtonPosition, 16); // ~60fps
      });
    }
    
    // Add keyboard support for all devices
    const buttons = actionGroup.querySelectorAll(".message-action-button");
    buttons.forEach((button, index) => {
      button.addEventListener("keydown", function(e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          button.click();
        } else if (e.key === "ArrowRight" || e.key === "ArrowDown") {
          e.preventDefault();
          const nextButton = buttons[index + 1] || buttons[0];
          nextButton.focus();
        } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
          e.preventDefault();
          const prevButton = buttons[index - 1] || buttons[buttons.length - 1];
          prevButton.focus();
        } else if (e.key === "Escape") {
          e.preventDefault();
          button.blur();
          if (document.body.classList.contains("device-touch")) {
            actionGroup.classList.remove("visible");
          }
        }
      });
    });
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
  const messageDiv = document.createElement("div");
  messageDiv.classList.add("message", mainClass, ...messageClasses);

  if (heading) {
    const headingElement = document.createElement("div");
    headingElement.classList.add("msg-heading");
    const headingH4 = document.createElement("h4");
    headingH4.innerHTML = convertIcons(escapeHTML(heading));
    headingElement.appendChild(headingH4);
    messageDiv.appendChild(headingElement);

    if (resizeBtns) {
      const minMaxBtn = document.createElement("div");
      minMaxBtn.classList.add("msg-min-max-btns");
      minMaxBtn.innerHTML = `
        <a href="#" class="msg-min-max-btn" @click.prevent="$store.messageResize.minimizeMessageClass('${mainClass}', $event)"><span class="material-symbols-outlined" x-text="$store.messageResize.getSetting('${mainClass}').minimized ? 'expand_content' : 'minimize'"></span></a>
        <a href="#" class="msg-min-max-btn" x-show="!$store.messageResize.getSetting('${mainClass}').minimized" @click.prevent="$store.messageResize.maximizeMessageClass('${mainClass}', $event)"><span class="material-symbols-outlined" x-text="$store.messageResize.getSetting('${mainClass}').maximized ? 'expand' : 'expand_all'"></span></a>
      `;
      headingElement.appendChild(minMaxBtn);
    }
  }

  const bodyDiv = document.createElement("div");
  bodyDiv.classList.add("message-body");
  messageDiv.appendChild(bodyDiv);

  drawKvps(bodyDiv, kvps, false);

  if (content && content.trim().length > 0) {
    if (markdown) {
      const contentDiv = document.createElement("div");
      contentDiv.classList.add("msg-content", ...contentClasses);

      const spanElement = document.createElement("span"); // Wrapper span
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

      contentDiv.appendChild(spanElement);
      addActionButtonsToElement(contentDiv);
      adjustMarkdownRender(contentDiv);
      bodyDiv.appendChild(contentDiv);
    } else {
      const preElement = document.createElement("pre");
      preElement.classList.add("msg-content", ...contentClasses);
      preElement.style.whiteSpace = "pre-wrap";
      preElement.style.wordBreak = "break-word";

      const spanElement = document.createElement("span");
      spanElement.innerHTML = convertHTML(content);

      // Click-to-copy removed - action buttons handle copying now

      preElement.appendChild(spanElement);
      addActionButtonsToElement(preElement);
      bodyDiv.appendChild(preElement);
    }
  }

  messageContainer.appendChild(messageDiv);

  if (followUp) {
    messageContainer.classList.add("message-followup");
  }

  // autoscroll the body if needed
  // if (getAutoScroll()) #TODO needs a better redraw system
    setTimeout(() => {
      bodyDiv.scrollTop = bodyDiv.scrollHeight;
    }, 0);

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
    textDiv.classList.add("msg-content", "user-message-content");

    // Create a span for the content
    const spanElement = document.createElement("pre");
    spanElement.innerHTML = escapeHTML(content);
    textDiv.appendChild(spanElement);

    // Click-to-copy removed - action buttons handle copying now

    addActionButtonsToElement(textDiv);
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
          addActionButtonsToElement(row);

          // Click-to-copy removed - action buttons handle copying now

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
  return str.replace("img://", "/image_get?path=");
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

// Initialize action buttons for existing messages when the page loads
document.addEventListener("DOMContentLoaded", function() {
  initializeActionButtons();
});

// Also initialize when the page is fully loaded (as a fallback)
window.addEventListener("load", function() {
  setTimeout(initializeActionButtons, 100);
});

// Function to initialize action buttons for all existing messages
function initializeActionButtons() {
  // Add action buttons to existing messages (including welcome message)
  const existingMessages = document.querySelectorAll(".msg-content, .kvps-row");
  existingMessages.forEach(element => {
    // Only add if not already present
    if (!element.querySelector(".message-actions")) {
      addActionButtonsToElement(element);
    }
  });

  // Force update button positions after a short delay to ensure proper layout
  setTimeout(() => {
    document.querySelectorAll(".message-actions").forEach(actionGroup => {
      const element = actionGroup.parentElement;
      if (element) {
        // Trigger position update for touch devices
        if (document.body.classList.contains("device-touch")) {
          actionGroup.classList.add("visible");
        }
      }
    });
  }, 200);
}

// Export the initialization function so it can be called manually if needed
export { initializeActionButtons };
