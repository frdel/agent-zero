// AG-UI Protocol JavaScript Module

class AGUIRenderer {
    constructor() {
        this.componentRegistry = new Map();
        this.eventHandlers = new Map();
        this.stateManager = null;
        
        // Register default components
        this.registerDefaultComponents();
    }
    
    registerComponent(type, renderFunction) {
        this.componentRegistry.set(type, renderFunction);
    }
    
    registerEventHandler(eventType, handler) {
        this.eventHandlers.set(eventType, handler);
    }
    
    setStateManager(stateManager) {
        this.stateManager = stateManager;
    }
    
    renderComponent(spec, container) {
        if (typeof spec === 'string') {
            try {
                spec = JSON.parse(spec);
            } catch (e) {
                console.error('Failed to parse AG-UI spec:', e);
                return this.renderError('Invalid JSON specification');
            }
        }
        
        if (!spec.type) {
            console.error('AG-UI spec missing type:', spec);
            return this.renderError('Component type is required');
        }
        
        const renderer = this.componentRegistry.get(spec.type);
        if (!renderer) {
            console.warn(`Unknown AG-UI component type: ${spec.type}`);
            return this.renderDefault(spec);
        }
        
        try {
            const element = renderer(spec, this);
            
            // Set up event handlers
            this.setupEventHandlers(element, spec);
            
            // Initialize state management
            if (this.stateManager && spec.id) {
                this.stateManager.initializeComponent(spec.id, spec.properties);
            }
            
            return element;
        } catch (e) {
            console.error('Error rendering AG-UI component:', e);
            return this.renderError(`Error rendering ${spec.type}: ${e.message}`);
        }
    }
    
    setupEventHandlers(element, spec) {
        if (!spec.events) return;
        
        for (const [event, handler] of Object.entries(spec.events)) {
            if (typeof handler === 'string') {
                // Handle string event handlers (JavaScript code)
                element.addEventListener(event, new Function('event', handler));
            } else if (typeof handler === 'function') {
                element.addEventListener(event, handler);
            }
        }
    }
    
