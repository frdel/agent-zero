import * as msgs from "/js/messages.js";
import * as api from "/js/api.js";
import * as css from "/js/css.js";
import { sleep } from "/js/sleep.js";
import { store as attachmentsStore } from "/components/chat/attachments/attachmentsStore.js";
import { store as speechStore } from "/components/chat/speech/speech-store.js";
import { store as notificationStore } from "/components/notifications/notification-store.js";

globalThis.fetchApi = api.fetchApi; // TODO - backward compatibility for non-modular scripts, remove once refactored to alpine

const leftPanel = document.getElementById("left-panel");
const rightPanel = document.getElementById("right-panel");
const container = document.querySelector(".container");
const chatInput = document.getElementById("chat-input");
const chatHistory = document.getElementById("chat-history");
const sendButton = document.getElementById("send-button");
const inputSection = document.getElementById("input-section");
const statusSection = document.getElementById("status-section");
const chatsSection = document.getElementById("chats-section");
const tasksSection = document.getElementById("tasks-section");
const progressBar = document.getElementById("progress-bar");
const autoScrollSwitch = document.getElementById("auto-scroll-switch");
const timeDate = document.getElementById("time-date-container");

let autoScroll = true;
let context = "";
let resetCounter = 0;
let skipOneSpeech = false;
let connectionStatus = undefined; // undefined = not checked yet, true = connected, false = disconnected

// Initialize the toggle button
setupSidebarToggle();
// Initialize tabs
setupTabs();

export function getAutoScroll() {
  return autoScroll;
}

function isMobile() {
  return window.innerWidth <= 768;
}

function toggleSidebar(show) {
  const overlay = document.getElementById("sidebar-overlay");
  if (typeof show === "boolean") {
    leftPanel.classList.toggle("hidden", !show);
    rightPanel.classList.toggle("expanded", !show);
    overlay.classList.toggle("visible", show);
  } else {
    leftPanel.classList.toggle("hidden");
    rightPanel.classList.toggle("expanded");
    overlay.classList.toggle(
      "visible",
      !leftPanel.classList.contains("hidden")
    );
  }
}

function handleResize() {
  const overlay = document.getElementById("sidebar-overlay");
  if (isMobile()) {
    leftPanel.classList.add("hidden");
    rightPanel.classList.add("expanded");
    overlay.classList.remove("visible");
  } else {
    leftPanel.classList.remove("hidden");
    rightPanel.classList.remove("expanded");
    overlay.classList.remove("visible");
  }
}

globalThis.addEventListener("load", handleResize);
globalThis.addEventListener("resize", handleResize);

document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("sidebar-overlay");
  overlay.addEventListener("click", () => {
    if (isMobile()) {
      toggleSidebar(false);
    }
  });
});

function setupSidebarToggle() {
  const leftPanel = document.getElementById("left-panel");
  const rightPanel = document.getElementById("right-panel");
  const toggleSidebarButton = document.getElementById("toggle-sidebar");
  if (toggleSidebarButton) {
    toggleSidebarButton.addEventListener("click", toggleSidebar);
  } else {
    console.error("Toggle sidebar button not found");
    setTimeout(setupSidebarToggle, 100);
  }
}
document.addEventListener("DOMContentLoaded", setupSidebarToggle);

export async function sendMessage() {
  try {
    const message = chatInput.value.trim();
    const attachmentsWithUrls = attachmentsStore.getAttachmentsForSending();
    const hasAttachments = attachmentsWithUrls.length > 0;

    if (message || hasAttachments) {
      let response;
      const messageId = generateGUID();

      // Clear input and attachments
      chatInput.value = "";
      attachmentsStore.clearAttachments();
      adjustTextareaHeight();

      // Include attachments in the user message
      if (hasAttachments) {
        const heading =
          attachmentsWithUrls.length > 0
            ? "Uploading attachments..."
            : "User message";

        // Render user message with attachments
        setMessage(messageId, "user", heading, message, false, {
          // attachments: attachmentsWithUrls, // skip here, let the backend properly log them
        });

        // sleep one frame to render the message before upload starts - better UX
        sleep(0);

        const formData = new FormData();
        formData.append("text", message);
        formData.append("context", context);
        formData.append("message_id", messageId);

        for (let i = 0; i < attachmentsWithUrls.length; i++) {
          formData.append("attachments", attachmentsWithUrls[i].file);
        }

        response = await api.fetchApi("/message_async", {
          method: "POST",
          body: formData,
        });
      } else {
        // For text-only messages
        const data = {
          text: message,
          context,
          message_id: messageId,
        };
        response = await api.fetchApi("/message_async", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(data),
        });
      }

      // Handle response
      const jsonResponse = await response.json();
      if (!jsonResponse) {
        toast("No response returned.", "error");
      } else {
        setContext(jsonResponse.context);
      }
    }
  } catch (e) {
    toastFetchError("Error sending message", e); // Will use new notification system
  }
}

