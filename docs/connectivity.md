# Agent Zero Connectivity Guide

This guide covers the different ways to connect to Agent Zero from external applications, including using the External API, connecting as an MCP client, and enabling agent-to-agent communication.

**Note:** You can find your specific URLs and API tokens in your Agent Zero instance under `Settings > External Services`.

### API Token Information

The API token is automatically generated from your username and password. This same token is used for External API endpoints, MCP server connections, and A2A communication. The token will change if you update your credentials.

---

## External API Endpoints

Agent Zero provides external API endpoints for integration with other applications. These endpoints use API key authentication and support text messages and file attachments.

### `POST /api_message`

Send messages to Agent Zero and receive responses. Supports text messages, file attachments, and conversation continuity.

### API Reference

**Parameters:**
*   `context_id` (string, optional): Existing chat context ID
*   `message` (string, required): The message to send
*   `attachments` (array, optional): Array of `{filename, base64}` objects
*   `lifetime_hours` (number, optional): Chat lifetime in hours (default: 24)

**Headers:**
*   `X-API-KEY` (required)
*   `Content-Type: application/json`

### JavaScript Examples

#### Basic Usage Example

```javascript
// Basic message example
async function sendMessage() {
    try {
        const response = await fetch('YOUR_AGENT_ZERO_URL/api_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-KEY': 'YOUR_API_KEY'
            },
            body: JSON.stringify({
                message: "Hello, how can you help me?",
                lifetime_hours: 24
            })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('✅ Success!');
            console.log('Response:', data.response);
            console.log('Context ID:', data.context_id);
            return data;
        } else {
            console.error('❌ Error:', data.error);
            return null;
        }
    } catch (error) {
        console.error('❌ Request failed:', error);
        return null;
    }
}

// Call the function
sendMessage().then(result => {
    if (result) {
        console.log('Message sent successfully!');
    }
});
```

#### Conversation Continuation Example

```javascript
// Continue conversation example
async function continueConversation(contextId) {
    try {
        const response = await fetch('YOUR_AGENT_ZERO_URL/api_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-KEY': 'YOUR_API_KEY'
            },
            body: JSON.stringify({
                context_id: contextId,
                message: "Can you tell me more about that?",
                lifetime_hours: 24
            })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('✅ Continuation Success!');
            console.log('Response:', data.response);
            return data;
        } else {
            console.error('❌ Error:', data.error);
            return null;
        }
    } catch (error) {
        console.error('❌ Request failed:', error);
        return null;
    }
}

// Example: First send a message, then continue the conversation
async function fullConversationExample() {
    const firstResult = await sendMessage();
    if (firstResult && firstResult.context_id) {
        await continueConversation(firstResult.context_id);
    }
}

fullConversationExample();
```

#### File Attachment Example

```javascript
// File attachment example
async function sendWithAttachment() {
    try {
        // Example with text content (convert to base64)
        const textContent = "Hello World from attachment!";
        const base64Content = btoa(textContent);

        const response = await fetch('YOUR_AGENT_ZERO_URL/api_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-KEY': 'YOUR_API_KEY'
            },
            body: JSON.stringify({
                message: "Please analyze this file:",
                attachments: [
                    {
                        filename: "document.txt",
                        base64: base64Content
                    }
                ],
                lifetime_hours: 12
            })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('✅ File sent successfully!');
            console.log('Response:', data.response);
            return data;
        } else {
            console.error('❌ Error:', data.error);
            return null;
        }
    } catch (error) {
        console.error('❌ Request failed:', error);
        return null;
    }
}

// Call the function
sendWithAttachment();
```

---

## `GET/POST /api_log_get`

Retrieve log data by context ID, limited to a specified number of entries from the newest.

### API Reference

**Parameters:**
*   `context_id` (string, required): Context ID to get logs from
*   `length` (integer, optional): Number of log items to return from newest (default: 100)

**Headers:**
*   `X-API-KEY` (required)
*   `Content-Type: application/json` (for POST)

### JavaScript Examples

#### GET Request Example

