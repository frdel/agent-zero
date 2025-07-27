import { createStore } from "/js/AlpineStore.js";

/**
 * Agent Selector Store - Alpine.js store for managing agent selection
 */
const agentSelectorModel = {
    // State
    agents: [],
    selectedAgentId: null,
    isLoading: false,
    error: null,
    showDropdown: false,
    
    // Initialize the store
    async init() {
        // Ensure agents array is properly initialized
        if (!Array.isArray(this.agents)) {
            this.agents = [];
        }
        
        // Wait for required functions to be available
        await this.waitForRequiredFunctions();
        
        await this.loadAgents();
        // Auto-select the main agent if none selected
        if (!this.selectedAgentId && this.agents.length > 0) {
            const mainAgent = this.agents.find(a => a.type === 'main');
            if (mainAgent) {
                this.selectedAgentId = mainAgent.id;
            }
        }
        
        // Set up periodic refresh for agent status
        setInterval(() => {
            if (!this.isLoading) {
                this.loadAgents();
            }
        }, 5000); // Refresh every 5 seconds
    },
    
    // Wait for required functions to be available
    async waitForRequiredFunctions() {
        let attempts = 0;
        const maxAttempts = 50; // 5 seconds total wait time
        
        while (attempts < maxAttempts) {
            if (window.sendJsonData && window.getContext) {
                return; // Functions are available
            }
            
            // Wait 100ms before checking again
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }
        
        throw new Error('Required functions (sendJsonData, getContext) not available after waiting');
    },
    
    // Load agents from API
    async loadAgents() {
        this.isLoading = true;
        this.error = null;
        
        try {
            // Check if required functions are available
            if (!window.sendJsonData) {
                throw new Error('sendJsonData function not available');
            }
            if (!window.getContext) {
                throw new Error('getContext function not available');
            }
            
            // Use the global sendJsonData function that's available in window
            const response = await window.sendJsonData('/agents_list', {
                context: window.getContext()
            });
            
            if (response.success) {
                // Filter out duplicates by ID and ensure unique keys
                const rawAgents = response.agents || [];
                const uniqueAgents = [];
                const seenIds = new Set();
                
                rawAgents.forEach(agent => {
                    if (agent && agent.id && !seenIds.has(agent.id)) {
                        seenIds.add(agent.id);
                        uniqueAgents.push(agent);
                    }
                });
                
                this.agents = uniqueAgents;
                
                // Debug logging
                console.log('Agents loaded:', this.agents);
                console.log('Active agent:', response.active_agent);
                
                // Update selected agent if it was the active one
                if (response.active_agent && !this.selectedAgentId) {
                    this.selectedAgentId = response.active_agent;
                }
            } else {
                throw new Error('Failed to load agents');
            }
        } catch (error) {
            this.error = error.message;
            console.error('Error loading agents:', error);
            // Ensure agents array is never undefined
            if (!Array.isArray(this.agents)) {
                this.agents = [];
            }
        } finally {
            this.isLoading = false;
        }
    },
    
    // Select an agent
    async selectAgent(agentId) {
        if (agentId === this.selectedAgentId) return;
        
        try {
            // Check if required functions are available
            if (!window.sendJsonData || !window.getContext) {
                throw new Error('Required functions not available');
            }
            
            const response = await window.sendJsonData('/agent_switch', {
                context: window.getContext(),
                target_agent_id: agentId
            });
            
            if (response.success) {
                this.selectedAgentId = agentId;
                this.showDropdown = false;
                
                // Notify other components
                window.dispatchEvent(new CustomEvent('agentChanged', {
                    detail: { agentId, agentInfo: response.agent_info }
                }));
                
                // Update chat input placeholder
                this.updateChatPlaceholder(agentId);
            } else {
                throw new Error('Failed to switch agent');
            }
        } catch (error) {
            this.error = error.message;
            console.error('Error switching agent:', error);
        }
    },
    
    // Get currently selected agent info
    getSelectedAgent() {
        return this.agents.find(a => a.id === this.selectedAgentId);
    },
    
    // Get agent display name
    getAgentDisplayName(agent) {
        if (!agent) return 'Unknown Agent';
        
        switch (agent.type) {
            case 'main': return 'Agent Zero';
            case 'subordinate': return `@${agent.role || 'subordinate'}`;
            case 'peer': return `@${agent.role || 'peer'}`;
            default: return `@${agent.id.slice(0, 8)}`;
        }
    },
    
    // Get agent mention handle (for @ mentions)
    getAgentMentionHandle(agent) {
        if (!agent) return '';
        
        switch (agent.type) {
            case 'main': return '@agent0';
            case 'subordinate': return `@${agent.role || 'subordinate'}`;
            case 'peer': return `@${agent.role || 'peer'}`;
            default: return `@${agent.id.slice(0, 8)}`;
        }
    },
    
    // Get agent status indicator
    getAgentStatusClass(agent) {
        if (!agent) return 'status-unknown';
        
        switch (agent.status) {
            case 'active':
            case 'ready':
            case 'idle': return 'status-active';
            case 'busy':
            case 'working': return 'status-busy';
            case 'paused':
            case 'stopping': return 'status-paused';
            case 'error':
            case 'failed': return 'status-error';
            default: return 'status-unknown';
        }
    },
    
    // Update chat input placeholder
    updateChatPlaceholder(agentId) {
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            const agent = this.agents.find(a => a.id === agentId);
            const agentName = this.getAgentDisplayName(agent);
            chatInput.placeholder = `Message ${agentName}...`;
        }
    },
    
    // Toggle dropdown
    toggleDropdown() {
        this.showDropdown = !this.showDropdown;
    },
    
    // Close dropdown
    closeDropdown() {
        this.showDropdown = false;
    },
    
    // Find agent by mention handle
    findAgentByMention(mentionText) {
        const cleanMention = mentionText.toLowerCase().replace('@', '');
        return this.agents.find(agent => {
            const handle = this.getAgentMentionHandle(agent).toLowerCase().replace('@', '');
            return handle === cleanMention;
        });
    },
    
    // Handle @ mention in chat input
    handleMentionInput(inputText, cursorPosition) {
        const textBeforeCursor = inputText.substring(0, cursorPosition);
        const mentionMatch = textBeforeCursor.match(/@(\w*)$/);
        
        if (mentionMatch) {
            const mentionPrefix = mentionMatch[1];
            const matchingAgents = this.agents.filter(agent => {
                const handle = this.getAgentMentionHandle(agent).toLowerCase().replace('@', '');
                return handle.startsWith(mentionPrefix.toLowerCase());
            });
            
            return {
                showSuggestions: true,
                suggestions: matchingAgents,
                mentionStart: mentionMatch.index,
                mentionPrefix: mentionPrefix
            };
        }
        
        return { showSuggestions: false, suggestions: [] };
    },
    
    // Apply mention selection to input
    applyMention(agent, inputElement, mentionStart, mentionPrefix) {
        const currentValue = inputElement.value;
        const beforeMention = currentValue.substring(0, mentionStart);
        const afterMention = currentValue.substring(mentionStart + mentionPrefix.length + 1); // +1 for @
        const mentionHandle = this.getAgentMentionHandle(agent);
        
        const newValue = beforeMention + mentionHandle + ' ' + afterMention;
        inputElement.value = newValue;
        
        // Set cursor position after the mention
        const cursorPos = beforeMention.length + mentionHandle.length + 1;
        inputElement.setSelectionRange(cursorPos, cursorPos);
        
        // Auto-select the mentioned agent
        this.selectAgent(agent.id);
    }
};

export const store = createStore("agentSelector", agentSelectorModel);