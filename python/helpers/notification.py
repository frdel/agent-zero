from dataclasses import dataclass
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum


class NotificationType(Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PROGRESS = "progress"

class NotificationPriority(Enum):
    NORMAL = 10
    HIGH = 20


@dataclass
class NotificationItem:
    manager: "NotificationManager"
    no: int
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    detail: str  # HTML content for expandable details
    timestamp: datetime
    display_time: int = 3  # Display duration in seconds, default 3 seconds
    read: bool = False
    id: str = ""
    group: str = ""  # Group identifier for grouping related notifications

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        # Ensure type is always NotificationType
        if isinstance(self.type, str):
            self.type = NotificationType(self.type)

    def mark_read(self):
        self.read = True
        self.manager._update_item(self.no, read=True)

    def output(self):
        return {
            "no": self.no,
            "id": self.id,
            "type": self.type.value if isinstance(self.type, NotificationType) else self.type,
            "priority": self.priority.value if isinstance(self.priority, NotificationPriority) else self.priority,
            "title": self.title,
            "message": self.message,
            "detail": self.detail,
            "timestamp": self.timestamp.isoformat(),
            "display_time": self.display_time,
            "read": self.read,
            "group": self.group,
        }


class NotificationManager:
    def __init__(self, max_notifications: int = 100):
        self.guid: str = str(uuid.uuid4())
        self.updates: list[int] = []
        self.notifications: list[NotificationItem] = []
        self.max_notifications = max_notifications

    @staticmethod
    def send_notification(
        type: NotificationType,
        priority: NotificationPriority,
        message: str,
        title: str = "",
        detail: str = "",
        display_time: int = 3,
        group: str = "",
    ) -> NotificationItem:
        from agent import AgentContext
        return AgentContext.get_notification_manager().add_notification(
            type, priority, message, title, detail, display_time, group
        )

    def add_notification(
        self,
        type: NotificationType,
        priority: NotificationPriority,
        message: str,
        title: str = "",
        detail: str = "",
        display_time: int = 3,
        group: str = "",
    ) -> NotificationItem:
        # Create notification item
        item = NotificationItem(
            manager=self,
            no=len(self.notifications),
            type=NotificationType(type),
            priority=NotificationPriority(priority),
            title=title,
            message=message,
            detail=detail,
            timestamp=datetime.now(timezone.utc),
            display_time=display_time,
            group=group,
        )

        # Add to notifications
        self.notifications.append(item)
        self.updates.append(item.no)

        # Enforce limit
        self._enforce_limit()

        return item

    def _enforce_limit(self):
        if len(self.notifications) > self.max_notifications:
            # Remove oldest notifications
            to_remove = len(self.notifications) - self.max_notifications
            self.notifications = self.notifications[to_remove:]
            # Adjust notification numbers
            for i, notification in enumerate(self.notifications):
                notification.no = i
            # Adjust updates list
            self.updates = [no - to_remove for no in self.updates if no >= to_remove]

    def get_recent_notifications(self, seconds: int = 30) -> list[NotificationItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        return [n for n in self.notifications if n.timestamp >= cutoff]

    def output(self, start: int | None = None, end: int | None = None) -> list[dict]:
        if start is None:
            start = 0
        if end is None:
            end = len(self.updates)

        out = []
        seen = set()
        for update in self.updates[start:end]:
            if update not in seen and update < len(self.notifications):
                out.append(self.notifications[update].output())
                seen.add(update)

        return out

    def _update_item(self, no: int, **kwargs):
        if no < len(self.notifications):
            item = self.notifications[no]
            for key, value in kwargs.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            self.updates.append(no)

    def mark_all_read(self):
        for notification in self.notifications:
            notification.read = True

    def clear_all(self):
        self.notifications = []
        self.updates = []
        self.guid = str(uuid.uuid4())

    def get_notifications_by_type(self, type: NotificationType) -> list[NotificationItem]:
        return [n for n in self.notifications if n.type == type]