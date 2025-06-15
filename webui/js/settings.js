
const settingsModalProxy = {
    isOpen: false,
    settings: {},
    resolvePromise: null,
    activeTab: 'agent', // Default tab
    provider: 'serveo',

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

    // Initialize interactive model picker
    initModelPicker() {
        // Create dropdown container if it doesn't exist
        let picker = document.getElementById('model-picker-dropdown');
        if (!picker) {
            picker = document.createElement('div');
            picker.id = 'model-picker-dropdown';
            picker.style.position = 'absolute';
            picker.style.zIndex = 10000;
            picker.style.maxHeight = '400px';
            picker.style.overflowY = 'auto';
            picker.style.width = 'auto';
            picker.style.minWidth = '250px';
            picker.style.maxWidth = '400px';
            picker.style.fontFamily = '"Rubik", Arial, Helvetica, sans-serif';
            picker.style.display = 'none';
            // Use CSS class instead of inline styles for theming
            picker.className = 'model-picker-dropdown';
            document.body.appendChild(picker);
        }

        // Use event delegation on document body to catch all inputs with data-provider
        document.body.removeEventListener('mouseenter', this.handleModelInputHover, true);
        document.body.removeEventListener('mouseleave', this.handleModelInputLeave, true);
        document.body.addEventListener('mouseenter', this.handleModelInputHover, true);
        // Re-enable mouseleave with better timing
        document.body.addEventListener('mouseleave', this.handleModelInputLeave, true);
        
        // Set up provider dropdown change listeners
        this.setupProviderChangeListeners();
    },

    // Set up listeners for provider dropdown changes
    setupProviderChangeListeners() {
        // Define mapping between provider dropdowns and their corresponding model name fields
        const providerMappings = [
            { provider: 'chat_model_provider', modelName: 'chat_model_name' },
            { provider: 'util_model_provider', modelName: 'util_model_name' },
            { provider: 'embed_model_provider', modelName: 'embed_model_name' },
            { provider: 'browser_model_provider', modelName: 'browser_model_name' }
        ];

        // Listen for ALL changes on dropdowns and inputs to debug
        document.body.addEventListener('change', (e) => {
            
            // If this is a SELECT element (dropdown), check if it's a provider dropdown
            if (e.target.tagName === 'SELECT') {
                // Look for provider dropdowns by checking if the value matches known providers
                const providerValues = ['OPENAI', 'GOOGLE', 'ANTHROPIC', 'HUGGINGFACE', 'GROQ', 'MISTRALAI', 'DEEPSEEK', 'SAMBANOVA', 'OPENROUTER'];
                if (providerValues.includes(e.target.value)) {
                    
                    
                    // Find the model name input in the same section
                    // Look for the closest parent section and find input with data-provider
                    let currentElement = e.target.parentElement;
                    let modelNameInput = null;
                    
                    // Search up the DOM tree to find the section container
                    while (currentElement && !currentElement.classList.contains('section')) {
                        currentElement = currentElement.parentElement;
                    }
                    
                    if (currentElement) {
                        // Found the section, now look for input with data-provider inside it
                        modelNameInput = currentElement.querySelector('input[data-provider]');
                        if (modelNameInput) {
                            modelNameInput.setAttribute('data-provider', e.target.value);
                        } else {
                        }
                    } else {
                    }
                }
            }
        });
        
    },

    // Handle hover on model input fields
    handleModelInputHover: async function(e) {
        if (e.target.tagName === 'INPUT' && e.target.hasAttribute('data-provider')) {
            
            // HACK: Try to get the current provider value from the corresponding provider dropdown
            let actualProvider = e.target.getAttribute('data-provider');
            
            // Look for the provider dropdown in the same section/form
            const parentSection = e.target.closest('.section, .field-group, form') || document;
            const providerSelects = parentSection.querySelectorAll('select');
            
            // Check if any select has a provider value
            providerSelects.forEach(select => {
                const providerValues = ['OPENAI', 'GOOGLE', 'ANTHROPIC', 'GROQ', 'MISTRALAI', 'DEEPSEEK', 'SAMBANOVA', 'OPENROUTER', 'HUGGINGFACE', 'OLLAMA', 'LMSTUDIO', 'CHUTES'];
                if (providerValues.includes(select.value)) {
                    actualProvider = select.value;
                }
            });
            
            const picker = document.getElementById('model-picker-dropdown');
            if (!picker) {
                return;
            }

            const prov = actualProvider;
            // fetch models for provider
            let models = [];
            let res = {};
            try {
                res = await sendJsonData('/models_list', { provider: prov });
                models = res.models || [];
            } catch (err) {
                console.error('Error fetching models', err);
                return;
            }
            // populate picker
            picker.innerHTML = '';
            
            // Add provider header
            if (models.length > 0) {
                const header = document.createElement('div');
                const sourceInfo = res.source ? ` • ${res.source}` : '';
                const dynamicInfo = res.dynamic ? ' 🔄' : '';
                header.textContent = `${prov} Models (${models.length})${dynamicInfo}${sourceInfo}`;
                header.className = 'model-picker-header';
                picker.appendChild(header);
                
                // Add search input for large model lists
                if (models.length > 5) {
                    const searchInput = document.createElement('input');
                    searchInput.type = 'text';
                    searchInput.placeholder = 'Search models...';
                    searchInput.className = 'model-picker-search';
                    picker.appendChild(searchInput);
                    
                    // Store reference for search functionality
                    searchInput._allItems = [];
                }
            }
            
            // Add model options
            models.forEach((m, index) => {
                const item = document.createElement('div');
                item.textContent = m;
                item.className = 'model-picker-item';
                item.dataset.modelName = m; // Store original name for search
                
                item.addEventListener('click', () => {
                    e.target.value = m;
                    picker.style.display = 'none';
                    // Trigger input event to ensure the value is saved
                    e.target.dispatchEvent(new Event('input', { bubbles: true }));
                });
                picker.appendChild(item);
                
                // Store reference for search functionality
                if (models.length > 5) {
                    const searchInput = picker.querySelector('.model-picker-search');
                    if (searchInput) {
                        searchInput._allItems.push(item);
                    }
                }
            });
            
            // Add search functionality after all items are added
            if (models.length > 5) {
                const searchInput = picker.querySelector('.model-picker-search');
                if (searchInput && searchInput._allItems) {
                    searchInput.addEventListener('input', (e) => {
                        const query = e.target.value.toLowerCase();
                        searchInput._allItems.forEach(item => {
                            const text = item.dataset.modelName.toLowerCase();
                            if (text.includes(query)) {
                                item.style.display = 'block';
                                // Highlight matching text
                                if (query) {
                                    const regex = new RegExp(`(${query})`, 'gi');
                                    item.innerHTML = item.dataset.modelName.replace(regex, '<span class="highlight">$1</span>');
                                } else {
                                    item.textContent = item.dataset.modelName;
                                }
                            } else {
                                item.style.display = 'none';
                            }
                        });
                    });
                    
                    // Focus search input when dropdown opens
                    setTimeout(() => searchInput.focus(), 50);
                }
            }
            
            // position picker
            const rect = e.target.getBoundingClientRect();
            const viewportHeight = window.innerHeight;
            const dropdownHeight = 300; // max-height from CSS
            
            // Check if there's enough space below the input
            const spaceBelow = viewportHeight - rect.bottom;
            const showAbove = spaceBelow < dropdownHeight && rect.top > dropdownHeight;
            
            if (showAbove) {
                picker.style.top = (rect.top + window.scrollY - Math.min(dropdownHeight, picker.scrollHeight)) + 'px';
            } else {
                picker.style.top = (rect.bottom + window.scrollY + 4) + 'px';
            }
            
            picker.style.left = (rect.left + window.scrollX) + 'px';
            picker.style.minWidth = Math.max(rect.width, 250) + 'px';
            picker.style.display = 'block';

        }
    },

    // Handle mouse leave from model input fields
    handleModelInputLeave: function(e) {
        if (e.target.tagName === 'INPUT' && e.target.hasAttribute('data-provider')) {
            const picker = document.getElementById('model-picker-dropdown');
            if (picker) {
                setTimeout(() => { 
                    // Only hide if mouse is not over the picker itself
                    if (!picker.matches(':hover')) {
                        picker.style.display = 'none'; 
                    }
                }, 300);
            }
        }
    },

    // Clean up model picker when modal closes
    cleanupModelPicker() {
        const picker = document.getElementById('model-picker-dropdown');
        if (picker) {
            picker.style.display = 'none';
        }
    },


    async openModal() {
        // console.log('Settings modal opening');
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

            // Initialize model picker after modal is loaded and Alpine.js has rendered
            setTimeout(() => {
                this.initModelPicker();
                // console.log('Model picker initialized');
                
                // Debug: Check if any inputs with data-provider exist
                const inputsWithProvider = document.querySelectorAll('input[data-provider]');
                // console.log('Found inputs with data-provider:', inputsWithProvider.length);
                inputsWithProvider.forEach((input, i) => {
                    // console.log(`Input ${i}: ID=${input.id}, provider=${input.getAttribute('data-provider')}`);
                });
            }, 500);

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

        // Clean up model picker
        this.cleanupModelPicker();

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

        // Clean up model picker
        this.cleanupModelPicker();

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
                // console.log('Stopping scheduler polling on modal close');
                schedulerData.stopPolling();
            }
        }
    },

    async handleFieldButton(field) {
        //  console.log(`Button clicked: ${field.id}`);

        if (field.id === "mcp_servers_config") {
            openModal("settings/mcp/client/mcp-servers.html");
        }
    }
};

// Make settingsModalProxy available globally
window.settingsModalProxy = settingsModalProxy;

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

    // Register settingsModalProxy as an Alpine data component
    Alpine.data('settingsModalProxy', () => settingsModalProxy);

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
