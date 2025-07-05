// AG-UI State Management
// This module handles the persistence of AG-UI component state using localStorage.

class AGUIStateManager {
    constructor() {
        this.stateKey = 'ag_ui_state';
        this.eventListeners = new Map();
        this.componentStates = new Map();
        this.syncInterval = null;
        
        // Load initial state from localStorage
        this.loadAllState();
        
        // Set up periodic sync with backend
        this.setupPeriodicSync();
        
        // Listen for storage events from other tabs
        window.addEventListener('storage', (e) => {
            if (e.key === this.stateKey) {
                this.handleStorageChange(e);
            }
        });
        
        // Set up state manager in AG-UI renderer
        if (window.aguiRenderer) {
            window.aguiRenderer.setStateManager(this);
        }
    }
    
    initializeComponent(componentId, initialState = {}) {
        if (!this.componentStates.has(componentId)) {
            this.componentStates.set(componentId, { ...initialState });
            
            // Try to load saved state
            const savedState = this.loadComponentState(componentId);
            if (savedState) {
                this.componentStates.set(componentId, { ...initialState, ...savedState });
            }
        }
    }
    
    getComponentState(componentId) {
        return this.componentStates.get(componentId) || {};
    }
    
    setComponentState(componentId, state, persist = true) {
        this.componentStates.set(componentId, state);
        
        if (persist) {
            this.saveComponentState(componentId, state);
        }
        
        // Notify listeners
        this.notifyStateChange(componentId, state);
    }
    
    updateComponentState(componentId, partialState, persist = true) {
        const currentState = this.getComponentState(componentId);
        const newState = { ...currentState, ...partialState };
        this.setComponentState(componentId, newState, persist);
    }
    
    saveComponentState(componentId, state) {
        const allState = this.loadAllState();
        allState[componentId] = state;
        localStorage.setItem(this.stateKey, JSON.stringify(allState));
        
        // Sync to backend if needed
        this.syncStateToBackend(componentId, state);
    }
    
    loadComponentState(componentId) {
        const allState = this.loadAllState();
        return allState[componentId] || null;
    }
    
    loadAllState() {
        try {
            const storedState = localStorage.getItem(this.stateKey);
            return storedState ? JSON.parse(storedState) : {};
        } catch (e) {
            console.error('Failed to load AG-UI state from localStorage:', e);
            return {};
        }
    }
    
    saveAllState() {
        const stateObject = {};
        this.componentStates.forEach((state, componentId) => {
            stateObject[componentId] = state;
        });
        
        try {
            localStorage.setItem(this.stateKey, JSON.stringify(stateObject));
        } catch (e) {
            console.error('Failed to save AG-UI state to localStorage:', e);
        }
    }
    
    clearComponentState(componentId) {
        this.componentStates.delete(componentId);
        
        const allState = this.loadAllState();
        delete allState[componentId];
        localStorage.setItem(this.stateKey, JSON.stringify(allState));
    }
    
    clearAllState() {
        this.componentStates.clear();
        localStorage.removeItem(this.stateKey);
    }
    
    addEventListener(componentId, listener) {
        if (!this.eventListeners.has(componentId)) {
            this.eventListeners.set(componentId, []);
        }
        this.eventListeners.get(componentId).push(listener);
    }
    
    removeEventListener(componentId, listener) {
        const listeners = this.eventListeners.get(componentId);
        if (listeners) {
            const index = listeners.indexOf(listener);
            if (index > -1) {
                listeners.splice(index, 1);
            }
        }
    }
    
    notifyStateChange(componentId, state) {
        const listeners = this.eventListeners.get(componentId) || [];
        listeners.forEach(listener => {
            try {
                listener(state, componentId);
            } catch (e) {
                console.error('Error in AG-UI state listener:', e);
            }
        });
        
        // Dispatch global event
        window.dispatchEvent(new CustomEvent('agui:stateChange', {
            detail: { componentId, state }
        }));
    }
    
