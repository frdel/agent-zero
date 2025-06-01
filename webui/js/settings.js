const settingsModalProxy = {
    isOpen: false,
    settings: {},
    resolvePromise: null,
    activeTab: 'agent', // Default tab

    // Computed property for filtered sections
    get filteredSections() {
        if (!this.settings || !this.settings.sections) return [];
        const filteredSections = this.settings.sections.filter(section => section.tab === this.activeTab);

        // If no sections match the current tab (or all tabs are missing), show all sections
        if (filteredSections.length === 0) {
            return this.settings.sections;
        }

        return filteredSections;
    },

    // Switch tab method
    switchTab(tabName) {
        // Update our component state
        this.activeTab = tabName;

        // Update the store safely
        const store = Alpine.store('root');
        if (store) {
            store.activeTab = tabName;
        }

        localStorage.setItem('settingsActiveTab', tabName);

        // Auto-scroll active tab into view after a short delay to ensure DOM updates
        setTimeout(() => {
            const activeTab = document.querySelector('.settings-tab.active');
            if (activeTab) {
                activeTab.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            }

            // When switching to the scheduler tab, initialize Flatpickr components
            if (tabName === 'scheduler') {
                console.log('Switching to scheduler tab, initializing Flatpickr');
                const schedulerElement = document.querySelector('[x-data="schedulerSettings"]');
                if (schedulerElement) {
                    const schedulerData = Alpine.$data(schedulerElement);
                    if (schedulerData) {
                        // Start polling
                        if (typeof schedulerData.startPolling === 'function') {
                            schedulerData.startPolling();
                        }

                        // Initialize Flatpickr if editing or creating
                        if (typeof schedulerData.initFlatpickr === 'function') {
                            // Check if we're creating or editing and initialize accordingly
                            if (schedulerData.isCreating) {
                                schedulerData.initFlatpickr('create');
                            } else if (schedulerData.isEditing) {
                                schedulerData.initFlatpickr('edit');
                            }
                        }

                        // Force an immediate fetch
                        if (typeof schedulerData.fetchTasks === 'function') {
                            schedulerData.fetchTasks();
                        }
                    }
                }
            }
            
            // When switching to the tunnel tab, initialize tunnelSettings
            if (tabName === 'tunnel') {
                console.log('Switching to tunnel tab, initializing tunnelSettings');
                const tunnelElement = document.querySelector('[x-data="tunnelSettings"]');
                if (tunnelElement) {
                    const tunnelData = Alpine.$data(tunnelElement);
                    if (tunnelData && typeof tunnelData.checkTunnelStatus === 'function') {
                        // Check tunnel status
                        tunnelData.checkTunnelStatus();
                    }
                }
            }
        }, 10);
    },

    async openModal() {
        console.log('Settings modal opening');
        const modalEl = document.getElementById('settingsModal');
        const modalAD = Alpine.$data(modalEl);

        // First, ensure the store is updated properly
        const store = Alpine.store('root');
        if (store) {
            // Set isOpen first to ensure proper state
            store.isOpen = true;
        }

        //get settings from backend
        try {
            const set = await sendJsonData("/settings_get", null);

            // First load the settings data without setting the active tab
            const settings = {
                "title": "Settings",
                "buttons": [
                    {
                        "id": "save",
                        "title": "Save",
                        "classes": "btn btn-ok"
                    },
                    {
                        "id": "cancel",
                        "title": "Cancel",
                        "type": "secondary",
                        "classes": "btn btn-cancel"
                    }
                ],
                "sections": set.settings.sections
            }

            // Update modal data
            modalAD.isOpen = true;
            modalAD.settings = settings;

            // Now set the active tab after the modal is open
            // This ensures Alpine reactivity works as expected
            setTimeout(() => {
                // Get stored tab or default to 'agent'
                const savedTab = localStorage.getItem('settingsActiveTab') || 'agent';
                console.log(`Setting initial tab to: ${savedTab}`);

                // Directly set the active tab
                modalAD.activeTab = savedTab;

                // Also update the store
                if (store) {
                    store.activeTab = savedTab;
                }

                localStorage.setItem('settingsActiveTab', savedTab);

                // Add a small delay *after* setting the tab to ensure scrolling works
                setTimeout(() => {
                    const activeTabElement = document.querySelector('.settings-tab.active');
                    if (activeTabElement) {
                        activeTabElement.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
                    }
                    // Debug log
                    const schedulerTab = document.querySelector('.settings-tab[title="Task Scheduler"]');
                    console.log(`Current active tab after direct set: ${modalAD.activeTab}`);
                    console.log('Scheduler tab active after direct initialization?',
                        schedulerTab && schedulerTab.classList.contains('active'));

                    // Explicitly start polling if we're on the scheduler tab
                    if (modalAD.activeTab === 'scheduler') {
                        console.log('Settings opened directly to scheduler tab, initializing polling');
                        const schedulerElement = document.querySelector('[x-data="schedulerSettings"]');
                        if (schedulerElement) {
                            const schedulerData = Alpine.$data(schedulerElement);
                            if (schedulerData && typeof schedulerData.startPolling === 'function') {
                                schedulerData.startPolling();
                                // Also force an immediate fetch
                                if (typeof schedulerData.fetchTasks === 'function') {
                                    schedulerData.fetchTasks();
                                }
                            }
                        }
                    }
                }, 10); // Small delay just for scrolling

            }, 5); // Keep a minimal delay for modal opening reactivity

            // Add a watcher to disable the Save button when a task is being created or edited
            const schedulerComponent = document.querySelector('[x-data="schedulerSettings"]');
            if (schedulerComponent) {
                // Watch for changes to the scheduler's editing state
                const checkSchedulerEditingState = () => {
                    const schedulerData = Alpine.$data(schedulerComponent);
                    if (schedulerData) {
                        // If we're on the scheduler tab and creating/editing a task, disable the Save button
                        const saveButton = document.querySelector('.modal-footer button.btn-ok');
                        if (saveButton && modalAD.activeTab === 'scheduler' &&
                            (schedulerData.isCreating || schedulerData.isEditing)) {
                            saveButton.disabled = true;
                            saveButton.classList.add('btn-disabled');
                        } else if (saveButton) {
                            saveButton.disabled = false;
                            saveButton.classList.remove('btn-disabled');
                        }
                    }
                };

                // Add a mutation observer to detect changes in the scheduler component's state
                const observer = new MutationObserver(checkSchedulerEditingState);
                observer.observe(schedulerComponent, { attributes: true, subtree: true, childList: true });

                // Also watch for tab changes to update button state
                modalAD.$watch('activeTab', checkSchedulerEditingState);

                // Initial check
                setTimeout(checkSchedulerEditingState, 100);
            }

            return new Promise(resolve => {
                this.resolvePromise = resolve;
            });

        } catch (e) {
            window.toastFetchError("Error getting settings", e)
        }
    },

    async handleButton(buttonId) {
        if (buttonId === 'save') {

            const modalEl = document.getElementById('settingsModal');
            const modalAD = Alpine.$data(modalEl);
            try {
                resp = await window.sendJsonData("/settings_set", modalAD.settings);
            } catch (e) {
                window.toastFetchError("Error saving settings", e)
                return
            }
            document.dispatchEvent(new CustomEvent('settings-updated', { detail: resp.settings }));
            this.resolvePromise({
                status: 'saved',
                data: resp.settings
            });
        } else if (buttonId === 'cancel') {
            this.handleCancel();
        }

        // Stop scheduler polling if it's running
        this.stopSchedulerPolling();

        // First update our component state
        this.isOpen = false;

        // Then safely update the store
        const store = Alpine.store('root');
        if (store) {
            // Use a slight delay to avoid reactivity issues
            setTimeout(() => {
                store.isOpen = false;
            }, 10);
        }
    },

    async handleCancel() {
        this.resolvePromise({
            status: 'cancelled',
            data: null
        });

        // Stop scheduler polling if it's running
        this.stopSchedulerPolling();

        // First update our component state
        this.isOpen = false;

        // Then safely update the store
        const store = Alpine.store('root');
        if (store) {
            // Use a slight delay to avoid reactivity issues
            setTimeout(() => {
                store.isOpen = false;
            }, 10);
        }
    },

    // Add a helper method to stop scheduler polling
    stopSchedulerPolling() {
        // Find the scheduler component and stop polling if it exists
        const schedulerElement = document.querySelector('[x-data="schedulerSettings"]');
        if (schedulerElement) {
            const schedulerData = Alpine.$data(schedulerElement);
            if (schedulerData && typeof schedulerData.stopPolling === 'function') {
                console.log('Stopping scheduler polling on modal close');
                schedulerData.stopPolling();
            }
        }
    },

    handleFieldButton(field) {
        console.log(`Button clicked: ${field.action}`);
    }
};


