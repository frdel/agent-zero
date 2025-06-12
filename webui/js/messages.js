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
  latex = false
) {
  const messageDiv = document.createElement("div");
  messageDiv.classList.add("message", ...messageClasses);

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
    messageDiv.appendChild(preElement);

    // Render LaTeX math within the span - always try to render math
    if (window.renderMathInElement) {
      // Use setTimeout to ensure DOM is ready and content is fully processed
      setTimeout(() => {
        renderMathInElement(spanElement, {
          delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "$", right: "$", display: false }
          ],
          throwOnError: false,
          errorColor: '#cc0000',
          strict: false,
          trust: true,
          macros: {
            "\\RR": "\\mathbb{R}",
            "\\NN": "\\mathbb{N}",
            "\\ZZ": "\\mathbb{Z}",
            "\\QQ": "\\mathbb{Q}",
            "\\CC": "\\mathbb{C}"
          }
        });
      }, 100);
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

          if (window.renderMathInElement) {
            // Use setTimeout to ensure DOM is ready and content is fully processed
            setTimeout(() => {
              renderMathInElement(span, {
                delimiters: [
                  { left: "$$", right: "$$", display: true },
                  { left: "$", right: "$", display: false }
                ],
                throwOnError: false,
                errorColor: '#cc0000',
                strict: false,
                trust: true,
                macros: {
                  "\\RR": "\\mathbb{R}",
                  "\\NN": "\\mathbb{N}",
                  "\\ZZ": "\\mathbb{Z}",
                  "\\QQ": "\\mathbb{Q}",
                  "\\CC": "\\mathbb{C}"
                }
              });
            }, 100);
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

// SOLUÇÃO DEFINITIVA: CORREÇÃO ROBUSTA DE COMANDOS LATEX TRUNCADOS
// Implementação sistemática sem loops infinitos

function processLatexCorrections(str) {
  let result = str;
  
  // ========== ETAPA 1: CORREÇÃO DE COMANDOS TRUNCADOS (ABORDAGEM SIMPLES) ==========
  
  // 1.1 - Corrigir rac{x}{y} → $\frac{x}{y}$ (frações)
  result = result.replace(/\brac\{([^}]*)\}\{([^}]*)\}/g, '$\\frac{$1}{$2}$');
  
  // 1.2 - Corrigir extbf{texto} → **texto** (negrito)
  result = result.replace(/\bextbf\{([^}]*)\}/g, '**$1**');
  
  // 1.3 - Corrigir imes seguido de números
  result = result.replace(/\bimes\s*([0-9]+(?:[,\.]\d+)*)/g, '$\\times$ $1');
  
  // 1.4 - Corrigir imes isolado
  result = result.replace(/\bimes(?![0-9])/g, '$\\times$');
  
  // ========== ETAPA 2: NORMALIZAÇÃO DE COMANDOS COM BARRA ==========
  
  // 2.1 - Corrigir comandos já com barra mas incorretos
  result = result.replace(/\\rac\{([^}]*)\}\{([^}]*)\}/g, '$\\frac{$1}{$2}$');
  result = result.replace(/\\extbf\{([^}]*)\}/g, '**$1**');
  result = result.replace(/\\imes\b/g, '$\\times$');
  
  // ========== ETAPA 3: OUTROS COMANDOS TRUNCADOS ==========
  
  // 3.1 - Corrigir qrt{} → $\sqrt{}$
  result = result.replace(/\bqrt\{([^}]*)\}/g, '$\\sqrt{$1}$');
  
  // 3.2 - Corrigir um{} → $\sum{}$
  result = result.replace(/\bum\{([^}]*)\}/g, '$\\sum{$1}$');
  
  // ========== ETAPA 4: LIMPEZA E CONSOLIDAÇÃO ==========
  
  // 4.1 - Consolidar delimitadores $ múltiplos
  result = result.replace(/\$+/g, '$');
  
  // 4.3 - NÃO limpar espaços - preservar formatação original
  
  // 4.4 - Balancear delimitadores finais
  const dollarCount = (result.match(/\$/g) || []).length;
  if (dollarCount % 2 !== 0) {
    result += '$';
  }
  
  return result;
}

function convertHTML(str) {
  if (typeof str !== "string") str = JSON.stringify(str, null, 2);

  // Check if marked library is available
  if (typeof marked !== 'undefined') {
    try {
      // Configure marked options for better rendering
      marked.setOptions({
        breaks: true,        // Convert \n to <br>
        gfm: true,          // GitHub Flavored Markdown
        tables: true,       // Enable table support
        sanitize: false,    // We'll handle sanitization ourselves
        smartypants: false, // Disable smartypants to avoid conflicts with LaTeX
        xhtml: false,       // Don't use XHTML self-closing tags
        headerIds: false,   // Don't generate header IDs
        mangle: false,      // Don't mangle email addresses
        highlight: function(code, lang) {
          // Basic syntax highlighting for common languages
          if (lang === 'python') {
            return code
              .replace(/\b(def|class|import|from|return|if|else|elif|for|while|try|except|with|as)\b/g, '<span style="color: #569cd6;">$1</span>')
              .replace(/\b(True|False|None)\b/g, '<span style="color: #4fc1ff;">$1</span>')
              .replace(/(#.*$)/gm, '<span style="color: #6a9955;">$1</span>');
          } else if (lang === 'javascript' || lang === 'js') {
            return code
              .replace(/\b(function|const|let|var|return|if|else|for|while|class|extends)\b/g, '<span style="color: #569cd6;">$1</span>')
              .replace(/\b(true|false|null|undefined)\b/g, '<span style="color: #4fc1ff;">$1</span>')
              .replace(/(\/\/.*$)/gm, '<span style="color: #6a9955;">$1</span>');
          } else if (lang === 'bash' || lang === 'sh') {
            return code
              .replace(/^(\$|#)\s*/gm, '<span style="color: #569cd6;">$1</span>')
              .replace(/(#.*$)/gm, '<span style="color: #6a9955;">$1</span>');
          }
          return code;
        }
      });
      
      // SOLUÇÃO DEFINITIVA: Processar correções LaTeX de forma robusta
      let processedStr = processLatexCorrections(str);
      
      // Detect if content looks like markdown (after LaTeX pre-processing)
      const hasMarkdownSyntax = /(\*\*[^*]*?\*\*|\*[^*]*?\*|__[^_]*?__|_[^_]*?_|`[^`]*?`|^#{1,6}\s|^\s*[-*+]\s|^\s*\d+\.\s|^>|^\|.*\||```)/m.test(processedStr);
      
      let result;
      if (hasMarkdownSyntax) {
        // For markdown content, let marked.js handle it normally
        // LaTeX math will be processed later by KaTeX
        result = marked.parse(processedStr);
      } else {
        // For plain text, escape HTML but preserve line breaks
        result = escapeHTML(processedStr).replace(/\n/g, '<br>');
      }
      
      // Apply our custom conversions
      result = convertPathsToLinks(result);
      result = convertImageTags(result);
      
      return result;
    } catch (error) {
      console.warn('Markdown parsing failed, falling back to plain text:', error);
      // Fallback to original behavior if markdown parsing fails
      let result = escapeHTML(str);
      result = convertPathsToLinks(result);
      result = convertImageTags(result);
      return result;
    }
  } else {
    // Fallback to original behavior if marked is not available
    let result = escapeHTML(str);
    result = convertPathsToLinks(result);
    result = convertImageTags(result);
    return result;
  }
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

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
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
