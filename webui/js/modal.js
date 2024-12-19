const fullScreenInputModalProxy = {
    isOpen: false,
    inputText: '',

    openModal() {
        const chatInput = document.getElementById('chat-input');
        this.inputText = chatInput.value;
        this.isOpen = true;
        
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

    async openModal(title, description, html) {
        const modalEl = document.getElementById('genericModal');
        const modalAD = Alpine.$data(modalEl);

        modalAD.isOpen = true;
        modalAD.title = title
        modalAD.description = description
        modalAD.html = html
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