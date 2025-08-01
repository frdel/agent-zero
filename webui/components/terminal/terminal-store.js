import { createStore } from '/js/AlpineStore.js';

// Terminal modal store
export const store = createStore('terminal', {
    // State
    show: false,
    isLoading: false,
    error: null,
    terminalUrl: null,
    sessionNumber: 0,
    contextId: null,
    connectionInfo: null,
    postMessageFilter: null,

    // Actions
    async openTerminal(contextId, sessionNumber = 0) {
        this.show = true;
        this.isLoading = true;
        this.error = null;
        this.terminalUrl = null;
        this.sessionNumber = sessionNumber;
        this.contextId = contextId;
        this.connectionInfo = null;

        // Install postMessage filter to prevent WebSSH errors
        this.installPostMessageFilter();

        try {
            // Get terminal connection details from API
            const response = await fetch('/terminal_connection_info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.csrf_token || ''
                },
                body: JSON.stringify({
                    context_id: contextId,
                    session: sessionNumber
                })
            });

            const data = await response.json();

            if (data.error) {
                this.error = data.error;
                this.isLoading = false;
                return;
            }

            if (data.success && data.webssh_url) {
                this.terminalUrl = data.webssh_url;
                this.connectionInfo = `${data.ssh_user}@${data.ssh_host}:${data.ssh_port}`;
                this.isLoading = false;
            } else {
                this.error = 'Failed to get terminal connection details';
                this.isLoading = false;
            }

        } catch (error) {
            console.error('Failed to open terminal:', error);
            this.error = `Failed to connect: ${error.message}`;
            this.isLoading = false;
        }
    },

    closeTerminal() {
        this.show = false;
        this.isLoading = false;
        this.error = null;
        this.terminalUrl = null;
        this.sessionNumber = 0;
        this.contextId = null;
        this.connectionInfo = null;

        // Remove postMessage filter
        this.removePostMessageFilter();
    },

    refreshTerminal() {
        if (this.contextId !== null) {
            // Close and reopen
            const contextId = this.contextId;
            const sessionNumber = this.sessionNumber;
            this.closeTerminal();

            // Small delay to ensure cleanup
            setTimeout(() => {
                this.openTerminal(contextId, sessionNumber);
            }, 100);
        }
    },

    onTerminalLoad() {
        // Terminal iframe has loaded successfully
        this.isLoading = false;
        this.error = null;
    },

    installPostMessageFilter() {
        // Filter postMessage events to prevent WebSSH errors
        this.postMessageFilter = (event) => {
            // Block postMessage events that don't have string data
            // These can cause WebSSH's cross_origin_connect to fail
            if (event.data && typeof event.data !== 'string') {
                console.debug('Blocked non-string postMessage for WebSSH protection:', event);
                event.stopImmediatePropagation();
                return false;
            }
        };

        // Install as capture listener to catch events before they reach the iframe
        window.addEventListener('message', this.postMessageFilter, true);
    },

    removePostMessageFilter() {
        if (this.postMessageFilter) {
            window.removeEventListener('message', this.postMessageFilter, true);
            this.postMessageFilter = null;
        }
    }
});
