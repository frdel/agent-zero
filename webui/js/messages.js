// copy button
import { openImageModal } from "./image_modal.js";
import { marked } from "https://cdn.jsdelivr.net/npm/marked/lib/marked.esm.js";

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
    case "canvas":
      return drawMessageCanvas;
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
  markdown = false
) {
  const messageDiv = document.createElement("div");
  messageDiv.classList.add("message", ...messageClasses);

  if (heading) {
    const headingElement = document.createElement("h4");
    headingElement.classList.add("msg-heading");
    headingElement.textContent = heading;
    messageDiv.appendChild(headingElement);
  }

  drawKvps(messageDiv, kvps, false);

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
      addCopyButtonToElement(contentDiv);
      messageDiv.appendChild(contentDiv);
    } else {
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
      messageDiv.appendChild(preElement);
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
  _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    false,
    kvps,
    ["message-ai", "message-default"],
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
    kvpsFlat,
    ["message-ai", "message-agent"],
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
    null,
    ["message-ai", "message-agent-response"],
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
    kvps,
    ["message-ai", "message-agent", "message-agent-delegation"],
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
    messageDiv.appendChild(textDiv);
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
  _drawMessage(
    messageContainer,
    heading,
    content,
    temp,
    true,
    kvps,
    ["message-ai", "message-tool"],
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
    null,
    ["message-ai", "message-code-exe"],
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
    kvps,
    ["message-ai", "message-browser"],
    ["msg-json"],
    false,
    false
  );
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
    ["message-info"],
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
    kvps,
    ["message-util"],
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
    ["message-warning"],
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
    ["message-error"],
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
          //   if (row.classList.contains("msg-thoughts")) {
          const span = document.createElement("span");
          span.innerHTML = convertHTML(value);
          pre.appendChild(span);
          td.appendChild(pre);
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
  result = convertImageTags(result);
  result = convertPathsToLinks(result);
  return result;
}

function convertImgFilePaths(str) {
  return str.replace("img://", "/image_get?path=");
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
    if (!parts[0]) parts.shift(); // drop empty element left of first “/”
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
      // if it *starts* with '<', it’s a tag -> leave untouched
      if (chunk.startsWith("<")) return chunk;
      // otherwise run your link-generation
      return chunk.replace(pathRegex, generateLinks);
    })
    .join("");
}

// function convertPathsToLinksInHtml(htmlString) {
//   // 1. Parse the input safely
//   const wrapper = document.createElement("div");
//   wrapper.innerHTML = htmlString;

//   // 2. Depth-first walk
//   function walk(node) {
//     // Skip <script> and <style> blocks entirely
//     if (node.nodeName === "SCRIPT" || node.nodeName === "STYLE") return;

//     if (node.nodeType === Node.TEXT_NODE) {
//       const original = node.nodeValue;
//       const replaced = convertPathsToLinks(original);
//       if (replaced !== original) {
//         // Turn the replacement HTML string into real nodes
//         const frag = document.createRange().createContextualFragment(replaced);
//         node.replaceWith(frag);
//       }
//     } else {
//       // Recurse into children
//       for (const child of Array.from(node.childNodes)) walk(child);
//     }
//   }

//   walk(wrapper);
//   return wrapper.innerHTML;
// }