function toastFetchError(text, error) {
  console.error(text, error);
  // Use new frontend error notification system (async, but we don't need to wait)
  const errorMessage = error?.message || error?.toString() || "Unknown error";

  if (getConnectionStatus()) {
    // Backend is connected, just show the error
    toastFrontendError(`${text}: ${errorMessage}`).catch((e) =>
      console.error("Failed to show error toast:", e)
    );
  } else {
    // Backend is disconnected, show connection error
    toastFrontendError(
      `${text} (backend appears to be disconnected): ${errorMessage}`,
      "Connection Error"
    ).catch((e) => console.error("Failed to show connection error toast:", e));
  }
}
globalThis.toastFetchError = toastFetchError;

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendButton.addEventListener("click", sendMessage);

export function updateChatInput(text) {
  console.log("updateChatInput called with:", text);

  // Append text with proper spacing
  const currentValue = chatInput.value;
  const needsSpace = currentValue.length > 0 && !currentValue.endsWith(" ");
  chatInput.value = currentValue + (needsSpace ? " " : "") + text + " ";

  // Adjust height and trigger input event
  adjustTextareaHeight();
  chatInput.dispatchEvent(new Event("input"));

  console.log("Updated chat input value:", chatInput.value);
}

function updateUserTime() {
  const now = new Date();
  const hours = now.getHours();
  const minutes = now.getMinutes();
  const seconds = now.getSeconds();
  const ampm = hours >= 12 ? "pm" : "am";
  const formattedHours = hours % 12 || 12;

  // Format the time
  const timeString = `${formattedHours}:${minutes
    .toString()
    .padStart(2, "0")}:${seconds.toString().padStart(2, "0")} ${ampm}`;

  // Format the date
  const options = { year: "numeric", month: "short", day: "numeric" };
  const dateString = now.toLocaleDateString(undefined, options);

  // Update the HTML
  const userTimeElement = document.getElementById("time-date");
  userTimeElement.innerHTML = `${timeString}<br><span id="user-date">${dateString}</span>`;
}

updateUserTime();
setInterval(updateUserTime, 1000);

function setMessage(id, type, heading, content, temp, kvps = null) {
  const result = msgs.setMessage(id, type, heading, content, temp, kvps);
  if (autoScroll) chatHistory.scrollTop = chatHistory.scrollHeight;
  return result;
}

globalThis.loadKnowledge = async function () {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".txt,.pdf,.csv,.html,.json,.md";
  input.multiple = true;

  input.onchange = async () => {
    try {
      const formData = new FormData();
      for (let file of input.files) {
        formData.append("files[]", file);
      }

      formData.append("ctxid", getContext());

      const response = await api.fetchApi("/import_knowledge", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        toast(await response.text(), "error");
      } else {
        const data = await response.json();
        toast(
          "Knowledge files imported: " + data.filenames.join(", "),
          "success"
        );
      }
    } catch (e) {
      toastFetchError("Error loading knowledge", e);
    }
  };

  input.click();
};

function adjustTextareaHeight() {
  chatInput.style.height = "auto";
  chatInput.style.height = chatInput.scrollHeight + "px";
}

export const sendJsonData = async function (url, data) {
  return await api.callJsonApi(url, data);
  // const response = await api.fetchApi(url, {
  //     method: 'POST',
  //     headers: {
  //         'Content-Type': 'application/json'
  //     },
  //     body: JSON.stringify(data)
  // });

  // if (!response.ok) {
  //     const error = await response.text();
  //     throw new Error(error);
  // }
  // const jsonResponse = await response.json();
  // return jsonResponse;
};
globalThis.sendJsonData = sendJsonData;

function generateGUID() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    var r = (Math.random() * 16) | 0;
    var v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function getConnectionStatus() {
  return connectionStatus;
}

function setConnectionStatus(connected) {
  connectionStatus = connected;
  if (globalThis.Alpine && timeDate) {
    const statusIconEl = timeDate.querySelector(".status-icon");
    if (statusIconEl) {
      const statusIcon = Alpine.$data(statusIconEl);
      if (statusIcon) {
        statusIcon.connected = connected;
      }
    }
  }
}

