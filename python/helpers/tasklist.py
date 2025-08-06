import uuid
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import ClassVar
from pydantic import BaseModel, Field, PrivateAttr
from python.helpers.localization import Localization


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskLog(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str

    def get_log_for_rendering(self) -> dict:
        """Convert log to dict with localized timestamp for display"""
        return {
            "timestamp": Localization.get().serialize_datetime(self.timestamp),
            "message": self.message
        }


class Task(BaseModel):
    uid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = Field(default="")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    logs: list[TaskLog] = Field(default_factory=list)

    def add_log(self, log: TaskLog):
        """Add a log entry to this task"""
        self.logs.append(log)

    def get_logs(self) -> list[TaskLog]:
        """Get all logs for this task"""
        return self.logs

    def get_logs_for_rendering(self) -> list[dict]:
        """Get logs formatted for display with localized timestamps"""
        return [log.get_log_for_rendering() for log in self.logs]


class TaskList(BaseModel):
    uid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tasks: list[Task] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Class-level storage for instances with thread safety
    __instances: ClassVar[dict[str, "TaskList"]] = PrivateAttr(default=dict())
    __lock: ClassVar[RLock] = PrivateAttr(default=RLock())

    # Global tasklist uid
    GLOBAL_TASKLIST_UID: ClassVar[str] = "global"

    @classmethod
    def get_instance(cls, uid: str | None = None) -> "TaskList":
        """Get or create a TaskList instance for the given context (synchronous)"""
        with cls.__lock:
            if uid is None:
                uid = cls.GLOBAL_TASKLIST_UID

            if uid not in cls.__instances:
                # Create new instance
                cls.__instances[uid] = cls(uid=uid)

            return cls.__instances[uid]

    @classmethod
    def get_global_instance(cls) -> "TaskList":
        """Get the global TaskList instance"""
        return cls.get_instance(cls.GLOBAL_TASKLIST_UID)

    @classmethod
    def get_all(cls) -> dict[str, "TaskList"]:
        """Get all TaskList instances currently in memory"""
        with cls.__lock:
            return cls.__instances.copy()

    @classmethod
    def delete_instance(cls, uid: str):
        """Delete a TaskList instance from memory"""
        with cls.__lock:
            if uid in cls.__instances:
                del cls.__instances[uid]

    @classmethod
    def set_instance(cls, uid: str, tasklist: "TaskList"):
        """Set a TaskList instance in memory (used for loading from storage)"""
        with cls.__lock:
            cls.__instances[uid] = tasklist

    def update_timestamp(self):
        """Update the last_updated timestamp"""
        self.last_updated = datetime.now(timezone.utc)

    def add_task(self, task: Task):
        """Add a task to the end of the list"""
        self.tasks.append(task)
        self.update_timestamp()

    def add_task_before(self, task: Task, before_uid: str):
        """Insert a task before the task with the given UID"""
        for i, existing_task in enumerate(self.tasks):
            if existing_task.uid == before_uid:
                self.tasks.insert(i, task)
                self.update_timestamp()
                return
        raise ValueError(f"Task with UID '{before_uid}' not found")

    def add_task_after(self, task: Task, after_uid: str):
        """Insert a task after the task with the given UID"""
        for i, existing_task in enumerate(self.tasks):
            if existing_task.uid == after_uid:
                self.tasks.insert(i + 1, task)
                self.update_timestamp()
                return
        raise ValueError(f"Task with UID '{after_uid}' not found")

    def remove_task(self, uid: str):
        """Remove a task by UID"""
        self.tasks = [task for task in self.tasks if task.uid != uid]
        self.update_timestamp()

    def get_task(self, uid: str) -> Task | None:
        """Get a task by UID"""
        return next((task for task in self.tasks if task.uid == uid), None)

    def update_task(self, uid: str, name: str, description: str, status: TaskStatus):
        """Update a task's properties"""
        task = self.get_task(uid)
        if task:
            task.name = name
            task.description = description
            task.status = status
            self.update_timestamp()
        else:
            raise ValueError(f"Task with UID '{uid}' not found")

    def swap_tasks(self, uid1: str, uid2: str):
        """Swap the positions of two tasks"""
        task1_index = None
        task2_index = None

        for i, task in enumerate(self.tasks):
            if task.uid == uid1:
                task1_index = i
            elif task.uid == uid2:
                task2_index = i

        if task1_index is not None and task2_index is not None:
            self.tasks[task1_index], self.tasks[task2_index] = self.tasks[task2_index], self.tasks[task1_index]
            self.update_timestamp()
        else:
            raise ValueError("One or both tasks not found")

    def get_tasks_for_rendering(self, status: list[TaskStatus] | None = None, include_logs: bool = False) -> list[dict]:
        """Get tasks formatted for display"""
        fields = {"uid", "name", "description", "status"}
        if include_logs:
            fields.add("logs")
        return [task.model_dump(mode="json", include=fields) for task in self.get_tasks(status)]

    def get_tasks(self, status: list[TaskStatus] | None = None) -> list[Task]:
        """Get tasks, optionally filtered by status"""
        if status is None:
            return self.tasks
        return [task for task in self.tasks if task.status in status]

    def get_task_in_progress(self) -> Task | None:
        """Get the task currently in progress (only one allowed)"""
        return next((task for task in self.tasks if task.status == TaskStatus.IN_PROGRESS), None)

    def set_task_status(self, uid: str, status: TaskStatus):
        """Set a task's status, ensuring only one task can be in progress"""
        task = self.get_task(uid)
        if task:
            if status == TaskStatus.IN_PROGRESS:
                # Clear any other task that's in progress
                for other_task in self.tasks:
                    if other_task.status == TaskStatus.IN_PROGRESS:
                        other_task.status = TaskStatus.PENDING

            task.status = status
            self.update_timestamp()
        else:
            raise ValueError(f"Task with UID '{uid}' not found")

    def clear_all_tasks(self):
        """Remove all tasks from the list"""
        self.tasks = []
        self.update_timestamp()