    handleStorageChange(event) {
        if (event.key === this.stateKey) {
            try {
                const newAllState = JSON.parse(event.newValue || '{}');
                const oldAllState = JSON.parse(event.oldValue || '{}');
                
                // Find changed components
                for (const [componentId, newState] of Object.entries(newAllState)) {
                    const oldState = oldAllState[componentId];
                    if (JSON.stringify(newState) !== JSON.stringify(oldState)) {
                        this.componentStates.set(componentId, newState);
                        this.notifyStateChange(componentId, newState);
                    }
                }
            } catch (e) {
                console.error('Error handling AG-UI storage change:', e);
            }
        }
    }
    
    async syncStateToBackend(componentId, state) {
        if (!window.fetchApi) {
            return; // No API available
        }
        
        try {
            await window.fetchApi('/ag_ui_state', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    action: "set",
                    component_id: componentId,
                    state: state
                })
            });
        } catch (error) {
            console.warn('Failed to sync AG-UI state to backend:', error);
        }
    }
    
    async syncStateFromBackend(componentId) {
        if (!window.fetchApi) {
            return null;
        }
        
        try {
            const response = await window.fetchApi('/ag_ui_state', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    action: "get",
                    component_id: componentId
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                return data.state || null;
            }
        } catch (error) {
            console.warn('Failed to sync AG-UI state from backend:', error);
        }
        
        return null;
    }
    
    setupPeriodicSync() {
        // Sync state every 30 seconds
        this.syncInterval = setInterval(() => {
            this.saveAllState();
        }, 30000);
    }
    
    destroy() {
        if (this.syncInterval) {
            clearInterval(this.syncInterval);
            this.syncInterval = null;
        }
        
        this.saveAllState();
        this.componentStates.clear();
        this.eventListeners.clear();
    }
    
    // Utility methods for form state management
    saveFormState(formId, formData) {
        this.updateComponentState(formId, {
            formData: formData,
            lastUpdated: Date.now()
        });
    }
    
    loadFormState(formId) {
        const state = this.getComponentState(formId);
        return state.formData || {};
    }
    
    // Utility methods for UI preferences
    saveUIPreference(componentId, preference, value) {
        this.updateComponentState(componentId, {
            preferences: {
                ...this.getComponentState(componentId).preferences,
                [preference]: value
            }
        });
    }
    
    loadUIPreference(componentId, preference, defaultValue = null) {
        const state = this.getComponentState(componentId);
        return state.preferences && state.preferences[preference] !== undefined
            ? state.preferences[preference]
            : defaultValue;
    }
    
    // Export state for debugging or backup
    exportState() {
        const stateData = {};
        this.componentStates.forEach((state, componentId) => {
            stateData[componentId] = state;
        });
        return JSON.stringify(stateData, null, 2);
    }
    
    // Import state from backup
    importState(stateData) {
        try {
            const parsedState = typeof stateData === 'string' ? JSON.parse(stateData) : stateData;
            
            for (const [componentId, state] of Object.entries(parsedState)) {
                this.setComponentState(componentId, state, true);
            }
            
            return true;
        } catch (e) {
            console.error('Failed to import AG-UI state:', e);
            return false;
        }
    }
}

// Create global state manager instance
window.aguiStateManager = new AGUIStateManager();

// Legacy functions for backward compatibility
window.saveAGUIState = function(componentId, state) {
    window.aguiStateManager.setComponentState(componentId, state);
};

window.loadAGUIState = function(componentId) {
    return window.aguiStateManager.getComponentState(componentId);
};

window.loadAllAGUIState = function() {
    return window.aguiStateManager.loadAllState();
};

// Initialize component state for containers
window.initializeAGUIStateFor = function(container) {
    const components = container.querySelectorAll('[id^="ag-ui-"]');
    components.forEach(component => {
        window.aguiStateManager.initializeComponent(component.id, {});
    });
};

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.aguiStateManager) {
        window.aguiStateManager.saveAllState();
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AGUIStateManager };
}