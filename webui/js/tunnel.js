// Tunnel Modal
const tunnelModalProxy = {
    isOpen: false,
    isLoading: false,
    tunnelLink: '',
    linkGenerated: false,
    loadingText: '',

    async openModal() {
        const modalEl = document.getElementById('tunnelModal');
        const modalAD = Alpine.$data(modalEl);

        modalAD.isOpen = true;
        modalAD.isLoading = false;
        modalAD.loadingText = '';
        
        // Check if we have a stored tunnel URL
        const storedTunnelUrl = localStorage.getItem('agent_zero_tunnel_url');
        
        if (storedTunnelUrl) {
            // Check if the tunnel is still running on the backend
            const response = await fetch('/tunnel', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ action: 'get' }),
            });

            const data = await response.json();

            if (data.success && data.tunnel_url) {
                // Use the stored URL
                modalAD.tunnelLink = storedTunnelUrl;
                modalAD.linkGenerated = true;
            } else {
                // Clear stale URL if no tunnel is running
                localStorage.removeItem('agent_zero_tunnel_url');
                modalAD.tunnelLink = '';
                modalAD.linkGenerated = false;
            }
        } else {
            // No stored URL, show the generate button
            modalAD.tunnelLink = '';
            modalAD.linkGenerated = false;
        }
    },

    async checkTunnelStatus() {
        try {
            const response = await fetch('/tunnel', {
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
            } else if (!data.is_running) {
                // Tunnel not running but we have a stored URL - keep the UI state
                // but it will be recreated if the user clicks generate
            }
        } catch (error) {
            console.error('Error checking tunnel status:', error);
        }
    },

    async refreshLink() {
        // Call generate but with a confirmation first
        if (confirm("Are you sure you want to generate a new tunnel URL? The old URL will no longer work.")) {
            this.isLoading = true;
            this.loadingText = 'Refreshing tunnel...';
            
            try {
                // First stop any existing tunnel
                const stopResponse = await fetch('/tunnel', {
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
                toast("Error refreshing tunnel", "error", 3000);
                this.isLoading = false;
                this.loadingText = '';
            }
        }
    },

    async generateLink() {
        this.isLoading = true;
        this.loadingText = 'Creating tunnel...';
        
        try {
            // Call the backend API to create a tunnel
            const response = await fetch('/tunnel', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    action: 'create',
                    port: window.location.port || (window.location.protocol === 'https:' ? 443 : 80)
                }),
            });
            
            const data = await response.json();
            
            if (data.success && data.tunnel_url) {
                // Store the tunnel URL in localStorage for persistence
                localStorage.setItem('agent_zero_tunnel_url', data.tunnel_url);
                
                this.tunnelLink = data.tunnel_url;
                this.linkGenerated = true;
                
                // Show success message to confirm creation
                toast("Tunnel created successfully", "success", 3000);
            } else {
                // The tunnel might still be starting up, check again after a delay
                this.loadingText = 'Tunnel creation taking longer than expected...';
                
                // Wait for 5 seconds and check if the tunnel is running
                await new Promise(resolve => setTimeout(resolve, 5000));
                
                // Check if tunnel is running now
                try {
                    const statusResponse = await fetch('/tunnel', {
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
                        toast("Tunnel created successfully", "success", 3000);
                        return;
                    }
                } catch (statusError) {
                    console.error("Error checking tunnel status:", statusError);
                }
                
                // If we get here, the tunnel really failed to start
                const errorMessage = data.message || "Failed to create tunnel. Please try again.";
                toast(errorMessage, "error", 5000);
                console.error("Tunnel creation failed:", data);
            }
        } catch (error) {
            toast("Error creating tunnel", "error", 5000);
            console.error("Error creating tunnel:", error);
        } finally {
            this.isLoading = false;
            this.loadingText = '';
        }
    },

    async stopTunnel() {
        if (confirm("Are you sure you want to stop the tunnel? The URL will no longer be accessible.")) {
            this.isLoading = true;
            this.loadingText = 'Stopping tunnel...';
            
            try {
                // Call the backend to stop the tunnel
                const response = await fetch('/tunnel', {
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
                    
                    toast("Tunnel stopped successfully", "success", 3000);
                } else {
                    toast("Failed to stop tunnel", "error", 3000);
                }
            } catch (error) {
                toast("Error stopping tunnel", "error", 3000);
                console.error("Error stopping tunnel:", error);
            } finally {
                this.isLoading = false;
                this.loadingText = '';
            }
        }
    },

    copyToClipboard() {
        if (!this.tunnelLink) return;
        
        navigator.clipboard.writeText(this.tunnelLink)
            .then(() => {
                toast("Tunnel URL copied to clipboard!", "success", 3000);
            })
            .catch(err => {
                console.error('Failed to copy URL: ', err);
                toast("Failed to copy tunnel URL", "error", 3000);
            });
    },

    handleClose() {
        this.isOpen = false;
    }
};

// Register the tunnel modal with Alpine
document.addEventListener('alpine:init', () => {
    Alpine.data('tunnelModalProxy', () => ({
        init() {
            Object.assign(this, tunnelModalProxy);
        }
    }));
});

// Keep the global assignment for backward compatibility
window.tunnelModalProxy = tunnelModalProxy;

// Add event listener for tunnel button
document.addEventListener('DOMContentLoaded', () => {
    const tunnelButton = document.getElementById('tunnel_button');
    if (tunnelButton) {
        tunnelButton.addEventListener('click', () => {
            tunnelModalProxy.openModal();
        });
    }
});