```javascript
// Get logs using GET request
async function getLogsGET(contextId, length = 50) {
    try {
        const params = new URLSearchParams({
            context_id: contextId,
            length: length.toString()
        });

        const response = await fetch('YOUR_AGENT_ZERO_URL/api_log_get?' + params, {
            method: 'GET',
            headers: {
                'X-API-KEY': 'YOUR_API_KEY'
            }
        });

        const data = await response.json();

        if (response.ok) {
            console.log('✅ Logs retrieved successfully!');
            console.log('Total items:', data.log.total_items);
            console.log('Returned items:', data.log.returned_items);
            console.log('Log items:', data.log.items);
            return data;
        } else {
            console.error('❌ Error:', data.error);
            return null;
        }
    } catch (error) {
        console.error('❌ Request failed:', error);
        return null;
    }
}

// Example usage
getLogsGET('ctx_abc123', 20);
```

#### POST Request Example

```javascript
// Get logs using POST request
async function getLogsPOST(contextId, length = 50) {
    try {
        const response = await fetch('YOUR_AGENT_ZERO_URL/api_log_get', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-KEY': 'YOUR_API_KEY'
            },
            body: JSON.stringify({
                context_id: contextId,
                length: length
            })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('✅ Logs retrieved successfully!');
            console.log('Context ID:', data.context_id);
            console.log('Log GUID:', data.log.guid);
            console.log('Total items:', data.log.total_items);
            console.log('Returned items:', data.log.returned_items);
            console.log('Start position:', data.log.start_position);
            console.log('Progress:', data.log.progress);
            console.log('Log items:', data.log.items);
            return data;
        } else {
            console.error('❌ Error:', data.error);
            return null;
        }
    } catch (error) {
        console.error('❌ Request failed:', error);
        return null;
    }
}

// Example usage - get latest 10 log entries
getLogsPOST('ctx_abc123', 10);
```

---

## `POST /api_terminate_chat`

Terminate and remove a chat context to free up resources. Similar to the MCP `finish_chat` function.

### API Reference

**Parameters:**
*   `context_id` (string, required): Context ID of the chat to terminate

**Headers:**
*   `X-API-KEY` (required)
*   `Content-Type: application/json`

### JavaScript Examples

#### Basic Termination Examples

```javascript
// Basic terminate chat function
async function terminateChat(contextId) {
    try {
        const response = await fetch('YOUR_AGENT_ZERO_URL/api_terminate_chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-KEY': 'YOUR_API_KEY'
            },
            body: JSON.stringify({
                context_id: contextId
            })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('✅ Chat deleted successfully!');
            console.log('Message:', data.message);
            return data;
        } else {
            console.error('❌ Error:', data.error);
            return null;
        }
    } catch (error) {
        console.error('❌ Request failed:', error);
        return null;
    }
}

// Example 1: Terminate a specific chat
terminateChat('ctx_abc123');

// Example 2: Complete workflow - send message, then terminate
async function simpleWorkflow() {
    // Send a message
    const result = await sendMessage();

    if (result && result.context_id) {
        console.log('Chat created:', result.context_id);

        // Do some work with the chat...
        // await continueConversation(result.context_id);

        // Clean up when done
        await terminateChat(result.context_id);
        console.log('Chat cleaned up');
    }
}

// Run the workflow
simpleWorkflow();
```

---

## `POST /api_reset_chat`

Reset a chat context to clear conversation history while keeping the `context_id` alive for continued use.

### API Reference

**Parameters:**
*   `context_id` (string, required): Context ID of the chat to reset

**Headers:**
*   `X-API-KEY` (required)
*   `Content-Type: application/json`

### JavaScript Examples

#### Basic Reset Examples

```javascript
// Basic reset chat function
async function resetChat(contextId) {
    try {
        const response = await fetch('YOUR_AGENT_ZERO_URL/api_reset_chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-KEY': 'YOUR_API_KEY'
            },
            body: JSON.stringify({
                context_id: contextId
            })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('✅ Chat reset successfully!');
            console.log('Message:', data.message);
            console.log('Context ID:', data.context_id);
            return data;
        } else {
            console.error('❌ Error:', data.error);
            return null;
        }
    } catch (error) {
        console.error('❌ Request failed:', error);
        return null;
    }
}

// Example 1: Reset a specific chat
resetChat('ctx_abc123');

// Example 2: Reset and continue conversation
async function resetAndContinue() {
    const contextId = 'ctx_abc123';

    // Reset the chat to clear history
    const resetResult = await resetChat(contextId);

    if (resetResult) {
        console.log('Chat reset, starting fresh conversation...');

        // Continue with same context_id but fresh history
        const response = await fetch('YOUR_AGENT_ZERO_URL/api_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-KEY': 'YOUR_API_KEY'
            },
            body: JSON.stringify({
                context_id: contextId,  // Same context ID
                message: "Hello, this is a fresh start!",
                lifetime_hours: 24
            })
        });

        const data = await response.json();
        console.log('New conversation started:', data.response);
    }
}

// Run the example
resetAndContinue();
```

