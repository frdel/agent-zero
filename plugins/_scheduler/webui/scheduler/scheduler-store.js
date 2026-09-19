import { createStore } from "/js/AlpineStore.js";
import { fetchApi } from "/js/api.js";
import { openModal, closeModal } from "/js/modals.js";
import {
  formatDateTime,
  getUserDateTimeParts,
  getUserTimezone,
  toUserISOString,
  toUserWallClockISOString,
} from "/js/time-utils.js";
import { store as chatsStore } from "/components/sidebar/chats/chats-store.js";
import { store as projectsStore } from "/components/projects/projects-store.js";
import { store as notificationsStore } from "/components/notifications/notification-store.js";

const VIEW_MODE_STORAGE_KEY = "scheduler_view_mode";
const NOTIFICATION_DURATION = {
  success: 3,
  info: 3,
  warning: 4,
  error: 5,
};
const DEFAULT_TASK_STATE = "idle";
const TASK_TYPES = ["scheduled", "adhoc", "planned"];

/**
 * @typedef {Object} SchedulerPlan
 * @property {string[]} todo
 * @property {string|null} in_progress
 * @property {string[]} done
 */

/**
 * @typedef {Object} SchedulerProject
 * @property {string|null} name
 * @property {string|null} title
 * @property {string} color
 */

/**
 * @typedef {Object} SchedulerTask
 * @property {string} uuid
 * @property {string} name
 * @property {string} type
 * @property {string} state
 * @property {SchedulerPlan} plan
 * @property {Object|string} schedule
 * @property {string} token
 * @property {SchedulerProject|null} project
 * @property {string|null} project_name
 * @property {string} [project_color]
 * @property {string[]} attachments
 * @property {string} [system_prompt]
 * @property {string} [prompt]
 * @property {string} [created_at]
 * @property {string} [updated_at]
 * @property {string} [last_run]
 * @property {string} [last_result]
 */

/**
 * @typedef {Object} EditingTask
 * @property {string} [uuid]
 * @property {string} name
 * @property {string} type
 * @property {string} state
 * @property {SchedulerPlan} plan
 * @property {ReturnType<typeof defaultSchedule>} schedule
 * @property {string} token
 * @property {SchedulerProject|null} project
 * @property {boolean} dedicated_context
 * @property {string[]} attachments
 * @property {string} system_prompt
 * @property {string} prompt
 */

/**
 * @template T
 * @typedef {Object} SchedulerApiResult
 * @property {boolean} ok
 * @property {string} [error]
 * @property {T} [data]
 */

// -----------------------------------------------------------------------------
// Pure helpers
// -----------------------------------------------------------------------------

const defaultSchedule = () => ({
  minute: "*",
  hour: "*",
  day: "*",
  month: "*",
  weekday: "*",
  timezone: getUserTimezone(),
});

const emptyPlan = () => ({
  todo: [],
  in_progress: null,
  done: [],
});

const defaultEditingTask = (overrides = {}) => ({
  name: "",
  type: "scheduled",
  state: DEFAULT_TASK_STATE,
  schedule: defaultSchedule(),
  token: "",
  plan: emptyPlan(),
  system_prompt: "",
  prompt: "",
  attachments: [],
  project: null,
  dedicated_context: true,
  ...overrides,
});

const readPersistedViewMode = () => {
  if (typeof window === "undefined") return "list";
  return window.localStorage?.getItem(VIEW_MODE_STORAGE_KEY) || "list";
};

const sleep = (ms = 0) =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

function safeJsonClone(value) {
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return value;
  }
}

function normalizeAttachments(value) {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value.filter((item) => typeof item === "string" && item.trim().length > 0);
  }
  if (typeof value === "string") {
    return value
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
  }
  return [];
}

function normalizeSchedule(schedule) {
  if (!schedule) return defaultSchedule();
  if (typeof schedule === "string") {
    const [minute = "*", hour = "*", day = "*", month = "*", weekday = "*"] = schedule
      .split(" ")
      .map((segment) => segment || "*");
    return {
      minute,
      hour,
      day,
      month,
      weekday,
      timezone: getUserTimezone(),
    };
  }
  return {
    minute: schedule.minute || "*",
    hour: schedule.hour || "*",
    day: schedule.day || "*",
    month: schedule.month || "*",
    weekday: schedule.weekday || "*",
    timezone: schedule.timezone || getUserTimezone(),
  };
}

