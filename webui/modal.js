const genericModalProxy = {
    isOpen: false,
    isLoading: false,

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