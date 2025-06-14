// copy button
import { openImageModal } from "./image_modal.js";

function createCopyButton() {
  const button = document.createElement("button");
  button.className = "copy-button";
  button.textContent = "Copy";

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

  // Get current states from localStorage
  let isHidden = localStorage.getItem(`msgHidden_${type}`) === 'true';
  let isFullHeight = localStorage.getItem(`msgFullHeight_${type}`) === 'true';

  // Function to apply state to ALL messages of this type
  const updateAllMessagesOfType = () => {
    const messageSelector = getMessageSelectorForType(type);
    const allMessagesOfType = document.querySelectorAll(messageSelector);
    
    allMessagesOfType.forEach(msg => {
      // Remove all state classes
      msg.classList.remove("message-collapsed", "message-scroll", "message-expanded");
      
      // Apply current state
      if (isHidden) {
        msg.classList.add("message-collapsed");
      } else {
        // Check global preference
        const isFixedHeightGlobal = localStorage.getItem('fixedHeight') !== 'false';
        if (isFixedHeightGlobal) {
          // Global preference overrides: always use scroll
          msg.classList.add("message-scroll");
        } else if (isFullHeight) {
          // Global allows expansion and user wants full height
          msg.classList.add("message-expanded");
        } else {
          // Default to expanded when global preference is off
          msg.classList.add("message-expanded");
        }
      }
    });

    // Update button visual states
    updateButtonStates();
  };

  // Toggle hide/show content
  const toggleVisibility = () => {
    isHidden = !isHidden;
    localStorage.setItem(`msgHidden_${type}`, isHidden);
    updateAllMessagesOfType();
  };

  // Toggle height (works as local override)
  const toggleHeight = () => {
    isFullHeight = !isFullHeight;
    localStorage.setItem(`msgFullHeight_${type}`, isFullHeight);
    updateAllMessagesOfType();
  };

  // Create buttons with clear, intuitive icons
  const hideBtn = createControlButton("", "", toggleVisibility);
  const heightBtn = createControlButton("", "", toggleHeight);

  hideBtn.classList.add('message-hide-btn');
  heightBtn.classList.add('message-height-btn');

  const updateButtonStates = () => {
    // Update hide/show button with better icons
    hideBtn.classList.toggle('active', isHidden);
    if (isHidden) {
      hideBtn.innerHTML = '👁️'; // Eye open - click to show
      hideBtn.style.color = '#10b981'; // Green when showing
      hideBtn.title = `Show all ${type} messages`;
    } else {
      hideBtn.innerHTML = '🫥'; // Hidden face - click to hide
      hideBtn.style.color = '#6b7280'; // Gray when visible
      hideBtn.title = `Hide all ${type} messages (show headings only)`;
    }

    // Update height button with better icons
    heightBtn.classList.toggle('active', isFullHeight);
    const isFixedHeightGlobal = localStorage.getItem('fixedHeight') !== 'false';
    
    if (isFixedHeightGlobal && !isFullHeight) {
      // Global fixed height mode, not expanded
      heightBtn.innerHTML = '📋'; // Clipboard - fixed height
      heightBtn.style.color = '#3b82f6'; // Blue for fixed
      heightBtn.title = `Expand all ${type} messages (override global setting)`;
    } else if (isFullHeight) {
      // Expanded mode
      heightBtn.innerHTML = '📄'; // Page - full height
      heightBtn.style.color = '#10b981'; // Green for expanded
      heightBtn.title = `Set all ${type} messages to scroll height`;
    } else {
      // Default expanded when global is off
      heightBtn.innerHTML = '📄'; // Page - full height
      heightBtn.style.color = '#10b981'; // Green for expanded
      heightBtn.title = `Set all ${type} messages to scroll height`;
    }
  };

  controls.append(hideBtn, heightBtn);
  messageDiv.prepend(controls);

  // Only add console summary for actual console/code execution messages
  if (type === 'code_exe' && command && command.trim().length > 0) {
    const summary = document.createElement("pre");
    summary.className = "console-summary";
    summary.textContent = command.split("\n")[0];
    messageDiv.insertBefore(summary, controls.nextSibling);
  }

  // Initialize button states and apply to messages
  updateAllMessagesOfType();
}

// Helper function to get CSS selector for message type
function getMessageSelectorForType(type) {
  switch (type) {
    case 'agent': return '.message-agent';
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
    null,
    ["message-ai", "message-agent-response"],
    [],
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
  injectConsoleControls(messageDiv, content || "", 'user');

  const headingElement = document.createElement("h4");
  headingElement.textContent = "User message";
  messageDiv.appendChild(headingElement);

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
  _drawMessage(
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
  // Find the message div inside the container and add controls
  const messageDiv = messageContainer.querySelector('.message');
  if (messageDiv) {
    injectConsoleControls(messageDiv, content || "", 'info');
  }
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
  // Find the message div inside the container and add controls
  const messageDiv = messageContainer.querySelector('.message');
  if (messageDiv) {
    injectConsoleControls(messageDiv, content || "", 'warning');
  }
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
  // Find the message div inside the container and add controls
  const messageDiv = messageContainer.querySelector('.message');
  if (messageDiv) {
    injectConsoleControls(messageDiv, content || "", 'error');
  }
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
          addCopyButtonToElement(row);

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
      //   } else {
      //     pre.textContent = value;

      //     // Add click handler
      //     pre.addEventListener("click", () => {
      //       copyText(value, pre);
      //     });

      //     td.appendChild(pre);
      //     addCopyButtonToElement(row);
      //   }
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