---

## `POST /api_files_get`

Retrieve file contents by paths, returning files as base64 encoded data. Useful for retrieving uploaded attachments.

### API Reference

**Parameters:**
*   `paths` (array, required): Array of file paths to retrieve (e.g., `["/a0/tmp/uploads/file.txt"]`)

**Headers:**
*   `X-API-KEY` (required)
*   `Content-Type: application/json`

### JavaScript Examples

#### File Retrieval Examples

```javascript
// Basic file retrieval
async function getFiles(filePaths) {
    try {
        const response = await fetch('YOUR_AGENT_ZERO_URL/api_files_get', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-KEY': 'YOUR_API_KEY'
            },
            body: JSON.stringify({
                paths: filePaths
            })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('✅ Files retrieved successfully!');
            console.log('Retrieved files:', Object.keys(data));

            // Convert base64 back to text for display
            for (const [filename, base64Content] of Object.entries(data)) {
                try {
                    const textContent = atob(base64Content);
                    console.log(`${filename}: ${textContent.substring(0, 100)}...`);
                } catch (e) {
                    console.log(`${filename}: Binary file (${base64Content.length} chars)`);
                }
            }

            return data;
        } else {
            console.error('❌ Error:', data.error);
            return null;
        }
    } catch (error) {
        console.error('❌ Request failed:', error);
        return null;
    }
}

// Example 1: Get specific files
const filePaths = [
    "/a0/tmp/uploads/document.txt",
    "/a0/tmp/uploads/data.json"
];
getFiles(filePaths);

// Example 2: Complete attachment workflow
async function attachmentWorkflow() {
    // Step 1: Send message with attachments
    const messageResponse = await fetch('YOUR_AGENT_ZERO_URL/api_message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-KEY': 'YOUR_API_KEY'
        },
        body: JSON.stringify({
            message: "Please analyze this file",
            attachments: [{
                filename: "test.txt",
                base64: btoa("Hello, this is test content!")
            }],
            lifetime_hours: 1
        })
    });

    if (messageResponse.ok) {
        console.log('Message sent with attachment');

        // Step 2: Retrieve the uploaded file
        const retrievedFiles = await getFiles(["/a0/tmp/uploads/test.txt"]);

        if (retrievedFiles && retrievedFiles["test.txt"]) {
            const originalContent = atob(retrievedFiles["test.txt"]);
            console.log('Retrieved content:', originalContent);
        }
    }
}

// Run the complete workflow
attachmentWorkflow();
```

---

## MCP Server Connectivity

Agent Zero includes an MCP Server that allows other MCP-compatible clients to connect to it. The server runs on the same URL and port as the Web UI.

It provides two endpoint types:
- **SSE (`/mcp/sse`):** For clients that support Server-Sent Events.
- **Streamable HTTP (`/mcp/http/`):** For clients that use streamable HTTP requests.

### Example MCP Server Configuration

Below is an example of a `mcp.json` configuration file that a client could use to connect to the Agent Zero MCP server. 

**Note:** You can find your personalized connection URLs under `Settings > MCP Server > MCP Server`.

```json
{
    "mcpServers":
    {
        "agent-zero": {
            "type": "sse",
            "url": "YOUR_AGENT_ZERO_URL/mcp/t-YOUR_API_TOKEN/sse"
        },
        "agent-zero-http": {
            "type": "streamable-http",
            "url": "YOUR_AGENT_ZERO_URL/mcp/t-YOUR_API_TOKEN/http/"
        }
    }
}
```

---

## A2A (Agent-to-Agent) Connectivity

Agent Zero's A2A Server enables communication with other agents using the FastA2A protocol. Other agents can connect to your instance using the connection URL.

### A2A Connection URL

To connect another agent to your Agent Zero instance, use the following URL format. 

**Note:** You can find your specific A2A connection URL under `Settings > External Services > A2A Connection`.

```
YOUR_AGENT_ZERO_URL/a2a/t-YOUR_API_TOKEN
```
