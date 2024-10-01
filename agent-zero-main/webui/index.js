import * as msgs from "./messages.js"

const splitter = document.getElementById('splitter');
const leftPanel = document.getElementById('left-panel');
const container = document.querySelector('.container');
const chatInput = document.getElementById('chat-input');
const chatHistory = document.getElementById('chat-history');
const sendButton = document.getElementById('send-button');
const inputSection = document.getElementById('input-section');
const statusSection = document.getElementById('status-section');
const chatsSection = document.getElementById('chats-section');

let isResizing = false;
let autoScroll = true;

let context = "";
let messageCounter = 0;

console.log("index.js loaded"); // Debug: Check if the script is loaded

splitter.addEventListener('mousedown', (e) => {
    isResizing = true;
    document.addEventListener('mousemove', resize);
    document.addEventListener('mouseup', stopResize);
});

function resize(e) {
    if (isResizing) {
        const newWidth = e.clientX - container.offsetLeft;
        leftPanel.style.width = `${newWidth}px`;
    }
}

function stopResize() {
    isResizing = false;
    document.removeEventListener('mousemove', resize);
}

async function sendMessage() {
    console.log("sendMessage function called"); // Debug: Check if the function is called
    const message = chatInput.value.trim();
    if (message) {
        console.log("Message to send:", message); // Debug: Log the message content
        messageCounter++;
        setMessage(messageCounter, 'user', 'User', message);

        try {
            const response = await sendJsonData("/msg", { text: message, context });
            console.log("Response from server:", response); // Debug: Log the server response

            if (response.ok) {
                messageCounter++;
                setMessage(messageCounter, 'agent', 'Agent', response.response);
            } else {
                console.error("Server response not OK:", response); // Debug: Log error if response is not OK
            }
        } catch (error) {
            console.error("Error sending message:", error); // Debug: Log any errors during the process
        }

        chatInput.value = '';
        adjustTextareaHeight();
    }
}

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        console.log("Enter key pressed"); // Debug: Check if the event listener is triggered
        e.preventDefault();
        sendMessage();
    }
});

sendButton.addEventListener('click', () => {
    console.log("Send button clicked"); // Debug: Check if the button click is detected
    sendMessage();
});

function setMessage(id, type, heading, content, kvps = null) {
    console.log("setMessage called:", id, type, heading); // Debug: Log when a message is set
    // Search for the existing message container by id
    let messageContainer = document.getElementById(`message-${id}`);

    if (messageContainer) {
        // Clear the existing container's content if found
        messageContainer.innerHTML = '';
    } else {
        // Create a new container if not found
        const sender = type === 'user' ? 'user' : 'ai';
        messageContainer = document.createElement('div');
        messageContainer.id = `message-${id}`;
        messageContainer.classList.add('message-container', `${sender}-container`);
    }

    const handler = msgs.getHandler(type);
    handler(messageContainer, id, type, heading, content, kvps);

    // If the container was found, it was already in the DOM, no need to append again
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
    console.log("Sending data to:", url, data); // Debug: Log the data being sent
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
    try {
        const response = await sendJsonData("/poll", { log_from: lastLogVersion, context });
        console.log("Poll response:", response); // Debug: Log the poll response

        if (response.ok) {
            setContext(response.context);

            if (lastLogGuid !== response.log_guid) {
                console.log("New log_guid received, updating lastLogGuid"); // Debug: Log when log_guid changes
                lastLogGuid = response.log_guid;
                lastLogVersion = 0; // Reset lastLogVersion when log_guid changes
                chatHistory.innerHTML = ""; // Clear chat history when log_guid changes
                messageCounter = 0; // Reset message counter
            }

            if (lastLogVersion !== response.log_version) {
                console.log("New messages received, updating chat history"); // Debug: Log when new messages are received
                for (const log of response.logs) {
                    if (log.no > lastLogVersion) {
                        setMessage(log.no, log.type, log.heading, log.content, log.kvps);
                        lastLogVersion = log.no;
                        messageCounter = log.no; // Update message counter
                    }
                }
            }

            // Set UI model vars from backend
            const inputAD = Alpine.$data(inputSection);
            inputAD.paused = response.paused;
            const statusAD = Alpine.$data(statusSection);
            statusAD.connected = response.ok;
            const chatsAD = Alpine.$data(chatsSection);
            chatsAD.contexts = response.contexts;
        }
    } catch (error) {
        console.error('Error in poll function:', error);
        const statusAD = Alpine.$data(statusSection);
        statusAD.connected = false;
    }
}

window.pauseAgent = async function (paused) {
    const resp = await sendJsonData("/pause", { paused: paused, context });
}

window.resetChat = async function () {
    const resp = await sendJsonData("/reset", { context });
    chatHistory.innerHTML = "";
    messageCounter = 0;
    lastLogVersion = 0;
    lastLogGuid = "";
}

window.newChat = async function () {
    setContext(generateGUID());
    chatHistory.innerHTML = "";
    messageCounter = 0;
    lastLogVersion = 0;
    lastLogGuid = "";
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
}

window.selectChat = async function (id) {
    setContext(id)
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

window.toggleShowJson = async function (showJson) {
    toggleCssProperty('.msg-json', 'display', showJson ? 'block' : 'none');
}

window.toggleShowThoughts = async function (showThoughts) {
    toggleCssProperty('.msg-thoughts', 'display', showThoughts ? undefined : 'none');
}

function toggleCssProperty(selector, property, value) {
    // Get the stylesheet that contains the class
    const styleSheets = document.styleSheets;

    // Iterate through all stylesheets to find the class
    for (let i = 0; i < styleSheets.length; i++) {
        const styleSheet = styleSheets[i];
        const rules = styleSheet.cssRules || styleSheet.rules;

        for (let j = 0; j < rules.length; j++) {
            const rule = rules[j];
            if (rule.selectorText == selector) {
                // Check if the property is already applied
                if (value === undefined) {
                    rule.style.removeProperty(property);  // Remove the property
                } else {
                    rule.style.setProperty(property, value);  // Add the property (you can customize the value)
                }
                return;
            }
        }
    }
}

chatInput.addEventListener('input', adjustTextareaHeight);

setInterval(poll, 250);

console.log("index.js finished loading"); // Debug: Check if the script has finished loading

// At the top, after existing imports
// ...

document.addEventListener('alpine:init', () => {
    // Fetch available models from the backend
    fetch('/get_available_models')
        .then(response => response.json())
        .then(data => {
            const modelSection = document.getElementById('model-selection-section');
            const modelData = Alpine.$data(modelSection);
            modelData.models = data.models;
            // Set default models
            modelData.chatModel = data.current_models.chat;
            modelData.utilityModel = data.current_models.utility;
            modelData.embeddingModel = data.current_models.embedding;
        });

    // Define the updateModel function
    window.updateModel = (role, modelName) => {
        fetch('/update_model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role, model_name: modelName })
        })
        .then(response => response.json())
        .then(data => {
            if (!data.ok) {
                console.error('Failed to update model:', data.message);
            } else {
                console.log(`Updated ${role} model to ${modelName}`);
            }
        })
        .catch(error => console.error('Error updating model:', error));
    };
});