    renderError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'ag-ui-error';
        errorDiv.innerHTML = `<span class="ag-ui-error-icon">⚠️</span> ${message}`;
        return errorDiv;
    }
    
    renderDefault(spec) {
        const div = document.createElement('div');
        div.className = `ag-ui-component ag-ui-${spec.type}`;
        div.innerHTML = `
            <div class="ag-ui-default-header">
                <strong>${spec.type}</strong>
            </div>
            <div class="ag-ui-default-content">
                ${JSON.stringify(spec.properties || {}, null, 2)}
            </div>
        `;
        return div;
    }
    
    registerDefaultComponents() {
        // Button component
        this.registerComponent('button', (spec) => {
            const button = document.createElement('button');
            button.className = 'ag-ui-button';
            button.textContent = spec.properties.label || 'Click me';

            if (spec.properties.disabled) {
                button.disabled = true;
            }

            if (spec.properties.variant) {
                button.classList.add(`ag-ui-button-${spec.properties.variant}`);
            }

            if (spec.id) {
                button.id = spec.id;
            }

            // Handle click events properly
            if (spec.events && spec.events.click) {
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

            return button;
        });
        
        // Text component
        this.registerComponent('text', (spec) => {
            const div = document.createElement('div');
            div.className = 'ag-ui-text';
            div.innerHTML = spec.properties.content || '';
            
            if (spec.properties.variant) {
                div.classList.add(`ag-ui-text-${spec.properties.variant}`);
            }
            
            if (spec.id) {
                div.id = spec.id;
            }
            
            return div;
        });
        
        // Input component
        this.registerComponent('input', (spec) => {
            const input = document.createElement('input');
            input.className = 'ag-ui-input';
            input.type = spec.properties.type || 'text';
            input.placeholder = spec.properties.placeholder || '';
            input.value = spec.properties.value || '';
            
            if (spec.properties.required) {
                input.required = true;
            }
            
            if (spec.properties.disabled) {
                input.disabled = true;
            }
            
            if (spec.id) {
                input.id = spec.id;
            }
            
            return input;
        });
        
        // Container component
        this.registerComponent('container', (spec, renderer) => {
            const div = document.createElement('div');
            div.className = 'ag-ui-container';
            
            if (spec.properties.layout) {
                div.classList.add(`ag-ui-layout-${spec.properties.layout}`);
            }
            
            if (spec.id) {
                div.id = spec.id;
            }
            
            // Render children
            if (spec.children && Array.isArray(spec.children)) {
                spec.children.forEach(childSpec => {
                    const childElement = renderer.renderComponent(childSpec);
                    div.appendChild(childElement);
                });
            }
            
            return div;
        });
        
        // Form component
        this.registerComponent('form', (spec, renderer) => {
            const form = document.createElement('form');
            form.className = 'ag-ui-form';
            form.action = spec.properties.action || '#';
            form.method = spec.properties.method || 'POST';
            
            if (spec.id) {
                form.id = spec.id;
            }
            
            // Prevent default form submission and handle with AG-UI
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleFormSubmit(form, spec);
            });
            
            // Render children
            if (spec.children && Array.isArray(spec.children)) {
                spec.children.forEach(childSpec => {
                    const childElement = renderer.renderComponent(childSpec);
                    form.appendChild(childElement);
                });
            }
            
            return form;
        });
        
        // Card component
        this.registerComponent('card', (spec, renderer) => {
            const card = document.createElement('div');
            card.className = 'ag-ui-card';
            
            if (spec.id) {
                card.id = spec.id;
            }
            
            if (spec.properties.title) {
                const header = document.createElement('div');
                header.className = 'ag-ui-card-header';
                header.innerHTML = `<h3>${spec.properties.title}</h3>`;
                card.appendChild(header);
            }
            
            const body = document.createElement('div');
            body.className = 'ag-ui-card-body';
            
            if (spec.properties.content) {
                body.innerHTML = spec.properties.content;
            }
            
            // Render children in body
            if (spec.children && Array.isArray(spec.children)) {
                spec.children.forEach(childSpec => {
                    const childElement = renderer.renderComponent(childSpec);
                    body.appendChild(childElement);
                });
            }
            
            card.appendChild(body);
            
            if (spec.properties.footer) {
                const footer = document.createElement('div');
                footer.className = 'ag-ui-card-footer';
                footer.innerHTML = spec.properties.footer;
                card.appendChild(footer);
            }
            
            return card;
        });
    }
    
    handleFormSubmit(form, spec) {
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        
        // Emit form submission event
        const event = {
            type: 'FORM_SUBMIT',
            componentId: spec.id,
            data: data,
            timestamp: Date.now()
        };
        
        this.emitEvent(event);
    }
    
    emitEvent(event) {
        // Send event to backend if needed
        if (window.fetchApi) {
            window.fetchApi('/ag_ui_event', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(event)
            }).catch(err => {
                console.error('Failed to send AG-UI event:', err);
            });
        }
        
        // Trigger local event handlers
        const handler = this.eventHandlers.get(event.type);
        if (handler) {
            handler(event);
        }
        
        // Dispatch custom event
        window.dispatchEvent(new CustomEvent('agui:event', { detail: event }));
    }
}

// Global AG-UI renderer instance
window.aguiRenderer = new AGUIRenderer();

// Legacy function for backward compatibility
function renderAGUI(elementId, aguiSpec) {
    console.log(`Rendering AG-UI for element ${elementId} with spec:`, aguiSpec);
    const element = document.getElementById(elementId);
    if (element) {
        const renderedComponent = window.aguiRenderer.renderComponent(aguiSpec);
        element.innerHTML = '';
        element.appendChild(renderedComponent);
    }
}

// Initialize AG-UI state management for a container
window.initializeAGUIStateFor = function(container) {
    const components = container.querySelectorAll('[id^="ag-ui-"]');
    components.forEach(component => {
        if (window.aguiRenderer.stateManager) {
            window.aguiRenderer.stateManager.initializeComponent(component.id, {});
        }
    });
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AGUIRenderer, renderAGUI };
}