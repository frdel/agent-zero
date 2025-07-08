
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

    async handleFieldButton(field) {
        console.log(`Button clicked: ${field.id}`);

        if (field.id === "mcp_servers_config") {
            openModal("settings/mcp/client/mcp-servers.html");
        }
        // Handle Ollama buttons - this assumes button IDs are like 'ollama_refresh_status_button_chat_model'
        const ollamaActionMatch = field.id.match(/^ollama_(\w+)_button_(\w+)$/);
        if (ollamaActionMatch) {
            const action = ollamaActionMatch[1]; // e.g., refresh_status, refresh_local_models, pull_model
            const prefix = ollamaActionMatch[2]; // e.g., chat_model, util_model, embed_model
            this.handleOllamaAction(action, prefix, field);
        }
    },

    async handleOllamaAction(action, prefix, field) {
        console.log(`Handling Ollama action: ${action} for prefix: ${prefix}`);
        switch (action) {
            case 'refresh_status':
                await this.refreshOllamaStatus(prefix);
                break;
            case 'refresh_local_models':
                await this.fetchOllamaLocalModels(prefix);
                break;
            case 'pull_model':
                await this.pullOllamaModel(prefix);
                break;
            default:
                console.warn(`Unknown Ollama action: ${action}`);
        }
    },

    async refreshOllamaStatus(prefix) {
        const statusFieldId = `ollama_status_${prefix}`;
        const statusField = this.findFieldById(statusFieldId);
        if (!statusField) return;

        statusField.value = "Checking...";
        try {
            const response = await fetch('/api/ollama/status');
            const data = await response.json();
            if (response.ok) {
                statusField.value = `Status: ${data.status} - ${data.message} (URL: ${data.url || 'N/A'})`;
            } else {
                statusField.value = `Error: ${data.error || 'Unknown error'} (URL: ${data.url || 'N/A'})`;
            }
        } catch (e) {
            statusField.value = `Failed to fetch status: ${e.message}`;
            window.toastFetchError("Error fetching Ollama status", e);
        }
        this.updateFieldValueInSettings(statusFieldId, statusField.value);
    },

    async fetchOllamaLocalModels(prefix) {
        const modelsListFieldId = `ollama_local_models_list_${prefix}`;
        const modelsListField = this.findFieldById(modelsListFieldId);
        if (!modelsListField) return;

        modelsListField.value = "Fetching models...";
        try {
            const response = await fetch('/api/ollama/models');
            const data = await response.json();
            if (response.ok) {
                if (data.models && data.models.length > 0) {
                    modelsListField.value = data.models.map(m => `${m.name} (Size: ${(m.size / 1e9).toFixed(2)}GB, Family: ${m.details.family || 'N/A'})`).join('\n');
                } else {
                    modelsListField.value = "No local models found or Ollama service not running.";
                }
            } else {
                modelsListField.value = `Error fetching models: ${data.error || 'Unknown error'}`;
            }
        } catch (e) {
            modelsListField.value = `Failed to fetch models: ${e.message}`;
            window.toastFetchError("Error fetching Ollama local models", e);
        }
        this.updateFieldValueInSettings(modelsListFieldId, modelsListField.value);
    },

    async pullOllamaModel(prefix) {
        const modelNameFieldId = `ollama_pull_model_name_${prefix}`;
        const pullStatusFieldId = `ollama_pull_model_status_${prefix}`;

        const modelNameField = this.findFieldById(modelNameFieldId);
        const pullStatusField = this.findFieldById(pullStatusFieldId);

        if (!modelNameField || !pullStatusField) return;

        const modelName = modelNameField.value;
        if (!modelName || modelName.trim() === "") {
            pullStatusField.value = "Please enter a model name to pull.";
            this.updateFieldValueInSettings(pullStatusFieldId, pullStatusField.value);
            return;
        }

        pullStatusField.value = `Starting to pull ${modelName}...`;
        this.updateFieldValueInSettings(pullStatusFieldId, pullStatusField.value);

        const eventSource = new EventSource(`/api/ollama/pull`, {
            method: 'POST', // EventSource doesn't directly support POST, this is a conceptual workaround
                            // Actual implementation requires fetch with stream and manual SSE parsing or a library
                            // For simplicity, assuming a backend that can handle POST for SSE initiation if possible,
                            // or this needs to be a GET endpoint if using EventSource directly.
                            // Given the python backend uses stream_with_context, it should work with a POST request
                            // initiated by fetch, and then the JS needs to read the stream.
                            // Let's adjust to use fetch for streaming.
        });

        // This is a simplified representation. Proper SSE handling with POST is more complex.
        // Typically, you'd use fetch() and read the stream.
        // The backend is set up for SSE, so fetch should work.

        try {
            const response = await fetch('/api/ollama/pull', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream'
                },
                body: JSON.stringify({ model_name: modelName, stream: true })
            });

            if (!response.ok) {
                const errorData = await response.json(); // Try to get JSON error from initial response
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            pullStatusField.value = `Pulling ${modelName}: \n`;

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    pullStatusField.value += "\nPull stream finished.";
                    this.updateFieldValueInSettings(pullStatusFieldId, pullStatusField.value);
                    // Automatically refresh local models list after pull
                    await this.fetchOllamaLocalModels(prefix);
                    break;
                }

                buffer += decoder.decode(value, { stream: true });

                // Process buffer line by line for SSE messages
                let eolIndex;
                while ((eolIndex = buffer.indexOf('\n')) >= 0) {
                    const line = buffer.substring(0, eolIndex).trim();
                    buffer = buffer.substring(eolIndex + 1);

                    if (line.startsWith("data: ")) {
                        const jsonData = line.substring(6); // Remove "data: "
                        try {
                            const eventData = JSON.parse(jsonData);
                            let statusMsg = "";
                            if(eventData.status) statusMsg += `Status: ${eventData.status}`;
                            if(eventData.digest) statusMsg += ` Digest: ${eventData.digest}`;
                            if(eventData.total && eventData.completed) {
                                const percent = eventData.total > 0 ? ((eventData.completed / eventData.total) * 100).toFixed(2) : 0;
                                statusMsg += ` Progress: ${percent}% (${(eventData.completed/1024/1024).toFixed(2)}MB / ${(eventData.total/1024/1024).toFixed(2)}MB)`;
                            } else if (eventData.total) {
                                statusMsg += ` Total: ${(eventData.total/1024/1024).toFixed(2)}MB`;
                            }

                            if (eventData.error) {
                                statusMsg = `Error: ${eventData.error}`;
                                if(eventData.details) statusMsg += ` Details: ${typeof eventData.details === 'string' ? eventData.details : JSON.stringify(eventData.details)}`;
                                pullStatusField.value += statusMsg + "\n";
                                this.updateFieldValueInSettings(pullStatusFieldId, pullStatusField.value);
                                return; // Stop on error
                            }

                            if (statusMsg) {
                                // Append to existing status, creating a log-like view
                                pullStatusField.value = pullStatusField.value.split('\n').slice(0, 1).join('\n') + '\n' + statusMsg; // Keep first line, update with latest
                                // To make it a log:
                                // pullStatusField.value += statusMsg + "\n";
                                this.updateFieldValueInSettings(pullStatusFieldId, pullStatusField.value);
                            }

                            if (eventData.status === 'success' || eventData.status === 'completed pull process') {
                                pullStatusField.value += "\nPull complete!";
                                this.updateFieldValueInSettings(pullStatusFieldId, pullStatusField.value);
                                // Automatically refresh local models list after pull
                                await this.fetchOllamaLocalModels(prefix);
                                return; // Exit loop
                            }
                        } catch (e) {
                            console.warn("Failed to parse SSE JSON data:", jsonData, e);
                            // pullStatusField.value += "Received non-JSON data: " + jsonData + "\n";
                            // this.updateFieldValueInSettings(pullStatusFieldId, pullStatusField.value);
                        }
                    }
                }
            }
        } catch (e) {
            pullStatusField.value = `Failed to pull model: ${e.message}`;
            this.updateFieldValueInSettings(pullStatusFieldId, pullStatusField.value);
            window.toastFetchError(`Error pulling Ollama model ${modelName}`, e);
        }
    },

    // Helper to find a field in the settings structure by its ID
    findFieldById(fieldId) {
        if (!this.settings || !this.settings.sections) return null;
        for (const section of this.settings.sections) {
            if (section.fields) {
                const field = section.fields.find(f => f.id === fieldId);
                if (field) return field;
            }
        }
        console.warn(`Field with ID ${fieldId} not found in settings structure.`);
        return null;
    },

    // Helper to update field value in the settings model to ensure Alpine reactivity
    updateFieldValueInSettings(fieldId, newValue) {
        if (!this.settings || !this.settings.sections) return;
        let found = false;
        for (const section of this.settings.sections) {
            if (section.fields) {
                const field = section.fields.find(f => f.id === fieldId);
                if (field) {
                    field.value = newValue;
                    found = true;
                    break;
                }
            }
        }
        // This is important if Alpine is not directly watching nested properties
        // Force a reactivity update if necessary, e.g. by reassigning this.settings
        // this.settings = { ...this.settings }; // Or a more targeted update if possible
    },

    // --- OpenRouter Autocomplete Logic ---
    openRouterFreeModels: [], // Stores fetched free models for OpenRouter
    currentOpenRouterSuggestions: [], // Stores current suggestions for the active input
    activeOpenRouterInputPrefix: null, // Tracks which model input (chat, util, embed) is active for suggestions

    async fetchOpenRouterFreeModels() {
        if (this.openRouterFreeModels.length > 0) { // Cache results
            // console.log("Using cached OpenRouter free models.");
            return;
        }
        console.log("Fetching OpenRouter free models...");
        try {
            const response = await fetch('/api/openrouter/models'); // Assuming this endpoint is created
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || `Failed to fetch OpenRouter models: ${response.status}`);
            }
            const data = await response.json();
            this.openRouterFreeModels = data.models || [];
            console.log("Fetched OpenRouter free models:", this.openRouterFreeModels.length);
        } catch (e) {
            this.openRouterFreeModels = []; // Clear on error
            window.toastFetchError("Error fetching OpenRouter models", e);
            console.error("Error fetching OpenRouter models:", e);
        }
    },

    // Call this when an OpenRouter model name input gets focus or input
    // providerPrefix: 'chat_model', 'util_model', or 'embed_model'
    // currentInputValue: the current text in the model name input
    updateOpenRouterSuggestions(providerPrefix, currentInputValue) {
        this.activeOpenRouterInputPrefix = providerPrefix;
        const modelProviderField = this.findFieldById(`${providerPrefix}_provider`);

        if (!modelProviderField || modelProviderField.value !== 'OPENROUTER') {
            this.currentOpenRouterSuggestions = [];
            return;
        }

        if (!currentInputValue || currentInputValue.trim() === "") {
            this.currentOpenRouterSuggestions = this.openRouterFreeModels.slice(0, 10); // Show some initial suggestions or all if few
        } else {
            const lowerInput = currentInputValue.toLowerCase();
            this.currentOpenRouterSuggestions = this.openRouterFreeModels.filter(model =>
                (model.id && model.id.toLowerCase().includes(lowerInput)) ||
                (model.name && model.name.toLowerCase().includes(lowerInput))
            ).slice(0, 10); // Limit suggestions
        }
        // console.log("Updated OpenRouter suggestions for", providerPrefix, ":", this.currentOpenRouterSuggestions.length);
        // In a real UI, you'd now re-render the suggestions dropdown.
        // With Alpine, this.currentOpenRouterSuggestions being reactive would update the UI.
    },

    // Call this when a suggestion is selected
    selectOpenRouterSuggestion(suggestion) {
        if (!this.activeOpenRouterInputPrefix || !suggestion || !suggestion.id) return;

        const modelNameFieldId = `${this.activeOpenRouterInputPrefix}_name`;
        const modelNameField = this.findFieldById(modelNameFieldId);
        if (modelNameField) {
            modelNameField.value = suggestion.id; // Set the model ID as the value
            this.updateFieldValueInSettings(modelNameFieldId, suggestion.id); // Ensure Alpine knows
        }
        this.currentOpenRouterSuggestions = []; // Clear suggestions
        this.activeOpenRouterInputPrefix = null; // Reset active input
        // console.log("Selected OpenRouter suggestion:", suggestion.id);
    },

    // This function should be triggered when a model provider <select> changes.
    // It needs to be wired up in the HTML, or called from an event listener on those select elements.
    async handleProviderChange(providerFieldId, providerPrefix) {
        const providerField = this.findFieldById(providerFieldId);
        if (providerField && providerField.value === 'OPENROUTER') {
            await this.fetchOpenRouterFreeModels();
        }
        // Hide/show Ollama fields based on provider (example)
        this.toggleOllamaFieldsVisibility(providerPrefix, providerField.value === 'OLLAMA');

        // Clear suggestions if provider is not OpenRouter
        if (providerField && providerField.value !== 'OPENROUTER' && this.activeOpenRouterInputPrefix === providerPrefix) {
            this.currentOpenRouterSuggestions = [];
        }
    },

    // Helper to toggle Ollama fields. Assumes specific IDs.
    // This is a basic example; more robust handling might be needed in Alpine templates.
    toggleOllamaFieldsVisibility(prefix, show) {
        const ollamaFieldIds = [
            `ollama_status_${prefix}`,
            `ollama_refresh_status_button_${prefix}`,
            `ollama_local_models_list_${prefix}`,
            `ollama_refresh_local_models_button_${prefix}`,
            `ollama_pull_model_name_${prefix}`,
            `ollama_pull_model_button_${prefix}`,
            `ollama_pull_model_status_${prefix}`,
        ];
        // This part is tricky without direct DOM access or Alpine's x-show.
        // If using Alpine, x-show on the field containers in HTML is the way.
        // This JS function is more of a placeholder for the logic.
        console.log(`Logic to ${show ? 'show' : 'hide'} Ollama fields for prefix ${prefix} should be handled by Alpine's x-show in the template.`);

        // If not using x-show, you'd find the DOM elements and toggle display:
        // ollamaFieldIds.forEach(id => {
        //     const element = document.getElementById(id); // Or a more specific selector
        //     if (element) {
        //          // Find the parent container of the field to hide/show the whole row
        //         const fieldContainer = element.closest('.settings-field-container'); // Example selector
        //         if (fieldContainer) fieldContainer.style.display = show ? '' : 'none';
        //     }
        // });
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
