/**
 * Canvas functionality for Agent Zero
 * Handles canvas panel toggling, content management, and real-time updates
 */

(function() {
    'use strict';

class CanvasManager {
    constructor() {
        this.canvasPanel = null;
        this.canvasPreview = null;
        this.canvasLoading = null;
        this.canvasToggleBtn = null;
        this.canvasCloseBtn = null;
        this.canvasRefreshBtn = null;
        this.canvasFullscreenBtn = null;
        this.canvasCopyBtn = null;
        this.canvasExportBtn = null;
        this.container = null;
        this.isVisible = false;
        this.isFullscreen = false;
        this.currentContent = null;
        this.currentType = null;
        this.currentRawCode = null;
        this.activeTab = 'preview';
        
        // Tab elements
        this.tabPreview = null;
        this.tabCode = null;
        this.tabContentPreview = null;
        this.tabContentCode = null;
        this.codeDisplay = null;
        this.codeTypeDisplay = null;
        this.codeCopyBtn = null;
        
        this.init();
    }

    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initElements());
        } else {
            this.initElements();
        }
    }

    initElements() {
        console.log('CanvasManager: initElements called');
        
        // Get DOM elements
        this.canvasPanel = document.getElementById('canvas-panel');
        this.canvasPreview = document.getElementById('canvas-preview');
        this.canvasLoading = document.getElementById('canvas-loading');
        this.canvasToggleBtn = document.getElementById('canvas_toggle');
        this.canvasCloseBtn = document.getElementById('canvas-close');
        this.canvasRefreshBtn = document.getElementById('canvas-refresh');
        this.canvasFullscreenBtn = document.getElementById('canvas-fullscreen');
        this.canvasCopyBtn = document.getElementById('canvas-copy');
        this.canvasExportBtn = document.getElementById('canvas-export');
        this.container = document.querySelector('.container');
        
        // Tab elements
        this.tabPreview = document.getElementById('canvas-tab-preview');
        this.tabCode = document.getElementById('canvas-tab-code');
        this.tabContentPreview = document.getElementById('canvas-preview-content');
        this.tabContentCode = document.getElementById('canvas-code-content');
        this.codeDisplay = document.getElementById('canvas-code-display');
        this.codeTypeDisplay = document.querySelector('.canvas-code-type');
        this.codeCopyBtn = document.getElementById('canvas-code-copy');

        console.log('CanvasManager: Elements found:', {
            canvasPanel: !!this.canvasPanel,
            canvasPreview: !!this.canvasPreview,
            canvasLoading: !!this.canvasLoading,
            canvasToggleBtn: !!this.canvasToggleBtn,
            canvasCloseBtn: !!this.canvasCloseBtn,
            container: !!this.container,
            tabPreview: !!this.tabPreview,
            tabCode: !!this.tabCode,
            codeDisplay: !!this.codeDisplay
        });

        this.bindEvents();
        this.setInitialState();
        
        console.log('CanvasManager: Initialization complete');
    }

    bindEvents() {
        // Toggle button (main toggle)
        if (this.canvasToggleBtn) {
            this.canvasToggleBtn.addEventListener('click', () => this.toggle());
        }

        // Close button
        if (this.canvasCloseBtn) {
            this.canvasCloseBtn.addEventListener('click', () => this.hide());
        }

        // Refresh button
        if (this.canvasRefreshBtn) {
            this.canvasRefreshBtn.addEventListener('click', () => this.refresh());
        }

        // Fullscreen button
        if (this.canvasFullscreenBtn) {
            this.canvasFullscreenBtn.addEventListener('click', () => this.toggleFullscreen());
        }

        // Copy button
        if (this.canvasCopyBtn) {
            this.canvasCopyBtn.addEventListener('click', () => this.copyCode());
        }

        // Export button
        if (this.canvasExportBtn) {
            this.canvasExportBtn.addEventListener('click', () => this.exportCode());
        }

        // Tab buttons
        if (this.tabPreview) {
            this.tabPreview.addEventListener('click', () => this.switchTab('preview'));
        }

        if (this.tabCode) {
            this.tabCode.addEventListener('click', () => this.switchTab('code'));
        }

        // Code copy button
        if (this.codeCopyBtn) {
            this.codeCopyBtn.addEventListener('click', () => this.copyCode());
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));

        // Window resize
        window.addEventListener('resize', () => this.handleResize());
    }

    setInitialState() {
        // Canvas starts hidden
        this.isVisible = false;
        this.isFullscreen = false;
        
        if (this.canvasPanel) {
            this.canvasPanel.classList.add('canvas-hidden');
            this.canvasPanel.classList.remove('canvas-visible', 'canvas-fullscreen');
        }

        if (this.container) {
            this.container.classList.remove('canvas-open');
        }
    }

    toggle() {
        console.log('CanvasManager: toggle called, isVisible:', this.isVisible);
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    show() {
        console.log('CanvasManager: show called');
        if (!this.canvasPanel || !this.container) {
            console.error('CanvasManager: Missing elements for show()', {
                canvasPanel: !!this.canvasPanel,
                container: !!this.container
            });
            return;
        }

        this.isVisible = true;
        
        // Check if left panel should be auto-closed when canvas opens
        const leftPanel = document.getElementById('left-panel');
        const rightPanel = document.getElementById('right-panel');
        
        console.log('Canvas show() called - checking if should auto-close left panel');
        console.log('  leftPanel found:', !!leftPanel);
        console.log('  rightPanel found:', !!rightPanel);
        
        if (leftPanel) {
            this.sidebarWasVisible = !leftPanel.classList.contains('hidden');
            console.log('  sidebarWasVisible:', this.sidebarWasVisible);
            
            // Check if user has manually controlled the sidebar
            // Wait a bit to ensure initialization is complete and user-controlled state is properly set
            setTimeout(() => {
                const isUserControlled = leftPanel.hasAttribute('data-user-controlled');
                console.log('  isUserControlled (after init):', isUserControlled);
                
                // Auto-close if not user-controlled and on desktop (don't interfere with mobile)
                const shouldAutoClose = !isUserControlled && window.innerWidth > 768;
                console.log('  shouldAutoClose:', shouldAutoClose, '(width:', window.innerWidth, ', userControlled:', isUserControlled, ')');
                
                if (shouldAutoClose && rightPanel) {
                    console.log('  Before auto-close - leftPanel hidden:', leftPanel.classList.contains('hidden'));
                    
                    // Auto-close the left panel when canvas opens (desktop only)
                    leftPanel.classList.add('hidden');
                    rightPanel.classList.add('expanded');
                    
                    console.log('  After auto-close - leftPanel hidden:', leftPanel.classList.contains('hidden'));
                    console.log('  After auto-close - rightPanel expanded:', rightPanel.classList.contains('expanded'));
                    
                    // Also hide overlay if visible
                    const overlay = document.getElementById('sidebar-overlay');
                    if (overlay) {
                        overlay.classList.remove('visible');
                        console.log('  Overlay hidden');
                    }
                } else {
                    console.log('  Skipping auto-close: user-controlled sidebar or mobile device');
                }
            }, 200); // Increased delay to ensure proper initialization
        } else {
            console.log('  Could not auto-close: panels not found');
        }
        
        // Update panel classes
        this.canvasPanel.classList.remove('canvas-hidden');
        this.canvasPanel.classList.add('canvas-visible');
        
        // Update container for split-screen layout
        this.container.classList.add('canvas-open');
        
        // Show loading state initially
        this.showLoading();
        
        // Force refresh of any existing content to apply new syntax highlighting
        setTimeout(() => {
            if (this.currentContent) {
                this.refreshCodeDisplay();
            }
        }, 100);
        
        // Hide loading after a brief moment (for demo purposes)
        setTimeout(() => {
            this.hideLoading();
        }, 1000);

        this.updateToggleButtonState();
    }

    hide() {
        console.log('CanvasManager: hide called');
        if (!this.canvasPanel || !this.container) {
            console.error('CanvasManager: Missing elements for hide()', {
                canvasPanel: !!this.canvasPanel,
                container: !!this.container
            });
            return;
        }

        this.isVisible = false;
        this.isFullscreen = false;
        
        // Update panel classes
        this.canvasPanel.classList.remove('canvas-visible', 'canvas-fullscreen');
        this.canvasPanel.classList.add('canvas-hidden');
        
        // Update container and clear any inline styles
        this.container.classList.remove('canvas-open');
        
        // Clear any inline styles that might have been set during fullscreen mode
        if (this.container) {
            this.container.style.marginRight = '';
            this.container.style.width = '';
        }
        
        // Remove fullscreen body class if it exists
        document.body.classList.remove('canvas-fullscreen-active');

        // Show the left sidebar when canvas is hidden
        if (window.toggleSidebar) {
            window.toggleSidebar(true);
        } else {
            console.warn('toggleSidebar function not available on window.');
        }
        
        // Don't auto-restore left panel when canvas closes - let user control it manually
        
        this.updateToggleButtonState();
    }

    toggleFullscreen() {
        if (!this.canvasPanel || !this.isVisible) return;

        this.isFullscreen = !this.isFullscreen;
        
        if (this.isFullscreen) {
            this.canvasPanel.classList.add('canvas-fullscreen');
            this.canvasPanel.classList.remove('canvas-visible');
            // Add body class for hiding UI elements
            document.body.classList.add('canvas-fullscreen-active');
            // Ensure container doesn't interfere with fullscreen mode
            if (this.container) {
                this.container.style.marginRight = '0';
                this.container.style.width = '100%';
            }
        } else {
            this.canvasPanel.classList.remove('canvas-fullscreen');
            this.canvasPanel.classList.add('canvas-visible');
            // Remove body class to restore UI elements
            document.body.classList.remove('canvas-fullscreen-active');
            // Restore container layout for side-by-side mode
            if (this.container) {
                this.container.style.marginRight = '50vw';
                this.container.style.width = 'calc(100% - 50vw)';
            }
        }
    }

    refresh() {
        if (!this.isVisible || !this.canvasPreview) return;
        
        this.showLoading();
        
        // Refresh the preview content
        if (this.currentContent) {
            this.updateContent(this.currentContent, this.currentType);
            // Also refresh code display if on code tab
            if (this.activeTab === 'code') {
                setTimeout(() => {
                    this.refreshCodeDisplay();
                }, 100);
            }
        } else {
            // Reload iframe if no specific content
            this.canvasPreview.src = this.canvasPreview.src;
        }
        
        setTimeout(() => {
            this.hideLoading();
        }, 500);
    }

    showLoading() {
        if (this.canvasLoading) {
            this.canvasLoading.classList.remove('hidden');
        }
    }

    hideLoading() {
        if (this.canvasLoading) {
            this.canvasLoading.classList.add('hidden');
        }
    }

    updateContent(content, type = 'html') {
        if (!this.canvasPreview || !this.isVisible) return;

        this.currentContent = content;
        this.currentType = type;
        
        // Store raw code for the code tab
        if (content.startsWith('http')) {
            // It's a URL, we'll need to fetch the content for code display
            this.currentRawCode = null;
        } else {
            this.currentRawCode = content;
        }
        
        this.showLoading();
        
        try {
            switch (type) {
                case 'html':
                    this.updateHTMLContent(content);
                    break;
                case 'url':
                    this.updateURLContent(content);
                    break;
                case 'markdown':
                    this.updateMarkdownContent(content);
                    break;
                default:
                    this.updateHTMLContent(content);
            }
            
            // Update code display if on code tab
            if (this.activeTab === 'code' && this.currentRawCode) {
                this.displayCode(this.currentRawCode, type);
            }
            
        } catch (error) {
            console.error('Error updating canvas content:', error);
            this.showError('Failed to update canvas content');
        }
        
        setTimeout(() => {
            this.hideLoading();
        }, 500);
    }

    updateHTMLContent(html) {
        // Replace external placeholder images with local data URIs to prevent network errors
        html = this.replaceExternalImages(html);
        
        // Get current theme
        const isDarkMode = document.body.classList.contains('dark-mode') || 
                          document.documentElement.classList.contains('dark-mode') ||
                          window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        // Create a complete HTML document with theme-aware styling
        const fullHTML = `
<!DOCTYPE html>
<html lang="en" class="${isDarkMode ? 'dark-mode' : 'light-mode'}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Canvas Preview</title>
    <style>
        :root {
            /* Dark mode variables */
            --color-background-dark: #131313;
            --color-text-dark: #d4d4d4;
            --color-primary-dark: #737a81;
            --color-secondary-dark: #656565;
            --color-accent-dark: #cf6679;
            --color-border-dark: #444444a8;
            
            /* Light mode variables */
            --color-background-light: #dbdbdb;
            --color-text-light: #333333;
            --color-primary-light: #384653;
            --color-secondary-light: #e8eaf6;
            --color-accent-light: #b00020;
            --color-border-light: #e0e0e0c7;
        }
        
        html.dark-mode {
            --color-background: var(--color-background-dark);
            --color-text: var(--color-text-dark);
            --color-primary: var(--color-primary-dark);
            --color-secondary: var(--color-secondary-dark);
            --color-accent: var(--color-accent-dark);
            --color-border: var(--color-border-dark);
        }
        
        html.light-mode {
            --color-background: var(--color-background-light);
            --color-text: var(--color-text-light);
            --color-primary: var(--color-primary-light);
            --color-secondary: var(--color-secondary-light);
            --color-accent: var(--color-accent-light);
            --color-border: var(--color-border-light);
        }
        
        body {
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: var(--color-text, #333);
            background-color: var(--color-background, #fff);
            min-height: 100vh;
        }
        
        .canvas-content {
            max-width: 100%;
            word-wrap: break-word;
        }
        
        /* Ensure user content inherits theme colors when appropriate */
        h1, h2, h3, h4, h5, h6 {
            color: var(--color-text, #333);
        }
        
        /* Style links to match theme */
        a {
            color: var(--color-accent, #007acc);
        }
        
        /* Style code blocks */
        pre, code {
            background-color: var(--color-secondary, #f5f5f5);
            color: var(--color-text, #333);
            border: 1px solid var(--color-border, #ddd);
            border-radius: 4px;
            padding: 8px;
        }
        
        /* Handle broken images gracefully */
        img {
            max-width: 100%;
            height: auto;
        }
        
        img[alt]:after {
            content: "🖼️ " attr(alt);
            display: block;
            padding: 10px;
            background-color: var(--color-secondary, #f5f5f5);
            color: var(--color-text, #666);
            border: 1px dashed var(--color-border, #ddd);
            border-radius: 4px;
            text-align: center;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="canvas-content">
        ${html}
    </div>
    <script>
        // Handle image loading errors gracefully
        document.addEventListener('DOMContentLoaded', function() {
            const images = document.querySelectorAll('img');
            images.forEach(img => {
                img.onerror = function() {
                    this.style.display = 'none';
                    const placeholder = document.createElement('div');
                    placeholder.style.cssText = 'padding: 20px; background-color: #f5f5f5; border: 1px dashed #ddd; border-radius: 4px; text-align: center; color: #666; font-style: italic;';
                    placeholder.innerHTML = '🖼️ Image not available: ' + (this.alt || 'Placeholder image');
                    this.parentNode.insertBefore(placeholder, this.nextSibling);
                };
            });
        });
    </script>
</body>
</html>`;

        // Use blob URL for security
        const blob = new Blob([fullHTML], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        this.canvasPreview.src = url;
        
        // Clean up blob URL after loading and prevent Alpine.js interference
        this.canvasPreview.onload = () => {
            URL.revokeObjectURL(url);
            
            // Prevent Alpine.js from processing iframe content
            try {
                const iframeDoc = this.canvasPreview.contentDocument;
                if (iframeDoc && iframeDoc.body) {
                    iframeDoc.body.setAttribute('x-data', '');
                    iframeDoc.documentElement.setAttribute('x-ignore', '');
                }
            } catch (e) {
                // Cross-origin restrictions prevent access, which is expected
                console.log('Canvas: Could not access iframe content for Alpine.js protection');
            }
        };
    }

    updateURLContent(url) {
        // If URL is relative, ensure it's resolved against current location
        let resolvedUrl = url;
        if (url.startsWith('/')) {
            // For relative URLs, use current host and port
            resolvedUrl = `${window.location.protocol}//${window.location.host}${url}`;
        }
        console.log('Canvas: Setting iframe src to:', resolvedUrl);
        console.log('Canvas: Original URL was:', url);
        console.log('Canvas: Current location:', window.location.href);
        
        // Fetch the content for the code tab
        this.fetchContentForCodeTab(resolvedUrl);
        
        // Add error handling for failed loads
        this.canvasPreview.onerror = () => {
            console.error('Canvas: Failed to load URL:', resolvedUrl);
            this.showError(`Canvas content not available. This may be due to port configuration or server connectivity issues.`);
        };
        
        // Also check for 404 errors by monitoring iframe load events
        this.canvasPreview.onload = () => {
            try {
                // Try to access iframe content to detect errors
                const iframeDoc = this.canvasPreview.contentDocument || this.canvasPreview.contentWindow.document;
                if (iframeDoc && iframeDoc.title.includes('Not Found')) {
                    console.warn('Canvas: Detected 404 error in iframe');
                    this.showError(`Canvas file not found. Please check if the server is running on the correct port.`);
                }
            } catch (e) {
                // Cross-origin restrictions prevent access, which is expected for external URLs
                console.log('Canvas: Iframe loaded (cross-origin or successful)');
            }
        };
        
        this.canvasPreview.src = resolvedUrl;
    }

    async fetchContentForCodeTab(url) {
        try {
            console.log('Canvas: Fetching content for code tab from:', url);
            const response = await fetch(url, {
                credentials: 'same-origin', // Include authentication cookies
                headers: {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
            });
            if (response.ok) {
                const content = await response.text();
                this.currentRawCode = content;
                console.log('Canvas: Successfully fetched content for code tab (', content.length, 'characters)');
                
                // If we're currently on the code tab, update it
                if (this.activeTab === 'code') {
                    this.displayCode(content, this.currentType || 'html');
                }
            } else {
                console.warn('Canvas: Failed to fetch content for code tab:', response.status, response.statusText);
                this.currentRawCode = `<!-- Unable to fetch content: ${response.status} ${response.statusText} -->`;
                
                // If we're currently on the code tab, show the error
                if (this.activeTab === 'code') {
                    this.displayCode(this.currentRawCode, this.currentType || 'html');
                }
            }
        } catch (error) {
            console.error('Canvas: Error fetching content for code tab:', error);
            this.currentRawCode = `<!-- Error fetching content: ${error.message} -->`;
            
            // If we're currently on the code tab, show the error
            if (this.activeTab === 'code') {
                this.displayCode(this.currentRawCode, this.currentType || 'html');
            }
        }
    }

    updateMarkdownContent(markdown) {
        // For now, convert basic markdown to HTML
        // In a real implementation, you'd use a proper markdown parser
        const html = this.basicMarkdownToHTML(markdown);
        this.updateHTMLContent(html);
    }

    basicMarkdownToHTML(markdown) {
        return markdown
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    replaceExternalImages(html) {
        // Replace external placeholder service URLs with local data URIs
        // This prevents network errors when external services are unavailable
        
        // Replace via.placeholder.com URLs
        html = html.replace(/https?:\/\/via\.placeholder\.com\/(\d+)x(\d+)\/([A-Fa-f0-9]{6})\/([A-Fa-f0-9]{6})\?text=([^"'\s]+)/g, 
            (match, width, height, bgColor, textColor, text) => {
                return this.generatePlaceholderDataURI(width, height, bgColor, textColor, decodeURIComponent(text.replace(/\+/g, ' ')));
            });
        
        // Replace other common placeholder services
        html = html.replace(/https?:\/\/(picsum\.photos|placeholder\.com|dummyimage\.com|placekitten\.com)\/[^"'\s]*/g, 
            (match) => {
                return this.generatePlaceholderDataURI(200, 200, 'CCCCCC', '666666', 'Image Placeholder');
            });
        
        return html;
    }

    generatePlaceholderDataURI(width, height, bgColor, textColor, text) {
        // Create a simple SVG placeholder image as a data URI
        const svg = `
            <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
                <rect width="100%" height="100%" fill="#${bgColor}" stroke="#${textColor}" stroke-width="2"/>
                <text x="50%" y="50%" font-family="Arial, sans-serif" font-size="14" fill="#${textColor}" 
                      text-anchor="middle" dominant-baseline="middle">${text}</text>
            </svg>
        `;
        
        // Convert SVG to data URI
        const encodedSvg = encodeURIComponent(svg);
        return `data:image/svg+xml,${encodedSvg}`;
    }

    showError(message) {
        const errorHTML = `
            <div class="canvas-error">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
                <h3>Canvas Error</h3>
                <p>${message}</p>
            </div>
        `;
        this.updateHTMLContent(errorHTML);
    }

    updateToggleButtonState() {
        if (!this.canvasToggleBtn) return;
        
        if (this.isVisible) {
            this.canvasToggleBtn.classList.add('active');
            this.canvasToggleBtn.style.backgroundColor = 'var(--color-secondary)';
        } else {
            this.canvasToggleBtn.classList.remove('active');
            this.canvasToggleBtn.style.backgroundColor = '';
        }
    }

    handleKeyboardShortcuts(e) {
        // Ctrl/Cmd + K to toggle canvas
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            this.toggle();
        }
        
        // Escape to close canvas
        if (e.key === 'Escape' && this.isVisible) {
            this.hide();
        }
        
        // F11 to toggle fullscreen (when canvas is visible)
        if (e.key === 'F11' && this.isVisible) {
            e.preventDefault();
            this.toggleFullscreen();
        }
    }

    handleResize() {
        // Handle responsive behavior on window resize
        if (this.isVisible && window.innerWidth <= 768) {
            // On mobile, make canvas fullscreen when visible
            if (!this.isFullscreen) {
                this.canvasPanel.classList.add('canvas-fullscreen');
                this.canvasPanel.classList.remove('canvas-visible');
            }
        }
    }

    // Public API for agent integration
    createArtifact(content, type = 'html', title = 'Canvas') {
        console.log('Canvas: createArtifact called', { type, title });
        if (!this.isVisible) {
            this.show();
        }
        
        // Update canvas title
        const titleElement = document.querySelector('.canvas-title');
        if (titleElement) {
            titleElement.textContent = title;
        }
        
        this.updateContent(content, type);
    }

    updateArtifact(content, type = 'html') {
        console.log('Canvas: updateArtifact called', { type });
        if (this.isVisible) {
            this.updateContent(content, type);
        }
    }

    // Method to display canvas from URL (used by agent integration)
    displayFromUrl(url, title = 'Canvas Artifact') {
        console.log('Canvas: displayFromUrl called', { url, title });
        if (!this.isVisible) {
            this.show();
        }
        
        // Update canvas title
        const titleElement = document.querySelector('.canvas-title');
        if (titleElement) {
            titleElement.textContent = title;
        }
        
        this.updateContent(url, 'url');
    }

    // Enhanced update method for real-time streaming
    streamContent(content, type = 'html', append = false) {
        if (!this.isVisible) {
            this.show();
        }
        
        if (append && this.currentContent) {
            // Append new content to existing content
            this.updateContent(this.currentContent + content, type);
        } else {
            this.updateContent(content, type);
        }
    }
    
    // Real-time streaming for canvas content
    startStreaming(canvasId, title = 'Live Canvas', type = 'html') {
        console.log('Canvas: Starting real-time streaming for', canvasId);
        
        // Show canvas and set up for streaming
        if (!this.isVisible) {
            this.show();
        }
        
        // Update canvas title
        const titleElement = document.querySelector('.canvas-title');
        if (titleElement) {
            titleElement.textContent = title;
        }
        
        // Initialize streaming state
        this.streamingCanvasId = canvasId;
        this.streamingContent = '';
        this.streamingType = type;
        this.isStreaming = true;
        
        // Show loading indicator
        this.showLoading();
        
        // Initialize content
        this.updateContent('<div class="streaming-placeholder">Canvas is being created...</div>', 'html');
    }
    
    // Update streaming content incrementally
    updateStreamingContent(canvasId, content, isComplete = false) {
        if (!this.isStreaming || this.streamingCanvasId !== canvasId) {
            return;
        }
        
        console.log('Canvas: Updating streaming content for', canvasId, 'complete:', isComplete);
        
        // Accumulate content
        this.streamingContent += content;
        
        // Update the canvas with accumulated content
        this.updateContent(this.streamingContent, this.streamingType);
        
        if (isComplete) {
            this.finishStreaming();
        }
    }
    
    // Finish streaming mode
    finishStreaming() {
        console.log('Canvas: Finishing streaming for', this.streamingCanvasId);
        
        this.isStreaming = false;
        this.streamingCanvasId = null;
        this.hideLoading();
        
        // Update code display if on code tab
        if (this.activeTab === 'code' && this.streamingContent) {
            this.displayCode(this.streamingContent, this.streamingType);
        }
        
        // Store the final content
        this.currentRawCode = this.streamingContent;
        this.streamingContent = '';
    }
    
    // Check if currently streaming a specific canvas
    isStreamingCanvas(canvasId) {
        return this.isStreaming && this.streamingCanvasId === canvasId;
    }

    isCanvasVisible() {
        return this.isVisible;
    }

    getCanvasContent() {
        return this.currentContent;
    }

    // Method for agents to check if canvas is available
    static isAvailable() {
        return window.canvasManager !== undefined;
    }

    // Tab management
    switchTab(tabName) {
        console.log('Canvas: Switching to tab', tabName);
        
        if (tabName === this.activeTab) return;
        
        this.activeTab = tabName;
        
        // Update tab buttons
        if (this.tabPreview && this.tabCode) {
            this.tabPreview.classList.toggle('active', tabName === 'preview');
            this.tabCode.classList.toggle('active', tabName === 'code');
        }
        
        // Update tab content
        if (this.tabContentPreview && this.tabContentCode) {
            this.tabContentPreview.classList.toggle('active', tabName === 'preview');
            this.tabContentCode.classList.toggle('active', tabName === 'code');
        }
        
        // If switching to code tab and we have content, display it with enhanced highlighting
        if (tabName === 'code' && this.currentRawCode) {
            this.displayCode(this.currentRawCode, this.currentType);
        } else if (tabName === 'code' && !this.currentRawCode) {
            // Try to fetch code from preview if not available
            this.refreshCodeDisplay();
        }
    }

    // Refresh code display with current content
    refreshCodeDisplay() {
        if (!this.currentContent) return;
        
        // If currentContent is a URL, fetch the content
        if (this.currentContent.startsWith('http') || this.currentContent.startsWith('/')) {
            this.fetchContentForCodeTab(this.currentContent);
        } else {
            // Display the content directly
            this.currentRawCode = this.currentContent;
            this.displayCode(this.currentContent, this.currentType || 'html');
        }
    }

    // Auto-detect language based on code content
    detectLanguage(code) {
        // Simple language detection based on patterns
        if (code.includes('<!DOCTYPE') || code.includes('<html') || /<\w+[^>]*>/i.test(code)) {
            return 'html';
        } else if (code.includes('{') && code.includes('}') && /[.#]\w+\s*\{/.test(code)) {
            return 'css';
        } else if (code.includes('function') || code.includes('const ') || code.includes('let ') || code.includes('=>')) {
            return 'javascript';
        } else if (code.includes('def ') || code.includes('import ') || code.includes('class ') || /^\s*#/.test(code)) {
            return 'python';
        } else if (code.trim().startsWith('{') && code.trim().endsWith('}')) {
            return 'json';
        }
        return 'text';
    }

    // Code display and management
    displayCode(code, type = 'html') {
        if (!this.codeDisplay) return;
        
        this.currentRawCode = code;
        
        // Auto-detect language if type is generic
        if (type === 'html' && !code.includes('<')) {
            type = this.detectLanguage(code);
        }
        
        // Update code type display
        if (this.codeTypeDisplay) {
            const displayType = type === 'javascript' ? 'JS' : type.toUpperCase();
            this.codeTypeDisplay.textContent = displayType;
        }
        
        // Enhanced syntax highlighting
        const highlightedCode = this.applySyntaxHighlighting(code, type);
        
        // Add line numbers
        const lines = highlightedCode.split('\n');
        const numberedLines = lines.map((line, index) => {
            const lineNumber = (index + 1).toString().padStart(3, ' ');
            return `<span class="line-number">${lineNumber}</span><span class="line-content">${line}</span>`;
        }).join('\n');
        
        // Apply canvas code display class and display in code block
        this.codeDisplay.className = 'canvas-code-display';
        this.codeDisplay.innerHTML = `<code>${numberedLines}</code>`;
    }

    // Enhanced syntax highlighting with VS Code-like styling
    applySyntaxHighlighting(code, type) {
        // First escape HTML entities
        const escaped = code
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        
        if (type === 'html') {
            return escaped
                // Comments first (to avoid interfering with other patterns)
                .replace(/(&lt;!--.*?--&gt;)/gs, '<span class="syntax-comment">$1</span>')
                // DOCTYPE declarations
                .replace(/(&lt;!DOCTYPE[^&]*&gt;)/gi, '<span class="syntax-keyword">$1</span>')
                // HTML tags with attributes
                .replace(/(&lt;\/?)([\w-]+)([^&]*?)(&gt;)/g, function(match, openBracket, tagName, attributes, closeBracket) {
                    const highlightedTag = `${openBracket}<span class="syntax-tag">${tagName}</span>`;
                    const highlightedAttributes = attributes
                        .replace(/([\w-]+)=/g, '<span class="syntax-attribute">$1</span>=')
                        .replace(/="([^"]*)"/g, '=<span class="syntax-string">"$1"</span>')
                        .replace(/='([^']*)'/g, '=<span class="syntax-string">\'$1\'</span>');
                    return highlightedTag + highlightedAttributes + closeBracket;
                });
        } else if (type === 'css') {
            return escaped
                // Comments
                .replace(/(\/\*.*?\*\/)/gs, '<span class="syntax-comment">$1</span>')
                // At-rules
                .replace(/@(media|import|keyframes|charset|font-face|namespace|supports|document)\b/g, '<span class="syntax-keyword">@$1</span>')
                // Selectors
                .replace(/([.#]?[a-zA-Z-_][a-zA-Z0-9-_]*(?:\[[^\]]*\])?(?:::?[a-zA-Z-_][a-zA-Z0-9-_]*(?:\([^)]*\))?)*)\s*{/g, '<span class="syntax-tag">$1</span> {')
                // Properties
                .replace(/([a-zA-Z-]+)(?=\s*:)/g, '<span class="syntax-attribute">$1</span>')
                // Values (excluding URLs which should be strings)
                .replace(/:\s*([^;{}]+);/g, function(match, value) {
                    return ': ' + value
                        .replace(/url\(([^)]*)\)/g, '<span class="syntax-function">url</span>(<span class="syntax-string">$1</span>)')
                        .replace(/#([a-fA-F0-9]{3,8})\b/g, '<span class="syntax-number">#$1</span>')
                        .replace(/\b(\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|pt|pc|in|cm|mm|ex|ch|vmin|vmax|s|ms|deg|rad|turn|hz|khz)?)\b/g, '<span class="syntax-number">$1</span>')
                        .replace(/\b(inherit|initial|unset|auto|none|normal|bold|italic|center|left|right|block|inline|flex|grid|absolute|relative|fixed|static|transparent)\b/g, '<span class="syntax-constant">$1</span>') + ';';
                });
        } else if (type === 'javascript' || type === 'js') {
            return escaped
                // Comments
                .replace(/(\/\/.*$)/gm, '<span class="syntax-comment">$1</span>')
                .replace(/(\/\*.*?\*\/)/gs, '<span class="syntax-comment">$1</span>')
                // Template literals
                .replace(/`([^`]*)`/g, '<span class="syntax-string">`$1`</span>')
                // Regular strings
                .replace(/'([^']*)'/g, '<span class="syntax-string">\'$1\'</span>')
                .replace(/"([^"]*)"/g, '<span class="syntax-string">"$1"</span>')
                // Numbers
                .replace(/\b(\d+\.?\d*)\b/g, '<span class="syntax-number">$1</span>')
                // Function definitions
                .replace(/\b(function)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)/g, '<span class="syntax-keyword">$1</span> <span class="syntax-function">$2</span>')
                .replace(/\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?=\()/g, '<span class="syntax-function">$1</span>')
                // Keywords
                .replace(/\b(function|var|let|const|if|else|for|while|do|switch|case|default|break|continue|return|class|extends|import|export|from|as|async|await|try|catch|finally|throw|new|this|super|typeof|instanceof|in|of|delete|void|null|undefined|true|false)\b/g, '<span class="syntax-keyword">$1</span>')
                // Built-in objects and functions
                .replace(/\b(String|Number|Boolean|Array|Object|Date|RegExp|Math|JSON|console|window|document|Promise|Set|Map|WeakMap|WeakSet|Symbol|BigInt|Proxy|Reflect|ArrayBuffer|DataView|Int8Array|Uint8Array|Uint8ClampedArray|Int16Array|Uint16Array|Int32Array|Uint32Array|Float32Array|Float64Array|BigInt64Array|BigUint64Array)\b/g, '<span class="syntax-builtin">$1</span>')
                // Operators
                .replace(/([+\-*\/=!<>&|^~%?:;,.])/g, '<span class="syntax-operator">$1</span>');
        } else if (type === 'python' || type === 'py') {
            return escaped
                // Multi-line strings/docstrings
                .replace(/""".*?"""/gs, '<span class="syntax-string">$&</span>')
                .replace(/'''.*?'''/gs, '<span class="syntax-string">$&</span>')
                // Comments
                .replace(/(#.*$)/gm, '<span class="syntax-comment">$1</span>')
                // Regular strings
                .replace(/'([^']*)'/g, '<span class="syntax-string">\'$1\'</span>')
                .replace(/"([^"]*)"/g, '<span class="syntax-string">"$1"</span>')
                // Numbers
                .replace(/\b(\d+\.?\d*)\b/g, '<span class="syntax-number">$1</span>')
                // Function definitions
                .replace(/\b(def)\s+([a-zA-Z_][a-zA-Z0-9_]*)/g, '<span class="syntax-keyword">$1</span> <span class="syntax-function">$2</span>')
                .replace(/\b(class)\s+([a-zA-Z_][a-zA-Z0-9_]*)/g, '<span class="syntax-keyword">$1</span> <span class="syntax-type">$2</span>')
                // Keywords
                .replace(/\b(def|class|if|else|elif|for|while|return|import|from|as|try|except|finally|raise|with|lambda|yield|global|nonlocal|pass|break|continue|and|or|not|in|is|assert|del|None|True|False)\b/g, '<span class="syntax-keyword">$1</span>')
                // Built-in functions and types
                .replace(/\b(str|int|float|bool|list|dict|tuple|set|frozenset|len|range|enumerate|zip|map|filter|open|print|input|type|isinstance|hasattr|getattr|setattr|delattr|abs|min|max|sum|sorted|reversed|any|all|round|pow|divmod|hash|id|repr|format|chr|ord|bin|oct|hex)\b/g, '<span class="syntax-builtin">$1</span>');
        } else if (type === 'json') {
            return escaped
                // String keys
                .replace(/"([^"]*)"(\s*:)/g, '<span class="syntax-attribute">"$1"</span>$2')
                // String values
                .replace(/:\s*"([^"]*)"/g, ': <span class="syntax-string">"$1"</span>')
                // Boolean and null values
                .replace(/:\s*(true|false|null)/g, ': <span class="syntax-keyword">$1</span>')
                // Number values
                .replace(/:\s*(-?\d+\.?\d*)/g, ': <span class="syntax-number">$1</span>')
                // Punctuation
                .replace(/([{}[\],])/g, '<span class="syntax-punctuation">$1</span>');
        }
        
        // Default: return escaped code
        return escaped;
    }

    // Copy code functionality
    async copyCode() {
        const codeToCopy = this.currentRawCode || this.getCodeFromPreview();
        
        if (!codeToCopy) {
            this.showToast('No code to copy', 'warning');
            return;
        }
        
        try {
            await navigator.clipboard.writeText(codeToCopy);
            this.showToast('Code copied to clipboard!', 'success');
        } catch (err) {
            console.error('Failed to copy code:', err);
            this.showToast('Failed to copy code', 'error');
        }
    }

    // Export functionality
    exportCode() {
        const codeToExport = this.currentRawCode || this.getCodeFromPreview();
        
        if (!codeToExport) {
            this.showToast('No code to export', 'warning');
            return;
        }
        
        const filename = `canvas-artifact-${Date.now()}.${this.getFileExtension()}`;
        const blob = new Blob([codeToExport], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.showToast(`Exported as ${filename}`, 'success');
    }

    // Helper methods
    getCodeFromPreview() {
        // Try to extract code from iframe if available
        try {
            const iframe = this.canvasPreview;
            if (iframe && iframe.contentDocument) {
                return iframe.contentDocument.documentElement.outerHTML;
            }
        } catch (e) {
            console.warn('Could not access iframe content:', e);
        }
        return null;
    }

    getFileExtension() {
        const typeExtensions = {
            'html': 'html',
            'css': 'css',
            'javascript': 'js',
            'js': 'js',
            'python': 'py',
            'markdown': 'md',
            'md': 'md'
        };
        return typeExtensions[this.currentType] || 'txt';
    }

    showToast(message, type = 'info') {
        // Use existing toast system if available
        if (window.showToast) {
            window.showToast(message, type);
        } else {
            console.log(`Toast ${type}: ${message}`);
        }
    }

    // Enhanced updateContent to support code display
    updateContent(content, type = 'html') {
        if (!this.canvasPreview || !this.isVisible) return;

        this.currentContent = content;
        this.currentType = type;
        
        // Store raw code for the code tab
        if (content.startsWith('http')) {
            // It's a URL, we'll need to fetch the content for code display
            this.currentRawCode = null;
        } else {
            this.currentRawCode = content;
        }
        
        this.showLoading();
        
        try {
            switch (type) {
                case 'html':
                    this.updateHTMLContent(content);
                    break;
                case 'url':
                    this.updateURLContent(content);
                    break;
                case 'markdown':
                    this.updateMarkdownContent(content);
                    break;
                default:
                    this.updateHTMLContent(content);
            }
            
            // Update code display if on code tab
            if (this.activeTab === 'code' && this.currentRawCode) {
                this.displayCode(this.currentRawCode, type);
            }
            
        } catch (error) {
            console.error('Error updating canvas content:', error);
            this.showError('Failed to update canvas content');
        }
        
        setTimeout(() => {
            this.hideLoading();
        }, 500);
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        window.canvasManager = new CanvasManager();
        console.log('Canvas Manager initialized!');
    });
} else {
    window.canvasManager = new CanvasManager();
    console.log('Canvas Manager initialized!');
}

})(); // End IIFE