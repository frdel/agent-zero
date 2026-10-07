// Message Action Buttons - DOM helpers for message action buttons

import { ICON_SELECTOR, setIconName } from "/js/icons.js";

const ACTION_ICON_MAP = {
  detail: "open_in_full",
  speak: "volume_up",
  copy: "content_copy",
};

const ACTION_LABELS = {
  detail: "View details",
  speak: "Speak",
  copy: "Copy",
};

function resolveActionIcon(icon) {
  if (!icon) return "";
  return ACTION_ICON_MAP[icon] || icon;
}

function buildActionLabel(icon, text) {
  const baseLabel = ACTION_LABELS[icon] || text || icon;
  if (text && ACTION_LABELS[icon]) return `${ACTION_LABELS[icon]} ${text}`;
  return baseLabel;
}

/**
 * Copy text to clipboard with fallback for non-secure contexts
 */
export async function copyToClipboard(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
  } else {
    // Fallback for local dev / non-secure contexts
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.cssText = "position:fixed;left:-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
  }
}

/**
 * Show visual feedback on a button (success/error state)
 */
export function showButtonFeedback(button, success, originalIcon) {
  const icon = button.querySelector(ICON_SELECTOR);
  if (!icon) return;
  
  setIconName(icon, success ? "check" : "error");
  button.classList.add(success ? "success" : "error");
  
  setTimeout(() => {
    setIconName(icon, originalIcon);
    button.classList.remove("success", "error");
  }, 1000);
}

export function syncActionButtons(container, actionButtons = []) {
  const previous = container.__managedActionButtons || [];
  const next = actionButtons.filter(Boolean).map((button, index) => {
    const existing = previous[index];
    if (
      existing?.isConnected &&
      existing.dataset.actionKey === button.dataset.actionKey
    ) {
      existing.__actionHandler = button.__actionHandler;
      return existing;
    }
    existing?.remove();
    return button;
  });
  // Re-inserting a mounted button detaches and remounts it, killing hover and clicks mid-stream
  next.forEach((button, index) => {
    const current = previous[index];
    if (current === button && current.isConnected) return;
    const anchor =
      current?.isConnected && current !== button
        ? current
        : [...container.children].find(
            (child) =>
              !previous.includes(child) &&
              !child.classList.contains("expand-btn"),
          );
    container.insertBefore(button, anchor || null);
  });
  previous.slice(next.length).forEach((button) => button.remove());
  container.__managedActionButtons = next;
}

/**
 * Create action button element
 *
 * @param {string} icon
 * @param {string} [text]
 * @param {(() => (any | Promise<any>)) | null} [handler]
 * @returns {HTMLButtonElement}
 */
export function createActionButton(icon, text = "", handler = null) {
  const iconName = resolveActionIcon(icon);

  const button = document.createElement("button");
  button.type = "button";
  button.className = `action-button action-${icon}`;
  button.dataset.actionKey = `${icon}:${text}`;
  button.__actionHandler = handler;
  const label = buildActionLabel(icon, text);
  if (label) {
    button.setAttribute("aria-label", label);
    button.setAttribute("title", label);
  }

  if (iconName) {
    const iconElement = document.createElement("x-icon");
    iconElement.name = iconName;
    button.appendChild(iconElement);
  } else if (text) {
    button.textContent = text;
  }

  button.addEventListener("click", async (event) => {
    event.stopPropagation();
    if (typeof button.__actionHandler !== "function") return;
    const shouldShowFeedback = Boolean(iconName); // icon === "copy" || icon === "speak";
    try {
      await button.__actionHandler();
      if (shouldShowFeedback) {
        showButtonFeedback(button, true, iconName);
      }
    } catch (err) {
      console.error("Action button failed:", err);
      if (shouldShowFeedback) {
        showButtonFeedback(button, false, iconName);
      }
    }
  });

  return button;
}
