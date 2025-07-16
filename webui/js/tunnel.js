
// Tunnel settings for the Settings modal
document.addEventListener('alpine:init', () => {
    Alpine.data('tunnelSettings', () => ({
        isLoading: false,
        tunnelLink: '',
        linkGenerated: false,
        loadingText: '',

        init() {
            this.checkTunnelStatus();
        },

        async checkTunnelStatus() {
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
                    window.toast("Error refreshing tunnel", "error", 3000);
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
                    
                    // Show success message to confirm creation
                    window.toast("Tunnel created successfully", "success", 3000);
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
                            window.toast("Tunnel created successfully", "success", 3000);
                            return;
                        }
                    } catch (statusError) {
                        console.error("Error checking tunnel status:", statusError);
                    }
                    
                    // If we get here, the tunnel really failed to start
                    const errorMessage = data.message || "Failed to create tunnel. Please try again.";
                    window.toast(errorMessage, "error", 5000);
                    console.error("Tunnel creation failed:", data);
                }
            } catch (error) {
                window.toast("Error creating tunnel", "error", 5000);
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
                        
                        // Update UI state
                        this.tunnelLink = '';
                        this.linkGenerated = false;
                        
                        window.toast("Tunnel stopped successfully", "success", 3000);
                    } else {
                        window.toast("Failed to stop tunnel", "error", 3000);
                        
                        // Reset stop button
                        stopButton.innerHTML = originalStopContent;
                        stopButton.disabled = false;
                        stopButton.classList.remove('stopping');
                    }
                } catch (error) {
                    window.toast("Error stopping tunnel", "error", 3000);
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
                    window.toast("Tunnel URL copied to clipboard!", "success", 3000);
                    
                    // Reset button after 2 seconds
                    setTimeout(() => {
                        copyButton.innerHTML = originalContent;
                        copyButton.classList.remove('copy-success');
                    }, 2000);
                })
                .catch(err => {
                    console.error('Failed to copy URL: ', err);
                    window.toast("Failed to copy tunnel URL", "error", 3000);
                    
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