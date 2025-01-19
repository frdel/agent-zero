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
