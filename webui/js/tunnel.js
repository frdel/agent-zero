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
                const response = await fetch('/tunnel_proxy', {
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
                        const verifyResponse = await fetch('/tunnel_proxy', {
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
                console.error(i18next.t('errorCheckingTunnelStatus'), error);
                this.tunnelLink = '';
                this.linkGenerated = false;
            }
        },

        async refreshLink() {
            // Call generate but with a confirmation first
            if (confirm(i18next.t('confirmRefreshTunnel'))) {
                this.isLoading = true;
                this.loadingText = i18next.t('refreshingTunnel');
                
                // Change refresh button appearance
                const refreshButton = document.querySelector('.refresh-link-button');
                const originalContent = refreshButton.innerHTML;
                refreshButton.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${i18next.t('refreshing')}`;
                refreshButton.disabled = true;
                refreshButton.classList.add('refreshing');
                
                try {
                    // First stop any existing tunnel
                    const stopResponse = await fetch('/tunnel_proxy', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ action: 'stop' }),
                    });
                    
                    // Check if stopping was successful
                    const stopData = await stopResponse.json();
                    if (!stopData.success) {
                        console.warn(i18next.t('warningCouldNotStopTunnel'));
                        // Continue anyway since we want to create a new one
                    }
                    
                    // Then generate a new one
                    await this.generateLink();
                } catch (error) {
                    console.error(i18next.t('errorRefreshingTunnel'), error);
                    window.toast(i18next.t('errorRefreshingTunnel'), "error", 3000);
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
                const authCheckResponse = await fetch('/settings_get');
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
                        i18next.t('warningNoAuthForTunnel')
                    );
                    
                    if (!proceed) {
                        return; // User cancelled
                    }
                }
            } catch (error) {
                console.error(i18next.t('errorCheckingAuthStatus'), error);
                // Continue anyway if we can't check auth status
            }
            
            this.isLoading = true;
            this.loadingText = i18next.t('creatingTunnel');

            // Get provider from the parent settings modal scope
            const modalEl = document.getElementById('settingsModal');
            const modalAD = Alpine.$data(modalEl);
            const provider = modalAD.provider || 'serveo'; // Default to serveo if not set
            
            // Change create button appearance
            const createButton = document.querySelector('.tunnel-actions .btn-ok');
            if (createButton) {
                createButton.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${i18next.t('creating')}`;
                createButton.disabled = true;
                createButton.classList.add('creating');
            }
            
            try {
                // Call the backend API to create a tunnel
                const response = await fetch('/tunnel_proxy', {
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
                    window.toast(i18next.t('tunnelCreatedSuccessfully'), "success", 3000);
                } else {
                    // The tunnel might still be starting up, check again after a delay
                    this.loadingText = i18next.t('tunnelCreationTakingLonger');
                    
                    // Wait for 5 seconds and check if the tunnel is running
                    await new Promise(resolve => setTimeout(resolve, 5000));
                    
                    // Check if tunnel is running now
                    try {
                        const statusResponse = await fetch('/tunnel_proxy', {
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
                            window.toast(i18next.t('tunnelCreatedSuccessfully'), "success", 3000);
                            return;
                        }
                    } catch (statusError) {
                        console.error(i18next.t('errorCheckingTunnelStatus'), statusError);
                    }
                    
                    // If we get here, the tunnel really failed to start
                    const errorMessage = data.message || i18next.t('failedToCreateTunnelPleaseTryAgain');
                    window.toast(errorMessage, "error", 5000);
                    console.error(i18next.t('tunnelCreationFailed'), data);
                }
            } catch (error) {
                window.toast(i18next.t('errorCreatingTunnel'), "error", 5000);
                console.error(i18next.t('errorCreatingTunnel'), error);
            } finally {
                this.isLoading = false;
                this.loadingText = '';
                
                // Reset create button if it's still in the DOM
                const createButton = document.querySelector('.tunnel-actions .btn-ok');
                if (createButton) {
                    createButton.innerHTML = `<i class="fas fa-play-circle"></i> ${i18next.t('createTunnel')}`;
                    createButton.disabled = false;
                    createButton.classList.remove('creating');
                }
            }
        },

        async stopTunnel() {
            if (confirm(i18next.t('confirmStopTunnel'))) {
                this.isLoading = true;
                this.loadingText = i18next.t('stoppingTunnel');
                
                
                try {
                    // Call the backend to stop the tunnel
                    const response = await fetch('/tunnel_proxy', {
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
                        
                        window.toast(i18next.t('tunnelStoppedSuccessfully'), "success", 3000);
                    } else {
                        window.toast(i18next.t('failedToStopTunnel'), "error", 3000);
                        
                        // Reset stop button
                        stopButton.innerHTML = originalStopContent;
                        stopButton.disabled = false;
                        stopButton.classList.remove('stopping');
                    }
                } catch (error) {
                    window.toast(i18next.t('errorStoppingTunnel'), "error", 3000);
                    console.error(i18next.t('errorStoppingTunnel'), error);
                    
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
                    copyButton.innerHTML = `<i class="fas fa-check"></i> ${i18next.t('copied')}`;
                    copyButton.classList.add('copy-success');
                    
                    // Show toast notification
                    window.toast(i18next.t('tunnelUrlCopied'), "success", 3000);
                    
                    // Reset button after 2 seconds
                    setTimeout(() => {
                        copyButton.innerHTML = originalContent;
                        copyButton.classList.remove('copy-success');
                    }, 2000);
                })
                .catch(err => {
                    console.error(i18next.t('failedToCopyUrl'), err);
                    window.toast(i18next.t('failedToCopyTunnelUrl'), "error", 3000);
                    
                    // Show error state
                    copyButton.innerHTML = `<i class="fas fa-times"></i> ${i18next.t('failed')}`;
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