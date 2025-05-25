from threading import RLock
import uuid
import os
from enum import Enum
from typing import ClassVar
from datetime import datetime, timezone
from python.helpers.localization import Localization

from pydantic import BaseModel, Field, PrivateAttr

from python.helpers.files import write_file, read_file, exists, get_abs_path, list_files


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskLog(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str


class Task(BaseModel):
    uid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = Field(default="")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    logs: list[TaskLog] = Field(default_factory=list)

    def add_log(self, log: TaskLog):
        self.logs.append(log)

    def get_logs(self) -> list[TaskLog]:
        return self.logs

    def get_logs_for_rendering(self) -> list[dict]:
        # the timestamp must be converted to local time via Localization class
        logs = []
        for log in self.logs:
            log_dict = log.model_dump(mode="json", include={"timestamp", "message"})
            log_dict["timestamp"] = Localization.get().utc_dt_to_localtime_str(
                datetime.fromisoformat(log_dict["timestamp"]),
                sep=" ",
                timespec="seconds",
            )
            logs.append(log_dict)
        return logs


class TaskList(BaseModel):
    uid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tasks: list[Task] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Global tasklist uid
    GLOBAL_TASKLIST_UID: ClassVar[str] = "global"

    # Singleton instances
    __instances: ClassVar[dict[str, "TaskList"]] = PrivateAttr(default=dict())
    __lock: ClassVar[RLock] = PrivateAttr(default=RLock())

    @classmethod
    def _preload_all_instances(cls) -> list["TaskList"]:
        with cls.__lock:
            for file in list_files("memory/tasklists", "*.json"):
                # extract uid from file by cutting absolute path prefix off and json suffix
                uid = file.split("/")[-1].replace(".json", "")
                cls.__instances[uid] = cls.model_validate_json(read_file(get_abs_path("memory/tasklists", f"{uid}.json")))
            return list(cls.__instances.values())

    @classmethod
    def get_instance(cls, uid: str | None = None, preload: bool = True) -> "TaskList":
        with cls.__lock:
            if preload:
                cls._preload_all_instances()
            if uid is None:
                uid = str(uuid.uuid4())
            if uid not in cls.__instances:
                path = get_abs_path("memory/tasklists", f"{uid}.json")
                if not exists(path):
                    cls.__instances[uid] = cls(uid=uid)
                    write_file(path, cls.__instances[uid].model_dump_json())
                else:
                    cls.__instances[uid] = cls.model_validate_json(read_file(path))
            return cls.__instances[uid]

    @classmethod
    def get_global_instance(cls) -> "TaskList":
        with cls.__lock:
            cls._preload_all_instances()
            return cls.get_instance(cls.GLOBAL_TASKLIST_UID)

    @classmethod
    def get_all(cls) -> dict[str, "TaskList"]:
        with cls.__lock:
            cls._preload_all_instances()
            return cls.__instances

    @classmethod
    def delete_instance(cls, uid: str, preload: bool = True):
        with cls.__lock:
            if preload:
                cls._preload_all_instances()
            path = get_abs_path("memory/tasklists", f"{uid}.json")
            if exists(path):
                os.remove(path)
            if uid in cls.__instances:
                del cls.__instances[uid]

    @classmethod
    def delete_by_prefix(cls, uid_prefix: str, preload: bool = True):
        with cls.__lock:
            if preload:
                cls._preload_all_instances()
            uids = list(cls.__instances.keys())
            for uid in uids:
                if uid.startswith(uid_prefix):
                    cls.delete_instance(uid, False)

    @classmethod
    def clear_by_prefix(cls, uid_prefix: str, preload: bool = True):
        with cls.__lock:
            if preload:
                cls._preload_all_instances()
            uids = list(cls.__instances.keys())
            for uid in uids:
                if uid.startswith(uid_prefix):
                    cls.__instances[uid].clear()

    def clear(self):
        with self.__lock:
            self.tasks = []
            self.last_updated = datetime.now(timezone.utc)
            self._save()

    def _save(self):
        with self.__lock:
            path = get_abs_path("memory/tasklists", f"{self.uid}.json")
            write_file(path, self.model_dump_json())

    def add_task(self, task: Task):
        with self.__lock:
            self.tasks.append(task)
            self.last_updated = datetime.now(timezone.utc)
            self._save()

    def add_task_before(self, task: Task, before_uid: str):
        with self.__lock:
            index = next((i for i, t in enumerate(self.tasks) if t.uid == before_uid), None)
            if index is not None:
                self.tasks.insert(index, task)
            else:
                self.tasks.insert(0, task)
            self.last_updated = datetime.now(timezone.utc)
            self._save()

    def add_task_after(self, task: Task, after_uid: str):
        with self.__lock:
            index = next((i for i, t in enumerate(self.tasks) if t.uid == after_uid), None)
            if index is not None:
                self.tasks.insert(index + 1, task)
            else:
                self.tasks.append(task)
            self.last_updated = datetime.now(timezone.utc)
            self._save()

    def get_task(self, uid: str) -> Task | None:
        with self.__lock:
            return next((task for task in self.tasks if task.uid == uid), None)

    def remove_task(self, uid: str):
        with self.__lock:
            self.tasks = [task for task in self.tasks if task.uid != uid]
            self.last_updated = datetime.now(timezone.utc)
            self._save()

    def update_task(self, uid: str, name: str, description: str, status: TaskStatus):
        with self.__lock:
            if task := self.get_task(uid):
                task.name = name
                task.description = description
                task.status = status
                self.last_updated = datetime.now(timezone.utc)
                self._save()

    def swap_tasks(self, uid1: str, uid2: str):
        with self.__lock:
            if task1 := self.get_task(uid1):
                task1_idx = self.tasks.index(task1)
                if task2 := self.get_task(uid2):
                    task2_idx = self.tasks.index(task2)
                    self.tasks[task1_idx], self.tasks[task2_idx] = self.tasks[task2_idx], self.tasks[task1_idx]
                    self.last_updated = datetime.now(timezone.utc)
                    self._save()

    def get_tasks_for_rendering(self, status: list[TaskStatus] | None = None, include_logs: bool = False) -> list[dict]:
        with self.__lock:
            fields = {"uid", "name", "description", "status"}
            if include_logs:
                fields.add("logs")
            return [task.model_dump(mode="json", include=fields) for task in self.get_tasks(status)]

    def get_tasks(self, status: list[TaskStatus] | None = None) -> list[Task]:
        with self.__lock:
            return [task for task in self.tasks if status is None or task.status in status]

    def get_task_in_progress(self) -> Task | None:
        with self.__lock:
            return next((task for task in self.tasks if task.status == TaskStatus.IN_PROGRESS), None)

    def set_task_status(self, uid: str, status: TaskStatus):
        with self.__lock:
            if status == TaskStatus.IN_PROGRESS:
                if inprogress := self.get_task_in_progress():
                    if inprogress.uid != uid:
                        raise ValueError(f"Task {inprogress.uid} is already in progress")
            if task := self.get_task(uid):
                task.status = status
                self.last_updated = datetime.now(timezone.utc)
                self._save()
            else:
                raise ValueError(f"Task {uid} not found")

    def get_task_logs(self, uid: str) -> list[TaskLog]:
        with self.__lock:
            return next((task.logs for task in self.tasks if task.uid == uid), [])

    def get_task_logs_for_rendering(self, uid: str) -> list[dict]:
        with self.__lock:
            return next((task.get_logs_for_rendering() for task in self.tasks if task.uid == uid), [])