function normalizePlanStruct(plan) {
  if (!plan) return emptyPlan();
  const clone = {
    todo: Array.isArray(plan.todo) ? [...plan.todo] : [],
    in_progress: plan.in_progress || null,
    done: Array.isArray(plan.done) ? [...plan.done] : [],
  };
  const sanitized = clone.todo
    .map((value) => new Date(value))
    .filter((date) => !Number.isNaN(date.getTime()))
    .map((date) => toUserISOString(date))
    .sort();
  clone.todo = sanitized;
  clone.done = clone.done
    .map((value) => new Date(value))
    .filter((date) => !Number.isNaN(date.getTime()))
    .map((date) => toUserISOString(date));
  if (clone.in_progress) {
    const inProgress = new Date(clone.in_progress);
    clone.in_progress = Number.isNaN(inProgress.getTime())
      ? null
      : toUserISOString(inProgress);
  }
  return clone;
}

function ensureTaskValidity(task) {
  return Boolean(task && task.uuid && task.name && task.type);
}

function extractProjectInfo(task) {
  if (!task) return null;
  const slug = task.project_name || task.project?.name || null;
  const title = task.project?.title || task.project?.name || slug;
  const color = task.project_color || task.project?.color || "";
  if (!slug && !title) return null;
  return {
    name: slug,
    title: title || slug,
    color: color || "",
  };
}

function composeEditingTask(task = {}) {
  const base = task && task.uuid ? { ...task } : { ...defaultEditingTask(), ...task };
  return {
    ...base,
    schedule: normalizeSchedule(base.schedule),
    plan: normalizePlanStruct(base.plan),
    attachments: normalizeAttachments(base.attachments),
    token: base.token || "",
    project: base.project || extractProjectInfo(base) || null,
    dedicated_context:
      typeof base.dedicated_context === "boolean" ? base.dedicated_context : true,
    state: base.state || DEFAULT_TASK_STATE,
  };
}

function normalizeTaskFromBackend(task) {
  if (!ensureTaskValidity(task)) return null;
  return composeEditingTask(task);
}

function buildPayloadFromEditingTask(editingTask, { isCreating = false } = {}) {
  const payload = {
    name: editingTask.name.trim(),
    system_prompt: editingTask.system_prompt || "",
    prompt: editingTask.prompt || "",
    state: editingTask.state || DEFAULT_TASK_STATE,
    timezone: getUserTimezone(),
    attachments: normalizeAttachments(editingTask.attachments),
    dedicated_context: editingTask.dedicated_context,
  };

  if (editingTask.type === "scheduled") {
    payload.schedule = normalizeSchedule(editingTask.schedule);
  }

  if (editingTask.type === "planned") {
    payload.plan = normalizePlanStruct(editingTask.plan);
  }

  if (editingTask.type === "adhoc") {
    payload.token = editingTask.token;
  }

  // Only send project fields when creating a new task (project changes are not allowed for existing tasks)
  if (isCreating && editingTask.project && editingTask.project.name) {
    payload.project_name = editingTask.project.name;
    if (editingTask.project.color) {
      payload.project_color = editingTask.project.color;
    }
  }

  if (!isCreating && editingTask.uuid) {
    payload.task_id = editingTask.uuid;
  }

  return payload;
}

async function callSchedulerEndpoint(endpoint, payload = {}, defaultError) {
  try {
    const response = await fetchApi(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data?.error) {
      return { ok: false, error: data?.error || defaultError || "Task request failed" };
    }
    return { ok: true, data };
  } catch (error) {
    return { ok: false, error: error?.message || defaultError || "Task request failed" };
  }
}