let lastLogVersion = 0;
let lastLogGuid = "";
let lastSpokenNo = 0;

async function poll() {
  let updated = false;
  try {
    // Get timezone from navigator
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    const log_from = lastLogVersion;
    const response = await sendJsonData("/poll", {
      log_from: log_from,
      notifications_from: notificationStore.lastNotificationVersion || 0,
      context: context || null,
      timezone: timezone,
    });

    // Check if the response is valid
    if (!response) {
      console.error("Invalid response from poll endpoint");
      return false;
    }

    if (!context) setContext(response.context);
    if (response.context != context) return; //skip late polls after context change

    // if the chat has been reset, restart this poll as it may have been called with incorrect log_from
    if (lastLogGuid != response.log_guid) {
      chatHistory.innerHTML = "";
      lastLogVersion = 0;
      lastLogGuid = response.log_guid;
      await poll();
      return;
    }

    if (lastLogVersion != response.log_version) {
      updated = true;
      for (const log of response.logs) {
        const messageId = log.id || log.no; // Use log.id if available
        setMessage(
          messageId,
          log.type,
          log.heading,
          log.content,
          log.temp,
          log.kvps
        );
      }
      afterMessagesUpdate(response.logs);
    }

    lastLogVersion = response.log_version;
    lastLogGuid = response.log_guid;

    updateProgress(response.log_progress, response.log_progress_active);

    // Update notifications from response
    notificationStore.updateFromPoll(response);

    //set ui model vars from backend
    if (globalThis.Alpine && inputSection) {
      const inputAD = Alpine.$data(inputSection);
      if (inputAD) {
        inputAD.paused = response.paused;
      }
    }

    // Update status icon state
    setConnectionStatus(true);

    // Update chats list and sort by created_at time (newer first)
    let chatsAD = null;
    let contexts = response.contexts || [];
    if (globalThis.Alpine && chatsSection) {
      chatsAD = Alpine.$data(chatsSection);
      if (chatsAD) {
        chatsAD.contexts = contexts.sort(
          (a, b) => (b.created_at || 0) - (a.created_at || 0)
        );
      }
    }

    // Update tasks list and sort by creation time (newer first)
    const tasksSection = document.getElementById("tasks-section");
    if (globalThis.Alpine && tasksSection) {
      const tasksAD = Alpine.$data(tasksSection);
      if (tasksAD) {
        let tasks = response.tasks || [];

        // Always update tasks to ensure state changes are reflected
        if (tasks.length > 0) {
          // Sort the tasks by creation time
          const sortedTasks = [...tasks].sort(
            (a, b) => (b.created_at || 0) - (a.created_at || 0)
          );

          // Assign the sorted tasks to the Alpine data
          tasksAD.tasks = sortedTasks;
        } else {
          // Make sure to use a new empty array instance
          tasksAD.tasks = [];
        }
      }
    }

    // Make sure the active context is properly selected in both lists
    if (context) {
      // Update selection in the active tab
      const activeTab = localStorage.getItem("activeTab") || "chats";

      if (activeTab === "chats" && chatsAD) {
        chatsAD.selected = context;
        localStorage.setItem("lastSelectedChat", context);

        // Check if this context exists in the chats list
        const contextExists = contexts.some((ctx) => ctx.id === context);

        // If it doesn't exist in the chats list but we're in chats tab, try to select the first chat
        if (!contextExists && contexts.length > 0) {
          // Check if the current context is empty before creating a new one
          // If there's already a current context and we're just updating UI, don't automatically
          // create a new context by calling setContext
          const firstChatId = contexts[0].id;

          // Only create a new context if we're not currently in an existing context
          // This helps prevent duplicate contexts when switching tabs
          setContext(firstChatId);
          chatsAD.selected = firstChatId;
          localStorage.setItem("lastSelectedChat", firstChatId);
        }
      } else if (activeTab === "tasks" && tasksSection) {
        const tasksAD = Alpine.$data(tasksSection);
        tasksAD.selected = context;
        localStorage.setItem("lastSelectedTask", context);

        // Check if this context exists in the tasks list
        const taskExists = response.tasks?.some((task) => task.id === context);

        // If it doesn't exist in the tasks list but we're in tasks tab, try to select the first task
        if (!taskExists && response.tasks?.length > 0) {
          const firstTaskId = response.tasks[0].id;
          setContext(firstTaskId);
          tasksAD.selected = firstTaskId;
          localStorage.setItem("lastSelectedTask", firstTaskId);
        }
      }
    } else if (
      response.tasks &&
      response.tasks.length > 0 &&
      localStorage.getItem("activeTab") === "tasks"
    ) {
      // If we're in tasks tab with no selection but have tasks, select the first one
      const firstTaskId = response.tasks[0].id;
      setContext(firstTaskId);
      if (tasksSection) {
        const tasksAD = Alpine.$data(tasksSection);
        tasksAD.selected = firstTaskId;
        localStorage.setItem("lastSelectedTask", firstTaskId);
      }
    } else if (
      contexts.length > 0 &&
      localStorage.getItem("activeTab") === "chats" &&
      chatsAD
    ) {
      // If we're in chats tab with no selection but have chats, select the first one
      const firstChatId = contexts[0].id;

      // Only set context if we don't already have one to avoid duplicates
      if (!context) {
        setContext(firstChatId);
        chatsAD.selected = firstChatId;
        localStorage.setItem("lastSelectedChat", firstChatId);
      }
    }

    lastLogVersion = response.log_version;
    lastLogGuid = response.log_guid;
  } catch (error) {
    console.error("Error:", error);
    setConnectionStatus(false);
  }

  return updated;
}

