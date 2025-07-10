// Alpine.js AG-UI Components

// Ensure Alpine.js is available before initializing
if (typeof Alpine !== 'undefined') {
    document.addEventListener('alpine:init', () => {
        console.log('Initializing AG-UI Alpine.js components...');

        // AG-UI Component Alpine.js directive
        Alpine.data('aguiComponent', (aguiSpec) => ({
            aguiSpec: aguiSpec,
            componentId: null,
            state: {},

            init() {
                // Generate unique component ID if not provided
                this.componentId = this.aguiSpec.id || `ag-ui-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

                // Initialize component state
                this.state = this.aguiSpec.properties || {};

                // Load saved state from localStorage
                this.loadState();

                // Render the AG-UI component when the Alpine component is initialized
                this.renderComponent();

                // Set up state persistence
                this.$watch('state', (newState) => {
                    this.saveState(newState);
                }, { deep: true });
            },
        
        renderComponent() {
            if (window.aguiRenderer) {
                const renderedComponent = window.aguiRenderer.renderComponent(this.aguiSpec);
                this.$el.innerHTML = '';
                this.$el.appendChild(renderedComponent);
            } else {
                // Enhanced fallback rendering with proper event handling
                this.renderFallbackComponent();
            }
        },

        renderFallbackComponent() {
            const spec = this.aguiSpec;

            if (spec.type === 'button') {
                const button = document.createElement('button');
                button.className = 'ag-ui-button';
                button.textContent = spec.properties?.label || 'Click me';

                if (spec.properties?.variant) {
                    button.classList.add(`ag-ui-button-${spec.properties.variant}`);
                }

                if (spec.properties?.disabled) {
                    button.disabled = true;
                }

                if (spec.id) {
                    button.id = spec.id;
                }

                // Properly handle click events
                if (spec.events?.click) {
                    button.addEventListener('click', (event) => {
                        try {
                            if (typeof spec.events.click === 'string') {
                                // Execute JavaScript code
                                new Function('event', spec.events.click)(event);
                            } else if (typeof spec.events.click === 'function') {
                                spec.events.click(event);
                            }
                        } catch (error) {
                            console.error('Button click error:', error);
                        }
                    });
                }

                this.$el.innerHTML = '';
                this.$el.appendChild(button);
            } else {
                // Generic fallback for other component types
                this.$el.innerHTML = `<div class="ag-ui-error">AG-UI renderer not available for ${spec.type}</div>`;
            }
        },
        
        loadState() {
            if (this.componentId && window.loadAGUIState) {
                const savedState = window.loadAGUIState(this.componentId);
                if (savedState) {
                    this.state = { ...this.state, ...savedState };
                }
            }
        },
        
        saveState(state) {
            if (this.componentId && window.saveAGUIState) {
                window.saveAGUIState(this.componentId, state);
            }
        },
        
        updateProperty(key, value) {
            this.state[key] = value;
            // Re-render component with updated state
            this.aguiSpec.properties = this.state;
            this.renderComponent();
        },
        
        triggerEvent(eventType, data = {}) {
            const event = {
                type: eventType,
                componentId: this.componentId,
                data: data,
                timestamp: Date.now()
            };
            
            if (window.aguiRenderer) {
                window.aguiRenderer.emitEvent(event);
            }
        }
    }));
    
    // AG-UI Form Component
    Alpine.data('aguiForm', (formSpec) => ({
        formSpec: formSpec,
        formData: {},
        errors: {},
        isSubmitting: false,
        
        init() {
            // Initialize form data with default values
            if (this.formSpec.children) {
                this.formSpec.children.forEach(field => {
                    if (field.type === 'input' && field.id) {
                        this.formData[field.id] = field.properties.value || '';
                    }
                });
            }
        },
        
        updateField(fieldId, value) {
            this.formData[fieldId] = value;
            // Clear error for this field
            if (this.errors[fieldId]) {
                delete this.errors[fieldId];
            }
        },
        
        validateForm() {
            this.errors = {};
            let isValid = true;
            
            if (this.formSpec.children) {
                this.formSpec.children.forEach(field => {
                    if (field.type === 'input' && field.properties.required) {
                        if (!this.formData[field.id] || this.formData[field.id].trim() === '') {
                            this.errors[field.id] = 'This field is required';
                            isValid = false;
                        }
                    }
                });
            }
            
            return isValid;
        },
        
        async submitForm() {
            if (!this.validateForm()) {
                return;
            }
            
            this.isSubmitting = true;
            
            try {
                const response = await window.fetchApi('/ag_ui_event', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        type: "FORM_SUBMIT",
                        componentId: this.formSpec.id,
                        data: this.formData,
                        timestamp: Date.now()
                    })
                });
                
                if (response.ok) {
                    const result = await response.json();
                    this.triggerEvent('FORM_SUBMIT_SUCCESS', { formData: this.formData, result });
                } else {
                    this.triggerEvent('FORM_SUBMIT_ERROR', { error: 'Form submission failed' });
                }
            } catch (error) {
                console.error('Form submission error:', error);
                this.triggerEvent('FORM_SUBMIT_ERROR', { error: error.message });
            } finally {
                this.isSubmitting = false;
            }
        },
        
        triggerEvent(eventType, data = {}) {
            if (window.aguiRenderer) {
                window.aguiRenderer.emitEvent({
                    type: eventType,
                    componentId: this.formSpec.id,
                    data: data,
                    timestamp: Date.now()
                });
            }
        }
    }));
    
    // AG-UI Button Component
    Alpine.data('aguiButton', (config) => ({
        id: config.id,
        properties: config.properties || {},
        events: config.events || {},
        isLoading: false,

        async handleClick() {
            console.log('AG-UI Button clicked:', this.id, this.events);
            console.log('Available global functions:', {
                setComponentState: typeof window.setComponentState,
                updateElement: typeof window.updateElement,
                changeElementClass: typeof window.changeElementClass
            });

            this.isLoading = true;

            try {
                // Trigger click event
                this.triggerEvent('BUTTON_CLICK', { buttonId: this.id });

                // Execute custom click handler if provided
                if (this.events.click) {
                    console.log('Executing click handler:', this.events.click);
                    if (typeof this.events.click === 'function') {
                        await this.events.click();
                    } else if (typeof this.events.click === 'string') {
                        // Execute as JavaScript code with better error handling
                        try {
                            console.log('Executing JavaScript code:', this.events.click);
                            new Function('event', this.events.click)(new Event('click'));
                            console.log('JavaScript code executed successfully');
                        } catch (jsError) {
                            console.error('JavaScript execution error:', jsError);
                            console.error('Failed code:', this.events.click);
                            throw jsError;
                        }
                    }
                } else {
                    console.log('No click handler found for button:', this.id);
                }
            } catch (error) {
                console.error('Button click error:', error);
                console.error('Error details:', {
                    message: error.message,
                    stack: error.stack,
                    buttonId: this.id,
                    clickHandler: this.events.click
                });
                this.triggerEvent('BUTTON_ERROR', { error: error.message });
            } finally {
                this.isLoading = false;
            }
        },

        triggerEvent(eventType, data = {}) {
            if (window.triggerAGUIEvent) {
                window.triggerAGUIEvent(eventType, this.id, data);
            } else if (window.aguiRenderer) {
                window.aguiRenderer.emitEvent({
                    type: eventType,
                    componentId: this.id,
                    data: data,
                    timestamp: Date.now()
                });
            }
        }
    }));
    
    // AG-UI Modal Component
    Alpine.data('aguiModal', (modalSpec) => ({
        modalSpec: modalSpec,
        isOpen: false,
        
        init() {
            // Listen for modal events
            window.addEventListener('agui:openModal', (event) => {
                if (event.detail.modalId === this.modalSpec.id) {
                    this.open();
                }
            });
            
            window.addEventListener('agui:closeModal', (event) => {
                if (event.detail.modalId === this.modalSpec.id) {
                    this.close();
                }
            });
        },
        
        open() {
            this.isOpen = true;
            this.triggerEvent('MODAL_OPEN');
            document.body.style.overflow = 'hidden'; // Prevent background scrolling
        },
        
        close() {
            this.isOpen = false;
            this.triggerEvent('MODAL_CLOSE');
            document.body.style.overflow = ''; // Restore scrolling
        },
        
        handleBackdropClick(event) {
            if (event.target === event.currentTarget) {
                this.close();
            }
        },
        
        triggerEvent(eventType, data = {}) {
            if (window.aguiRenderer) {
                window.aguiRenderer.emitEvent({
                    type: eventType,
                    componentId: this.modalSpec.id,
                    data: data,
                    timestamp: Date.now()
                });
            }
        }
    }));
    
    // AG-UI Tab Component
    Alpine.data('aguiTabs', (tabsSpec) => ({
        tabsSpec: tabsSpec,
        activeTab: 0,
        
        init() {
            // Set initial active tab
            if (this.tabsSpec.properties && this.tabsSpec.properties.activeTab !== undefined) {
                this.activeTab = this.tabsSpec.properties.activeTab;
            }
        },
        
        setActiveTab(index) {
            if (index >= 0 && index < this.getTabCount()) {
                this.activeTab = index;
                this.triggerEvent('TAB_CHANGE', { activeTab: index });
            }
        },
        
        getTabCount() {
            return this.tabsSpec.properties.tabs ? this.tabsSpec.properties.tabs.length : 0;
        },
        
        getActiveTabContent() {
            if (this.tabsSpec.properties.tabs && this.tabsSpec.properties.tabs[this.activeTab]) {
                return this.tabsSpec.properties.tabs[this.activeTab].content;
            }
            return '';
        },
        
        triggerEvent(eventType, data = {}) {
            if (window.aguiRenderer) {
                window.aguiRenderer.emitEvent({
                    type: eventType,
                    componentId: this.tabsSpec.id,
                    data: data,
                    timestamp: Date.now()
                });
            }
        }
    }));
});

// Helper functions for AG-UI modal management
window.openAGUIModal = function(modalId) {
    window.dispatchEvent(new CustomEvent('agui:openModal', { detail: { modalId } }));
};

window.closeAGUIModal = function(modalId) {
    window.dispatchEvent(new CustomEvent('agui:closeModal', { detail: { modalId } }));
};

// Global AG-UI event trigger function
window.triggerAGUIEvent = function(eventType, componentId, data = {}) {
    console.log('AG-UI Event triggered:', eventType, componentId, data);

    // Dispatch custom event for other parts of the application to listen to
    window.dispatchEvent(new CustomEvent('agui:event', {
        detail: {
            type: eventType,
            componentId: componentId,
            data: data,
            timestamp: Date.now()
        }
    }));

    // Also trigger through the AG-UI renderer if available
    if (window.aguiRenderer && window.aguiRenderer.emitEvent) {
        window.aguiRenderer.emitEvent({
            type: eventType,
            componentId: componentId,
            data: data,
            timestamp: Date.now()
        });
    }
};

// Global AG-UI state management functions
window.setComponentState = function(componentId, state) {
    console.log('Setting component state:', componentId, state);

    if (window.aguiStateManager) {
        window.aguiStateManager.setComponentState(componentId, state);
    }

    // Also update the DOM element directly for immediate visual feedback
    const element = document.getElementById(componentId);
    if (element && state.class) {
        element.className = state.class;
    }

    // Update text content if provided
    if (element && state.value) {
        if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
            element.value = state.value;
        } else {
            element.textContent = state.value;
        }
    }

    // Trigger a custom event for component state change
    window.dispatchEvent(new CustomEvent('agui:componentStateChanged', {
        detail: { componentId, state }
    }));
};

window.updateComponentState = function(componentId, partialState) {
    console.log('Updating component state:', componentId, partialState);

    if (window.aguiStateManager) {
        window.aguiStateManager.updateComponentState(componentId, partialState);
    }

    // Also update the DOM element directly for immediate visual feedback
    const element = document.getElementById(componentId);
    if (element && partialState.class) {
        element.className = partialState.class;
    }

    // Update text content if provided
    if (element && partialState.value) {
        if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
            element.value = partialState.value;
        } else {
            element.textContent = partialState.value;
        }
    }

    // Trigger a custom event for component state change
    window.dispatchEvent(new CustomEvent('agui:componentStateChanged', {
        detail: { componentId, state: partialState }
    }));
};

window.getComponentState = function(componentId) {
    if (window.aguiStateManager) {
        return window.aguiStateManager.getComponentState(componentId);
    }
    return {};
};

// Simple DOM manipulation functions for immediate visual feedback
window.changeElementClass = function(elementId, newClass) {
    console.log('Changing element class:', elementId, newClass);
    const element = document.getElementById(elementId);
    if (element) {
        element.className = newClass;
        console.log('Element class changed successfully');
        return true;
    } else {
        console.error('Element not found:', elementId);
        return false;
    }
};

window.changeElementText = function(elementId, newText) {
    console.log('Changing element text:', elementId, newText);
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = newText;
        console.log('Element text changed successfully');
        return true;
    } else {
        console.error('Element not found:', elementId);
        return false;
    }
};

// Combined function for changing both class and text
window.updateElement = function(elementId, options = {}) {
    console.log('Updating element:', elementId, options);
    const element = document.getElementById(elementId);
    if (element) {
        if (options.class) {
            element.className = options.class;
        }
        if (options.text) {
            element.textContent = options.text;
        }
        if (options.value) {
            if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                element.value = options.value;
            } else {
                element.textContent = options.value;
            }
        }
        console.log('Element updated successfully');
        return true;
    } else {
        console.error('Element not found:', elementId);
        return false;
    }
};

// Helper function to initialize AG-UI components after dynamic content is added
window.initializeAGUIComponents = function(container) {
    console.log('Initializing AG-UI components in container:', container);

    // Initialize Alpine.js for the new content
    if (window.Alpine && container) {
        window.Alpine.initTree(container);
    }

    // Initialize AG-UI state management
    if (window.initializeAGUIStateFor) {
        window.initializeAGUIStateFor(container);
    }
};

// ===== Comprehensive Alpine.js Component Definitions =====

// Modal Component
Alpine.data('aguiModal', (config) => ({
    id: config.id,
    properties: config.properties || {},
    isOpen: false,
    
    init() {
        // Listen for modal open events
        this.$watch('isOpen', (value) => {
            if (value) {
                this.triggerEvent('MODAL_OPEN');
                document.body.style.overflow = 'hidden';
            } else {
                this.triggerEvent('MODAL_CLOSE');
                document.body.style.overflow = '';
            }
        });
    },
    
    open() {
        this.isOpen = true;
    },
    
    close() {
        this.isOpen = false;
    },
    
    confirm() {
        this.triggerEvent('MODAL_CONFIRM');
        this.close();
    },
    
    handleBackdropClick(event) {
        if (event.target === event.currentTarget) {
            this.close();
        }
    },
    
    triggerEvent(eventType, data = {}) {
        window.triggerAGUIEvent(eventType, this.id, { ...data, modal: this.properties });
    }
}));

// Tabs Component
Alpine.data('aguiTabs', (config) => ({
    id: config.id,
    properties: config.properties || {},
    activeTab: 0,
    
    init() {
        this.activeTab = this.properties.active_tab || 0;
    },
    
    setActiveTab(index) {
        if (index !== this.activeTab) {
            this.activeTab = index;
            this.triggerEvent('TAB_CHANGE', { 
                previousTab: this.activeTab, 
                newTab: index,
                tabData: this.properties.tabs?.[index]
            });
        }
    },
    
    triggerEvent(eventType, data = {}) {
        window.triggerAGUIEvent(eventType, this.id, data);
    }
}));

// Table Component
Alpine.data('aguiTable', (config) => ({
    id: config.id,
    sortable: config.sortable || false,
    searchable: config.searchable || false,
    sortColumn: null,
    sortDirection: 'asc',
    searchQuery: '',
    selectedRows: [],
    
    sortBy(column) {
        if (!this.sortable) return;
        
        if (this.sortColumn === column) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = column;
            this.sortDirection = 'asc';
        }
        
        this.triggerEvent('TABLE_SORT', {
            column: column,
            direction: this.sortDirection
        });
    },
    
    filterTable(event) {
        this.searchQuery = event.target.value;
        this.triggerEvent('TABLE_SEARCH', {
            query: this.searchQuery
        });
    },
    
    selectRow(rowIndex, event) {
        const isSelected = this.selectedRows.includes(rowIndex);
        
        if (event.ctrlKey || event.metaKey) {
            // Multi-select
            if (isSelected) {
                this.selectedRows = this.selectedRows.filter(i => i !== rowIndex);
            } else {
                this.selectedRows.push(rowIndex);
            }
        } else {
            // Single select
            this.selectedRows = isSelected ? [] : [rowIndex];
        }
        
        this.triggerEvent('TABLE_ROW_SELECT', {
            selectedRows: this.selectedRows,
            rowIndex: rowIndex
        });
    },
    
    triggerEvent(eventType, data = {}) {
        window.triggerAGUIEvent(eventType, this.id, data);
    }
}));

// Alert Component
Alpine.data('aguiAlert', (config) => ({
    id: config.id,
    isVisible: true,
    
    dismiss() {
        this.isVisible = false;
        this.triggerEvent('ALERT_DISMISS');
    },
    
    action(actionType) {
        this.triggerEvent('ALERT_ACTION', { action: actionType });
    },
    
    triggerEvent(eventType, data = {}) {
        window.triggerAGUIEvent(eventType, this.id, data);
    }
}));

// Dropdown Component
Alpine.data('aguiDropdown', (config = {}) => ({
    id: config.id,
    properties: config.properties || {},
    events: config.events || {},
    isOpen: false,
    selectedValue: '',

    init() {
        // Listen for clicks outside to close dropdown
        document.addEventListener('click', (e) => {
            if (!this.$el.contains(e.target)) {
                this.isOpen = false;
            }
        });
        this.selectedValue = this.getInitialValue();
    },

    getInitialValue() {
        // Get initial value from select element
        const selectElement = this.$el.querySelector('select') || this.$el;
        return selectElement.value || '';
    },

    handleChange(event) {
        console.log('AG-UI Dropdown changed:', this.id, event.target.value);
        this.selectedValue = event.target.value;

        if (this.events.change) {
            try {
                if (typeof this.events.change === 'string') {
                    new Function('event', 'value', this.events.change)(event, this.selectedValue);
                } else if (typeof this.events.change === 'function') {
                    this.events.change(event, this.selectedValue);
                }
            } catch (error) {
                console.error('Dropdown change error:', error);
            }
        }

        this.triggerEvent('DROPDOWN_CHANGE', { value: this.selectedValue });
    },

    toggle() {
        this.isOpen = !this.isOpen;
        this.triggerEvent(this.isOpen ? 'DROPDOWN_OPEN' : 'DROPDOWN_CLOSE');
    },

    select(value, label) {
        this.selectedValue = value;
        this.isOpen = false;
        this.triggerEvent('DROPDOWN_CHANGE', {
            value: value,
            label: label
        });
    },

    triggerEvent(eventType, data = {}) {
        if (window.triggerAGUIEvent) {
            window.triggerAGUIEvent(eventType, this.id, data);
        }
    }
}));

// Slider Component
Alpine.data('aguiSlider', (config) => ({
    sliderValue: config.value || 50,
    min: config.min || 0,
    max: config.max || 100,
    isDragging: false,
    
    startDrag() {
        this.isDragging = true;
        this.triggerEvent('SLIDER_START', { value: this.sliderValue });
    },
    
    endDrag() {
        this.isDragging = false;
        this.triggerEvent('SLIDER_END', { value: this.sliderValue });
    },
    
    valueChanged() {
        this.triggerEvent('SLIDER_CHANGE', { value: this.sliderValue });
    },
    
    triggerEvent(eventType, data = {}) {
        window.triggerAGUIEvent(eventType, this.id, data);
    }
}));

// Progress Component
Alpine.data('aguiProgress', (config) => ({
    id: config.id,
    value: config.value || 0,
    max: config.max || 100,
    
    updateProgress(newValue) {
        const oldValue = this.value;
        this.value = Math.min(this.max, Math.max(0, newValue));
        
        this.triggerEvent('PROGRESS_UPDATE', {
            oldValue: oldValue,
            newValue: this.value,
            percentage: (this.value / this.max) * 100
        });
        
        if (this.value >= this.max) {
            this.triggerEvent('PROGRESS_COMPLETE', {
                value: this.value,
                max: this.max
            });
        }
    },
    
    triggerEvent(eventType, data = {}) {
        window.triggerAGUIEvent(eventType, this.id, data);
    }
}));

// Input Component
Alpine.data('aguiInput', (config) => ({
    id: config.id,
    properties: config.properties || {},
    events: config.events || {},
    value: config.properties?.value || '',

    handleInput(event) {
        console.log('AG-UI Input changed:', this.id, event.target.value);
        this.value = event.target.value;

        if (this.events.input) {
            try {
                if (typeof this.events.input === 'string') {
                    new Function('event', 'value', this.events.input)(event, this.value);
                } else if (typeof this.events.input === 'function') {
                    this.events.input(event, this.value);
                }
            } catch (error) {
                console.error('Input event error:', error);
            }
        }

        this.triggerEvent('INPUT_CHANGE', { value: this.value });
    },

    handleChange(event) {
        console.log('AG-UI Input change event:', this.id, event.target.value);
        this.value = event.target.value;

        if (this.events.change) {
            try {
                if (typeof this.events.change === 'string') {
                    new Function('event', 'value', this.events.change)(event, this.value);
                } else if (typeof this.events.change === 'function') {
                    this.events.change(event, this.value);
                }
            } catch (error) {
                console.error('Change event error:', error);
            }
        }

        this.triggerEvent('INPUT_BLUR', { value: this.value });
    },

    triggerEvent(eventType, data = {}) {
        if (window.triggerAGUIEvent) {
            window.triggerAGUIEvent(eventType, this.id, data);
        }
    }
}));

// Textarea Component
Alpine.data('aguiTextarea', (config) => ({
    id: config.id,
    properties: config.properties || {},
    events: config.events || {},
    value: config.properties?.value || '',

    handleInput(event) {
        console.log('AG-UI Textarea input:', this.id, event.target.value);
        this.value = event.target.value;

        if (this.events.input) {
            try {
                if (typeof this.events.input === 'string') {
                    new Function('event', 'value', this.events.input)(event, this.value);
                } else if (typeof this.events.input === 'function') {
                    this.events.input(event, this.value);
                }
            } catch (error) {
                console.error('Textarea input error:', error);
            }
        }

        this.triggerEvent('TEXTAREA_INPUT', { value: this.value });
    },

    handleChange(event) {
        console.log('AG-UI Textarea change:', this.id, event.target.value);
        this.value = event.target.value;

        if (this.events.change) {
            try {
                if (typeof this.events.change === 'string') {
                    new Function('event', 'value', this.events.change)(event, this.value);
                } else if (typeof this.events.change === 'function') {
                    this.events.change(event, this.value);
                }
            } catch (error) {
                console.error('Textarea change error:', error);
            }
        }

        this.triggerEvent('TEXTAREA_CHANGE', { value: this.value });
    },

    triggerEvent(eventType, data = {}) {
        if (window.triggerAGUIEvent) {
            window.triggerAGUIEvent(eventType, this.id, data);
        }
    }
}));

// Checkbox Component
Alpine.data('aguiCheckbox', (config) => ({
    id: config.id,
    properties: config.properties || {},
    events: config.events || {},
    checked: config.properties?.checked || false,

    handleChange(event) {
        console.log('AG-UI Checkbox changed:', this.id, event.target.checked);
        this.checked = event.target.checked;

        if (this.events.change) {
            try {
                if (typeof this.events.change === 'string') {
                    new Function('event', 'checked', this.events.change)(event, this.checked);
                } else if (typeof this.events.change === 'function') {
                    this.events.change(event, this.checked);
                }
            } catch (error) {
                console.error('Checkbox change error:', error);
            }
        }

        this.triggerEvent('CHECKBOX_CHANGE', { checked: this.checked });
    },

    triggerEvent(eventType, data = {}) {
        if (window.triggerAGUIEvent) {
            window.triggerAGUIEvent(eventType, this.id, data);
        }
    }
}));

// Enhanced Form Component
Alpine.data('aguiForm', (config) => ({
    id: config.id,
    properties: config.properties || {},
    events: config.events || {},
    formData: {},
    isSubmitting: false,

    handleSubmit(event) {
        console.log('AG-UI Form submitted:', this.id);

        // Prevent default form submission if we have custom handler
        if (this.events.submit) {
            event.preventDefault();
        }

        this.isSubmitting = true;

        // Collect form data
        const formElement = event.target;
        const formData = new FormData(formElement);
        this.formData = Object.fromEntries(formData.entries());

        if (this.events.submit) {
            try {
                if (typeof this.events.submit === 'string') {
                    new Function('event', 'formData', this.events.submit)(event, this.formData);
                } else if (typeof this.events.submit === 'function') {
                    this.events.submit(event, this.formData);
                }
            } catch (error) {
                console.error('Form submit error:', error);
            }
        }

        this.triggerEvent('FORM_SUBMIT', { formData: this.formData });
        this.isSubmitting = false;
    },

    triggerEvent(eventType, data = {}) {
        if (window.triggerAGUIEvent) {
            window.triggerAGUIEvent(eventType, this.id, data);
        }
    }
}));

// Canvas Component
Alpine.data('aguiCanvas', (config) => ({
    id: config.id,
    nodes: config.properties?.nodes || [],
    edges: config.properties?.edges || [],
    selectedNode: null,
    isDragging: false,
    dragOffset: { x: 0, y: 0 },
    
    init() {
        console.log('AG-UI Canvas initializing:', this.id, this.nodes);
        this.initializeNodePositions();
        this.setupCanvasEvents();

        // Force re-initialization after a short delay to ensure DOM is ready
        setTimeout(() => {
            this.setupCanvasEvents();
            console.log('Canvas events re-initialized for:', this.id);
        }, 100);
    },
    
    initializeNodePositions() {
        // Ensure all nodes have proper positions
        this.nodes.forEach(node => {
            if (!node.position) {
                node.position = { x: 50, y: 50 };
            }
        });
    },
    
    setupCanvasEvents() {
        console.log('Setting up canvas events for:', this.id);

        // Remove existing event listeners to prevent duplicates
        this.$el.removeEventListener('mousedown', this.handleMouseDown);
        this.$el.removeEventListener('mousemove', this.handleMouseMove);
        this.$el.removeEventListener('mouseup', this.handleMouseUp);
        this.$el.removeEventListener('mouseleave', this.handleMouseUp);

        // Add event listeners with proper binding
        this.$el.addEventListener('mousedown', this.handleMouseDown.bind(this), { passive: false });
        this.$el.addEventListener('mousemove', this.handleMouseMove.bind(this), { passive: false });
        this.$el.addEventListener('mouseup', this.handleMouseUp.bind(this), { passive: false });
        this.$el.addEventListener('mouseleave', this.handleMouseUp.bind(this), { passive: false });

        // Touch events for mobile support
        this.$el.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
        this.$el.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
        this.$el.addEventListener('touchend', this.handleTouchEnd.bind(this), { passive: false });

        // Prevent default drag behavior on nodes
        this.$el.addEventListener('dragstart', (e) => e.preventDefault());

        // Ensure nodes are properly set up for dragging
        this.$nextTick(() => {
            const nodes = this.$el.querySelectorAll('.ag-ui-canvas-node');
            nodes.forEach(node => {
                node.style.cursor = 'grab';
                node.style.pointerEvents = 'auto';
                node.style.userSelect = 'none';
            });
        });
    },
    
    handleMouseDown(event) {
        const nodeElement = event.target.closest('.ag-ui-canvas-node');
        if (nodeElement) {
            console.log('Mouse down on node:', nodeElement.getAttribute('data-node-id'));

            const nodeId = nodeElement.getAttribute('data-node-id');
            this.selectedNode = nodeId;
            this.isDragging = true;

            const rect = nodeElement.getBoundingClientRect();
            const canvasRect = this.$el.getBoundingClientRect();

            this.dragOffset = {
                x: event.clientX - rect.left,
                y: event.clientY - rect.top
            };

            // Add visual feedback
            nodeElement.classList.add('dragging');
            nodeElement.style.cursor = 'grabbing';
            nodeElement.style.zIndex = '1000';

            // Prevent text selection and default behavior
            event.preventDefault();
            event.stopPropagation();

            this.triggerEvent('CANVAS_NODE_CLICK', {
                nodeId: nodeId,
                position: { x: event.clientX - canvasRect.left, y: event.clientY - canvasRect.top }
            });
        }
    },
    
    handleMouseMove(event) {
        if (this.isDragging && this.selectedNode) {
            const canvas = this.$el;
            const rect = canvas.getBoundingClientRect();
            const newX = event.clientX - rect.left - this.dragOffset.x;
            const newY = event.clientY - rect.top - this.dragOffset.y;

            // Actually move the node element
            const nodeElement = canvas.querySelector(`[data-node-id="${this.selectedNode}"]`);
            if (nodeElement) {
                // Constrain to canvas bounds
                const maxX = canvas.clientWidth - nodeElement.offsetWidth;
                const maxY = canvas.clientHeight - nodeElement.offsetHeight;
                const constrainedX = Math.max(0, Math.min(newX, maxX));
                const constrainedY = Math.max(0, Math.min(newY, maxY));

                // Update node position immediately with no transition
                nodeElement.style.left = constrainedX + 'px';
                nodeElement.style.top = constrainedY + 'px';
                nodeElement.style.transform = 'none';
                nodeElement.style.transition = 'none';

                // Update the node data
                const nodeIndex = this.nodes.findIndex(n => n.id === this.selectedNode);
                if (nodeIndex !== -1) {
                    this.nodes[nodeIndex].position = { x: constrainedX, y: constrainedY };
                }

                // Redraw edges if they exist
                this.updateEdges();

                // Prevent default behavior
                event.preventDefault();
                event.stopPropagation();
            }

            this.triggerEvent('CANVAS_NODE_DRAG', {
                nodeId: this.selectedNode,
                position: { x: constrainedX, y: constrainedY }
            });
        }
    },
    
    handleMouseUp() {
        if (this.isDragging) {
            console.log('Mouse up - ending drag');

            // Store the node ID before clearing it
            const draggedNodeId = this.selectedNode;

            // Remove visual feedback
            const nodeElement = this.$el.querySelector(`[data-node-id="${this.selectedNode}"]`);
            if (nodeElement) {
                nodeElement.classList.remove('dragging');
                nodeElement.style.cursor = 'grab';
                nodeElement.style.zIndex = '2';
                nodeElement.style.transition = 'all 0.2s ease'; // Restore transition
            }

            this.isDragging = false;
            this.selectedNode = null;

            this.triggerEvent('CANVAS_NODE_DROP', {
                nodeId: draggedNodeId
            });
        }
    },
    
    // Touch event handlers for mobile support
    handleTouchStart(event) {
        event.preventDefault();
        const touch = event.touches[0];
        const mouseEvent = new MouseEvent('mousedown', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        this.handleMouseDown(mouseEvent);
    },
    
    handleTouchMove(event) {
        event.preventDefault();
        const touch = event.touches[0];
        const mouseEvent = new MouseEvent('mousemove', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        this.handleMouseMove(mouseEvent);
    },
    
    handleTouchEnd(event) {
        event.preventDefault();
        this.handleMouseUp();
    },

    updateEdges() {
        // Update SVG edges when nodes move
        const svgElement = this.$el.querySelector('.ag-ui-canvas-svg');
        if (svgElement && this.edges.length > 0) {
            // Clear existing lines
            const lines = svgElement.querySelectorAll('line');
            lines.forEach(line => line.remove());

            // Redraw lines based on current node positions
            this.edges.forEach(edge => {
                const sourceNode = this.nodes.find(n => n.id === edge.source);
                const targetNode = this.nodes.find(n => n.id === edge.target);

                if (sourceNode && targetNode) {
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', sourceNode.position.x + 40); // Node center offset
                    line.setAttribute('y1', sourceNode.position.y + 20);
                    line.setAttribute('x2', targetNode.position.x + 40);
                    line.setAttribute('y2', targetNode.position.y + 20);
                    line.setAttribute('stroke', '#666');
                    line.setAttribute('stroke-width', '2');
                    line.setAttribute('marker-end', 'url(#arrowhead)');
                    svgElement.appendChild(line);
                }
            });
        }
    },

    zoomCanvas(delta) {
        this.triggerEvent('CANVAS_ZOOM', { delta: delta });
    },

    panCanvas(dx, dy) {
        this.triggerEvent('CANVAS_PAN', { deltaX: dx, deltaY: dy });
    },

    triggerEvent(eventType, data = {}) {
        window.triggerAGUIEvent(eventType, this.id, data);
    },
    
    // Canvas action handlers
    addNewNode() {
        console.log('Adding new node...');
        
        // Generate a unique ID for the new node
        const newNodeId = `node_${Date.now()}`;
        
        // Find a good position for the new node (avoid overlapping)
        const newX = Math.random() * (this.$el.clientWidth - 100);
        const newY = Math.random() * (this.$el.clientHeight - 50);
        
        // Create new node object
        const newNode = {
            id: newNodeId,
            label: 'New Node',
            position: { x: newX, y: newY }
        };
        
        // Add to nodes array
        this.nodes.push(newNode);
        
        // Create and insert the new node element
        const nodeElement = document.createElement('div');
        nodeElement.className = 'ag-ui-canvas-node';
        nodeElement.setAttribute('data-node-id', newNodeId);
        nodeElement.style.left = `${newX}px`;
        nodeElement.style.top = `${newY}px`;
        nodeElement.innerHTML = `<div class="ag-ui-node-content">${newNode.label}</div>`;
        
        // Add to DOM
        const nodesContainer = this.$el.querySelector('.ag-ui-canvas-nodes');
        if (nodesContainer) {
            nodesContainer.appendChild(nodeElement);
        }
        
        // Trigger event
        this.triggerEvent('CANVAS_NODE_ADDED', {
            nodeId: newNodeId,
            node: newNode
        });
        
        console.log('New node added:', newNode);
    },
    
    changeBackground() {
        console.log('Changing background...');
        
        // Cycle through different background colors
        const backgrounds = [
            '#f8f9fa', // Light gray
            '#e3f2fd', // Light blue
            '#f3e5f5', // Light purple
            '#e8f5e8', // Light green
            '#fff3e0', // Light orange
            '#ffffff'  // White (default)
        ];
        
        const currentBg = this.$el.style.backgroundColor || '#ffffff';
        const currentIndex = backgrounds.findIndex(bg => 
            this.rgbToHex(window.getComputedStyle(this.$el).backgroundColor) === bg ||
            currentBg === bg
        );
        
        const nextIndex = (currentIndex + 1) % backgrounds.length;
        const newBackground = backgrounds[nextIndex];
        
        // Apply new background
        this.$el.style.backgroundColor = newBackground;
        
        // Trigger event
        this.triggerEvent('CANVAS_BACKGROUND_CHANGED', {
            oldBackground: currentBg,
            newBackground: newBackground
        });
        
        console.log('Background changed to:', newBackground);
    },
    
    // Helper function to convert RGB to hex
    rgbToHex(rgb) {
        if (rgb.startsWith('#')) return rgb;
        const result = rgb.match(/\d+/g);
        if (!result) return '#ffffff';
        return '#' + result.map(x => {
            const hex = parseInt(x).toString(16);
            return hex.length === 1 ? '0' + hex : hex;
        }).join('');
    }
}));

// ===== Global Event Triggering Function =====
window.triggerAGUIEvent = function(eventType, componentId, data = {}) {
    const eventData = {
        type: eventType,
        componentId: componentId,
        data: data,
        timestamp: new Date().toISOString()
    };
    
    // Send to backend if API is available
    if (window.fetchApi) {
        window.fetchApi('/ag_ui_event', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(eventData)
        }).catch(error => {
            console.error('Failed to send AG-UI event:', error);
        });
    }
    
    // Trigger custom DOM event for local listeners
    const customEvent = new CustomEvent('ag-ui-event', {
        detail: eventData
    });
    document.dispatchEvent(customEvent);
    
    console.log('AG-UI Event:', eventData);
};

// ===== Fallback Canvas Drag Functionality =====
window.initializeCanvasDragFallback = function() {
    console.log('Initializing canvas drag fallback...');
    
    // Find all canvas elements that might not have Alpine.js initialized
    const canvasElements = document.querySelectorAll('.ag-ui-canvas');
    
    canvasElements.forEach(canvas => {
        // Skip if Alpine.js is already handling this canvas
        if (canvas.__x) return;
        
        console.log('Setting up fallback drag for canvas:', canvas.id);
        
        let isDragging = false;
        let selectedNode = null;
        let dragOffset = { x: 0, y: 0 };
        
        const handleMouseDown = (event) => {
            const nodeElement = event.target.closest('.ag-ui-canvas-node');
            if (nodeElement) {
                console.log('Fallback: Mouse down on node:', nodeElement.getAttribute('data-node-id'));
                
                const nodeId = nodeElement.getAttribute('data-node-id');
                selectedNode = nodeId;
                isDragging = true;
                
                const rect = nodeElement.getBoundingClientRect();
                const canvasRect = canvas.getBoundingClientRect();
                
                dragOffset = {
                    x: event.clientX - rect.left,
                    y: event.clientY - rect.top
                };
                
                nodeElement.classList.add('dragging');
                event.preventDefault();
                
                window.triggerAGUIEvent('CANVAS_NODE_CLICK', canvas.id, {
                    nodeId: nodeId,
                    position: { x: event.clientX - canvasRect.left, y: event.clientY - canvasRect.top }
                });
            }
        };
        
        const handleMouseMove = (event) => {
            if (isDragging && selectedNode) {
                const rect = canvas.getBoundingClientRect();
                const newX = event.clientX - rect.left - dragOffset.x;
                const newY = event.clientY - rect.top - dragOffset.y;
                
                const nodeElement = canvas.querySelector(`[data-node-id="${selectedNode}"]`);
                if (nodeElement) {
                    const maxX = canvas.clientWidth - nodeElement.offsetWidth;
                    const maxY = canvas.clientHeight - nodeElement.offsetHeight;
                    const constrainedX = Math.max(0, Math.min(newX, maxX));
                    const constrainedY = Math.max(0, Math.min(newY, maxY));
                    
                    nodeElement.style.left = constrainedX + 'px';
                    nodeElement.style.top = constrainedY + 'px';
                    
                    // Update edges if they exist
                    updateCanvasEdges(canvas);
                    
                    window.triggerAGUIEvent('CANVAS_NODE_DRAG', canvas.id, {
                        nodeId: selectedNode,
                        position: { x: constrainedX, y: constrainedY }
                    });
                }
            }
        };
        
        const handleMouseUp = () => {
            if (isDragging) {
                console.log('Fallback: Mouse up - ending drag');
                
                const nodeElement = canvas.querySelector(`[data-node-id="${selectedNode}"]`);
                if (nodeElement) {
                    nodeElement.classList.remove('dragging');
                }
                
                window.triggerAGUIEvent('CANVAS_NODE_DROP', canvas.id, {
                    nodeId: selectedNode
                });
                
                isDragging = false;
                selectedNode = null;
            }
        };
        
        // Attach event listeners
        canvas.addEventListener('mousedown', handleMouseDown);
        canvas.addEventListener('mousemove', handleMouseMove);
        canvas.addEventListener('mouseup', handleMouseUp);
        canvas.addEventListener('mouseleave', handleMouseUp);
        canvas.addEventListener('dragstart', (e) => e.preventDefault());
    });
};

// Helper function to update canvas edges
window.updateCanvasEdges = function(canvas) {
    const svgElement = canvas.querySelector('.ag-ui-canvas-svg');
    if (!svgElement) return;
    
    // Clear existing lines
    const lines = svgElement.querySelectorAll('line');
    lines.forEach(line => line.remove());
    
    // Get all nodes and edges data (this is a simplified version)
    const nodes = Array.from(canvas.querySelectorAll('.ag-ui-canvas-node')).map(node => ({
        id: node.getAttribute('data-node-id'),
        x: parseInt(node.style.left) + 40, // Center offset
        y: parseInt(node.style.top) + 20
    }));
    
    // This is a simplified edge redraw - in a real implementation you'd need the edge data
    // For now, we'll just demonstrate the concept
    console.log('Updating canvas edges for nodes:', nodes);
};

// Auto-initialize fallback when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Wait a bit for Alpine.js to initialize
    setTimeout(() => {
        window.initializeCanvasDragFallback();
    }, 1000);
});

} else {
    console.warn('Alpine.js not available, AG-UI components will not be initialized');
}