const schedulerApi = {
  async listTasks() {
    const result = await callSchedulerEndpoint(
      "/plugins/_scheduler/scheduler_tasks_list",
      { timezone: getUserTimezone() },
      "Failed to fetch tasks"
    );
    if (!result.ok) return { ok: false, error: result.error };
    const rawTasks = Array.isArray(result.data?.tasks) ? result.data.tasks : [];
    const normalized = rawTasks
      .filter(ensureTaskValidity)
      .map((task) => normalizeTaskFromBackend(task))
      .filter(Boolean);
    return { ok: true, tasks: normalized };
  },

  async createTask(payload) {
    const result = await callSchedulerEndpoint(
      "/plugins/_scheduler/scheduler_task_create",
      payload,
      "Failed to create task"
    );
    if (!result.ok) return { ok: false, error: result.error };
    const task = result.data?.task ? normalizeTaskFromBackend(result.data.task) : null;
    return { ok: true, task };
  },

  async updateTask(payload) {
    const result = await callSchedulerEndpoint(
      "/plugins/_scheduler/scheduler_task_update",
      payload,
      "Failed to update task"
    );
    if (!result.ok) return { ok: false, error: result.error };
    const task = result.data?.task ? normalizeTaskFromBackend(result.data.task) : null;
    return { ok: true, task };
  },

  async runTask(taskId) {
    return callSchedulerEndpoint(
      "/plugins/_scheduler/scheduler_task_run",
      { task_id: taskId, timezone: getUserTimezone() },
      "Failed to run task"
    );
  },

  async deleteTask(taskId) {
    return callSchedulerEndpoint(
      "/plugins/_scheduler/scheduler_task_delete",
      { task_id: taskId, timezone: getUserTimezone() },
      "Failed to delete task"
    );
  },
};

const notificationChannels = {
  success: "frontendSuccess",
  info: "frontendInfo",
  warning: "frontendWarning",
  error: "frontendError",
};

function pushNotification(type, message, title = "Tasks", duration) {
  const channel = notificationChannels[type];
  if (!channel || typeof notificationsStore[channel] !== "function") return;
  const ttl = duration ?? NOTIFICATION_DURATION[type] ?? 4;
  notificationsStore[channel](message, title, ttl);
}

function destroyPlannerInput(inputId) {
  const input = typeof document !== "undefined" ? document.getElementById(inputId) : null;
  if (!input || !input._flatpickr) return;
  input._flatpickr.destroy();
  const wrapper = input.closest(".scheduler-flatpickr-wrapper");
  if (wrapper && wrapper.parentNode) {
    wrapper.parentNode.insertBefore(input, wrapper);
    wrapper.parentNode.removeChild(wrapper);
  }
  input.classList.remove("scheduler-flatpickr-input");
}

function setupPlannerInput(inputId) {
  if (typeof flatpickr === "undefined") {
    return null;
  }
  const input = document.getElementById(inputId);
  if (!input) return null;

  destroyPlannerInput(inputId);

  const wrapper = document.createElement("div");
  wrapper.className = "scheduler-flatpickr-wrapper";
  wrapper.style.overflow = "visible";
  input.parentNode.insertBefore(wrapper, input);
  wrapper.appendChild(input);
  input.classList.add("scheduler-flatpickr-input");

  const nowParts = getUserDateTimeParts();
  const roundedMinute = Math.ceil(nowParts.minute / 5) * 5;
  const options = {
    dateFormat: "Y-m-d H:i",
    enableTime: true,
    time_24hr: true,
    static: false,
    appendTo: document.body,
    allowInput: true,
    positionElement: wrapper,
    theme: "scheduler-theme",
    minuteIncrement: 5,
    defaultHour: roundedMinute >= 60 ? (nowParts.hour + 1) % 24 : nowParts.hour,
    defaultMinute: roundedMinute % 60,
    onOpen(selectedDates, dateStr, instance) {
      instance.calendarContainer.style.zIndex = "9999";
      instance.calendarContainer.style.position = "absolute";
      instance.calendarContainer.style.visibility = "visible";
      instance.calendarContainer.style.opacity = "1";
      instance.calendarContainer.classList.add("scheduler-theme");
    },
    onReady(selectedDates, dateStr, instance) {
      if (!dateStr) {
        const now = new Date();
        now.setMinutes(now.getMinutes() + 30);
        instance.setDate(now, true);
      }
    },
  };

  const picker = flatpickr(input, options);
  const clearButton = document.createElement("button");
  clearButton.className = "scheduler-flatpickr-clear";
  clearButton.innerHTML = "×";
  clearButton.type = "button";
  clearButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (picker) picker.clear();
  });
  wrapper.appendChild(clearButton);

  return picker;
}

