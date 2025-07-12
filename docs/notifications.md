# Agent Zero Notifications

Quick guide for using the notification system in Agent Zero.

## Backend Usage

Use `AgentNotification` helper methods anywhere in your Python code:

```python
from python.helpers.notification import AgentNotification

# Basic notifications
AgentNotification.info("Operation completed")
AgentNotification.success("File saved successfully", "File Manager")
AgentNotification.warning("High CPU usage detected", "System Monitor")
AgentNotification.error("Connection failed", "Network Error")
AgentNotification.progress("Processing files...", "Task Progress")

# With details and custom display time
AgentNotification.info(
    message="System backup completed",
    title="Backup Manager",
    detail="<p>Backup size: <strong>2.4 GB</strong></p>",
    display_time=8  # seconds
)

# Grouped notifications (replaces previous in same group)
AgentNotification.progress("Download: 25%", "File Download", group="download-status")
AgentNotification.progress("Download: 75%", "File Download", group="download-status")  # Replaces previous
AgentNotification.progress("Download: Complete!", "File Download", group="download-status")  # Replaces previous
```

## Frontend Usage

Use the notification store in Alpine.js components:

```javascript
// Basic notifications
$store.notificationStore.info("User logged in")
$store.notificationStore.success("Settings saved", "Configuration")
$store.notificationStore.warning("Session expiring soon")
$store.notificationStore.error("Failed to load data")

// With grouping
$store.notificationStore.info("Connecting...", "Status", "", 3, "connection")
$store.notificationStore.success("Connected!", "Status", "", 3, "connection")  // Replaces previous

// Frontend notifications with backend persistence (new feature!)
$store.notificationStore.frontendError("Database timeout", "Connection Error")
$store.notificationStore.frontendWarning("High memory usage", "Performance")
$store.notificationStore.frontendInfo("Cache cleared", "System")
```

## Frontend Notifications with Backend Sync

**New Feature**: Frontend notifications now automatically sync to the backend when connected, providing persistent history and cross-session availability.

### How it Works:
- **Backend Connected**: Notifications are sent to backend and appear via polling (persistent)
- **Backend Disconnected**: Notifications show as frontend-only toasts (temporary)
- **Automatic Fallback**: Seamless degradation when backend is unavailable

### Global Functions:
```javascript
// These functions automatically try backend first, then fallback to frontend-only
toastFrontendError("Server unreachable", "Connection Error")
toastFrontendWarning("Slow connection detected")
toastFrontendInfo("Reconnected successfully")
```

## HTML Usage

```html
<button @click="$store.notificationStore.success('Task completed!')">
    Complete Task
</button>

<button @click="$store.notificationStore.warning('Progress: 50%', 'Upload', '', 5, 'upload-progress')">
    Update Progress
</button>

<!-- Frontend notifications with backend sync -->
<button @click="$store.notificationStore.frontendError('Connection failed', 'Network')">
    Report Connection Error
</button>
```

## Notification Groups

Groups ensure only the latest notification from each group is shown in the toast stack:

```python
# Progress updates - each new notification replaces the previous one
AgentNotification.info("Starting backup...", group="backup-status")
AgentNotification.progress("Backup: 30%", group="backup-status")  # Replaces previous
AgentNotification.progress("Backup: 80%", group="backup-status")  # Replaces previous
AgentNotification.success("Backup complete!", group="backup-status")  # Replaces previous

# Connection status - only show current state
AgentNotification.warning("Disconnected", group="network")
AgentNotification.info("Reconnecting...", group="network")  # Replaces previous
AgentNotification.success("Connected", group="network")  # Replaces previous
```

## Parameters

All notification methods support these parameters:

- `message` (required): Main notification text
- `title` (optional): Notification title
- `detail` (optional): HTML content for expandable details
- `display_time` (optional): Toast display duration in seconds (default: 3)
- `group` (optional): Group identifier for replacement behavior

## Types

- **info** (ℹ️): General information
- **success** (✅): Successful operations
- **warning** (⚠️): Important alerts
- **error** (❌): Error conditions
- **progress** (⏳): Ongoing operations

## Behavior

- **Toast Display**: Notifications appear as toasts in the bottom-right corner
- **Persistent History**: All notifications (including synced frontend ones) are stored in notification history
- **Modal Access**: Full history accessible via the bell icon
- **Auto-dismiss**: Toasts automatically disappear after `display_time`
- **Group Replacement**: Notifications with the same group replace previous ones immediately
- **Backend Sync**: Frontend notifications automatically sync to backend when connected
