
// Tunnel settings for the Settings modal
document.addEventListener('alpine:init', () => {
    Alpine.data('tunnelSettings', () => ({
        isLoading: false,
        tunnelLink: '',
        linkGenerated: false,
        loadingText: '',
        qrCodeInstance: null,

        init() {
            this.checkTunnelStatus();

            // Listen for authentication success to refresh tunnel status
            window.addEventListener('authenticationSuccess', () => {
                // Wait a bit for API calls to be properly resumed
                setTimeout(() => {
                    if (!window.isApiCallsPaused || !window.isApiCallsPaused()) {
                        this.checkTunnelStatus();
                    }
                }, 100);
            });
        },

        generateQRCode() {
            if (!this.tunnelLink) return;

            const qrContainer = document.getElementById('qrcode-tunnel');
            if (!qrContainer) return;

            // Clear any existing QR code
            qrContainer.innerHTML = '';

            try {
                // Generate new QR code
                this.qrCodeInstance = new QRCode(qrContainer, {
                    text: this.tunnelLink,
                    width: 128,
                    height: 128,
                    colorDark: "#000000",
                    colorLight: "#ffffff",
                    correctLevel: QRCode.CorrectLevel.M
                });
            } catch (error) {
                console.error('Error generating QR code:', error);
                qrContainer.innerHTML = '<div class="qr-error">QR code generation failed</div>';
            }
        },

        async checkTunnelStatus() {
            // Don't check tunnel status if API calls are paused
            if ((window.isApiCallsPaused && window.isApiCallsPaused()) ||
                (window.authFailureTriggered)) {
                // Silently skip tunnel status check
                return;
            }

            try {
                const response = await fetchApi('/tunnel_proxy', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ action: 'get' }),
                });

                const data = await response.json();

                if (data.success && data.tunnel_url) {
                    // Update the stored URL if it's different from what we have
                    if (this.tunnelLink !== data.tunnel_url) {
                        this.tunnelLink = data.tunnel_url;
                        localStorage.setItem('agent_zero_tunnel_url', data.tunnel_url);
                    }
                    this.linkGenerated = true;
                    // Generate QR code for the tunnel URL
                    this.$nextTick(() => this.generateQRCode());
                } else {
                    // Check if we have a stored tunnel URL
                    const storedTunnelUrl = localStorage.getItem('agent_zero_tunnel_url');

                    if (storedTunnelUrl) {
                        // Use the stored URL but verify it's still valid
                        const verifyResponse = await fetchApi('/tunnel_proxy', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ action: 'verify', url: storedTunnelUrl }),
                        });

                        const verifyData = await verifyResponse.json();

                        if (verifyData.success && verifyData.is_valid) {
                            this.tunnelLink = storedTunnelUrl;
                            this.linkGenerated = true;
                            // Generate QR code for the tunnel URL
                            this.$nextTick(() => this.generateQRCode());
                        } else {
                            // Clear stale URL
                            localStorage.removeItem('agent_zero_tunnel_url');
                            this.tunnelLink = '';
                            this.linkGenerated = false;
                        }
                    } else {
                        // No stored URL, show the generate button
                        this.tunnelLink = '';
                        this.linkGenerated = false;
                    }
                }
            } catch (error) {
                console.error('Error checking tunnel status:', error);
                this.tunnelLink = '';
                this.linkGenerated = false;
            }
        },

        async refreshLink() {
            // Call generate but with a confirmation first
            if (confirm("Are you sure you want to generate a new tunnel URL? The old URL will no longer work.")) {
                this.isLoading = true;
                this.loadingText = 'Refreshing tunnel...';

                // Change refresh button appearance
                const refreshButton = document.querySelector('.refresh-link-button');
                const originalContent = refreshButton.innerHTML;
                refreshButton.innerHTML = '<span class="icon material-symbols-outlined spin">progress_activity</span> Refreshing...';
                refreshButton.disabled = true;
                refreshButton.classList.add('refreshing');

                try {
                    // First stop any existing tunnel
                    const stopResponse = await fetchApi('/tunnel_proxy', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ action: 'stop' }),
                    });

                    // Check if stopping was successful
                    const stopData = await stopResponse.json();
                    if (!stopData.success) {
                        console.warn("Warning: Couldn't stop existing tunnel cleanly");
                        // Continue anyway since we want to create a new one
                    }

                    // Then generate a new one
                    await this.generateLink();
                } catch (error) {
                    console.error("Error refreshing tunnel:", error);
                    window.toastFrontendError("Error refreshing tunnel", "Tunnel Error");
                    this.isLoading = false;
                    this.loadingText = '';
                } finally {
                    // Reset refresh button
                    refreshButton.innerHTML = originalContent;
                    refreshButton.disabled = false;
                    refreshButton.classList.remove('refreshing');
                }
            }
        },

        async generateLink() {
            // Don't generate link if API calls are paused
            if (window.isApiCallsPaused && window.isApiCallsPaused()) {
                console.log('Cannot generate tunnel link - API calls are paused');
                return;
            }

            // First check if authentication is enabled
            try {
                const authCheckResponse = await fetchApi('/settings_get');
                const authData = await authCheckResponse.json();

                // Find the auth_login and auth_password in the settings
                let hasAuth = false;

                if (authData && authData.settings && authData.settings.sections) {
                    for (const section of authData.settings.sections) {
                        if (section.fields) {
                            const authLoginField = section.fields.find(field => field.id === 'auth_login');
                            const authPasswordField = section.fields.find(field => field.id === 'auth_password');

                            if (authLoginField && authPasswordField &&
                                authLoginField.value && authPasswordField.value) {
                                hasAuth = true;
                                break;
                            }
                        }
                    }
                }

                // If no authentication is set, warn the user
                if (!hasAuth) {
                    const proceed = confirm(
                        "WARNING: No authentication is configured for your Agent Zero instance.\n\n" +
                        "Creating a public tunnel without authentication means anyone with the URL " +
                        "can access your Agent Zero instance.\n\n" +
                        "It is recommended to set up authentication in the Settings > Authentication section " +
                        "before creating a public tunnel.\n\n" +
                        "Do you want to proceed anyway?"
                    );

                    if (!proceed) {
                        return; // User cancelled
                    }
                }
            } catch (error) {
                console.error("Error checking authentication status:", error);
                // Continue anyway if we can't check auth status
            }

            this.isLoading = true;
            this.loadingText = 'Creating tunnel...';

            // Get provider from the parent settings modal scope
            const modalEl = document.getElementById('settingsModal');
            const modalAD = Alpine.$data(modalEl);
            const provider = modalAD.provider || 'cloudflared'; // Default to cloudflared if not set

            // Change create button appearance
            const createButton = document.querySelector('.tunnel-actions .btn-ok');
            if (createButton) {
                createButton.innerHTML = '<span class="icon material-symbols-outlined spin">progress_activity</span> Creating...';
                createButton.disabled = true;
                createButton.classList.add('creating');
            }

            try {
                // Call the backend API to create a tunnel
                const response = await fetchApi('/tunnel_proxy', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        action: 'create',
                        provider: provider
                        // port: window.location.port || (window.location.protocol === 'https:' ? 443 : 80)
                    }),
                });

                const data = await response.json();

                if (data.success && data.tunnel_url) {
                    // Store the tunnel URL in localStorage for persistence
                    localStorage.setItem('agent_zero_tunnel_url', data.tunnel_url);

                    this.tunnelLink = data.tunnel_url;
                    this.linkGenerated = true;

                    // Generate QR code for the tunnel URL
                    this.$nextTick(() => this.generateQRCode());

                    // Show success message to confirm creation
                    window.toastFrontendInfo("Tunnel created successfully", "Tunnel Status");
                } else {
                    // The tunnel might still be starting up, check again after a delay
                    this.loadingText = 'Tunnel creation taking longer than expected...';

                    // Wait for 5 seconds and check if the tunnel is running
                    await new Promise(resolve => setTimeout(resolve, 5000));

                    // Check if tunnel is running now
                    try {
                        const statusResponse = await fetchApi('/tunnel_proxy', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ action: 'get' }),
                        });

                        const statusData = await statusResponse.json();

                        if (statusData.success && statusData.tunnel_url) {
                            // Tunnel is now running, we can update the UI
                            localStorage.setItem('agent_zero_tunnel_url', statusData.tunnel_url);
                            this.tunnelLink = statusData.tunnel_url;
                            this.linkGenerated = true;

                            // Generate QR code for the tunnel URL
                            this.$nextTick(() => this.generateQRCode());

                            window.toastFrontendInfo("Tunnel created successfully", "Tunnel Status");
                            return;
                        }
                    } catch (statusError) {
                        console.error("Error checking tunnel status:", statusError);
                    }

                    // If we get here, the tunnel really failed to start
                    const errorMessage = data.message || "Failed to create tunnel. Please try again.";
                    window.toastFrontendError(errorMessage, "Tunnel Error");
                    console.error("Tunnel creation failed:", data);
                }
            } catch (error) {
                window.toastFrontendError("Error creating tunnel", "Tunnel Error");
                console.error("Error creating tunnel:", error);
            } finally {
                this.isLoading = false;
                this.loadingText = '';

                // Reset create button if it's still in the DOM
                const createButton = document.querySelector('.tunnel-actions .btn-ok');
                if (createButton) {
                    createButton.innerHTML = '<span class="icon material-symbols-outlined">play_circle</span> Create Tunnel';
                    createButton.disabled = false;
                    createButton.classList.remove('creating');
                }
            }
        },

        async stopTunnel() {
            // Don't stop tunnel if API calls are paused
            if (window.isApiCallsPaused && window.isApiCallsPaused()) {
                console.log('Cannot stop tunnel - API calls are paused');
                return;
            }

            if (confirm("Are you sure you want to stop the tunnel? The URL will no longer be accessible.")) {
                this.isLoading = true;
                this.loadingText = 'Stopping tunnel...';


                try {
                    // Call the backend to stop the tunnel
                    const response = await fetchApi('/tunnel_proxy', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ action: 'stop' }),
                    });

                    const data = await response.json();

                    if (data.success) {
                        // Clear the stored URL
                        localStorage.removeItem('agent_zero_tunnel_url');

                        // Clear QR code
                        const qrContainer = document.getElementById('qrcode-tunnel');
                        if (qrContainer) {
                            qrContainer.innerHTML = '';
                        }
                        this.qrCodeInstance = null;

                        // Update UI state
                        this.tunnelLink = '';
                        this.linkGenerated = false;

                        window.toastFrontendInfo("Tunnel stopped successfully", "Tunnel Status");
                    } else {
                        window.toastFrontendError("Failed to stop tunnel", "Tunnel Error");

                        // Reset stop button
                        stopButton.innerHTML = originalStopContent;
                        stopButton.disabled = false;
                        stopButton.classList.remove('stopping');
                    }
                } catch (error) {
                    window.toastFrontendError("Error stopping tunnel", "Tunnel Error");
                    console.error("Error stopping tunnel:", error);

                    // Reset stop button
                    stopButton.innerHTML = originalStopContent;
                    stopButton.disabled = false;
                    stopButton.classList.remove('stopping');
                } finally {
                    this.isLoading = false;
                    this.loadingText = '';
                }
            }
        },

        copyToClipboard() {
            if (!this.tunnelLink) return;

            const copyButton = document.querySelector('.copy-link-button');
            const originalContent = copyButton.innerHTML;

            navigator.clipboard.writeText(this.tunnelLink)
                .then(() => {
                    // Update button to show success state
                    copyButton.innerHTML = '<span class="icon material-symbols-outlined">check</span> Copied!';
                    copyButton.classList.add('copy-success');

                    // Show toast notification
                    window.toastFrontendInfo("Tunnel URL copied to clipboard!", "Clipboard");

                    // Reset button after 2 seconds
                    setTimeout(() => {
                        copyButton.innerHTML = originalContent;
                        copyButton.classList.remove('copy-success');
                    }, 2000);
                })
                .catch(err => {
                    console.error('Failed to copy URL: ', err);
                    window.toastFrontendError("Failed to copy tunnel URL", "Clipboard Error");

                    // Show error state
                    copyButton.innerHTML = '<span class="icon material-symbols-outlined">close</span> Failed';
                    copyButton.classList.add('copy-error');

                    // Reset button after 2 seconds
                    setTimeout(() => {
                        copyButton.innerHTML = originalContent;
                        copyButton.classList.remove('copy-error');
                    }, 2000);
                });
        }
    }));
});