export function drawMessageCanvas(
  messageContainer,
  id,
  type,
  heading,
  content,
  temp,
  kvps = null
) {
  console.log('Canvas: drawMessageCanvas called with kvps:', kvps);
  
  // Handle different canvas message types
  if (kvps && kvps.type === "canvas") {
    
    if (kvps.action === "start_streaming") {
      // Start real-time streaming mode
      const canvasId = kvps.canvas_id;
      const canvasTitle = kvps.metadata?.title || 'Live Canvas';
      const canvasType = kvps.metadata?.type || 'html';
      
      console.log('Canvas: Starting streaming mode for', canvasId);
      
      if (window.canvasManager) {
        window.canvasManager.startStreaming(canvasId, canvasTitle, canvasType);
      }
      
      // Create a minimal message for streaming start
      const streamingDiv = document.createElement('div');
      streamingDiv.classList.add('message', 'message-canvas', 'message-streaming');
      streamingDiv.innerHTML = `
        <div class="streaming-indicator">
          <i class="fas fa-paint-brush"></i>
          <span>Creating canvas artifact: ${canvasTitle}</span>
          <div class="streaming-dots">
            <span>.</span><span>.</span><span>.</span>
          </div>
        </div>
      `;
      messageContainer.appendChild(streamingDiv);
      return;
      
    } else if (kvps.action === "update_streaming") {
      // Update streaming content
      const canvasId = kvps.canvas_id;
      const contentChunk = kvps.content_chunk || '';
      const isComplete = kvps.is_complete || false;
      
      console.log('Canvas: Updating streaming content for', canvasId, 'chunk length:', contentChunk.length);
      
      if (window.canvasManager) {
        window.canvasManager.updateStreamingContent(canvasId, contentChunk, isComplete);
      }
      
      // Don't create a message for streaming updates
      return;
      
    } else if (kvps.action === "display") {
      // Create the in-chat artifact preview card
      createArtifactPreviewCard(messageContainer, kvps);
      
      // Also trigger canvas display in the UI with retry mechanism
      const displayCanvas = () => {
        if (window.canvasManager) {
          try {
            const metadata = kvps.metadata;
            const canvasUrl = metadata.url;
            const canvasTitle = metadata.title || 'Canvas Artifact';
            const canvasType = metadata.type || 'html';
            
            console.log('Canvas: Displaying artifact', {
              id: kvps.canvas_id,
              title: canvasTitle,
              type: canvasType,
              url: canvasUrl
            });
            
            // If we were streaming this canvas, finish streaming mode
            if (window.canvasManager.isStreamingCanvas(kvps.canvas_id)) {
              window.canvasManager.finishStreaming();
            }

            // Hide the left sidebar when canvas is shown
            window.toggleSidebar(false);

            // Show the canvas with the artifact content
            console.log('Canvas: About to call window.canvasManager.show() - opening canvas');
            window.canvasManager.show();
            console.log('Canvas: window.canvasManager.show() called successfully');
            
            // Update canvas title
            const titleElement = document.querySelector('.canvas-title');
            if (titleElement) {
              titleElement.textContent = canvasTitle;
            }
            
            // Update canvas content with the served URL
            setTimeout(() => {
              if (canvasUrl) {
                window.canvasManager.updateContent(canvasUrl, 'url');
              } else {
                console.warn('Canvas: No URL provided for canvas content');
              }
            }, 500); // Small delay to ensure canvas is shown
            
          } catch (error) {
            console.error('Canvas: Error displaying canvas artifact:', error);
          }
        } else {
          // Retry after a short delay if canvasManager isn't ready
          console.log('Canvas: canvasManager not ready, retrying...');
          setTimeout(displayCanvas, 100);
        }
      };
      
      displayCanvas();
      
      // Return early to avoid drawing the default message
      return;
    }
  }
  
  // Draw the message normally for non-canvas messages
  return drawMessageAgentPlain(
    ["message-canvas"],
    messageContainer,
    id,
    type,
    heading,
    content,
    temp,
    kvps
  );
}