// function initSettingsModal() {

//     window.openSettings = function () {
//         proxy.openModal().then(result => {
//             console.log(result);  // This will log the result when the modal is closed
//         });
//     }

//     return proxy
// }


// document.addEventListener('alpine:init', () => {
//     Alpine.store('settingsModal', initSettingsModal());
// });

document.addEventListener('alpine:init', function () {
    // Initialize the root store first to ensure it exists before components try to access it
    Alpine.store('root', {
        activeTab: localStorage.getItem('settingsActiveTab') || 'agent',
        isOpen: false,

        toggleSettings() {
            this.isOpen = !this.isOpen;
        }
    });

    // Then initialize other Alpine components
    Alpine.data('settingsModal', function () {
        return {
            settingsData: {},
            filteredSections: [],
            activeTab: 'agent',
            isLoading: true,

            async init() {
                // Initialize with the store value
                this.activeTab = Alpine.store('root').activeTab || 'agent';

                // Watch store tab changes
                this.$watch('$store.root.activeTab', (newTab) => {
                    if (typeof newTab !== 'undefined') {
                        this.activeTab = newTab;
                        localStorage.setItem('settingsActiveTab', newTab);
                        this.updateFilteredSections();
                    }
                });

                // Load settings
                await this.fetchSettings();
                this.updateFilteredSections();
            },

            switchTab(tab) {
                // Update our component state
                this.activeTab = tab;

                // Update the store safely
                const store = Alpine.store('root');
                if (store) {
                    store.activeTab = tab;
                }
            },

            async fetchSettings() {
                try {
                    this.isLoading = true;
                    const response = await fetch('/api/settings_get', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });

                    if (response.ok) {
                        const data = await response.json();
                        if (data && data.settings) {
                            this.settingsData = data.settings;
                            injectModelHints(this.settingsData);
                        } else {
                            console.error('Invalid settings data format');
                        }
                    } else {
                        console.error('Failed to fetch settings:', response.statusText);
                    }
                } catch (error) {
                    console.error('Error fetching settings:', error);
                } finally {
                    this.isLoading = false;
                }
            },

            updateFilteredSections() {
                // Filter sections based on active tab
                if (this.activeTab === 'agent') {
                    this.filteredSections = this.settingsData.sections?.filter(section =>
                        section.group === 'agent'
                    ) || [];
                } else if (this.activeTab === 'external') {
                    this.filteredSections = this.settingsData.sections?.filter(section =>
                        section.group === 'external'
                    ) || [];
                } else if (this.activeTab === 'developer') {
                    this.filteredSections = this.settingsData.sections?.filter(section =>
                        section.group === 'developer'
                    ) || [];
                } else {
                    // For any other tab, show nothing since those tabs have custom UI
                    this.filteredSections = [];
                }

                // Re-inject model hints after filtering
                this.$nextTick(() => {
                    injectModelHints(this.settingsData);
                });
            },

            // Handle provider change to update model hints
            onProviderChange(sectionId, fieldId, newValue) {
                // Find the section and update the provider value
                const section = this.settingsData.sections?.find(s => s.id === sectionId);
                if (section) {
                    const field = section.fields?.find(f => f.id === fieldId);
                    if (field) {
                        field.value = newValue;
                        // Re-inject model hints for this section
                        this.$nextTick(() => {
                            injectModelHints(this.settingsData);
                        });
                    }
                }
            },

            async saveSettings() {
                try {
                    // First validate
                    for (const section of this.settingsData.sections) {
                        for (const field of section.fields) {
                            if (field.required && (!field.value || field.value.trim() === '')) {
                                showToast(`${field.title} in ${section.title} is required`, 'error');
                                return;
                            }
                        }
                    }

                    // Prepare data
                    const formData = {};
                    for (const section of this.settingsData.sections) {
                        for (const field of section.fields) {
                            formData[field.id] = field.value;
                        }
                    }

                    // Send request
                    const response = await fetch('/api/settings_save', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(formData)
                    });

                    if (response.ok) {
                        showToast('Settings saved successfully', 'success');
                        // Refresh settings
                        await this.fetchSettings();
                    } else {
                        const errorData = await response.json();
                        throw new Error(errorData.error || 'Failed to save settings');
                    }
                } catch (error) {
                    console.error('Error saving settings:', error);
                    showToast('Failed to save settings: ' + error.message, 'error');
                }
            },

            // Handle special button field actions
            handleFieldButton(field) {
                if (field.action === 'test_connection') {
                    this.testConnection(field);
                } else if (field.action === 'reveal_token') {
                    this.revealToken(field);
                } else if (field.action === 'generate_token') {
                    this.generateToken(field);
                } else {
                    console.warn('Unknown button action:', field.action);
                }
            },

            // Test API connection
            async testConnection(field) {
                try {
                    field.testResult = 'Testing...';
                    field.testStatus = 'loading';

                    // Find the API key field
                    let apiKey = '';
                    for (const section of this.settingsData.sections) {
                        for (const f of section.fields) {
                            if (f.id === field.target) {
                                apiKey = f.value;
                                break;
                            }
                        }
                    }

                    if (!apiKey) {
                        throw new Error('API key is required');
                    }

                    // Send test request
                    const response = await fetch('/api/test_connection', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            service: field.service,
                            api_key: apiKey
                        })
                    });

                    const data = await response.json();

                    if (response.ok && data.success) {
                        field.testResult = 'Connection successful!';
                        field.testStatus = 'success';
                    } else {
                        throw new Error(data.error || 'Connection failed');
                    }
                } catch (error) {
                    console.error('Connection test failed:', error);
                    field.testResult = `Failed: ${error.message}`;
                    field.testStatus = 'error';
                }
            },

            // Reveal token temporarily
            revealToken(field) {
                // Find target field
                for (const section of this.settingsData.sections) {
                    for (const f of section.fields) {
                        if (f.id === field.target) {
                            // Toggle field type
                            f.type = f.type === 'password' ? 'text' : 'password';

                            // Update button text
                            field.value = f.type === 'password' ? 'Show' : 'Hide';

                            break;
                        }
                    }
                }
            },

            // Generate random token
            generateToken(field) {
                // Find target field
                for (const section of this.settingsData.sections) {
                    for (const f of section.fields) {
                        if (f.id === field.target) {
                            // Generate random token
                            const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
                            let token = '';
                            for (let i = 0; i < 32; i++) {
                                token += chars.charAt(Math.floor(Math.random() * chars.length));
                            }

                            // Set field value
                            f.value = token;
                            break;
                        }
                    }
                }
            },

            closeModal() {
                // Stop scheduler polling before closing the modal
                const schedulerElement = document.querySelector('[x-data="schedulerSettings"]');
                if (schedulerElement) {
                    const schedulerData = Alpine.$data(schedulerElement);
                    if (schedulerData && typeof schedulerData.stopPolling === 'function') {
                        console.log('Stopping scheduler polling on modal close');
                        schedulerData.stopPolling();
                    }
                }

                this.$store.root.isOpen = false;
            }
        };
    });
});

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    // Trigger animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    // Remove after delay
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