function afterMessagesUpdate(logs) {
  if (localStorage.getItem("speech") == "true") {
    speakMessages(logs);
  }
}

function speakMessages(logs) {
  if (skipOneSpeech) {
    skipOneSpeech = false;
    return;
  }
  // log.no, log.type, log.heading, log.content
  for (let i = logs.length - 1; i >= 0; i--) {
    const log = logs[i];

    // if already spoken, end
    // if(log.no < lastSpokenNo) break;

    // finished response
    if (log.type == "response") {
      // lastSpokenNo = log.no;
      speechStore.speakStream(
        getChatBasedId(log.no),
        log.content,
        log.kvps?.finished
      );
      return;

      // finished LLM headline, not response
    } else if (
      log.type == "agent" &&
      log.kvps &&
      log.kvps.headline &&
      log.kvps.tool_args &&
      log.kvps.tool_name != "response"
    ) {
      // lastSpokenNo = log.no;
      speechStore.speakStream(getChatBasedId(log.no), log.kvps.headline, true);
      return;
    }
  }
}

function updateProgress(progress, active) {
  if (!progress) progress = "";

  if (!active) {
    removeClassFromElement(progressBar, "shiny-text");
  } else {
    addClassToElement(progressBar, "shiny-text");
  }

  progress = msgs.convertIcons(progress);

  if (progressBar.innerHTML != progress) {
    progressBar.innerHTML = progress;
  }
}

globalThis.pauseAgent = async function (paused) {
  try {
    const resp = await sendJsonData("/pause", { paused: paused, context });
  } catch (e) {
    globalThis.toastFetchError("Error pausing agent", e);
  }
};

globalThis.resetChat = async function (ctxid = null) {
  try {
    const resp = await sendJsonData("/chat_reset", {
      context: ctxid === null ? context : ctxid,
    });
    resetCounter++;
    if (ctxid === null) updateAfterScroll();
  } catch (e) {
    globalThis.toastFetchError("Error resetting chat", e);
  }
};

globalThis.newChat = async function () {
  try {
    setContext(generateGUID());
    updateAfterScroll();
  } catch (e) {
    globalThis.toastFetchError("Error creating new chat", e);
  }
};

globalThis.killChat = async function (id) {
  if (!id) {
    console.error("No chat ID provided for deletion");
    return;
  }

  console.log("Deleting chat with ID:", id);

  try {
    const chatsAD = Alpine.$data(chatsSection);
    console.log(
      "Current contexts before deletion:",
      JSON.stringify(chatsAD.contexts.map((c) => ({ id: c.id, name: c.name })))
    );

    // switch to another context if deleting current
    switchFromContext(id);

    // Delete the chat on the server
    await sendJsonData("/chat_remove", { context: id });

    // Update the UI manually to ensure the correct chat is removed
    // Deep clone the contexts array to prevent reference issues
    const updatedContexts = chatsAD.contexts.filter((ctx) => ctx.id !== id);
    console.log(
      "Updated contexts after deletion:",
      JSON.stringify(updatedContexts.map((c) => ({ id: c.id, name: c.name })))
    );

    // Force UI update by creating a new array
    chatsAD.contexts = [...updatedContexts];

    updateAfterScroll();

    justToast("Chat deleted successfully", "success", 1000, "chat-removal");
  } catch (e) {
    console.error("Error deleting chat:", e);
    globalThis.toastFetchError("Error deleting chat", e);
  }
};