// Create Claude-like artifact preview cards in chat
function createArtifactPreviewCard(messageContainer, kvps) {
  const metadata = kvps.metadata;
  const canvasId = kvps.canvas_id;
  const canvasUrl = metadata.url;
  const canvasTitle = metadata.title || 'Canvas Artifact';
  const canvasType = metadata.type || 'html';
  
  // Create the artifact card container
  const artifactCard = document.createElement('div');
  artifactCard.classList.add('artifact-card');
  artifactCard.setAttribute('data-canvas-id', canvasId);
  
  // Create the artifact header
  const artifactHeader = document.createElement('div');
  artifactHeader.classList.add('artifact-header');
  
  // Artifact icon based on type
  const artifactIcon = document.createElement('div');
  artifactIcon.classList.add('artifact-icon');
  artifactIcon.innerHTML = getArtifactIcon(canvasType);
  
  // Artifact title and type
  const artifactInfo = document.createElement('div');
  artifactInfo.classList.add('artifact-info');
  
  const artifactTitleEl = document.createElement('h4');
  artifactTitleEl.classList.add('artifact-title');
  artifactTitleEl.textContent = canvasTitle;
  
  const artifactTypeEl = document.createElement('span');
  artifactTypeEl.classList.add('artifact-type');
  artifactTypeEl.textContent = canvasType.toUpperCase();
  
  artifactInfo.appendChild(artifactTitleEl);
  artifactInfo.appendChild(artifactTypeEl);
  
  // Artifact actions
  const artifactActions = document.createElement('div');
  artifactActions.classList.add('artifact-actions');
  
  // Open in canvas button
  const openCanvasBtn = document.createElement('button');
  openCanvasBtn.classList.add('artifact-action-btn', 'artifact-open-btn');
  openCanvasBtn.innerHTML = '<i class="fas fa-external-link-alt"></i> Open';
  openCanvasBtn.title = 'Open in Canvas';
  openCanvasBtn.onclick = () => {
    if (window.canvasManager) {
      console.log('Canvas: About to call window.canvasManager.show() from artifact card open button');
      // Hide the left sidebar when canvas is shown
      window.toggleSidebar(false);
      window.canvasManager.show();
      console.log('Canvas: window.canvasManager.show() called from artifact card open button');
      if (canvasUrl) {
        window.canvasManager.updateContent(canvasUrl, 'url');
      }
      // Update canvas title
      const titleElement = document.querySelector('.canvas-title');
      if (titleElement) {
        titleElement.textContent = canvasTitle;
      }
    }
  };
  
  // Copy URL button
  const copyUrlBtn = document.createElement('button');
  copyUrlBtn.classList.add('artifact-action-btn', 'artifact-copy-btn');
  copyUrlBtn.innerHTML = '<i class="fas fa-copy"></i>';
  copyUrlBtn.title = 'Copy URL';
  copyUrlBtn.onclick = async () => {
    try {
      await navigator.clipboard.writeText(canvasUrl);
      copyUrlBtn.innerHTML = '<i class="fas fa-check"></i>';
      setTimeout(() => {
        copyUrlBtn.innerHTML = '<i class="fas fa-copy"></i>';
      }, 2000);
    } catch (err) {
      console.error('Failed to copy URL:', err);
    }
  };
  
  artifactActions.appendChild(openCanvasBtn);
  artifactActions.appendChild(copyUrlBtn);
  
  // Assemble header
  artifactHeader.appendChild(artifactIcon);
  artifactHeader.appendChild(artifactInfo);
  artifactHeader.appendChild(artifactActions);
  
  // Create the artifact preview
  const artifactPreview = document.createElement('div');
  artifactPreview.classList.add('artifact-preview');
  
  // Create preview iframe
  const previewIframe = document.createElement('iframe');
  previewIframe.classList.add('artifact-preview-iframe');
  previewIframe.src = canvasUrl;
  previewIframe.style.width = '100%';
  previewIframe.style.height = '200px';
  previewIframe.style.border = 'none';
  previewIframe.style.borderRadius = '8px';
  previewIframe.sandbox = 'allow-scripts allow-same-origin';
  
  // Handle iframe load errors
  previewIframe.onerror = () => {
    artifactPreview.innerHTML = `
      <div class="artifact-preview-error">
        <i class="fas fa-exclamation-triangle"></i>
        <p>Preview not available</p>
      </div>
    `;
  };
  
  artifactPreview.appendChild(previewIframe);
  
  // Assemble the complete card
  artifactCard.appendChild(artifactHeader);
  artifactCard.appendChild(artifactPreview);
  
  // Add click handler to the entire card for opening in canvas
  artifactCard.onclick = (e) => {
    // Don't trigger if clicking on action buttons
    if (!e.target.closest('.artifact-action-btn')) {
      console.log('Canvas: Artifact card clicked - delegating to open button');
      openCanvasBtn.onclick();
    }
  };
  
  // Add the artifact card to the message container
  messageContainer.appendChild(artifactCard);
}

// Get appropriate icon for artifact type
function getArtifactIcon(type) {
  const icons = {
    'html': '<i class="fab fa-html5"></i>',
    'css': '<i class="fab fa-css3-alt"></i>',
    'javascript': '<i class="fab fa-js-square"></i>',
    'js': '<i class="fab fa-js-square"></i>',
    'python': '<i class="fab fa-python"></i>',
    'markdown': '<i class="fab fa-markdown"></i>',
    'md': '<i class="fab fa-markdown"></i>',
    'json': '<i class="fas fa-code"></i>',
    'xml': '<i class="fas fa-code"></i>',
    'svg': '<i class="fas fa-image"></i>'
  };
  
  return icons[type.toLowerCase()] || '<i class="fas fa-file-code"></i>';
}
