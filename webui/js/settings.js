const settingsModalProxy = {
    isOpen: false,
    settings: {},
    resolvePromise: null,

    async openModal() {
        const modalEl = document.getElementById('settingsModal');
        const modalAD = Alpine.$data(modalEl);

        //get settings from backend
        try {
            const set = await sendJsonData("/settings_get", null);

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

            modalAD.isOpen = true; // Update directly
            modalAD.settings = settings; // Update directly

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
        this.isOpen = false;
    },

    async handleCancel() {
        this.resolvePromise({
            status: 'cancelled',
            data: null
        });
        this.isOpen = false;
    },

    handleFieldButton(field) {
        console.log(`Button clicked: ${field.action}`);
    }
};

// Add new input sections for the newly added tools and models
document.addEventListener('settings-updated', (event) => {
    const settings = event.detail;
    const sections = settings.sections;

    // Add Jina AI API Key section
    sections.push({
        id: "jina-api-key",
        title: "Jina AI API Key",
        description: "Set your Jina AI API key. Get your Jina AI API key for free: https://jina.ai/?sui=apikey",
        fields: [
            {
                type: "text",
                title: "API Key",
                value: "",
                description: "Enter your Jina AI API key here."
            }
        ]
    });

    // Add Jina AI Model Selector section
    sections.push({
        id: "jina-model-selector",
        title: "Jina AI Model Selector",
        description: "Select the Jina AI model you want to use.",
        fields: [
            {
                type: "select",
                title: "Model",
                options: [
                    { value: "jina-clip-v2", label: "Jina CLIP v2" },
                    { value: "jina-embeddings-v3", label: "Jina Embeddings v3" },
                    { value: "jina-reranker-v2-base-multilingual", label: "Jina Reranker v2 Base Multilingual" },
                    { value: "jina-colbert-v2", label: "Jina ColBERT v2" }
                ],
                value: ""
            }
        ]
    });

    // Add Jina AI as a provider to the different model selectors
    sections.forEach(section => {
        if (section.id === "model-provider") {
            section.fields.forEach(field => {
                if (field.type === "select") {
                    field.options.push({ value: "Jina", label: "Jina AI" });
                }
            });
        }
    });
});
