// copy button
import { openImageModal } from "./image_modal.js";
import { marked } from "../vendor/marked/marked.esm.js";
import { getAutoScroll, getContext } from "/index.js";
import { store as _messageResizeStore } from "/components/messages/resize/message-resize-store.js"; // keep here, required in html
import { store as attachmentsStore } from "/components/chat/attachments/attachmentsStore.js";
import { store as terminalStore } from "/components/terminal/terminal-store.js"; // terminal store

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
      }, 1000);
    } catch (err) {
      console.error("Failed to copy text:", err);
    }
  });

  return button;
}

function createTerminalButton(heading, kvps) {
  // Check if this is a terminal-related code execution message
  if (!heading || !heading.includes("icon://terminal")) {
    return null;
  }

  // Extract session number from heading or kvps
  let sessionNumber = 0;

  // Try to extract session number from heading like "[0]" or "[1]"
  const sessionMatch = heading.match(/\[(\d+)\]/);
  if (sessionMatch) {
    sessionNumber = parseInt(sessionMatch[1], 10);
  }

  // Or try to get session from kvps
  if (kvps && kvps.session !== undefined) {
    sessionNumber = parseInt(kvps.session, 10);
  }

  // Create terminal button
  const button = document.createElement("button");
  button.className = "terminal-button";
  button.innerHTML = `
    <i class="material-symbols-outlined">terminal</i>
    <span>Open Terminal</span>
  `;

  button.addEventListener("click", async function (e) {
    e.stopPropagation();

    // Get current context from imported function
    const currentContext = getContext();
    if (!currentContext) {
      console.error("No context available for terminal connection");
      return;
    }

    // Open terminal modal
    terminalStore.openTerminal(currentContext, sessionNumber);
  });

  return button;
}

function addCopyButtonToElement(element) {
  if (!element.querySelector(".copy-button")) {
    element.appendChild(createCopyButton());
  }
}

function addTerminalButtonToHeading(headingElement, heading, kvps) {
  const terminalButton = createTerminalButton(heading, kvps);
  if (terminalButton && !headingElement.querySelector(".terminal-button")) {
    // Add terminal button to heading after the h4 element
    const h4 = headingElement.querySelector("h4");
    if (h4) {
      h4.appendChild(terminalButton);
    }
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

    // Add terminal button for terminal-related code execution messages
    addTerminalButtonToHeading(headingElement, heading, kvps);

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

  // Content
  if (content) {
    const contentDiv = document.createElement("div");
    contentDiv.classList.add("msg-content", ...contentClasses);

    let processedContent = convertImageTags(content);

    if (markdown) {
      processedContent = marked.parse(processedContent);
    } else {
      processedContent = convertHTML(processedContent);
    }

    if (followUp) {
      processedContent = `${processedContent}<div class="msg-dots">${repeatString(".", 3)}</div>`;
    }

    const span = document.createElement("span");
    span.innerHTML = processedContent;
    contentDiv.appendChild(span);
    bodyDiv.appendChild(contentDiv);
    addCopyButtonToElement(contentDiv);

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

  messageContainer.appendChild(messageDiv);
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

function repeatString(str, count) {
  return str.repeat(count);
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