export function switchFromContext(id) {
  // If we're deleting the currently selected chat, switch to another one first
  if (context === id) {
    const chatsAD = Alpine.$data(chatsSection);

    // Find an alternate chat to switch to if we're deleting the current one
    let alternateChat = null;
    for (let i = 0; i < chatsAD.contexts.length; i++) {
      if (chatsAD.contexts[i].id !== id) {
        alternateChat = chatsAD.contexts[i];
        break;
      }
    }

    if (alternateChat) {
      setContext(alternateChat.id);
    } else {
      // If no other chats, create a new empty context
      setContext(generateGUID());
    }
  }
}

// Function to ensure proper UI state when switching contexts
function ensureProperTabSelection(contextId) {
  // Get current active tab
  const activeTab = localStorage.getItem("activeTab") || "chats";

  // First attempt to determine if this is a task or chat based on the task list
  const tasksSection = document.getElementById("tasks-section");
  let isTask = false;

  if (tasksSection) {
    const tasksAD = Alpine.$data(tasksSection);
    if (tasksAD && tasksAD.tasks) {
      isTask = tasksAD.tasks.some((task) => task.id === contextId);
    }
  }

  // If we're selecting a task but are in the chats tab, switch to tasks tab
  if (isTask && activeTab === "chats") {
    // Store this as the last selected task before switching
    localStorage.setItem("lastSelectedTask", contextId);
    activateTab("tasks");
    return true;
  }

  // If we're selecting a chat but are in the tasks tab, switch to chats tab
  if (!isTask && activeTab === "tasks") {
    // Store this as the last selected chat before switching
    localStorage.setItem("lastSelectedChat", contextId);
    activateTab("chats");
    return true;
  }

  return false;
}

globalThis.selectChat = async function (id) {
  if (id === context) return; //already selected

  // Check if we need to switch tabs based on the context type
  const tabSwitched = ensureProperTabSelection(id);

  // If we didn't switch tabs, proceed with normal selection
  if (!tabSwitched) {
    // Switch to the new context - this will clear chat history and reset tracking variables
    setContext(id);

    // Update both contexts and tasks lists to reflect the selected item
    const chatsAD = Alpine.$data(chatsSection);
    const tasksSection = document.getElementById("tasks-section");
    if (tasksSection) {
      const tasksAD = Alpine.$data(tasksSection);
      tasksAD.selected = id;
    }
    chatsAD.selected = id;

    // Store this selection in the appropriate localStorage key
    const activeTab = localStorage.getItem("activeTab") || "chats";
    if (activeTab === "chats") {
      localStorage.setItem("lastSelectedChat", id);
    } else if (activeTab === "tasks") {
      localStorage.setItem("lastSelectedTask", id);
    }

    // Trigger an immediate poll to fetch content
    poll();
  }

  updateAfterScroll();
};

export const setContext = function (id) {
  if (id == context) return;
  context = id;
  // Always reset the log tracking variables when switching contexts
  // This ensures we get fresh data from the backend
  lastLogGuid = "";
  lastLogVersion = 0;
  lastSpokenNo = 0;

  // Stop speech when switching chats
  speechStore.stopAudio();

  // Clear the chat history immediately to avoid showing stale content
  chatHistory.innerHTML = "";

  // Update both selected states
  if (globalThis.Alpine) {
    if (chatsSection) {
      const chatsAD = Alpine.$data(chatsSection);
      if (chatsAD) chatsAD.selected = id;
    }
    if (tasksSection) {
      const tasksAD = Alpine.$data(tasksSection);
      if (tasksAD) tasksAD.selected = id;
    }
  }

  //skip one speech if enabled when switching context
  if (localStorage.getItem("speech") == "true") skipOneSpeech = true;
};

export const getContext = function () {
  return context;
};

export const getChatBasedId = function (id) {
  return context + "-" + resetCounter + "-" + id;
};

globalThis.toggleAutoScroll = async function (_autoScroll) {
  autoScroll = _autoScroll;
};

globalThis.toggleJson = async function (showJson) {
  css.toggleCssProperty(".msg-json", "display", showJson ? "block" : "none");
};

globalThis.toggleThoughts = async function (showThoughts) {
  css.toggleCssProperty(
    ".msg-thoughts",
    "display",
    showThoughts ? undefined : "none"
  );
};

