// Canvas UI Display for Agent Zero Artifacts
export class ArtifactCanvas {
    constructor() {
        this.canvasContainer = null;
        this.activeCanvas = null;
        this.artifacts = new Map();
        this.wsConnection = null;
        this.isStreaming = false;
        this.currentChatId = null;
        this.init();
    }

    init() {
        this.createCanvasContainer();
        this.setupWebSocketConnection();
        this.setupArtifactHandlers();
    }

    createCanvasContainer() {
        // Create the canvas container as a side panel
        this.canvasContainer = document.createElement('div');
        this.canvasContainer.id = 'artifact-canvas-panel';
        this.canvasContainer.className = 'artifact-canvas-panel hidden';
        
        this.canvasContainer.innerHTML = `
            <div class="artifact-canvas-header">
                <div class="artifact-canvas-title">Live Artifact Preview</div>
                <div class="artifact-canvas-controls">
                    <button class="artifact-btn" id="artifact-refresh">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
                        </svg>
                    </button>
                    <button class="artifact-btn" id="artifact-fullscreen">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
                        </svg>
                    </button>
                    <button class="artifact-btn" id="artifact-close">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                        </svg>
                    </button>
                </div>
            </div>
            <div class="artifact-canvas-content">
                <div class="artifact-tabs">
                    <div class="artifact-tab active" data-type="preview">Preview</div>
                    <div class="artifact-tab" data-type="code">Code</div>
                    <div class="artifact-tab" data-type="metadata">Info</div>
                </div>
                <div class="artifact-display">
                    <div class="artifact-preview-panel active" id="artifact-preview">
                        <div class="artifact-stream-indicator" id="artifact-stream-indicator" style="display: none;">
                            <div class="stream-dots">
                                <span></span><span></span><span></span>
                            </div>
                            <span class="stream-text">Agent is writing...</span>
                        </div>
                        <iframe id="artifact-iframe" sandbox="allow-scripts allow-same-origin"></iframe>
                        <canvas id="artifact-canvas" style="display: none;"></canvas>
                        <div id="artifact-image-container" style="display: none;"></div>
                    </div>
                    <div class="artifact-code-panel" id="artifact-code">
                        <pre><code id="artifact-code-content" class="language-auto"></code></pre>
                    </div>
                    <div class="artifact-metadata-panel" id="artifact-metadata">
                        <div class="metadata-content"></div>
                    </div>
                </div>
            </div>
            <div class="artifact-canvas-footer">
                <div class="artifact-status">
                    <span class="status-indicator"></span>
                    <span class="status-text">Ready</span>
                </div>
                <div class="artifact-actions">
                    <button class="artifact-btn-secondary" id="artifact-download">Download</button>
                    <button class="artifact-btn-secondary" id="artifact-share">Share</button>
                </div>
            </div>
        `;
        
        // Insert after the right panel in the main container
        const rightPanel = document.getElementById('right-panel');
        rightPanel.parentNode.insertBefore(this.canvasContainer, rightPanel.nextSibling);
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Close button
        document.getElementById('artifact-close').addEventListener('click', () => {
            this.hideCanvas();
        });

        // Refresh button
        document.getElementById('artifact-refresh').addEventListener('click', () => {
            this.refreshArtifact();
        });

        // Fullscreen button
        document.getElementById('artifact-fullscreen').addEventListener('click', () => {
            this.toggleFullscreen();
        });

        // Tab switching
        document.querySelectorAll('.artifact-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.type);
            });
        });

        // Download button
        document.getElementById('artifact-download').addEventListener('click', () => {
            this.downloadArtifact();
        });

        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.canvasContainer.classList.contains('hidden')) {
                this.hideCanvas();
            }
        });
    }

    setupWebSocketConnection() {
        // Use Socket.IO for WebSocket connection
        if (typeof io === 'undefined') {
            console.error('Socket.IO not loaded');
            this.updateStatus('Error: Socket.IO not available', 'error');
            return;
        }

        this.wsConnection = io('/artifacts', {
            transports: ['websocket', 'polling']
        });
        
        this.wsConnection.on('connect', () => {
            console.log('Artifact Socket.IO connected');
            this.updateStatus('Connected', 'connected');
            
            // Subscribe to current chat if available
            if (this.currentChatId) {
                this.wsConnection.emit('subscribe', { chat_id: this.currentChatId });
            }
        });

        this.wsConnection.on('disconnect', () => {
            console.log('Artifact Socket.IO disconnected');
            this.updateStatus('Disconnected', 'disconnected');
        });

        this.wsConnection.on('artifact_update', (data) => {
            this.handleArtifactUpdate(data);
        });

        this.wsConnection.on('artifact_stream', (data) => {
            this.handleStreamUpdate(data.payload);
        });

        this.wsConnection.on('artifacts_list', (data) => {
            // Handle initial artifacts list
            console.log('Received artifacts list:', data);
        });

        this.wsConnection.on('connect_error', (error) => {
            console.error('Artifact Socket.IO connection error:', error);
            this.updateStatus('Connection Error', 'error');
        });
    }

    setupArtifactHandlers() {
        // Listen for artifact creation events from Agent Zero
        window.addEventListener('agent-artifact-created', (event) => {
            this.handleNewArtifact(event.detail);
        });

        // Listen for code execution results that might contain artifacts
        window.addEventListener('agent-code-executed', (event) => {
            this.handleCodeExecution(event.detail);
        });
    }

    handleNewArtifact(artifactData) {
        const { id, type, content, metadata } = artifactData;
        
        this.artifacts.set(id, {
            id,
            type,
            content,
            metadata,
            timestamp: Date.now()
        });

        this.displayArtifact(id);
        this.showCanvas();
    }

    handleCodeExecution(executionData) {
        // Check if code execution generated HTML, images, or other artifacts
        const { result, type, session } = executionData;
        
        if (this.isArtifactContent(result)) {
            const artifactId = `code_${session}_${Date.now()}`;
            this.handleNewArtifact({
                id: artifactId,
                type: this.detectArtifactType(result),
                content: result,
                metadata: {
                    source: 'code_execution',
                    session,
                    timestamp: Date.now()
                }
            });
        }
    }

    isArtifactContent(content) {
        // Detect if content is an artifact (HTML, SVG, image data URL, etc.)
        const htmlPattern = /<html|<svg|<canvas|data:image/i;
        const filePathPattern = /\.(html|svg|png|jpg|jpeg|gif|webp)$/i;
        
        return htmlPattern.test(content) || filePathPattern.test(content);
    }

    detectArtifactType(content) {
        if (content.includes('<html')) return 'html';
        if (content.includes('<svg')) return 'svg';
        if (content.includes('<canvas')) return 'canvas';
        if (content.startsWith('data:image')) return 'image';
        if (content.match(/\.(png|jpg|jpeg|gif|webp)$/i)) return 'image';
        return 'html'; // Default to HTML
    }

    detectLanguage(type, content) {
        // Language detection based on type and content
        if (type === 'html') return 'html';
        if (type === 'svg') return 'xml';
        if (type === 'image') return 'text';
        
        // Try to detect language from content patterns
        if (content.includes('def ') || content.includes('import ')) return 'python';
        if (content.includes('function ') || content.includes('const ') || content.includes('let ')) return 'javascript';
        if (content.includes('class ') && content.includes('public ')) return 'java';
        if (content.includes('#include') || content.includes('int main')) return 'cpp';
        if (content.includes('SELECT') || content.includes('INSERT')) return 'sql';
        if (content.includes('```')) return 'markdown';
        if (content.includes('{') && content.includes('"')) return 'json';
        
        return 'text'; // Default to plain text
    }

    displayArtifact(artifactId) {
        const artifact = this.artifacts.get(artifactId);
        if (!artifact) return;

        const iframe = document.getElementById('artifact-iframe');
        const canvas = document.getElementById('artifact-canvas');
        const imageContainer = document.getElementById('artifact-image-container');
        const codeContent = document.getElementById('artifact-code-content');
        const metadataContent = document.querySelector('.metadata-content');

        // Hide all display panels
        iframe.style.display = 'none';
        canvas.style.display = 'none';
        imageContainer.style.display = 'none';

        // Update code panel with syntax highlighting
        codeContent.textContent = artifact.content;
        
        // Detect language for syntax highlighting
        const language = this.detectLanguage(artifact.type, artifact.content);
        codeContent.className = `language-${language}`;
        
        // Apply syntax highlighting if Prism is available
        if (window.Prism) {
            window.Prism.highlightElement(codeContent);
        }

        // Update metadata panel
        metadataContent.innerHTML = `
            <div class="metadata-item">
                <label>Type:</label>
                <span>${artifact.type}</span>
            </div>
            <div class="metadata-item">
                <label>ID:</label>
                <span>${artifact.id}</span>
            </div>
            <div class="metadata-item">
                <label>Created:</label>
                <span>${new Date(artifact.timestamp).toLocaleString()}</span>
            </div>
            <div class="metadata-item">
                <label>Size:</label>
                <span>${this.formatBytes(artifact.content.length)}</span>
            </div>
            <div class="metadata-item">
                <label>Language:</label>
                <span>${language}</span>
            </div>
        `;

        // Update canvas title
        const titleElem = this.canvasContainer.querySelector('.artifact-canvas-title');
        let title = '';
        if (artifact.metadata && artifact.metadata.title) {
            title = artifact.metadata.title;
        } else if (artifact.id) {
            title = artifact.id;
        }
        titleElem.textContent = title ? `Artifact: ${title}` : '';

        // Display based on type
        switch (artifact.type) {
            case 'html':
                this.displayHTML(artifact.content);
                break;
            case 'svg':
                this.displaySVG(artifact.content);
                break;
            case 'canvas':
                this.displayCanvas(artifact.content);
                break;
            case 'image':
                this.displayImage(artifact.content);
                break;
            default:
                this.displayHTML(artifact.content);
        }

        this.updateStatus(`Displaying ${artifact.type.toUpperCase()}`, 'active');
    }

    displayHTML(content) {
        const iframe = document.getElementById('artifact-iframe');
        iframe.style.display = 'block';
        
        // Create a blob URL for the HTML content
        const blob = new Blob([content], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        iframe.src = url;
        
        // Clean up the URL after loading
        iframe.onload = () => {
            URL.revokeObjectURL(url);
        };
    }

    displaySVG(content) {
        const iframe = document.getElementById('artifact-iframe');
        iframe.style.display = 'block';
        
        const svgContent = `
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
                    svg { max-width: 100%; max-height: 100%; }
                </style>
            </head>
            <body>${content}</body>
            </html>
        `;
        
        const blob = new Blob([svgContent], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        iframe.src = url;
        
        iframe.onload = () => {
            URL.revokeObjectURL(url);
        };
    }

    displayCanvas(content) {
        // For canvas content, we'll render it in an iframe with the canvas code
        this.displayHTML(content);
    }

    displayImage(content) {
        const imageContainer = document.getElementById('artifact-image-container');
        imageContainer.style.display = 'block';
        
        const img = document.createElement('img');
        img.src = content;
        img.style.maxWidth = '100%';
        img.style.maxHeight = '100%';
        img.style.objectFit = 'contain';
        
        imageContainer.innerHTML = '';
        imageContainer.appendChild(img);
    }

    showCanvas() {
        this.canvasContainer.classList.remove('hidden');
        this.canvasContainer.classList.add('visible');
        // Adjust the main container layout to accommodate the canvas
        const container = document.querySelector('.container');
        if (container) {
            container.classList.add('canvas-open');
            // Collapse left panel if open
            const leftPanel = document.getElementById('left-panel');
            if (leftPanel && !leftPanel.classList.contains('hidden')) {
                leftPanel.classList.add('hidden');
            }
            // Track left panel open state for resizing
            if (!container.classList.contains('left-panel-open')) {
                container.classList.remove('left-panel-open');
            }
        }
        // Default to Code tab
        this.switchTab('code');
    }

    hideCanvas() {
        this.canvasContainer.classList.remove('visible');
        this.canvasContainer.classList.add('hidden');
        // Restore the main container layout
        const container = document.querySelector('.container');
        if (container) {
            container.classList.remove('canvas-open');
        }
        // Restore the left panel if it was hidden
        const leftPanel = document.getElementById('left-panel');
        if (leftPanel && leftPanel.classList.contains('hidden')) {
            leftPanel.classList.remove('hidden');
        }
    }

    toggleCanvas() {
        if (this.canvasContainer.classList.contains('hidden')) {
            this.showCanvas();
        } else {
            this.hideCanvas();
        }
    }

    switchTab(tabType) {
        // Update tab buttons
        document.querySelectorAll('.artifact-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelector(`[data-type="${tabType}"]`).classList.add('active');

        // Update panels
        document.querySelectorAll('.artifact-preview-panel, .artifact-code-panel, .artifact-metadata-panel').forEach(panel => {
            panel.classList.remove('active');
        });
        document.getElementById(`artifact-${tabType}`).classList.add('active');
    }

    refreshArtifact() {
        const activeArtifact = Array.from(this.artifacts.values()).pop();
        if (activeArtifact) {
            this.displayArtifact(activeArtifact.id);
        }
    }

    toggleFullscreen() {
        this.canvasContainer.classList.toggle('fullscreen');
    }

    downloadArtifact() {
        const activeArtifact = Array.from(this.artifacts.values()).pop();
        if (!activeArtifact) return;

        const blob = new Blob([activeArtifact.content], { 
            type: this.getMimeType(activeArtifact.type) 
        });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `artifact_${activeArtifact.id}.${this.getFileExtension(activeArtifact.type)}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        URL.revokeObjectURL(url);
    }

    updateStatus(text, type) {
        const statusText = document.querySelector('.status-text');
        const statusIndicator = document.querySelector('.status-indicator');
        
        statusText.textContent = text;
        statusIndicator.className = `status-indicator ${type}`;
    }

    getMimeType(type) {
        const mimeTypes = {
            'html': 'text/html',
            'svg': 'image/svg+xml',
            'canvas': 'text/html',
            'image': 'image/png'
        };
        return mimeTypes[type] || 'text/plain';
    }

    getFileExtension(type) {
        const extensions = {
            'html': 'html',
            'svg': 'svg',
            'canvas': 'html',
            'image': 'png'
        };
        return extensions[type] || 'txt';
    }

    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    handleArtifactUpdate(data) {
        // Handle real-time updates from WebSocket
        if (data.type === 'artifact_update') {
            this.handleNewArtifact(data.payload);
        } else if (data.type === 'artifact_stream') {
            this.handleStreamUpdate(data.payload);
        }
    }

    handleStreamUpdate(streamData) {
        // Handle streaming updates for live artifacts
        const { artifactId, chunk, isComplete, metadata, type } = streamData;
        let artifact = this.artifacts.get(artifactId);
        if (!artifact) {
            // Create new artifact entry on first chunk
            artifact = {
                id: artifactId,
                type: type || 'text',
                content: '',
                metadata: metadata || {},
                timestamp: Date.now()
            };
            this.artifacts.set(artifactId, artifact);
            this.showCanvas();
        }
        artifact.content += chunk;
        // Show streaming indicator if not complete
        const streamIndicator = document.getElementById('artifact-stream-indicator');
        if (streamIndicator) {
            streamIndicator.style.display = isComplete ? 'none' : 'flex';
        }
        // Update code panel in real time
        this.displayArtifact(artifactId);
        if (isComplete) {
            // Optionally, finalize artifact (e.g., save, hide indicator)
            if (streamIndicator) streamIndicator.style.display = 'none';
        }
    }

    setChatId(chatId) {
        this.currentChatId = chatId;
        if (this.wsConnection && this.wsConnection.connected) {
            // Unsubscribe from previous chat
            if (this.currentChatId) {
                this.wsConnection.emit('unsubscribe', { chat_id: this.currentChatId });
            }
            // Subscribe to new chat
            this.wsConnection.emit('subscribe', { chat_id: chatId });
            this.updateStatus(`Watching chat: ${chatId}`, 'active');
        }
    }

    // Add method to create artifacts from agent output
    createArtifactFromAgentOutput(content, type = 'auto', metadata = {}) {
        // Auto-detect type if not specified
        if (type === 'auto') {
            type = this.detectArtifactType(content);
        }
        
        const artifactId = `agent_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        // Create artifact data
        const artifactData = {
            id: artifactId,
            type: type,
            content: content,
            metadata: {
                source: 'agent_output',
                chat_id: this.currentChatId || 'default',
                created_at: new Date().toISOString(),
                ...metadata
            }
        };
        
        // Store locally first
        this.artifacts.set(artifactId, {
            ...artifactData,
            timestamp: Date.now()
        });
        
        // Display the artifact
        this.displayArtifact(artifactId);
        this.showCanvas();
        
        // Send to backend to persist
        if (this.wsConnection && this.wsConnection.connected) {
            this.wsConnection.emit('create_artifact', artifactData);
        }
        
        return artifactId;
    }
}

// Listen for left panel open/close to adjust layout
window.addEventListener('DOMContentLoaded', () => {
    const leftPanel = document.getElementById('left-panel');
    const container = document.querySelector('.container');
    if (leftPanel && container) {
        const observer = new MutationObserver(() => {
            if (window.artifactCanvas && window.artifactCanvas.canvasContainer.classList.contains('visible')) {
                if (!leftPanel.classList.contains('hidden')) {
                    container.classList.add('left-panel-open');
                } else {
                    container.classList.remove('left-panel-open');
                }
            }
        });
        observer.observe(leftPanel, { attributes: true, attributeFilter: ['class'] });
    }
});
