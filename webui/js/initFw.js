import * as _modals from "./modals.js";
import * as _components from "./components.js";
import * as api from "./api.js";

// Register Alpine components before importing Alpine.js
document.addEventListener('alpine:init', function() {
    Alpine.data('personaSelector', () => ({
        isOpen: false,
        currentPersona: 'agent0',
        options: [],

        init() {
            this.loadCurrentPersona();
            this.loadPersonaOptions();
        },

        async loadCurrentPersona() {
            try {
                const data = await window.sendJsonData('/settings_get', null);

                if (data && data.settings && data.settings.sections) {
                    // Find the agent_prompts_subdir field in the settings (this is the persona field)
                    for (const section of data.settings.sections) {
                        if (section.fields) {
                            const personaField = section.fields.find(field => field.id === 'agent_prompts_subdir');
                            if (personaField && personaField.value) {
                                this.currentPersona = personaField.value;
                                break;
                            }
                        }
                    }
                }
            } catch (error) {
                console.error('Error loading current persona:', error);
            }
        },

        async loadPersonaOptions() {
            try {
                const data = await window.sendJsonData('/settings_get', null);

                if (data && data.settings && data.settings.sections) {
                    // Find the agent_prompts_subdir field options
                    for (const section of data.settings.sections) {
                        if (section.fields) {
                            const personaField = section.fields.find(field => field.id === 'agent_prompts_subdir');
                            if (personaField && personaField.options) {
                                this.options = personaField.options;
                                break;
                            }
                        }
                    }
                }
            } catch (error) {
                console.error('Error loading persona options:', error);
                // Fallback options
                this.options = [
                    { value: 'agent0', label: 'agent0' },
                    { value: 'default', label: 'default' },
                    { value: 'data_analyst', label: 'data_analyst' },
                    { value: 'developer', label: 'developer' },
                    { value: 'hacker', label: 'hacker' },
                    { value: 'researcher', label: 'researcher' }
                ];
            }
        },

        setPersona() {
            this.isOpen = !this.isOpen;
        },

        async selectPersona(value) {
            this.isOpen = false;

            if (value === this.currentPersona) {
                return; // No change needed
            }

            try {
                // First get current settings
                const settingsData = await window.sendJsonData('/settings_get', null);

                if (!settingsData || !settingsData.settings) {
                    throw new Error('Failed to load current settings');
                }

                // Find and update the agent_prompts_subdir field
                let personaUpdated = false;
                for (const section of settingsData.settings.sections) {
                    if (section.fields) {
                        const personaField = section.fields.find(field => field.id === 'agent_prompts_subdir');
                        if (personaField) {
                            personaField.value = value;
                            personaUpdated = true;
                            break;
                        }
                    }
                }

                if (!personaUpdated) {
                    throw new Error('Persona field not found in settings');
                }

                // Save the updated settings using the same format as the settings modal
                const saveResponse = await window.sendJsonData('/settings_set', settingsData.settings);

                if (saveResponse && saveResponse.settings) {
                    this.currentPersona = value;
                    const toast = window.showPersonaToast || window.showToast || console.log;
                    toast(`Persona switched to ${value}`, 'success');
                    // Dispatch settings updated event
                    document.dispatchEvent(new CustomEvent('settings-updated', {
                        detail: saveResponse.settings
                    }));
                } else {
                    throw new Error('Failed to save settings');
                }

            } catch (error) {
                console.error('Error selecting persona:', error);
                const toast = window.showPersonaToast || window.showToast || console.error;
                toast('Failed to switch persona', 'error');
                // Revert the selection
                this.loadCurrentPersona();
            }
        }
    }));
    console.log('Persona selector Alpine component registered');
});

await import("../vendor/alpine/alpine.min.js");

// Make Alpine globally available
window.Alpine = Alpine;

// Simple toast function for persona selector
function showPersonaToast(message, type = 'info') {
    // Try to use global showToast if available
    if (window.showToast) {
        window.showToast(message, type);
        return;
    }
    
    // Fallback: create a simple toast
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#F44336' : '#2196F3'};
        color: white;
        padding: 12px 24px;
        border-radius: 4px;
        z-index: 10000;
        font-family: Arial, sans-serif;
        font-size: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        opacity: 0;
        transition: opacity 0.3s;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Show animation
    setTimeout(() => toast.style.opacity = '1', 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => document.body.removeChild(toast), 300);
    }, 3000);
}

// add x-destroy directive
Alpine.directive(
  "destroy",
  (el, { expression }, { evaluateLater, cleanup }) => {
    const onDestroy = evaluateLater(expression);
    cleanup(() => onDestroy());
  }
);

// Simple toastFetchError function for early use
function toastFetchError(text, error) {
    const toast = window.showPersonaToast || showPersonaToast;
    toast(`${text}: ${error.message}`, 'error');
    console.error(text, error);
}

// Make API and toast available globally for persona selector
window.personaApi = api;
window.showPersonaToast = showPersonaToast;
window.toastFetchError = toastFetchError;