globalThis.toggleUtils = async function (showUtils) {
  css.toggleCssProperty(
    ".message-util",
    "display",
    showUtils ? undefined : "none"
  );
};

globalThis.toggleDarkMode = function (isDark) {
  if (isDark) {
    document.body.classList.remove("light-mode");
    document.body.classList.add("dark-mode");
  } else {
    document.body.classList.remove("dark-mode");
    document.body.classList.add("light-mode");
  }
  console.log("Dark mode:", isDark);
  localStorage.setItem("darkMode", isDark);
};

globalThis.toggleSpeech = function (isOn) {
  console.log("Speech:", isOn);
  localStorage.setItem("speech", isOn);
  if (!isOn) speechStore.stopAudio();
};

globalThis.nudge = async function () {
  try {
    const resp = await sendJsonData("/nudge", { ctxid: getContext() });
  } catch (e) {
    toastFetchError("Error nudging agent", e);
  }
};

globalThis.restart = async function () {
  try {
    if (!getConnectionStatus()) {
      await toastFrontendError(
        "Backend disconnected, cannot restart.",
        "Restart Error"
      );
      return;
    }
    // First try to initiate restart
    const resp = await sendJsonData("/restart", {});
  } catch (e) {
    // Show restarting message with no timeout and restart group
    await toastFrontendInfo("Restarting...", "System Restart", 9999, "restart");

    let retries = 0;
    const maxRetries = 240; // Maximum number of retries (60 seconds with 250ms interval)

    while (retries < maxRetries) {
      try {
        const resp = await sendJsonData("/health", {});
        // Server is back up, show success message that replaces the restarting message
        await new Promise((resolve) => setTimeout(resolve, 250));
        await toastFrontendSuccess("Restarted", "System Restart", 5, "restart");
        return;
      } catch (e) {
        // Server still down, keep waiting
        retries++;
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
    }

    // If we get here, restart failed or took too long
    await toastFrontendError(
      "Restart timed out or failed",
      "Restart Error",
      8,
      "restart"
    );
  }
};

// Modify this part
document.addEventListener("DOMContentLoaded", () => {
  const isDarkMode = localStorage.getItem("darkMode") !== "false";
  toggleDarkMode(isDarkMode);
});

globalThis.loadChats = async function () {
  try {
    const fileContents = await readJsonFiles();
    const response = await sendJsonData("/chat_load", { chats: fileContents });

    if (!response) {
      toast("No response returned.", "error");
    }
    // else if (!response.ok) {
    //     if (response.message) {
    //         toast(response.message, "error")
    //     } else {
    //         toast("Undefined error.", "error")
    //     }
    // }
    else {
      setContext(response.ctxids[0]);
      toast("Chats loaded.", "success");
    }
  } catch (e) {
    toastFetchError("Error loading chats", e);
  }
};

globalThis.saveChat = async function () {
  try {
    const response = await sendJsonData("/chat_export", { ctxid: context });

    if (!response) {
      toast("No response returned.", "error");
    }
    //  else if (!response.ok) {
    //     if (response.message) {
    //         toast(response.message, "error")
    //     } else {
    //         toast("Undefined error.", "error")
    //     }
    // }
    else {
      downloadFile(response.ctxid + ".json", response.content);
      toast("Chat file downloaded.", "success");
    }
  } catch (e) {
    toastFetchError("Error saving chat", e);
  }
};

function downloadFile(filename, content) {
  // Create a Blob with the content to save
  const blob = new Blob([content], { type: "application/json" });

  // Create a link element
  const link = document.createElement("a");

  // Create a URL for the Blob
  const url = URL.createObjectURL(blob);
  link.href = url;

  // Set the file name for download
  link.download = filename;

  // Programmatically click the link to trigger the download
  link.click();

  // Clean up by revoking the object URL
  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 0);
}

function readJsonFiles() {
  return new Promise((resolve, reject) => {
    // Create an input element of type 'file'
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json"; // Only accept JSON files
    input.multiple = true; // Allow multiple file selection

    // Trigger the file dialog
    input.click();

    // When files are selected
    input.onchange = async () => {
      const files = input.files;
      if (!files.length) {
        resolve([]); // Return an empty array if no files are selected
        return;
      }

      // Read each file as a string and store in an array
      const filePromises = Array.from(files).map((file) => {
        return new Promise((fileResolve, fileReject) => {
          const reader = new FileReader();
          reader.onload = () => fileResolve(reader.result);
          reader.onerror = fileReject;
          reader.readAsText(file);
        });
      });

      try {
        const fileContents = await Promise.all(filePromises);
        resolve(fileContents);
      } catch (error) {
        reject(error); // In case of any file reading error
      }
    };
  });
}

