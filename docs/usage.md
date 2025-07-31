# Usage Guide
This guide explores usage and configuration scenarios for Agent Zero. You can consider this as a reference post-installation guide.

![Utility Message with Solutions](res/memory-man.png)

## Basic Operations
Agent Zero provides several basic operations through its interface:

### Restart Framework
The Restart button allows you to quickly restart the Agent Zero framework without using the terminal:

![Restart Framework](res/ui-restarting.png)

* Click the "Restart" button in the sidebar
* A blue notification will appear indicating "Restarting..."
* Once complete, a green success message "Restarted" will be shown
* The framework will reinitialize while maintaining your current chat history and context

> [!TIP]
> Use the Restart function when you want to:
> - Reset the framework if you encounter unexpected behavior
> - Reinitialize the system when agents become unresponsive

### Action Buttons
Located beneath the chat input box, Agent Zero provides a set of action buttons for enhanced control and visibility:

![Action Buttons](res/ui-actions.png)
#### Chat Flow Control
* **Pause/Resume Agent:** Toggle button to pause and resume chat flow
  - Click to pause ongoing agent operations
  - Changes to "Resume Agent" when paused
  - Click again to resume chat flow and command execution

#### Knowledge and File Management
* **Import Knowledge:** Import external files into the agent's knowledge base
  - Supports `.txt`, `.pdf`, `.csv`, `.html`, `.json`, and `.md` formats
  - Files are stored in `\knowledge\custom\main`
  - Success message confirms successful import
  - See [knowledge](architecture.md#knowledge) for more details

### File Browser: Manage files in the Agent Zero environment
  - Upload new files and folders
  - Download files (click filename) or folders (as zip archives)
  - Delete files and folders
  - Navigate directories using the "Up" button
  - Support for file renaming and search coming soon
  - See [File Browser](#file-browser) section for detailed features

#### Debugging and Monitoring
* **Context:** View the complete context window sent to the LLM
  - Includes system prompts
  - Shows current conversation context
  - Displays active instructions and parameters

![Context](res/ui-context.png)

### History:
Access the chat history in JSON format
  - View the conversation as processed by the LLM
  - Useful for debugging and understanding agent behavior

![History](res/ui-history.png)

* **Nudge:** Restart the agent's last process
  - Useful when agents become unresponsive
  - Retries the last operation
  - Helps recover from stuck states

![Nudge](res/ui-nudge.png)

> [!TIP]
> Use the Context and History buttons to understand how the agent interprets your instructions and debug any unexpected behavior.

### File Attachments
Agent Zero supports direct file attachments in the chat interface for seamless file operations:

#### Attaching Files
* Click the attachment icon (📎) on the left side of the chat input box
* Select one or multiple files to attach
* Preview attached files before sending:
  - File names are displayed with their types (HTML, PDF, JPG, etc.)
  - Images show thumbnails when available
  - Files are listed in the chat input area waiting to be sent

![File Attachments](res/ui-attachments.png)

#### Working with Attached Files
* Files can be referenced directly in your messages
* Agent Zero can:
  - Process attached files
  - Move files to specific directories
  - Perform operations on multiple files simultaneously
  - Confirm successful file operations with detailed responses

![Working with Attachments](res/ui-attachments-2.png)

> [!TIP]
> When working with multiple files, you can attach them all at once and then give instructions about what to do with them. The agent will handle them as a batch while keeping you informed of the progress.

## Tool Usage
Agent Zero's power comes from its ability to use [tools](architecture.md#tools). Here's how to leverage them effectively:

- **Understand Tools:** Agent Zero includes default tools like knowledge (powered by SearXNG), code execution, and communication. Understand the capabilities of these tools and how to invoke them.

## Example of Tools Usage: Web Search and Code Execution
Let's say you want Agent Zero to perform some financial analysis tasks. Here's a possible prompt:

> Please be a professional financial analyst. Find last month Bitcoin/ USD price trend and make a chart in your environment. The chart must  have highlighted key points corresponding with dates of major news  about cryptocurrency. Use the 'search_engine' and 'document_query_tool' to find the price and  the news, and the 'code_execution_tool' to perform the rest of the job.

Agent Zero might then:

1. Use the `search_engine` and `document_query_tool` to query a reliable source for the Bitcoin price and for the news about cryptocurrency as prompted.
2. Extract the price from the search results and save the news, extracting their dates and possible impact on the price.
3. Use the `code_execution_tool` to execute a Python script that performs the graph creation and key points highlighting, using the extracted data and the news dates as inputs.
4. Return the final chart that you'll find in `/work_dir`, responding to the user with the `response_tool`.

> [!NOTE]
> The first run of `code_execution_tool` may take a while as it downloads and builds the Agent Zero Docker image. Subsequent runs will be faster.

This example demonstrates how to combine multiple tools to achieve an analysis task. By mastering prompt engineering and tool usage, you can unlock the full potential of Agent Zero to solve complex problems.

## Multi-Agent Cooperation
One of Agent Zero's unique features is multi-agent cooperation.

* **Creating Sub-Agents:** Agents can create sub-agents to delegate sub-tasks.  This helps manage complexity and distribute workload.
* **Communication:** Agents can communicate with each other, sharing information and coordinating actions. The system prompt and message history play a key role in guiding this communication.
* **Hierarchy:** Agent Zero uses a [hierarchical structure](architecture.md#agent-hierarchy-and-communication), with superior agents delegating tasks to subordinates.  This allows for structured problem-solving and efficient resource allocation.

![](res/physics.png)
![](res/physics-2.png)

## Prompt Engineering
Effective prompt engineering is crucial for getting the most out of Agent Zero. Here are some tips and techniques:

* **Be Clear and Specific:** Clearly state your desired outcome.  The more specific you are, the better Agent Zero can understand and fulfill your request.  Avoid vague or ambiguous language.
* **Provide Context:** If necessary, provide background information or context to help the agent understand the task better. This might include relevant details, constraints, or desired format for the response.
* **Break Down Complex Tasks:**  For complex tasks, break them down into smaller, more manageable sub-tasks.  This makes it easier for the agent to reason through the problem and generate a solution.
* **Iterative Refinement:** Don't expect perfect results on the first try.  Experiment with different prompts, refine your instructions based on the agent's responses, and iterate until you achieve the desired outcome. To achieve a full-stack, web-app development task, for example, you might need to iterate for a few hours for 100% success.

## Voice Interface
Agent Zero provides both Text-to-Speech (TTS) and Speech-to-Text (STT) capabilities for natural voice interaction:

### Text-to-Speech
Enable voice responses from agents:
* Toggle the "Speech" switch in the Preferences section of the sidebar
* Agents will use your system's built-in voice synthesizer to speak their messages
* Click the "Stop Speech" button above the input area to immediately stop any ongoing speech

![TTS Stop Speech](res/ui-tts-stop-speech.png)

- The interface allows users to stop speech at any time if a response is too lengthy or if they wish to intervene during the conversation.

The TTS uses a standard voice interface provided by modern browsers, which may sound robotic but is effective and does not require complex AI models. This ensures low latency and quick responses across various platforms, including mobile devices.


> [!TIP]
> The Text-to-Speech feature is great for:
> - Multitasking while receiving agent responses
> - Accessibility purposes
> - Creating a more interactive experience

### Speech-to-Text
Send voice messages to agents using OpenAI's Whisper model (does not require OpenAI API key!):

1. Click the microphone button in the input area to start recording
2. The button color indicates the current status:
   - Grey: Inactive
   - Red: Listening
   - Green: Recording
   - Teal: Waiting
   - Cyan (pulsing): Processing

Users can adjust settings such as silence threshold and message duration before sending to optimize their interaction experience.

Configure STT settings in the Settings page:
* **Model Size:** Choose between Base (74M, English) or other models
  - Note: Only Large and Turbo models support multiple languages
* **Language Code:** Set your preferred language (e.g., 'en', 'fr', 'it', 'cz')
* **Silence Detection:**
  - Threshold: Adjust sensitivity (lower values are more sensitive)
  - Duration: Set how long silence should last before ending recording
  - Timeout: Set maximum waiting time before closing the microphone

![Speech to Text Settings](res/ui-settings-5-speech-to-text.png)

> [!IMPORTANT]
> All STT and TTS functionalities operate locally within the Docker container,
> ensuring that no data is transmitted to external servers or OpenAI APIs. This
> enhances user privacy while maintaining functionality.

### Mathematical Expressions
Agent Zero supports KaTeX for beautiful mathematical typesetting:

* **Inline Math:** Use single dollars `$...$` for inline expressions
  - Example: Type `The area of a circle is $A = πr^2$`
  - Renders as: The area of a circle is $A = πr^2$

* **Display Math:** Use double dollars `$$...$$` for centered display equations
  - Example: Type `$$F = G\frac{m_1m_2}{r^2}$$`
  - Renders as a centered equation

![KaTeX](res/ui-katex-1.png)

* **Complex Mathematics:** Supports full KaTeX syntax for:
  - Fractions, exponents, and roots
  - Matrices and arrays
  - Greek letters and mathematical symbols
  - Integrals, summations, and limits
  - Mathematical alignments and equations

![KaTeX display](res/ui-katex-2.png)

> [!TIP]
> When asking the agent to solve mathematical problems, it will automatically respond using KaTeX formatting for clear and professional-looking mathematical expressions.

### File Browser
Agent Zero provides a powerful file browser interface for managing your workspace:

#### Interface Overview
- **Navigation Bar**: Shows current directory path with "Up" button for parent directory
- **File List**: Displays files and directories with key information:
  - Name (sortable)
  - Size in bytes
  - Last modified timestamp
- **Action Icons**: Each file/directory has:
  - Download button
  - Delete button (with confirmation)

![File Browser](res/ui-file-browser.png)

#### Features
- **Directory Navigation**:
  - Click directories to enter them
  - Use "Up" button to move to parent directory
  - Current path always visible for context

> [!NOTE]
> The files browser allows the user to go in the Agent Zero root folder if you click the `Up` button, but the working directory of Agents will always be `/work_dir`
>
- **File Operations**:
  - Create new files and directories
  - Delete existing files and directories
  - Download files to your local system
  - Upload files from your local system
- **File Information**:
  - Visual indicators for file types (folders, code files, documents)
  - Size information in human-readable format
  - Last modification timestamps
- **Bulk Operations**:
  - Upload multiple files simultaneously
  - Select and manage multiple files at once

> [!TIP]
> The File Browser integrates seamlessly with Agent Zero's capabilities. You can reference files directly in your conversations, and the agent can help you manage, modify, and organize your files.

## Backup & Restore
Agent Zero provides a comprehensive backup and restore system to protect your data and configurations. This feature helps you safeguard your work and migrate Agent Zero setups between different systems.

### Creating Backups
Access the backup functionality through the Settings interface:

1. Click the **Settings** button in the sidebar
2. Navigate to the **Backup** tab
3. Click **Create Backup** to start the backup process

#### What Gets Backed Up
By default, Agent Zero backs up your most important data:

* **Knowledge Base**: Your custom knowledge files and documents
* **Memory System**: Agent memories and learned information
* **Chat History**: All your conversations and interactions
* **Configuration Files**: Settings, API keys, and system preferences
* **Custom Instruments**: Any tools you've added or modified
* **Uploaded Files**: Documents and files you've worked with

#### Customizing Backup Content
Before creating a backup, you can customize what to include:

* **Edit Patterns**: Use the built-in editor to specify exactly which files and folders to backup
* **Include Hidden Files**: Choose whether to include system and configuration files
* **Preview Files**: See exactly what will be included before creating the backup
* **Organized View**: Files are grouped by directory for easy review

> [!TIP]
> The backup system uses pattern matching, so you can include or exclude specific file types. For example, you can backup all `.py` files but exclude temporary `.tmp` files.

#### Creating Your Backup
1. Review the file preview to ensure you're backing up what you need
2. Give your backup a descriptive name
3. Click **Create Backup** to generate the archive
4. The backup file will download automatically as a ZIP archive

> [!NOTE]
> Backup creation may take a few minutes depending on the amount of data. You'll see progress updates during the process.

### Restoring from Backup
The restore process allows you to recover your Agent Zero setup from a previous backup:

#### Starting a Restore
1. Navigate to **Settings** → **Backup** tab
2. Click **Restore from Backup**
3. Upload your backup ZIP file

#### Reviewing Before Restore
After uploading, you can review and customize the restore:

* **Inspect Metadata**: View information about when and where the backup was created
* **Edit Restore Patterns**: Choose exactly which files to restore
* **Preview Changes**: See which files will be restored, overwritten, or skipped
* **Cross-System Compatibility**: Paths are automatically adjusted when restoring on different systems

#### Restore Options
Configure how the restore should handle existing files:

* **Overwrite**: Replace existing files with backup versions
* **Skip**: Keep existing files, only restore missing ones
* **Backup Existing**: Create backup copies of existing files before overwriting

#### Clean Before Restore
Optionally clean up existing files before restoring:

* **Smart Cleanup**: Remove files that match backup patterns before restoring
* **Preview Cleanup**: See which files would be deleted before confirming
* **Safe Operation**: Only affects files that match your specified patterns

### Best Practices

#### When to Create Backups
* **Before Major Changes**: Always backup before significant modifications
* **Regular Schedule**: Create weekly or monthly backups of your work
* **Before System Updates**: Backup before updating Agent Zero or system components
* **Project Milestones**: Save backups when completing important work

#### Backup Management
* **Descriptive Names**: Use clear names like "project-completion-2024-01"
* **External Storage**: Keep backup files in a safe location outside Agent Zero
* **Multiple Versions**: Maintain several backup versions for different time periods
* **Test Restores**: Occasionally test restoring backups to ensure they work

#### Security Considerations
* **API Keys**: Backups include your API keys and sensitive configuration
* **Secure Storage**: Store backup files securely and don't share them
* **Clean Systems**: When restoring on new systems, verify all configurations

### Common Use Cases

#### System Migration
Moving Agent Zero to a new server or computer:
1. Create a complete backup on the original system
2. Install Agent Zero on the new system
3. Restore the backup to migrate all your data and settings

#### Project Archival
Preserving completed projects:
1. Create project-specific backup patterns
2. Include only relevant files and conversations
3. Store the backup as a project archive

#### Development Snapshots
Saving work-in-progress states:
1. Create frequent backups during development
2. Use descriptive names to track progress
3. Restore previous versions if something goes wrong

#### Team Collaboration
Sharing Agent Zero configurations:
1. Create backups with shared configurations and tools
2. Team members can restore to get consistent setups
3. Include documentation and project files

> [!IMPORTANT]
> Always test your backup and restore process in a safe environment before relying on it for critical data. Keep multiple backup versions and store them in secure, accessible locations.

> [!TIP]
> The backup system is designed to work across different operating systems and Agent Zero installations. Your backups from a Windows system will work on Linux, and vice versa.
