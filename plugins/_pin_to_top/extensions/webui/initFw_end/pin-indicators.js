import { store } from "/plugins/_pin_to_top/webui/pin-to-top-store.js";

const TITLES = '#chats-section x-component[path$="sidebar/chats/chat-tree.html"] .chat-name, #tasks-section x-component[path$="sidebar/task-row.html"] .task-name';
let observer = null;

function addIndicator(title) {
  if (title.nextElementSibling?.classList.contains("pin-to-top-indicator")) return;
  const task = title.classList.contains("task-name");
  const item = task ? "task" : title.closest(".chat-child-list") ? "child" : "context";
  const icon = document.createElement("x-icon");
  icon.className = "pin-to-top-indicator";
  icon.setAttribute("name", "push_pin");
  icon.setAttribute("aria-label", "Pinned");
  icon.setAttribute("x-cloak", "");
  icon.setAttribute("x-show", `$store.pinToTop.isPinned('${task ? "task" : "chat"}', ${item}.id)`);
  title.after(icon);
}

function scan(root) {
  if (root.matches?.(TITLES)) addIndicator(root);
  root.querySelectorAll(TITLES).forEach(addIndicator);
}

export default function initPinIndicators() {
  if (observer) return;
  store.init();
  scan(document);
  observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node instanceof Element) scan(node);
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
}
