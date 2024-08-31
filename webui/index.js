import * as msgs from "./messages.js"

const splitter = document.getElementById('splitter');
const leftPanel = document.getElementById('left-panel');
const container = document.querySelector('.container');
const chatInput = document.getElementById('chat-input');
const chatHistory = document.getElementById('chat-history');
const sendButton = document.getElementById('send-button');
const inputSection = document.getElementById('input-section');
const statusSection = document.getElementById('status-section');

let isResizing = false;
let autoScroll = true;


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
    const message = chatInput.value.trim();
    if (message) {

        const response = await sendJsonData("/msg", { text: message });

        //setMessage('user', message);
        chatInput.value = '';
        adjustTextareaHeight();
    }
}

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

sendButton.addEventListener('click', sendMessage);

function setMessage(id, type, heading, content, kvps = null) {
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

    if(autoScroll) chatHistory.scrollTop = chatHistory.scrollHeight;
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

let lastLog = 0;
let lastLogVersion = 0;
let lastLogGuid = ""

async function poll() {
    try{
    const response = await sendJsonData("/poll", { log_from: lastLog });
    // console.log(response)

    if (response.ok) {

        if (lastLogGuid != response.log_guid) {
            chatHistory.innerHTML = ""
        }

        if (lastLogVersion != response.log_version) {
            for (const log of response.logs) {
                setMessage(log.no, log.type, log.heading, log.content, log.kvps);
            }
        }

        //set ui model vars from backend
        const inputAD = Alpine.$data(inputSection);
        inputAD.paused = response.paused;
        const statusAD = Alpine.$data(statusSection);
        statusAD.connected = response.ok;

        lastLog = response.log_to;
        lastLogVersion = response.log_version;
        lastLogGuid = response.log_guid;
    }

    } catch (error) {
        console.error('Error:', error);
        const statusAD = Alpine.$data(statusSection);
        statusAD.connected = false;
    }
}

window.pauseAgent = async function (paused) {
    const resp = await sendJsonData("/pause", { paused: paused });
}

window.resetChat = async function () {
    const resp = await sendJsonData("/reset", {});
}

window.toggleAutoScroll = async function (_autoScroll) {
    autoScroll = _autoScroll;
}

window.toggleJson = async function (showJson) {
    // add display:none to .msg-json class definition
    toggleCssProperty('.msg-json', 'display', showJson ? 'block' : 'none');
}

window.toggleThoughts = async function (showThoughts) {
    // add display:none to .msg-json class definition
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
                if (value===undefined) {
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