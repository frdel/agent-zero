import { createStore } from "/js/AlpineStore.js";
import * as API from "/js/api.js";

const model = {
    notifications: [],
    loading: false,
    lastNotificationVersion: 0,
    lastNotificationGuid: "",
    unreadCount: 0,

    // NEW: Toast stack management
    toastStack: [],
    maxToastStack: 5,

    // Initialize the notification store
    initialize() {
        console.log("NotificationStore: Initializing with toast stack");
        this.loading = true;
        this.updateUnreadCount();
        this.removeOldNotifications();
        this.toastStack = [];

        // Auto-cleanup old notifications and toasts
        setInterval(() => {
            this.removeOldNotifications();
            this.cleanupExpiredToasts();
        }, 5 * 60 * 1000); // Every 5 minutes
    },

    // Update notifications from polling data
    updateFromPoll(pollData) {
        if (!pollData) return;

        // Check if GUID changed (system restart)
        if (pollData.notifications_guid !== this.lastNotificationGuid) {
            this.lastNotificationVersion = 0;
            this.notifications = [];
            this.toastStack = []; // Clear toast stack on restart
            this.lastNotificationGuid = pollData.notifications_guid || '';
        }

        // Process new notifications and add to toast stack
        if (pollData.notifications && pollData.notifications.length > 0) {
            pollData.notifications.forEach(notification => {
                const isNew = !this.notifications.find(n => n.id === notification.id);
                this.addOrUpdateNotification(notification);

                // Add new notifications to toast stack
                if (isNew && !notification.read) {
                    this.addToToastStack(notification);
                }
            });
        }

        // Update version tracking
        this.lastNotificationVersion = pollData.notifications_version || 0;
        this.lastNotificationGuid = pollData.notifications_guid || '';

        // Update UI state
        this.updateUnreadCount();
        this.removeOldNotifications();

        // Limit notifications to prevent memory issues (keep most recent)
        if (this.notifications.length > 50) {
            // Sort by timestamp and keep newest 50
            this.notifications.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            this.notifications = this.notifications.slice(0, 50);
        }
    },

    // NEW: Add notification to toast stack
    addToToastStack(notification) {
        // Create toast object with auto-dismiss timer
        const toast = {
            ...notification,
            toastId: `toast-${notification.id}`,
            addedAt: Date.now(),
            autoRemoveTimer: null
        };

        // Add to bottom of stack (newest at bottom)
        this.toastStack.push(toast);

        // Enforce max stack limit (remove oldest from top)
        if (this.toastStack.length > this.maxToastStack) {
            const removed = this.toastStack.shift(); // Remove from top
            if (removed.autoRemoveTimer) {
                clearTimeout(removed.autoRemoveTimer);
            }
        }

        // Set auto-dismiss timer
        toast.autoRemoveTimer = setTimeout(() => {
            this.removeFromToastStack(toast.toastId);
        }, notification.display_time * 1000);

        console.log(`Toast added: ${notification.type} - ${notification.message}`);
    },

    // NEW: Remove toast from stack
    removeFromToastStack(toastId) {
        const index = this.toastStack.findIndex(t => t.toastId === toastId);
        if (index >= 0) {
            const toast = this.toastStack[index];
            if (toast.autoRemoveTimer) {
                clearTimeout(toast.autoRemoveTimer);
            }
            this.toastStack.splice(index, 1);
            console.log(`Toast removed: ${toastId}`);
        }
    },

    // NEW: Clear entire toast stack
    clearToastStack() {
        this.toastStack.forEach(toast => {
            if (toast.autoRemoveTimer) {
                clearTimeout(toast.autoRemoveTimer);
            }
        });
        this.toastStack = [];
        console.log('Toast stack cleared');
    },

    // NEW: Clean up expired toasts (backup cleanup)
    cleanupExpiredToasts() {
        const now = Date.now();
        this.toastStack = this.toastStack.filter(toast => {
            const age = now - toast.addedAt;
            const maxAge = toast.display_time * 1000;

            if (age > maxAge) {
                if (toast.autoRemoveTimer) {
                    clearTimeout(toast.autoRemoveTimer);
                }
                return false;
            }
            return true;
        });
    },

    // NEW: Handle toast click (opens modal)
    async handleToastClick(toastId) {
        console.log(`Toast clicked: ${toastId}`);
        await this.openModal();
        // Modal opening will clear toast stack via markAllAsRead
    },

    // Add or update a notification
    addOrUpdateNotification(notification) {
        const existingIndex = this.notifications.findIndex(n => n.id === notification.id);

        if (existingIndex >= 0) {
            // Update existing notification
            this.notifications[existingIndex] = notification;
        } else {
            // Add new notification at the beginning (most recent first)
            this.notifications.unshift(notification);
        }
    },

    // Update unread count
    updateUnreadCount() {
        this.unreadCount = this.notifications.filter(n => !n.read).length;
    },

    // Mark notification as read
    async markAsRead(notificationId) {
        const notification = this.notifications.find(n => n.id === notificationId);
        if (notification && !notification.read) {
            notification.read = true;
            this.updateUnreadCount();

            // Sync with backend (non-blocking)
            try {
                await API.callJsonApi('notifications_mark_read', {
                    notification_ids: [notificationId]
                });
            } catch (error) {
                console.error('Failed to sync notification read status:', error);
                // Don't revert the UI change - user experience should not be affected
            }
        }
    },

    // Enhanced: Mark all as read and clear toast stack
    async markAllAsRead() {
        const unreadNotifications = this.notifications.filter(n => !n.read);
        if (unreadNotifications.length === 0) return;

        // Update UI immediately
        this.notifications.forEach(notification => {
            notification.read = true;
        });
        this.updateUnreadCount();

        // Clear toast stack when marking all as read
        this.clearToastStack();

        // Sync with backend (non-blocking)
        try {
            await API.callJsonApi('notifications_mark_read', {
                mark_all: true
            });
        } catch (error) {
            console.error('Failed to sync mark all as read:', error);
        }
    },

    // Clear all notifications
    async clearAll() {
        this.notifications = [];
        this.unreadCount = 0;
        this.clearToastStack(); // Also clear toast stack

        // Note: We don't sync clear with backend as notifications are stored in memory only
        console.log('All notifications cleared');
    },

    // Get notifications by type
    getNotificationsByType(type) {
        return this.notifications.filter(n => n.type === type);
    },

    // Get notifications for display: ALL unread + read from last 5 minutes
    getDisplayNotifications() {
        const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);

        return this.notifications.filter(notification => {
            // Always show unread notifications
            if (!notification.read) {
                return true;
            }

            // Show read notifications only if they're from the last 5 minutes
            const notificationDate = new Date(notification.timestamp);
            return notificationDate > fiveMinutesAgo;
        });
    },

    // Get recent notifications (last 5) - kept for backwards compatibility
    getRecentNotifications() {
        return this.notifications.slice(0, 5);
    },

    // Get notification by ID
    getNotificationById(id) {
        return this.notifications.find(n => n.id === id);
    },

    // Remove old notifications (older than 1 hour)
    removeOldNotifications() {
        const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
        const initialCount = this.notifications.length;
        this.notifications = this.notifications.filter(n =>
            new Date(n.timestamp) > oneHourAgo
        );

        if (this.notifications.length !== initialCount) {
            this.updateUnreadCount();
        }
    },

    // Format timestamp for display
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString();
    },

    // Get CSS class for notification type
    getNotificationClass(type) {
        const classes = {
            info: "notification-info",
            success: "notification-success",
            warning: "notification-warning",
            error: "notification-error",
            progress: "notification-progress"
        };
        return classes[type] || "notification-info";
    },

    // Get CSS class for notification item including read state
    getNotificationItemClass(notification) {
        const typeClass = this.getNotificationClass(notification.type);
        const readClass = notification.read ? "read" : "unread";
        return `notification-item ${typeClass} ${readClass}`;
    },

    // Get icon for notification type
    getNotificationIcon(type) {
        const icons = {
            info: "ℹ️",
            success: "✅",
            warning: "⚠️",
            error: "❌",
            progress: "⏳"
        };
        return icons[type] || "ℹ️";
    },

    // Create notification via backend (will appear via polling)
    async createNotification(type, message, title = "", detail = "", display_time = 3) {
        try {
            const response = await window.sendJsonData('/notification_create', {
                type: type,
                message: message,
                title: title,
                detail: detail,
                display_time: display_time
            });

            if (response.success) {
                console.log('Notification created:', response.notification_id);
                return response.notification_id;
            } else {
                console.error('Failed to create notification:', response.error);
                return null;
            }
        } catch (error) {
            console.error('Error creating notification:', error);
            return null;
        }
    },

    // Convenience methods for different notification types
    async info(message, title = "", detail = "", display_time = 3) {
        return await this.createNotification('info', message, title, detail, display_time);
    },

    async success(message, title = "", detail = "", display_time = 3) {
        return await this.createNotification('success', message, title, detail, display_time);
    },

    async warning(message, title = "", detail = "", display_time = 3) {
        return await this.createNotification('warning', message, title, detail, display_time);
    },

    async error(message, title = "", detail = "", display_time = 3) {
        return await this.createNotification('error', message, title, detail, display_time);
    },

    async progress(message, title = "", detail = "", display_time = 3) {
        return await this.createNotification('progress', message, title, detail, display_time);
    },

    // Enhanced: Open modal and clear toast stack
    async openModal() {
        // Import the standard modal system
        const { openModal } = await import("/js/modals.js");
        await openModal("notifications/notification-modal.html");

        // Clear toast stack when modal opens
        this.clearToastStack();
    },

    // Legacy method for backward compatibility
    toggleNotifications() {
        this.openModal();
    },

    // NEW: Add frontend-only toast directly to stack (for connection errors, etc.)
    addFrontendToast(type, message, title = "", display_time = 5) {
        const timestamp = new Date().toISOString();
        const notification = {
            id: `frontend-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            type: type,
            title: title,
            message: message,
            detail: "",
            timestamp: timestamp,
            display_time: display_time,
            read: false,
            frontend: true  // Mark as frontend-only
        };

        // Create toast object with auto-dismiss timer
        const toast = {
            ...notification,
            toastId: `toast-${notification.id}`,
            addedAt: Date.now(),
            autoRemoveTimer: null
        };

        // Add to bottom of stack (newest at bottom)
        this.toastStack.push(toast);

        // Enforce max stack limit (remove oldest from top)
        if (this.toastStack.length > this.maxToastStack) {
            const removed = this.toastStack.shift(); // Remove from top
            if (removed.autoRemoveTimer) {
                clearTimeout(removed.autoRemoveTimer);
            }
        }

        // Set auto-dismiss timer
        toast.autoRemoveTimer = setTimeout(() => {
            this.removeFromToastStack(toast.toastId);
        }, notification.display_time * 1000);

        console.log(`Frontend toast added: ${notification.type} - ${notification.message}`);
        return notification.id;
    },

    // NEW: Convenience methods for frontend-only notifications
    frontendError(message, title = "Connection Error", display_time = 8) {
        return this.addFrontendToast('error', message, title, display_time);
    },

    frontendWarning(message, title = "Warning", display_time = 5) {
        return this.addFrontendToast('warning', message, title, display_time);
    },

    frontendInfo(message, title = "Info", display_time = 3) {
        return this.addFrontendToast('info', message, title, display_time);
    }
};

// Create and export the store
const store = createStore("notificationStore", model);

// NEW: Global function for frontend error toasts (replaces toastFetchError)
window.toastFrontendError = function(message, title = "Connection Error") {
    if (window.Alpine && window.Alpine.store && window.Alpine.store('notificationStore')) {
        return window.Alpine.store('notificationStore').frontendError(message, title);
    } else {
        // Fallback if Alpine/store not ready
        console.error('Frontend Error:', title, '-', message);
        return null;
    }
};

// NEW: Additional global convenience functions
window.toastFrontendWarning = function(message, title = "Warning") {
    if (window.Alpine && window.Alpine.store && window.Alpine.store('notificationStore')) {
        return window.Alpine.store('notificationStore').frontendWarning(message, title);
    } else {
        console.warn('Frontend Warning:', title, '-', message);
        return null;
    }
};

window.toastFrontendInfo = function(message, title = "Info") {
    if (window.Alpine && window.Alpine.store && window.Alpine.store('notificationStore')) {
        return window.Alpine.store('notificationStore').frontendInfo(message, title);
    } else {
        console.log('Frontend Info:', title, '-', message);
        return null;
    }
};

export { store };
