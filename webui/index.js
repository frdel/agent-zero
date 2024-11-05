import * as msgs from "./messages.js"

const leftPanel = document.getElementById('left-panel');
const rightPanel = document.getElementById('right-panel');
const container = document.querySelector('.container');
const chatInput = document.getElementById('chat-input');
const chatHistory = document.getElementById('chat-history');
const sendButton = document.getElementById('send-button');
const inputSection = document.getElementById('input-section');
const statusSection = document.getElementById('status-section');
const chatsSection = document.getElementById('chats-section');
const scrollbarThumb = document.querySelector('#chat-history::-webkit-scrollbar-thumb');
const progressBar = document.getElementById('progress-bar');
const autoScrollSwitch = document.getElementById('auto-scroll-switch');

let autoScroll = true;
let context = "";

// Initialize the toggle button 
setupSidebarToggle();

function isMobile() {
    return window.innerWidth <= 768;
}

function toggleSidebar() {
    leftPanel.classList.toggle('hidden');
    rightPanel.classList.toggle('expanded');
}

function handleResize() {
    if (isMobile()) {
        leftPanel.classList.add('hidden');
        rightPanel.classList.add('expanded');
    } else {
        leftPanel.classList.remove('hidden');
        rightPanel.classList.remove('expanded');
    }
}

// Run on startup and window resize
window.addEventListener('load', handleResize);
window.addEventListener('resize', handleResize);

function setupSidebarToggle() {
    const leftPanel = document.getElementById('left-panel');
    const rightPanel = document.getElementById('right-panel');
    const toggleSidebarButton = document.getElementById('toggle-sidebar');
    if (toggleSidebarButton) {
        toggleSidebarButton.addEventListener('click', toggleSidebar);
    } else {
        console.error('Toggle sidebar button not found');
        setTimeout(setupSidebarToggle, 100);
    }
}

async function sendMessage() {
    try {
        const message = chatInput.value.trim();
        if (message) {
            const response = await sendJsonData("/msg", { text: message, context });

            if (!response) {
                toast("No response returned.", "error")
            } else if (!response.ok) {
                if (response.message) {
                    toast(response.message, "error")
                } else {
                    toast("Undefined error.", "error")
                }
            } else {
                setContext(response.context)
            }

            chatInput.value = '';
            adjustTextareaHeight();
        }
    } catch (e) {
        toast(e.message, "error")
    }
}

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

sendButton.addEventListener('click', sendMessage);

function updateUserTime() {
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();
    const seconds = now.getSeconds();
    const ampm = hours >= 12 ? 'pm' : 'am';
    const formattedHours = hours % 12 || 12;

    const timeString = `${formattedHours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')} ${ampm}`;
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    const dateString = now.toLocaleDateString(undefined, options);

    const userTimeElement = document.getElementById('time-date');
    userTimeElement.innerHTML = `${timeString}<br><span id="user-date">${dateString}</span>`;
}

updateUserTime();
setInterval(updateUserTime, 1000);

function setMessage(id, type, heading, content, temp, kvps = null) {
    let messageContainer = document.getElementById(`message-${id}`);

    if (messageContainer) {
        messageContainer.innerHTML = '';
    } else {
        const sender = type === 'user' ? 'user' : 'ai';
        messageContainer = document.createElement('div');
        messageContainer.id = `message-${id}`;
        messageContainer.classList.add('message-container', `${sender}-container`);
        if (temp) messageContainer.classList.add("message-temp")
    }

    const handler = msgs.getHandler(type);
    handler(messageContainer, id, type, heading, content, temp, kvps);

    if (!document.getElementById(`message-${id}`)) {
        chatHistory.appendChild(messageContainer);
    }

    if (autoScroll) chatHistory.scrollTop = chatHistory.scrollHeight;
}

function adjustTextareaHeight() {
    chatInput.style.height = 'auto';
    chatInput.style.height = (chatInput.scrollHeight) + 'px';
}

async function sendJsonData(url, data) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    });

    if (!response.ok) {
        throw new Error('Network response was not ok');
    }
    const jsonResponse = await response.json();
    return jsonResponse;
}

function generateGUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        var r = Math.random() * 16 | 0;
        var v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

let lastLogVersion = 0;
let lastLogGuid = ""

async function poll() {
    let updated = false
    try {
        const response = await sendJsonData("/poll", { log_from: lastLogVersion, context });

        if (response.ok) {
            if (!context) setContext(response.context)
            if (response.context != context) return

            if (lastLogGuid != response.log_guid) {
                chatHistory.innerHTML = ""
                lastLogVersion = 0
            }

            if (lastLogVersion != response.log_version) {
                updated = true
                for (const log of response.logs) {
                    setMessage(log.no, log.type, log.heading, log.content, log.temp, log.kvps);
                }
            }

            updateProgress(response.log_progress)

            const inputAD = Alpine.$data(inputSection);
            inputAD.paused = response.paused;
            const statusAD = Alpine.$data(statusSection);
            statusAD.connected = response.ok;
            const chatsAD = Alpine.$data(chatsSection);
            chatsAD.contexts = response.contexts;

            lastLogVersion = response.log_version;
            lastLogGuid = response.log_guid;
        }

    } catch (error) {
        console.error('Error:', error);
        const statusAD = Alpine.$data(statusSection);
        statusAD.connected = false;
    }

    return updated
}

