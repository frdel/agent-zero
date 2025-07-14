import { createStore } from "/js/AlpineStore.js";

const model = {


    devices: [],
    selectedDevice: "",

    async init() {
        // Load selected device from localStorage if present
        const saved = localStorage.getItem('microphoneSelectedDevice');
        await this.loadDevices();
        if (saved && this.devices.some(d => d.deviceId === saved)) {
            this.selectedDevice = saved;
        }
    },

    async loadDevices() {
        // Get media devices
        const devices = await navigator.mediaDevices.enumerateDevices();
        // Filter for audio input (microphones)
        this.devices = devices.filter(d => d.kind === "audioinput" && d.deviceId);
        // Set selected device to first available, if any
        this.selectedDevice = this.devices.length > 0 ? this.devices[0].deviceId : "";
    },

    requestPermission() {
        navigator.mediaDevices.getUserMedia({ audio: true });
        this.loadDevices();
    },

    async selectDevice(deviceId) {
        this.selectedDevice = deviceId;
        this.onSelectDevice();
    },

    async onSelectDevice() {
        localStorage.setItem('microphoneSelectedDevice', this.selectedDevice);
    },

    getSelectedDevice() {
        let device = this.devices.find(d => d.deviceId === this.selectedDevice);
        if (!device && this.devices.length > 0) {
            device = this.devices.find(d => d.deviceId === "default") || this.devices[0];
        }
        return device;
    }

};

const store = createStore("microphoneSetting", model);

export { store };
