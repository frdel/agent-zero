const secretsFullscreenModalProxy = {
    isOpen: false,
    secretsText: '',
    originalField: null,
    undoStack: [],
    redoStack: [],
    maxStackSize: 100,
    lastSavedState: '',

    openModal(secretsField) {
        this.originalField = secretsField;
        this.secretsText = secretsField.value;
        this.lastSavedState = this.secretsText;
        this.isOpen = true;
        this.undoStack = [];
        this.redoStack = [];

        // Focus the full screen input after a short delay to ensure the modal is rendered
        setTimeout(() => {
            const fullScreenInput = document.getElementById('secrets-fullscreen-input');
            if (fullScreenInput) {
                fullScreenInput.focus();
            }
        }, 100);
    },

    handleClose() {
        this.isOpen = false;
    },

    handleSave() {
        if (this.originalField) {
            this.originalField.value = this.secretsText;
        }
        this.isOpen = false;
    },

    handleCancel() {
        // Restore original value
        this.secretsText = this.lastSavedState;
        this.isOpen = false;
    },

    updateHistory() {
        if (this.secretsText !== this.lastSavedState) {
            this.undoStack.push(this.lastSavedState);
            if (this.undoStack.length > this.maxStackSize) {
                this.undoStack.shift();
            }
            this.redoStack = []; // Clear redo stack when new change is made
            this.lastSavedState = this.secretsText;
        }
    },

    undo() {
        if (!this.canUndo) return;

        this.redoStack.push(this.secretsText);
        this.secretsText = this.undoStack.pop();
        this.lastSavedState = this.secretsText;
    },

    redo() {
        if (!this.canRedo) return;

        this.undoStack.push(this.secretsText);
        this.secretsText = this.redoStack.pop();
        this.lastSavedState = this.secretsText;
    },

    clearText() {
        if (this.secretsText) {
            this.updateHistory(); // Save current state before clearing
            this.secretsText = '';
            this.lastSavedState = '';
        }
    },

    get canUndo() {
        return this.undoStack.length > 0;
    },

    get canRedo() {
        return this.redoStack.length > 0;
    },

    // Handle keyboard shortcuts
    handleKeydown(event) {
        if (event.ctrlKey || event.metaKey) {
            switch (event.key) {
                case 'z':
                    if (event.shiftKey) {
                        event.preventDefault();
                        this.redo();
                    } else {
                        event.preventDefault();
                        this.undo();
                    }
                    break;
                case 'y':
                    event.preventDefault();
                    this.redo();
                    break;
                case 's':
                    event.preventDefault();
                    this.handleSave();
                    break;
            }
        } else if (event.key === 'Escape') {
            event.preventDefault();
            this.handleCancel();
        }
    }
};

// Register the secrets fullscreen modal with Alpine as a store
document.addEventListener('alpine:init', () => {
    Alpine.store('secretsFullscreenModal', secretsFullscreenModalProxy);
});

// Also register as a component for x-data usage
document.addEventListener('alpine:init', () => {
    Alpine.data('secretsFullscreenModalProxy', () => secretsFullscreenModalProxy);
});