function addClassToElement(element, className) {
  element.classList.add(className);
}

function removeClassFromElement(element, className) {
  element.classList.remove(className);
}

function justToast(text, type = "info", timeout = 5000, group = "") {
  notificationStore.addFrontendToastOnly(
    type,
    text,
    "",
    timeout / 1000,
    group
  )
}
  

function toast(text, type = "info", timeout = 5000) {
  // Convert timeout from milliseconds to seconds for new notification system
  const display_time = Math.max(timeout / 1000, 1); // Minimum 1 second

  // Use new frontend notification system based on type
    switch (type.toLowerCase()) {
      case "error":
        return notificationStore.frontendError(text, "Error", display_time);
      case "success":
        return notificationStore.frontendInfo(text, "Success", display_time);
      case "warning":
        return notificationStore.frontendWarning(text, "Warning", display_time);
      case "info":
      default:
        return notificationStore.frontendInfo(text, "Info", display_time);
    }

}
globalThis.toast = toast;

// OLD: hideToast function removed - now using new notification system

function scrollChanged(isAtBottom) {
  if (globalThis.Alpine && autoScrollSwitch) {
    const inputAS = Alpine.$data(autoScrollSwitch);
    if (inputAS) {
      inputAS.autoScroll = isAtBottom;
    }
  }
  // autoScrollSwitch.checked = isAtBottom
}

function updateAfterScroll() {
  // const toleranceEm = 1; // Tolerance in em units
  // const tolerancePx = toleranceEm * parseFloat(getComputedStyle(document.documentElement).fontSize); // Convert em to pixels
  const tolerancePx = 10;
  const chatHistory = document.getElementById("chat-history");
  const isAtBottom =
    chatHistory.scrollHeight - chatHistory.scrollTop <=
    chatHistory.clientHeight + tolerancePx;

  scrollChanged(isAtBottom);
}

chatHistory.addEventListener("scroll", updateAfterScroll);

chatInput.addEventListener("input", adjustTextareaHeight);

// setInterval(poll, 250);

async function startPolling() {
  const shortInterval = 25;
  const longInterval = 250;
  const shortIntervalPeriod = 100;
  let shortIntervalCount = 0;

  async function _doPoll() {
    let nextInterval = longInterval;

    try {
      const result = await poll();
      if (result) shortIntervalCount = shortIntervalPeriod; // Reset the counter when the result is true
      if (shortIntervalCount > 0) shortIntervalCount--; // Decrease the counter on each call
      nextInterval = shortIntervalCount > 0 ? shortInterval : longInterval;
    } catch (error) {
      console.error("Error:", error);
    }

    // Call the function again after the selected interval
    setTimeout(_doPoll.bind(this), nextInterval);
  }

  _doPoll();
}

document.addEventListener("DOMContentLoaded", startPolling);

// Setup event handlers once the DOM is fully loaded
document.addEventListener("DOMContentLoaded", function () {
  setupSidebarToggle();
  setupTabs();
  initializeActiveTab();
});

// Setup tabs functionality
function setupTabs() {
  const chatsTab = document.getElementById("chats-tab");
  const tasksTab = document.getElementById("tasks-tab");

  if (chatsTab && tasksTab) {
    chatsTab.addEventListener("click", function () {
      activateTab("chats");
    });

    tasksTab.addEventListener("click", function () {
      activateTab("tasks");
    });
  } else {
    console.error("Tab elements not found");
    setTimeout(setupTabs, 100); // Retry setup
  }
}