function readDateFromPlannerInput(input) {
  if (!input) return null;
  if (input._flatpickr && input._flatpickr.selectedDates.length > 0) {
    return input._flatpickr.selectedDates[0];
  }
  if (input.value) {
    const date = new Date(input.value);
    if (!Number.isNaN(date.getTime())) {
      return date;
    }
  }
  return null;
}

function sortByDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

// -----------------------------------------------------------------------------
// Store definition
// -----------------------------------------------------------------------------

const schedulerStoreModel = {
  // Core collection state -----------------------------------------------------
  tasks: [],
  isLoading: false,
  showLoadingState: false,
  hasNoTasks: true,

  // Filtering & view ---------------------------------------------------------
  filterType: "all",
  filterState: "all",
  sortField: "name",
  sortDirection: "asc",
  viewMode: readPersistedViewMode(),
  selectedTaskForDetail: null,

  // Pagination ---------------------------------------------------------------
  currentPage: 1,
  pageSize: 10,

  // Editor state -------------------------------------------------------------
  isCreating: false,
  isEditing: false,
  editingTask: defaultEditingTask(),
  promptField: "prompt",
  selectedProjectSlug: "",
  projectOptions: [],

  // Polling ------------------------------------------------------------------
  pollingInterval: null,
  pollingActive: false,

  // Computed -----------------------------------------------------------------
  get filteredTasks() {
    if (!Array.isArray(this.tasks)) return [];
    let filtered = [...this.tasks];

    if (this.filterType && this.filterType !== "all") {
      filtered = filtered.filter((task) =>
        task.type ? task.type.toLowerCase() === this.filterType.toLowerCase() : false
      );
    }

    if (this.filterState && this.filterState !== "all") {
      filtered = filtered.filter((task) =>
        task.state ? task.state.toLowerCase() === this.filterState.toLowerCase() : false
      );
    }

    return this.sortTasks(filtered);
  },

  get totalPages() {
    if (!Array.isArray(this.filteredTasks) || this.filteredTasks.length === 0) return 1;
    return Math.ceil(this.filteredTasks.length / this.pageSize);
  },

  get paginatedTasks() {
    if (!Array.isArray(this.filteredTasks)) return [];
    // Ensure currentPage is within valid range
    const maxPage = this.totalPages;
    if (this.currentPage > maxPage) {
      this.currentPage = Math.max(1, maxPage);
    }
    const start = (this.currentPage - 1) * this.pageSize;
    const end = start + this.pageSize;
    return this.filteredTasks.slice(start, end);
  },

  get attachmentsText() {
    const attachments = Array.isArray(this.editingTask.attachments)
      ? this.editingTask.attachments
      : [];
    return attachments.join("\n");
  },

  set attachmentsText(value) {
    if (typeof value === "string") {
      this.editingTask.attachments = value.split("\n");
    } else {
      this.editingTask.attachments = [];
    }
  },

  // Lifecycle ----------------------------------------------------------------
  init() {
    this.resetEditingTask();
    this.refreshProjectOptions();
  },

  persistViewMode(mode) {
    this.viewMode = mode;
    try {
      window.localStorage?.setItem(VIEW_MODE_STORAGE_KEY, mode);
    } catch {
      /* ignore storage failures */
    }
  },

  setViewMode(mode) {
    this.persistViewMode(mode);
  },

  onTabActivated() {
    this.pollingActive = true;
    this.startPolling();
  },

  onTabDeactivated() {
    this.stopPolling();
  },

  async onModalClosed() {
    this.stopPolling();
    this.destroyFlatpickr("all");
    this.isCreating = false;
    this.isEditing = false;
    this.resetEditingTask();
    this.selectedTaskForDetail = null;
    this.persistViewMode("list");
  },

  startPolling() {
    if (this.pollingInterval) return;
    this.fetchTasks();
    this.pollingInterval = setInterval(() => {
      if (this.pollingActive) {
        this.fetchTasks();
      }
    }, 2000);
  },

  stopPolling() {
    this.pollingActive = false;
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  },

  // Data fetching -------------------------------------------------------------
  async fetchTasks({ manual = false } = {}) {
    if (this.isCreating || this.isEditing) return;
    if (manual) this.isLoading = true;

    try {
      const { ok, error, tasks } = await schedulerApi.listTasks();
      if (!ok) {
        if (manual) this.notifyError(`Failed to fetch tasks: ${error}`);
        this.tasks = [];
        this.hasNoTasks = true;
        return;
      }

      // Smart merge: preserve object references to prevent UI flickering
      const taskMap = new Map(this.tasks.map((t) => [t.uuid, t]));
      this.tasks = tasks.map((newTask) => {
        const existing = taskMap.get(newTask.uuid);
        if (existing) {
          // Update existing object in-place if different
          if (JSON.stringify(existing) !== JSON.stringify(newTask)) {
            Object.assign(existing, newTask);
          }
          return existing; // Return the SAME object reference
        }
        return newTask; // New object
      });

      this.hasNoTasks = this.tasks.length === 0;
    } catch (error) {
      if (manual) this.notifyError(`Failed to fetch tasks: ${error.message}`);
      this.tasks = [];
      this.hasNoTasks = true;
    } finally {
      this.isLoading = false;
    }
  },

  async saveTask() {
    if (!this.editingTask.name?.trim() || !this.editingTask.prompt?.trim()) {
      window.alert("Task name and prompt are required");
      return;
    }

    if (!TASK_TYPES.includes(this.editingTask.type)) {
      window.alert("Invalid task type");
      return;
    }

    if (this.editingTask.type === "adhoc" && !this.editingTask.token) {
      this.editingTask.token = this.generateRandomToken();
    }

    const payload = buildPayloadFromEditingTask(this.editingTask, {
      isCreating: this.isCreating,
    });

    try {
      const result = this.isCreating
        ? await schedulerApi.createTask(payload)
        : await schedulerApi.updateTask(payload);

      if (!result.ok) {
        throw new Error(result.error);
      }

      const message = this.isCreating
        ? "Task created successfully"
        : "Task updated successfully";
      this.notifySuccess(message);

      if (result.task) {
        if (this.isCreating) {
          this.tasks = [...this.tasks, result.task];
        } else {
          this.tasks = this.tasks.map((task) =>
            task.uuid === result.task.uuid ? result.task : task
          );
        }
      } else {
        await this.fetchTasks({ manual: true });
      }
    } catch (error) {
      this.notifyError(`Failed to save task: ${error.message}`);
      return;
    }
    this.cancelEdit();
  },

  async runTask(taskId) {
    try {
      const result = await schedulerApi.runTask(taskId);
      if (!result.ok) throw new Error(result.error);
      const warning = result.data?.warning;
      const message = result.data?.message || "Task started successfully";
      if (warning) {
        this.notifyWarning(warning);
      } else {
        this.notifySuccess(message);
      }
      this.fetchTasks({ manual: true });
    } catch (error) {
      this.notifyError(`Failed to run task: ${error.message}`);
    }
  },

  async resetTaskState(taskId) {
    const task = this.tasks.find((t) => t.uuid === taskId);
    if (!task) {
      this.notifyError("Task not found");
      return;
    }
    if (task.state === "idle") {
      this.notifyInfo("Task is already in idle state");
      return;
    }

    this.showLoadingState = true;
    try {
      const result = await schedulerApi.updateTask({ task_id: taskId, state: "idle" });
      if (!result.ok) throw new Error(result.error);
      this.notifySuccess("Task state reset to idle");
      await this.fetchTasks({ manual: true });
    } catch (error) {
      this.notifyError(`Failed to reset task state: ${error.message}`);
    } finally {
      this.showLoadingState = false;
    }
  },

  async deleteTask(taskId) {
    try {
      if (typeof chatsStore.switchFromContext === "function") {
        await chatsStore.switchFromContext(taskId);
      }
    } catch (error) {
      console.warn("[scheduler] Failed to switch from context before delete", error);
    }

    try {
      const result = await schedulerApi.deleteTask(taskId);
      if (!result.ok) throw new Error(result.error);
      this.notifySuccess("Task deleted successfully");
      this.tasks = this.tasks.filter((task) => task.uuid !== taskId);
      this.hasNoTasks = this.tasks.length === 0;
      if (this.selectedTaskForDetail?.uuid === taskId) {
        this.closeTaskDetail();
      }
    } catch (error) {
      this.notifyError(`Failed to delete task: ${error.message}`);
    }
  },

  async deleteTaskFromSidebar(taskId) {
    await this.deleteTask(taskId);
  },

  // Domain helpers -----------------------------------------------------------
  openPromptEditor(field) {
    if (!["system_prompt", "prompt"].includes(field)) return;
    this.promptField = field;
    return openModal("/plugins/_scheduler/webui/scheduler/scheduler-prompt-editor.html");
  },

  closePromptEditor() {
    return closeModal("/plugins/_scheduler/webui/scheduler/scheduler-prompt-editor.html");
  },

  resetEditingTask() {
    this.editingTask = defaultEditingTask();
    this.promptField = "prompt";
    this.selectedProjectSlug = "";
  },

  setEditingTask(task) {
    const normalized = composeEditingTask(task);
    this.editingTask = normalized;
    this.selectedProjectSlug = normalized.project?.name || "";
  },

  async refreshProjectOptions() {
    try {
      if (
        !Array.isArray(projectsStore.projectList) ||
        projectsStore.projectList.length === 0
      ) {
        if (typeof projectsStore.loadProjectsList === "function") {
          await projectsStore.loadProjectsList();
        }
      }
    } catch (error) {
      console.warn("[scheduler] Failed to load project list", error);
    }

    const list = Array.isArray(projectsStore.projectList)
      ? projectsStore.projectList
      : [];

    this.projectOptions = list.map((proj) => ({
      name: proj.name,
      title: proj.title || proj.name,
      color: proj.color || "",
    }));
  },

  deriveActiveProject() {
    const selected = chatsStore?.selectedContext || null;
    if (!selected || !selected.project) return null;
    const project = selected.project;
    return {
      name: project.name || null,
      title: project.title || project.name || null,
      color: project.color || "",
    };
  },

  onProjectSelect(slug) {
    this.selectedProjectSlug = slug || "";
    if (!slug) {
      this.editingTask.project = null;
      return;
    }

    const option = this.projectOptions.find((item) => item.name === slug);
    if (option) {
      this.editingTask.project = { ...option };
    } else {
      this.editingTask.project = { name: slug, title: slug, color: "" };
    }
  },

  changeSort(field) {
    if (this.sortField === field) {
      this.sortDirection = this.sortDirection === "asc" ? "desc" : "asc";
    } else {
      this.sortField = field;
      this.sortDirection = "asc";
    }
    // Reset to first page when sorting changes
    this.currentPage = 1;
  },

  // Pagination methods --------------------------------------------------------
  nextPage() {
    if (this.currentPage < this.totalPages) {
      this.currentPage++;
    }
  },

  prevPage() {
    if (this.currentPage > 1) {
      this.currentPage--;
    }
  },

  goToPage(page) {
    const pageNum = parseInt(page, 10);
    if (Number.isNaN(pageNum)) return;
    if (pageNum < 1) {
      this.currentPage = 1;
    } else if (pageNum > this.totalPages) {
      this.currentPage = this.totalPages;
    } else {
      this.currentPage = pageNum;
    }
  },

  sortTasks(tasks) {
    if (!Array.isArray(tasks) || tasks.length === 0) return tasks;
    const direction = this.sortDirection === "asc" ? 1 : -1;
    const field = this.sortField;
    return [...tasks].sort((a, b) => {
      const fieldA = a[field];
      const fieldB = b[field];
      if (fieldA === undefined && fieldB === undefined) return 0;
      if (fieldA === undefined) return 1;
      if (fieldB === undefined) return -1;
      if (["createdAt", "updatedAt", "last_run"].includes(field)) {
        return (sortByDate(fieldA) - sortByDate(fieldB)) * direction;
      }
      if (typeof fieldA === "string" && typeof fieldB === "string") {
        return fieldA.localeCompare(fieldB) * direction;
      }
      return (fieldA - fieldB) * direction;
    });
  },

  formatDate(dateString) {
    if (!dateString) return "Never";
    return formatDateTime(dateString, "full");
  },

  formatPlan(task) {
    if (!task || !task.plan) return "No plan";
    const todoCount = Array.isArray(task.plan.todo) ? task.plan.todo.length : 0;
    const inProgress = task.plan.in_progress ? "Yes" : "No";
    const doneCount = Array.isArray(task.plan.done) ? task.plan.done.length : 0;
    let nextRun = "";
    if (Array.isArray(task.plan.todo) && task.plan.todo.length > 0) {
      const nextTime = new Date(task.plan.todo[0]);
      nextRun = Number.isNaN(nextTime.getTime())
        ? "Invalid date"
        : formatDateTime(nextTime, "short");
    } else {
      nextRun = "None";
    }
    return `Next: ${nextRun}\nTodo: ${todoCount}\nIn Progress: ${inProgress}\nDone: ${doneCount}`;
  },

  formatSchedule(task) {
    if (!task.schedule) return "None";
    if (typeof task.schedule === "string") return task.schedule;
    return `${task.schedule.minute || "*"} ${task.schedule.hour || "*"} ${
      task.schedule.day || "*"
    } ${task.schedule.month || "*"} ${task.schedule.weekday || "*"}`;
  },

  formatTaskType(type) {
    const typeMap = {
      scheduled: "Scheduled",
      adhoc: "Ad-hoc",
      planned: "Planned",
    };
    return typeMap[type] || type;
  },

  getStateBadgeClass(state) {
    switch (state) {
      case "idle":
        return "scheduler-status-idle";
      case "running":
        return "scheduler-status-running";
      case "disabled":
        return "scheduler-status-disabled";
      case "error":
        return "scheduler-status-error";
      default:
        return "";
    }
  },

  extractTaskProject(task) {
    return extractProjectInfo(task);
  },

  formatProjectName(project) {
    if (!project) return "No Project";
    return project.title || project.name || "No Project";
  },

  formatProjectLabel(project) {
    return `Project: ${this.formatProjectName(project)}`;
  },

  formatTaskProject(task) {
    return this.formatProjectName(this.extractTaskProject(task));
  },

  syncTasksFromSidebar(sidebarTasks) {
    // Sync scheduler store with sidebar's poll data for instant access
    if (!Array.isArray(sidebarTasks) || sidebarTasks.length === 0) return;
    
    // Smart merge: preserve object references to prevent UI flickering
    const taskMap = new Map(this.tasks.map((t) => [t.uuid, t]));
    this.tasks = sidebarTasks.map((sidebarTask) => {
      const taskId = sidebarTask.uuid || sidebarTask.id;
      const existing = taskMap.get(taskId);
      if (existing) {
        // Update existing object in-place if different
        if (JSON.stringify(existing) !== JSON.stringify(sidebarTask)) {
          Object.assign(existing, sidebarTask);
        }
        return existing;
      }
      return sidebarTask;
    });
    this.hasNoTasks = this.tasks.length === 0;
  },

  showTaskDetail(taskId) {
    // Sync with sidebar data if our array is empty (e.g., on page load before modal opened)
    if (this.tasks.length === 0) {
      const tasksStore = globalThis.Alpine?.store?.('tasks');
      if (tasksStore?.tasks?.length > 0) {
        this.syncTasksFromSidebar(tasksStore.tasks);
      }
    }
    
    const task = this.tasks.find((t) => t.uuid === taskId);
    if (!task) {
      this.notifyError("Task not found");
      return;
    }

    const snapshot = safeJsonClone(task);
    if (!snapshot.attachments) {
      snapshot.attachments = [];
    }

    this.selectedTaskForDetail = snapshot;
    const closePromise = window.openModal("/plugins/_scheduler/webui/scheduler/scheduler-task-detail.html");
    if (closePromise && typeof closePromise.then === "function") {
      closePromise.then(() => {
        if (this.selectedTaskForDetail?.uuid === snapshot.uuid) {
          this.selectedTaskForDetail = null;
        }
      });
    }
  },

  closeTaskDetail() {
    this.selectedTaskForDetail = null;
    window.closeModal();
  },

  async editFromDetail() {
    const taskId = this.selectedTaskForDetail?.uuid;
    if (!taskId) return;
    this.closeTaskDetail();
    await this.startEditTask(taskId);
    // Open main scheduler modal to show the editor
    window.openModal("/plugins/_scheduler/webui/scheduler/scheduler-modal.html");
  },

  async deleteFromDetail() {
    const taskId = this.selectedTaskForDetail?.uuid;
    if (!taskId) return;
    await this.deleteTask(taskId);
  },

  async startCreateTask() {
    this.isCreating = true;
    this.isEditing = false;
    await this.refreshProjectOptions();

    const initialProject = this.deriveActiveProject();

    this.editingTask = defaultEditingTask({
      token: this.generateRandomToken(),
      project: initialProject,
    });
    this.selectedProjectSlug = initialProject?.name || "";
    setTimeout(() => this.initFlatpickr("create"), 100);
  },

  async startEditTask(taskId) {
    const task = this.tasks.find((t) => t.uuid === taskId);
    if (!task) {
      this.notifyError("Task not found");
      return;
    }

    this.isCreating = false;
    this.isEditing = true;
    this.setEditingTask(safeJsonClone(task));
    setTimeout(() => this.initFlatpickr("edit"), 100);
  },

  cancelEdit() {
    this.destroyFlatpickr("all");
    this.resetEditingTask();
    this.selectedProjectSlug = "";
    this.isCreating = false;
    this.isEditing = false;
  },

  normalizePlan() {
    this.editingTask.plan = normalizePlanStruct(this.editingTask.plan);
  },

  addPlannedTime(mode = "create") {
    if (!this.editingTask.plan) {
      this.editingTask.plan = emptyPlan();
    }
    if (!Array.isArray(this.editingTask.plan.todo)) {
      this.editingTask.plan.todo = [];
    }

    const inputId = mode === "edit" ? "newPlannedTime-edit" : "newPlannedTime-create";
    const input = document.getElementById(inputId);
    if (!input) {
      console.warn("[scheduler] Input element not found for planned time", inputId);
      return;
    }

    const selectedDate = readDateFromPlannerInput(input);
    if (!selectedDate) {
      window.alert("Please select a valid date and time");
      return;
    }

    this.editingTask.plan.todo.push(toUserWallClockISOString(selectedDate));
    this.editingTask.plan.todo.sort();

    if (input._flatpickr) {
      input._flatpickr.clear();
    } else {
      input.value = "";
    }
  },

  generateRandomToken() {
    const characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    let token = "";
    for (let i = 0; i < 16; i++) {
      token += characters.charAt(Math.floor(Math.random() * characters.length));
    }
    return token;
  },

  // UI bridge helpers --------------------------------------------------------
  initFlatpickr(mode = "all") {
    if (mode === "all" || mode === "create") {
      setupPlannerInput("newPlannedTime-create");
    }
    if (mode === "all" || mode === "edit") {
      setupPlannerInput("newPlannedTime-edit");
    }
  },

  destroyFlatpickr(mode = "all") {
    if (mode === "all" || mode === "create") {
      destroyPlannerInput("newPlannedTime-create");
    }
    if (mode === "all" || mode === "edit") {
      destroyPlannerInput("newPlannedTime-edit");
    }
  },

  // Notifications ------------------------------------------------------------
  notifySuccess(message, options = {}) {
    pushNotification("success", message, options.title, options.duration);
  },

  notifyInfo(message, options = {}) {
    pushNotification("info", message, options.title, options.duration);
  },

  notifyWarning(message, options = {}) {
    pushNotification("warning", message, options.title, options.duration);
  },

  notifyError(message, options = {}) {
    pushNotification("error", message, options.title, options.duration);
  },
};

const store = createStore("schedulerStore", schedulerStoreModel);

export { store };