function updateProgress(progress) {
    if (!progress) progress = "Waiting for input"
    if (progressBar.innerHTML != progress) {
        progressBar.innerHTML = progress
    }
}

function updatePauseButtonState(isPaused) {
    const pauseButton = document.getElementById('pause-button');
    const unpauseButton = document.getElementById('unpause-button');

    if (isPaused) {
        pauseButton.style.display = 'none';
        unpauseButton.style.display = 'flex';
    } else {
        pauseButton.style.display = 'flex';
        unpauseButton.style.display = 'none';
    }
}

window.pauseAgent = async function (paused) {
    const resp = await sendJsonData("/pause", { paused: paused, context });
    updatePauseButtonState(paused);
}

window.resetChat = async function () {
    const resp = await sendJsonData("/reset", { context });
    updateAfterScroll()
}

window.newChat = async function () {
    setContext(generateGUID());
    updateAfterScroll()
}

window.killChat = async function (id) {
    const chatsAD = Alpine.$data(chatsSection);
    let found, other
    for (let i = 0; i < chatsAD.contexts.length; i++) {
        if (chatsAD.contexts[i].id == id) {
            found = true
        } else {
            other = chatsAD.contexts[i]
        }
        if (found && other) break
    }

    if (context == id && found) {
        if (other) setContext(other.id)
        else setContext(generateGUID())
    }

    if (found) sendJsonData("/remove", { context: id });

    updateAfterScroll()
}

window.selectChat = async function (id) {
    setContext(id)
    updateAfterScroll()
}

const setContext = function (id) {
    if (id == context) return
    context = id
    lastLogGuid = ""
    lastLogVersion = 0
    const chatsAD = Alpine.$data(chatsSection);
    chatsAD.selected = id
}

window.toggleAutoScroll = async function (_autoScroll) {
    autoScroll = _autoScroll;
}

window.toggleJson = async function (showJson) {
    toggleCssProperty('.msg-json', 'display', showJson ? 'block' : 'none');
}

window.toggleThoughts = async function (showThoughts) {
    toggleCssProperty('.msg-thoughts', 'display', showThoughts ? undefined : 'none');
}

window.toggleUtils = async function (showUtils) {
    toggleCssProperty('.message-util', 'display', showUtils ? undefined : 'none');
}

window.toggleDarkMode = function (isDark) {
    if (isDark) {
        document.body.classList.remove('light-mode');
    } else {
        document.body.classList.add('light-mode');
    }
    localStorage.setItem('darkMode', isDark);
};

document.addEventListener('DOMContentLoaded', () => {
    const isDarkMode = localStorage.getItem('darkMode') !== 'false';
    toggleDarkMode(isDarkMode);
    populateModelDropdowns();
    document.getElementById('save-models-button').addEventListener('click', saveSelectedModels);
});

function toggleCssProperty(selector, property, value) {
    const styleSheets = document.styleSheets;
    for (let i = 0; i < styleSheets.length; i++) {
        const styleSheet = styleSheets[i];
        const rules = styleSheet.cssRules || styleSheet.rules;

        for (let j = 0; j < rules.length; j++) {
            const rule = rules[j];
            if (rule.selectorText == selector) {
                if (value === undefined) {
                    rule.style.removeProperty(property);
                } else {
                    rule.style.setProperty(property, value);
                }
                return;
            }
        }
    }
}

window.loadChats = async function () {
    try {
        const fileContents = await readJsonFiles();
        const response = await sendJsonData("/loadChats", { chats: fileContents });

        if (!response) {
            toast("No response returned.", "error")
        } else if (!response.ok) {
            if (response.message) {
                toast(response.message, "error")
            } else {
                toast("Undefined error.", "error")
            }
        } else {
            setContext(response.ctxids[0])
            toast("Chats loaded.", "success")
        }

    } catch (e) {
        toast(e.message, "error")
    }
}

window.saveChat = async function () {
    try {
        const response = await sendJsonData("/exportChat", { ctxid: context });

        if (!response) {
            toast("No response returned.", "error")
        } else if (!response.ok) {
            if (response.message) {
                toast(response.message, "error")
            } else {
                toast("Undefined error.", "error")
            }
        } else {
            downloadFile(response.ctxid + ".json", response.content)
            toast("Chat file downloaded.", "success")
        }

    } catch (e) {
        toast(e.message, "error")
    }
}

function downloadFile(filename, content) {
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    
    setTimeout(() => {
        URL.revokeObjectURL(url);
    }, 0);
}