function activateTab(tabName) {
  const chatsTab = document.getElementById("chats-tab");
  const tasksTab = document.getElementById("tasks-tab");
  const chatsSection = document.getElementById("chats-section");
  const tasksSection = document.getElementById("tasks-section");

  // Get current context to preserve before switching
  const currentContext = context;

  // Store the current selection for the active tab before switching
  const previousTab = localStorage.getItem("activeTab");
  if (previousTab === "chats") {
    localStorage.setItem("lastSelectedChat", currentContext);
  } else if (previousTab === "tasks") {
    localStorage.setItem("lastSelectedTask", currentContext);
  }

  // Reset all tabs and sections
  chatsTab.classList.remove("active");
  tasksTab.classList.remove("active");
  chatsSection.style.display = "none";
  tasksSection.style.display = "none";

  // Remember the last active tab in localStorage
  localStorage.setItem("activeTab", tabName);

  // Activate selected tab and section
  if (tabName === "chats") {
    chatsTab.classList.add("active");
    chatsSection.style.display = "";

    // Get the available contexts from Alpine.js data
    const chatsAD = globalThis.Alpine ? Alpine.$data(chatsSection) : null;
    const availableContexts = chatsAD?.contexts || [];

    // Restore previous chat selection
    const lastSelectedChat = localStorage.getItem("lastSelectedChat");

    // Only switch if:
    // 1. lastSelectedChat exists AND
    // 2. It's different from current context AND
    // 3. The context actually exists in our contexts list OR there are no contexts yet
    if (
      lastSelectedChat &&
      lastSelectedChat !== currentContext &&
      (availableContexts.some((ctx) => ctx.id === lastSelectedChat) ||
        availableContexts.length === 0)
    ) {
      setContext(lastSelectedChat);
    }
  } else if (tabName === "tasks") {
    tasksTab.classList.add("active");
    tasksSection.style.display = "flex";
    tasksSection.style.flexDirection = "column";

    // Get the available tasks from Alpine.js data
    const tasksAD = globalThis.Alpine ? Alpine.$data(tasksSection) : null;
    const availableTasks = tasksAD?.tasks || [];

    // Restore previous task selection
    const lastSelectedTask = localStorage.getItem("lastSelectedTask");

    // Only switch if:
    // 1. lastSelectedTask exists AND
    // 2. It's different from current context AND
    // 3. The task actually exists in our tasks list
    if (
      lastSelectedTask &&
      lastSelectedTask !== currentContext &&
      availableTasks.some((task) => task.id === lastSelectedTask)
    ) {
      setContext(lastSelectedTask);
    }
  }

  // Request a poll update
  poll();
}

// Add function to initialize active tab and selections from localStorage
function initializeActiveTab() {
  // Initialize selection storage if not present
  if (!localStorage.getItem("lastSelectedChat")) {
    localStorage.setItem("lastSelectedChat", "");
  }
  if (!localStorage.getItem("lastSelectedTask")) {
    localStorage.setItem("lastSelectedTask", "");
  }

  const activeTab = localStorage.getItem("activeTab") || "chats";
  activateTab(activeTab);
}

/*
 * A0 Chat UI
 *
 * Tasks tab functionality:
 * - Tasks are displayed in the Tasks tab with the same mechanics as chats
 * - Both lists are sorted by creation time (newest first)
 * - Selection state is preserved across tab switches
 * - The active tab is remembered across sessions
 * - Tasks use the same context system as chats for communication with the backend
 * - Future support for renaming and deletion will be implemented later
 */

// Open the scheduler detail view for a specific task
function openTaskDetail(taskId) {
  // Wait for Alpine.js to be fully loaded
  if (globalThis.Alpine) {
    // Get the settings modal button and click it to ensure all init logic happens
    const settingsButton = document.getElementById("settings");
    if (settingsButton) {
      // Programmatically click the settings button
      settingsButton.click();

      // Now get a reference to the modal element
      const modalEl = document.getElementById("settingsModal");
      if (!modalEl) {
        console.error("Settings modal element not found after clicking button");
        return;
      }

      // Get the Alpine.js data for the modal
      const modalData = globalThis.Alpine ? Alpine.$data(modalEl) : null;

      // Use a timeout to ensure the modal is fully rendered
      setTimeout(() => {
        // Switch to the scheduler tab first
        modalData.switchTab("scheduler");

        // Use another timeout to ensure the scheduler component is initialized
        setTimeout(() => {
          // Get the scheduler component
          const schedulerComponent = document.querySelector(
            '[x-data="schedulerSettings"]'
          );
          if (!schedulerComponent) {
            console.error("Scheduler component not found");
            return;
          }

          // Get the Alpine.js data for the scheduler component
          const schedulerData = globalThis.Alpine
            ? Alpine.$data(schedulerComponent)
            : null;

          // Show the task detail view for the specific task
          schedulerData.showTaskDetail(taskId);

          console.log("Task detail view opened for task:", taskId);
        }, 50); // Give time for the scheduler tab to initialize
      }, 25); // Give time for the modal to render
    } else {
      console.error("Settings button not found");
    }
  } else {
    console.error("Alpine.js not loaded");
  }
}

// Make the function available globally
globalThis.openTaskDetail = openTaskDetail;
