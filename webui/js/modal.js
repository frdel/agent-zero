const fullScreenInputModalProxy = {
    isOpen: false,
    inputText: '',
    wordWrap: true,
    undoStack: [],
    redoStack: [],
    maxStackSize: 100,
    lastSavedState: '',

    openModal() {
        const chatInput = document.getElementById('chat-input');
        this.inputText = chatInput.value;
        this.lastSavedState = this.inputText;
        this.isOpen = true;
        this.undoStack = [];
        this.redoStack = [];
        
        // Focus the full screen input after a short delay to ensure the modal is rendered
        setTimeout(() => {
            const fullScreenInput = document.getElementById('full-screen-input');
            fullScreenInput.focus();
        }, 100);
    },

    handleClose() {
        const chatInput = document.getElementById('chat-input');
        chatInput.value = this.inputText;
        chatInput.dispatchEvent(new Event('input')); // Trigger input event for textarea auto-resize
        this.isOpen = false;
    },

    updateHistory() {
        // Don't save if the text hasn't changed
        if (this.lastSavedState === this.inputText) return;
        
        this.undoStack.push(this.lastSavedState);
        if (this.undoStack.length > this.maxStackSize) {
            this.undoStack.shift();
        }
        this.redoStack = [];
        this.lastSavedState = this.inputText;
    },

    undo() {
        if (!this.canUndo) return;
        
        this.redoStack.push(this.inputText);
        this.inputText = this.undoStack.pop();
        this.lastSavedState = this.inputText;
    },

    redo() {
        if (!this.canRedo) return;
        
        this.undoStack.push(this.inputText);
        this.inputText = this.redoStack.pop();
        this.lastSavedState = this.inputText;
    },

    clearText() {
        if (this.inputText) {
            this.updateHistory(); // Save current state before clearing
            this.inputText = '';
            this.lastSavedState = '';
        }
    },

    toggleWrap() {
        this.wordWrap = !this.wordWrap;
    },

    get canUndo() {
        return this.undoStack.length > 0;
    },

    get canRedo() {
        return this.redoStack.length > 0;
    }
};

// Register the full screen input modal with Alpine as a store
document.addEventListener('alpine:init', () => {
    Alpine.store('fullScreenInputModal', fullScreenInputModalProxy);
});

// Also register as a component for x-data usage
document.addEventListener('alpine:init', () => {
    Alpine.data('fullScreenInputModalProxy', () => fullScreenInputModalProxy);
});

const genericModalProxy = {
    isOpen: false,
    isLoading: false,
    title: '',
    description: '',
    html: '',

    async openModal(title, description, html, contentClasses = []) {
        const modalEl = document.getElementById('genericModal');
        const modalContent = document.getElementById('viewer');
        const modalAD = Alpine.$data(modalEl);

        modalAD.isOpen = true;
        modalAD.title = title
        modalAD.description = description
        modalAD.html = html

        modalContent.className = 'modal-content';
        modalContent.classList.add(...contentClasses);
    },

    handleClose() {
        this.isOpen = false;
    }
}

// Wait for Alpine to be ready
document.addEventListener('alpine:init', () => {
    Alpine.data('genericModalProxy', () => ({
        init() {
            Object.assign(this, genericModalProxy);
            // Ensure immediate file fetch when modal opens
            this.$watch('isOpen', async (value) => {
               // what now?
            });
        }
    }));
});

// Keep the global assignment for backward compatibility
window.genericModalProxy = genericModalProxy;