function readJsonFiles() {
    return new Promise((resolve, reject) => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.multiple = true;

        input.click();

        input.onchange = async () => {
            const files = input.files;
            if (!files.length) {
                resolve([]);
                return;
            }

            const filePromises = Array.from(files).map(file => {
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
                reject(error);
            }
        };
    });
}

function toast(text, type = 'info') {
    const toast = document.getElementById('toast');
    toast.querySelector('.toast__message').textContent = text;
    toast.className = `toast toast--${type}`;
    toast.style.display = 'flex';

    const closeButton = toast.querySelector('.toast__close');
    closeButton.onclick = () => {
        toast.style.display = 'none';
        clearTimeout(toast.timeoutId);
    };

    const copyButton = toast.querySelector('.toast__copy');
    copyButton.onclick = () => {
        navigator.clipboard.writeText(text);
        copyButton.textContent = 'Copied!';
        setTimeout(() => {
            copyButton.textContent = 'Copy';
        }, 2000);
    };

    clearTimeout(toast.timeoutId);
    toast.timeoutId = setTimeout(() => {
        toast.style.display = 'none';
    }, 10000);
}

function scrollChanged(isAtBottom) {
    const inputAS = Alpine.$data(autoScrollSwitch);
    inputAS.autoScroll = isAtBottom;
}

function updateAfterScroll() {
    const tolerancePx = 50;
    const chatHistory = document.getElementById('chat-history');
    const isAtBottom = (chatHistory.scrollHeight - chatHistory.scrollTop) <= (chatHistory.clientHeight + tolerancePx);
    scrollChanged(isAtBottom);
}

chatHistory.addEventListener('scroll', updateAfterScroll);
chatInput.addEventListener('input', adjustTextareaHeight);

async function startPolling() {
    const shortInterval = 100;  // Increased from 25ms
    const longInterval = 1000;  // Increased from 250ms
    const shortIntervalPeriod = 50; // Reduced from 100
    
    let shortIntervalCount = 0;
    let consecutiveErrors = 0;
    const maxConsecutiveErrors = 3;

    async function _doPoll() {
        let nextInterval = longInterval;

        try {
            const result = await poll();
            if (result) {
                shortIntervalCount = shortIntervalPeriod;
                consecutiveErrors = 0;  // Reset error count on success
            }
            if (shortIntervalCount > 0) shortIntervalCount--;
            nextInterval = shortIntervalCount > 0 ? shortInterval : longInterval;
        } catch (error) {
            console.error('Error:', error);
            consecutiveErrors++;
            
            // Exponential backoff if there are consecutive errors
            if (consecutiveErrors > maxConsecutiveErrors) {
                nextInterval = Math.min(longInterval * Math.pow(2, consecutiveErrors - maxConsecutiveErrors), 10000);
            }
        }

        setTimeout(_doPoll.bind(this), nextInterval);
    }

    _doPoll();
}

document.addEventListener("DOMContentLoaded", startPolling);

async function populateModelDropdowns() {
    try {
        const response = await sendJsonData("/api/models", {});

        if (!response || !response.ok) {
            throw new Error(response?.error || "Failed to fetch models");
        }

        const models = response.models;
        const available = response.available_models;

        if (!models || !available) {
            throw new Error("Invalid response format");
        }

        // Populate dropdowns
        populateDropdown('chat-model', models.chat_model, available.chat_model);
        populateDropdown('utility-model', models.utility_model, available.utility_model);
        populateDropdown('embedding-model', models.embedding_model, available.embedding_model);

    } catch (error) {
        console.error('Error fetching models:', error);
        toast("Failed to fetch available models: " + error.message, "error");
    }
}

function populateDropdown(elementId, selectedModel, availableModels) {
    const dropdown = document.getElementById(elementId);
    if (!dropdown) {
        console.error(`Dropdown element with ID '${elementId}' not found.`);
        return;
    }
    
    dropdown.innerHTML = '';
    
    if (Array.isArray(availableModels)) {
        availableModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            option.selected = model === selectedModel;
            dropdown.appendChild(option);
        });
    }
}

async function saveSelectedModels() {
    const chatModel = document.getElementById('chat-model').value;
    const utilityModel = document.getElementById('utility-model').value;
    const embeddingModel = document.getElementById('embedding-model').value;

    try {
        const response = await fetch('/api/models', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                chat_model: chatModel,
                utility_model: utilityModel,
                embedding_model: embeddingModel
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        if (result.ok) {
            toast('Models updated successfully.', 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            toast('Failed to update models.', 'error');
        }
    } catch (error) {
        console.error('Error updating models:', error);
        toast('Error updating models.', 'error');
    }
}

function updateTemperature() {
    const temp = document.getElementById('temperature').value;
    fetch('/msg', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            text: `set temperature ${temp}`,
            context: context
        })
    })
    .then(response => response.json())
    .then(data => {
        if(data.ok) {
            toast('Temperature updated successfully.', 'success');
        } else {
            toast('Failed to update temperature.', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        toast('Error updating temperature.', 'error');
    });
}