// ---------------------------------------------------------------------------
// LiteLLM model hints for API key fields and model name fields
// ---------------------------------------------------------------------------

const LITELLM_MODEL_HINTS = {
    openai: ['gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo', 'gpt-4o-mini', 'text-embedding-3-small', 'text-embedding-3-large'],
    anthropic: ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229'],
    deepseek: ['deepseek-chat', 'deepseek-coder', 'deepseek-v2'],
    google: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro', 'gemini-pro-vision'],
    groq: ['llama-3.1-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
    huggingface: ['sentence-transformers/all-MiniLM-L6-v2', 'mistralai/Mixtral-8x7B-Instruct-v0.1', 'HuggingFaceH4/zephyr-7b-beta'],
    mistralai: ['mistral-large-latest', 'mistral-small-latest', 'mistral-embed'],
    openrouter: ['openrouter/openai/gpt-4o', 'openrouter/anthropic/claude-3.5-sonnet', 'openrouter/mistralai/mistral-large'],
    sambanova: ['sambanova/Meta-Llama-3.1-8B-Instruct', 'sambanova/Meta-Llama-3.1-70B-Instruct'],
    azure: ['azure/gpt-4o', 'azure/gpt-35-turbo', 'azure/text-embedding-ada-002'],
    vertex_ai: ['vertex_ai/gemini-1.5-pro', 'vertex_ai/gemini-1.5-flash', 'vertex_ai/text-embedding-004'],
    bedrock: ['bedrock/anthropic.claude-3-sonnet-20240229-v1:0', 'bedrock/anthropic.claude-3-haiku-20240307-v1:0'],
    cohere: ['command-r-plus', 'command-r', 'embed-english-v3.0'],
    together_ai: ['together_ai/meta-llama/Llama-3-70b-chat-hf', 'together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1'],
};

// Model hints specifically for model name fields (with LiteLLM prefixes)
const LITELLM_MODEL_NAME_HINTS = {
    OPENAI: ['gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo', 'gpt-4o-mini', 'text-embedding-3-small', 'text-embedding-3-large'],
    ANTHROPIC: ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229'],
    DEEPSEEK: ['deepseek-chat', 'deepseek-coder', 'deepseek-v2'],
    GOOGLE: ['gemini/gemini-1.5-pro', 'gemini/gemini-1.5-flash', 'gemini/gemini-pro', 'gemini/gemini-pro-vision'],
    GROQ: ['groq/llama-3.1-70b-versatile', 'groq/llama-3.1-8b-instant', 'groq/mixtral-8x7b-32768', 'groq/gemma2-9b-it'],
    HUGGINGFACE: ['sentence-transformers/all-MiniLM-L6-v2', 'huggingface/mistralai/Mixtral-8x7B-Instruct-v0.1', 'huggingface/HuggingFaceH4/zephyr-7b-beta'],
    MISTRALAI: ['mistral/mistral-large-latest', 'mistral/mistral-small-latest', 'mistral/mistral-embed'],
    OPENROUTER: ['openrouter/openai/gpt-4o', 'openrouter/anthropic/claude-3.5-sonnet', 'openrouter/mistralai/mistral-large'],
    SAMBANOVA: ['sambanova/Meta-Llama-3.1-8B-Instruct', 'sambanova/Meta-Llama-3.1-70B-Instruct'],
    AZURE: ['azure/gpt-4o', 'azure/gpt-35-turbo', 'azure/text-embedding-ada-002'],
    VERTEX_AI: ['vertex_ai/gemini-1.5-pro', 'vertex_ai/gemini-1.5-flash', 'vertex_ai/text-embedding-004'],
    BEDROCK: ['bedrock/anthropic.claude-3-sonnet-20240229-v1:0', 'bedrock/anthropic.claude-3-haiku-20240307-v1:0'],
    COHERE: ['command-r-plus', 'command-r', 'embed-english-v3.0'],
    TOGETHER_AI: ['together_ai/meta-llama/Llama-3-70b-chat-hf', 'together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1'],
};

function injectModelHints(settings) {
    if (!settings || !settings.sections) return;

    for (const section of settings.sections) {
        if (!section.fields) continue;

        // Handle API key fields
        if (section.id === 'api_keys') {
            for (const field of section.fields) {
                if (!field.id || !field.id.startsWith('api_key_')) continue;
                const provider = field.id.replace('api_key_', '');
                const list = LITELLM_MODEL_HINTS[provider];
                if (!list) continue;
                const items = list.map(m => `<li>${m}</li>`).join('');
                field.description =
                    `<div class="model-hints"><a href="#" class="models-toggle">` +
                    `Popular models</a><div class="models-list" style="display:none"><ul>` +
                    items +
                    `</ul></div></div>`;
            }
        }

        // Handle model name fields for Chat Model, Utility Model, Embedding Model, Browser Model
        const modelSections = ['chat_model', 'util_model', 'embed_model', 'browser_model'];
        if (modelSections.includes(section.id)) {
            for (const field of section.fields) {
                if (field.id && field.id.endsWith('_model_name')) {
                    // Find the corresponding provider field
                    const providerFieldId = field.id.replace('_name', '_provider');
                    const providerField = section.fields.find(f => f.id === providerFieldId);

                    if (providerField && providerField.value) {
                        const provider = providerField.value;
                        const list = LITELLM_MODEL_NAME_HINTS[provider];
                        if (list) {
                            const items = list.map(m => `<li class="model-hint-item" data-model="${m}">${m}</li>`).join('');
                            field.description = (field.description || '') +
                                `<div class="model-hints"><a href="#" class="models-toggle">` +
                                `LiteLLM model examples</a><div class="models-list" style="display:none"><ul>` +
                                items +
                                `</ul><p class="model-hint-note">Click on a model name to copy it to the field above.</p></div></div>`;
                        }
                    }
                }
            }
        }
    }
}