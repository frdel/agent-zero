import { createStore } from "/js/AlpineStore.js";
import * as API from "/js/api.js";
import { openModal } from "/js/modals.js";

export const NotificationType = {
  INFO: "info",
  SUCCESS: "success",
  WARNING: "warning",
  ERROR: "error",
  PROGRESS: "progress",
};

export const NotificationPriority = {
  NORMAL: 10,
  HIGH: 20,
};

export const defaultPriority = NotificationPriority.NORMAL;

const maxNotifications = 100
const maxToasts = 5

const model = {
  notifications: [],
  loading: false,
  lastNotificationVersion: 0,
  lastNotificationGuid: "",
  unreadCount: 0,
  unreadPrioCount: 0,

  // NEW: Toast stack management
  toastStack: [],
  
  init() {
    this.initialize();
  },

  // Initialize the notification store
  initialize() {
    this.loading = true;
    this.updateUnreadCount();
    // this.removeOldNotifications();
    this.toastStack = [];

    // // Auto-cleanup old notifications and toasts
    // setInterval(() => {
    //   this.removeOldNotifications();
    //   this.cleanupExpiredToasts();
    // }, 5 * 60 * 1000); // Every 5 minutes
  },

  // Update notifications from polling data
  updateFromPoll(pollData) {
    if (!pollData) return;

    // Check if GUID changed (system restart)
    if (pollData.notifications_guid !== this.lastNotificationGuid) {
      this.lastNotificationVersion = 0;
      this.notifications = [];
      this.toastStack = []; // Clear toast stack on restart
      this.lastNotificationGuid = pollData.notifications_guid || "";
    }

    // Process new notifications and add to toast stack
    if (pollData.notifications && pollData.notifications.length > 0) {
      pollData.notifications.forEach((notification) => {
        // should we toast the notification?
        const shouldToast = !notification.read;

        // adjust notification data before adding
        this.adjustNotificationData(notification);

        const isNew = !this.notifications.find((n) => n.id === notification.id);
        this.addOrUpdateNotification(notification);

        // Add new unread notifications to toast stack
        if (isNew && shouldToast) {
          this.addToToastStack(notification);
        }
      });
    }

    // Update version tracking
    this.lastNotificationVersion = pollData.notifications_version || 0;
    this.lastNotificationGuid = pollData.notifications_guid || "";

    // Update UI state
    this.updateUnreadCount();
    // this.removeOldNotifications();
  },

  adjustNotificationData(notification) {
    // set default priority if not set
    if (!notification.priority) {
      notification.priority = defaultPriority;
    }
  },

  // NEW: Add notification to toast stack
  addToToastStack(notification) {
    // If notification has a group, remove any existing toasts with the same group
    if (notification.group && notification.group.trim() !== "") {
      const existingToast = this.toastStack.find(
        (t) => t.group === notification.group
      );
      if (existingToast && existingToast.toastId)
        this.removeFromToastStack(existingToast.toastId);
    }

    // Create toast object with auto-dismiss timer
    const toast = {
      ...notification,
      toastId: `toast-${notification.id}`,
      addedAt: Date.now(),
      autoRemoveTimer: null,
    };

    // Add to bottom of stack (newest at bottom)
    this.toastStack.push(toast);

    // Enforce max stack limit (remove oldest)
    while (this.toastStack.length > maxToasts) {
      const oldest = this.toastStack[0];
      if (oldest && oldest.toastId) this.removeFromToastStack(oldest.toastId);
    }

    // Set auto-dismiss timer
    toast.autoRemoveTimer = setTimeout(() => {
      this.removeFromToastStack(toast.toastId);
    }, notification.display_time * 1000);
  },

  // NEW: Remove toast from stack
  removeFromToastStack(toastId, removedByUser = false) {
    const index = this.toastStack.findIndex((t) => t.toastId === toastId);
    if (index >= 0) {
      const toast = this.toastStack[index];
      if (toast.autoRemoveTimer) {
        clearTimeout(toast.autoRemoveTimer);
      }
      this.toastStack.splice(index, 1);

      // execute after toast removed callback
      this.afterToastRemoved(toast, removedByUser);
    }
  },

  // called by UI
  dismissToast(toastId) {
    this.removeFromToastStack(toastId, true);
  },

  async afterToastRemoved(toast, removedByUser = false) {
    // if the toast is closed by the user OR timed out with normal priority, mark it as read
    if (removedByUser || toast.priority <= NotificationPriority.NORMAL) {
      this.markAsRead(toast.id);
    }
  },

  // NEW: Clear entire toast stack
  clearToastStack(withCallback = true, removedByUser = false) {
    this.toastStack.forEach((toast) => {
      if (toast.autoRemoveTimer) {
        clearTimeout(toast.autoRemoveTimer);
        if (withCallback) this.afterToastRemoved(toast, removedByUser);
      }
    });
    this.toastStack = [];
  },

  // NEW: Clean up expired toasts (backup cleanup)
  cleanupExpiredToasts() {
    const now = Date.now();
    this.toastStack = this.toastStack.filter((toast) => {
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
    await this.openModal();
    // Modal opening will clear toast stack via markAllAsRead
  },

  // Add or update a notification
  addOrUpdateNotification(notification) {
    const existingIndex = this.notifications.findIndex(
      (n) => n.id === notification.id
    );

    if (existingIndex >= 0) {
      // Update existing notification
      this.notifications[existingIndex] = notification;
    } else {
      // Add new notification at the beginning (most recent first)
      this.notifications.unshift(notification);
    }

    // Limit notifications to prevent memory issues (keep most recent)
    if (this.notifications.length > maxNotifications) {
      this.notifications = this.notifications.slice(0, maxNotifications);
    }
  },

  // Update unread count
  updateUnreadCount() {
    const unread = this.notifications.filter((n) => !n.read).length;
    const unreadPrio = this.notifications.filter(
      (n) => !n.read && n.priority > NotificationPriority.NORMAL
    ).length;
    if (this.unreadCount !== unread) this.unreadCount = unread;
    if (this.unreadPrioCount !== unreadPrio) this.unreadPrioCount = unreadPrio;
  },

  // Mark notification as read
  async markAsRead(notificationId) {
    const notification = this.notifications.find(
      (n) => n.id === notificationId
    );
    if (notification && !notification.read) {
      notification.read = true;
      this.updateUnreadCount();

      // Sync with backend (non-blocking)
      try {
        await API.callJsonApi("notifications_mark_read", {
          notification_ids: [notificationId],
        });
      } catch (error) {
        console.error("Failed to sync notification read status:", error);
        // Don't revert the UI change - user experience should not be affected
      }
    }
  },

  // Enhanced: Mark all as read and clear toast stack
  async markAllAsRead() {
    const unreadNotifications = this.notifications.filter((n) => !n.read);
    if (unreadNotifications.length === 0) return;

    // Update UI immediately
    this.notifications.forEach((notification) => {
      notification.read = true;
    });
    this.updateUnreadCount();

    // Clear toast stack when marking all as read
    this.clearToastStack(false);

    // Sync with backend (non-blocking)
    try {
      await API.callJsonApi("notifications_mark_read", {
        mark_all: true,
      });
    } catch (error) {
      console.error("Failed to sync mark all as read:", error);
    }
  },

  // Clear all notifications
  async clearAll(syncBackend = true) {
    this.notifications = [];
    this.unreadCount = 0;
    this.clearToastStack(false); // Also clear toast stack
    this.clearBackendNotifications();
  },

  async clearBackendNotifications() {
    try {
      await API.callJsonApi("notifications_clear", null);
    } catch (error) {
      console.error("Failed to clear notifications:", error);
    }
  },

  // Get notifications by type
  getNotificationsByType(type) {
    return this.notifications.filter((n) => n.type === type);
  },

  // Get notifications for display: ALL unread + read from last 5 minutes
  getDisplayNotifications() {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);

    return this.notifications.filter((notification) => {
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
    return this.notifications.find((n) => n.id === id);
  },

  // Remove old notifications (older than 1 hour)
  removeOldNotifications() {
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
    const initialCount = this.notifications.length;
    this.notifications = this.notifications.filter(
      (n) => new Date(n.timestamp) > oneHourAgo
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
    const diffMins = diffMs / 60000;
    const diffHours = diffMs / 3600000;
    const diffDays = diffMs / 86400000;

    if (diffMins < 0.15) return "Just now";
    else if (diffMins < 1) return "Less than a minute ago";
    else if (diffMins < 60) return `${Math.round(diffMins)}m ago`;
    else if (diffHours < 24) return `${Math.round(diffHours)}h ago`;
    else if (diffDays < 7) return `${Math.round(diffDays)}d ago`;

    return date.toLocaleDateString();
  },

  // Get CSS class for notification type
  getNotificationClass(type) {
    const classes = {
      info: "notification-info",
      success: "notification-success",
      warning: "notification-warning",
      error: "notification-error",
      progress: "notification-progress",
    };
    return classes[type] || "notification-info";
  },

  // Get CSS class for notification item including read state
  getNotificationItemClass(notification) {
    const typeClass = this.getNotificationClass(notification.type);
    const readClass = notification.read ? "read" : "unread";
    return `notification-item ${typeClass} ${readClass}`;
  },

  // Get icon for notification type (Google Material Icons)
  getNotificationIcon(type) {
    const icons = {
      info: "info",
      success: "check_circle",
      warning: "warning",
      error: "error",
      progress: "hourglass_empty",
    };
    const iconName = icons[type] || "info";
    return `<span class="material-symbols-outlined">${iconName}</span>`;
  },

  // Create notification via backend (will appear via polling)
  async createNotification(
    type,
    message,
    title = "",
    detail = "",
    display_time = 3,
    group = "",
    priority = defaultPriority
  ) {
    try {
      const response = await globalThis.sendJsonData("/notification_create", {
        type: type,
        message: message,
        title: title,
        detail: detail,
        display_time: display_time,
        group: group,
        priority: priority,
      });

      if (response.success) {
        return response.notification_id;
      } else {
        console.error("Failed to create notification:", response.error);
        return null;
      }
    } catch (error) {
      console.error("Error creating notification:", error);
      return null;
    }
  },

  // Convenience methods for different notification types
  async info(
    message,
    title = "",
    detail = "",
    display_time = 3,
    group = "",
    priority = defaultPriority
  ) {
    return await this.createNotification(
      NotificationType.INFO,
      message,
      title,
      detail,
      display_time,
      group,
      priority
    );
  },

  async success(
    message,
    title = "",
    detail = "",
    display_time = 3,
    group = "",
    priority = defaultPriority
  ) {
    return await this.createNotification(
      NotificationType.SUCCESS,
      message,
      title,
      detail,
      display_time,
      group,
      priority
    );
  },

  async warning(
    message,
    title = "",
    detail = "",
    display_time = 3,
    group = "",
    priority = defaultPriority
  ) {
    return await this.createNotification(
      NotificationType.WARNING,
      message,
      title,
      detail,
      display_time,
      group,
      priority
    );
  },

  async error(
    message,
    title = "",
    detail = "",
    display_time = 3,
    group = "",
    priority = defaultPriority
  ) {
    return await this.createNotification(
      NotificationType.ERROR,
      message,
      title,
      detail,
      display_time,
      group,
      priority
    );
  },

  async progress(
    message,
    title = "",
    detail = "",
    display_time = 3,
    group = "",
    priority = defaultPriority
  ) {
    return await this.createNotification(
      NotificationType.PROGRESS,
      message,
      title,
      detail,
      display_time,
      group,
      priority
    );
  },

  // Enhanced: Open modal and clear toast stack
  async openModal() {
    // Clear toast stack when modal opens
    this.clearToastStack(false);
    // open modal
    await openModal("notifications/notification-modal.html");
    // mark all as read when modal closes
    this.markAllAsRead();
  },

  // Legacy method for backward compatibility
  toggleNotifications() {
    this.openModal();
  },

  // NEW: Check if backend connection is available
  isConnected() {
    // Use the global connection status from index.js, but default to true if undefined
    // This handles the case where polling hasn't run yet but backend is actually available
    const pollingStatus =
      typeof globalThis.getConnectionStatus === "function"
        ? globalThis.getConnectionStatus()
        : undefined;

    // If polling status is explicitly false, respect that
    if (pollingStatus === false) {
      return false;
    }

    // If polling status is undefined/true, assume backend is available
    // (since the page loaded successfully, backend must be working)
    return true;
  },

  // NEW: Add frontend-only toast directly to stack (renamed from original addFrontendToast)
  addFrontendToastOnly(
    type,
    message,
    title = "",
    display_time = 5,
    group = "",
    priority = defaultPriority
  ) {
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
      frontend: true, // Mark as frontend-only
      group: group,
      priority: priority,
    };

    //adjust data before using
    this.adjustNotificationData(notification);

    // If notification has a group, remove any existing toasts with the same group
    if (group && String(group).trim() !== "") {
      const existingToastIndex = this.toastStack.findIndex(
        (t) => t.group === group
      );

      if (existingToastIndex >= 0) {
        const existingToast = this.toastStack[existingToastIndex];
        if (existingToast.autoRemoveTimer) {
          clearTimeout(existingToast.autoRemoveTimer);
        }
        this.toastStack.splice(existingToastIndex, 1);
      }
    }

    // Create toast object with auto-dismiss timer
    const toast = {
      ...notification,
      toastId: `toast-${notification.id}`,
      addedAt: Date.now(),
      autoRemoveTimer: null,
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

    return notification.id;
  },

  // NEW: Enhanced frontend toast that tries backend first, falls back to frontend-only
  async addFrontendToast(
    type,
    message,
    title = "",
    display_time = 5,
    group = "",
    priority = defaultPriority
  ) {
    // Try to send to backend first if connected
    if (this.isConnected()) {
      try {
        const notificationId = await this.createNotification(
          type,
          message,
          title,
          "",
          display_time,
          group,
          priority
        );
        if (notificationId) {
          // Backend handled it, notification will arrive via polling
          return notificationId;
        }
      } catch (error) {
        console.log(
          `Backend unavailable for notification, showing as frontend-only: ${
            error.message || error
          }`
        );
      }
    } else {
      console.log("Backend disconnected, showing as frontend-only toast");
    }

    // Fallback to frontend-only toast
    return this.addFrontendToastOnly(
      type,
      message,
      title,
      display_time,
      group,
      priority
    );
  },

  // NEW: Convenience methods for frontend notifications (updated to use new backend-first logic)
  async frontendError(
    message,
    title = "Connection Error",
    display_time = 8,
    group = "",
    priority = defaultPriority
  ) {
    return await this.addFrontendToast(
      NotificationType.ERROR,
      message,
      title,
      display_time,
      group,
      priority
    );
  },

  async frontendWarning(
    message,
    title = "Warning",
    display_time = 5,
    group = "",
    priority = defaultPriority
  ) {
    return await this.addFrontendToast(
      NotificationType.WARNING,
      message,
      title,
      display_time,
      group,
      priority
    );
  },

  async frontendInfo(
    message,
    title = "Info",
    display_time = 3,
    group = "",
    priority = defaultPriority
  ) {
    return await this.addFrontendToast(
      NotificationType.INFO,
      message,
      title,
      display_time,
      group,
      priority
    );
  },

  async frontendSuccess(
    message,
    title = "Success",
    display_time = 3,
    group = "",
    priority = defaultPriority
  ) {
    return await this.addFrontendToast(
      NotificationType.SUCCESS,
      message,
      title,
      display_time,
      group,
      priority
    );
  },
};

// Create and export the store
const store = createStore("notificationStore", model);
export { store };

// add toasts to global for backward compatibility with older scripts
globalThis.toastFrontendInfo = store.frontendInfo.bind(store);
globalThis.toastFrontendSuccess = store.frontendSuccess.bind(store);
globalThis.toastFrontendWarning = store.frontendWarning.bind(store);
globalThis.toastFrontendError = store.frontendError.bind(store);
