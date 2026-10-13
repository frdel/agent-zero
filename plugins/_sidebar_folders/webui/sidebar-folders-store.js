import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { toastFrontendError } from "/components/notifications/notification-store.js";
import { store as sidebar } from "/components/sidebar/sidebar-store.js";
import { store as chats } from "/components/sidebar/chats/chats-store.js";
import { store as tasks } from "/components/sidebar/tasks/tasks-store.js";
import { store as projects } from "/components/projects/projects-store.js";
import { store as pins } from "/plugins/_pin_to_top/webui/pin-to-top-store.js";

const PLUGIN = "_sidebar_folders";
const SORTS = ["recent", "created", "name", "manual"];
let menuExitTimer = null;

function timestamp(value) {
  return typeof value === "number" ? value : Date.parse(value || "") || 0;
}

export const store = createStore("sidebarFolders", {
  config: { folder_view: true, sort_by: "created", project_filter: "*", status_filter: "all", activity_filter: "all" },
  order: { project: [], chat: [], task: [] },
  collapsed: {},
  lastSelection: {},
  menu: "",
  menuProject: "",
  menuStyle: {},
  menuTrigger: null,
  drag: null,
  dropTarget: null,
  busy: false,
  _initialized: false,

  async init() {
    if (this._initialized) return;
    this._initialized = true;
    try {
      const saved = JSON.parse(localStorage.getItem("sidebarFoldersCollapsed") || "{}");
      if (saved && typeof saved === "object" && !Array.isArray(saved)) this.collapsed = saved;
    } catch (error) {
      console.error("Could not restore sidebar folders", error);
    }
    window.addEventListener("focus", () => this.refresh());
    await this.refresh();
  },

  mountList(kind) {
    sidebar.registerRowListExtension(kind, PLUGIN, {
      hasView: () => this.config.folder_view,
      sort: (rows) => this.sortRows(kind, rows),
    });
  },

  unmountList(kind) {
    sidebar.unregisterRowListExtension(kind, PLUGIN);
  },

  async refresh() {
    await Promise.all([this.loadConfig(), this.loadOrder(), projects.loadProjectsList()]);
  },

  async loadConfig() {
    try {
      const result = await callJsonApi("plugins", { action: "get_config", plugin_name: PLUGIN });
      if (!result.ok) throw new Error(result.error || "Could not load folder settings");
      const config = {
        folder_view: result.data?.folder_view !== false,
        sort_by: SORTS.includes(result.data?.sort_by) ? result.data.sort_by : "created",
        project_filter: typeof result.data?.project_filter === "string" ? result.data.project_filter : "*",
        status_filter: ["all", "running", "idle"].includes(result.data?.status_filter) ? result.data.status_filter : "all",
        activity_filter: ["all", "1", "3", "7", "30"].includes(result.data?.activity_filter) ? result.data.activity_filter : "all",
      };
      if (JSON.stringify(config) !== JSON.stringify(this.config)) this.config = config;
    } catch (error) {
      this.report(error, true);
    }
  },

  async loadOrder() {
    try {
      const result = await callJsonApi(`/plugins/${PLUGIN}/layout`, {});
      if (JSON.stringify(result.order) !== JSON.stringify(this.order)) this.order = result.order;
    } catch (error) {
      this.report(error, true);
    }
  },

  async setConfig(change) {
    if (this.busy) return;
    this.busy = true;
    try {
      const config = { ...this.config, ...change };
      const result = await callJsonApi("plugins", {
        action: "save_config", plugin_name: PLUGIN, settings: config,
      });
      if (!result.ok) throw new Error(result.error || "Could not save folder settings");
      this.config = config;
      if ("folder_view" in change || "sort_by" in change) this.closeMenu();
    } catch (error) {
      this.report(error);
    } finally {
      this.busy = false;
    }
  },

  roots(kind) {
    return kind === "chat" ? chats.topLevelContexts() : tasks.visibleTasks();
  },

  rootChat(id) {
    let row = chats.contexts.find((item) => item.id === id);
    const seen = new Set();
    while (row?.parent_context_id && !seen.has(row.id)) {
      seen.add(row.id);
      const parent = chats.contexts.find((item) => item.id === row.parent_context_id);
      if (!parent) break;
      row = parent;
    }
    return row;
  },

  childIndex() {
    const children = new Map();
    for (const context of chats.contexts) {
      if (!context.parent_context_id) continue;
      if (!children.has(context.parent_context_id)) children.set(context.parent_context_id, []);
      children.get(context.parent_context_id).push(context);
    }
    return children;
  },

  family(row, kind, children = null) {
    if (kind !== "chat") return [row];
    children ??= this.childIndex();
    const family = [row];
    const seen = new Set([row.id]);
    for (const parent of family) {
      for (const child of children.get(parent.id) || []) {
        if (!seen.has(child.id)) {
          seen.add(child.id);
          family.push(child);
        }
      }
    }
    return family;
  },

  matches(row, kind, children) {
    if (this.config.project_filter !== "*" && (row.project?.name || "") !== this.config.project_filter) return false;
    if (this.config.status_filter === "all" && this.config.activity_filter === "all") return true;
    const family = this.family(row, kind, children);
    const working = family.some((item) => item.running && !item.paused && item.state !== "disabled");
    if (this.config.status_filter === "running" && !working) return false;
    if (this.config.status_filter === "idle" && working) return false;
    return family.some((item) => {
      if (this.config.activity_filter !== "all") {
        const cutoff = Date.now() - Number(this.config.activity_filter) * 86400000;
        if (timestamp(item.last_message || item.created_at) < cutoff) return false;
      }
      return true;
    });
  },

  sortRows(kind, rows) {
    const children = kind === "chat" && (this.config.status_filter !== "all" || this.config.activity_filter !== "all")
      ? this.childIndex() : null;
    const rank = new Map(this.order[kind].map((id, index) => [id, index]));
    return rows.filter((row) => row.parent_context_id || this.matches(row, kind, children)).sort((a, b) => {
      const pinned = Number(pins.isPinned(kind, b.id)) - Number(pins.isPinned(kind, a.id));
      if (pinned) return pinned;
      if (this.config.sort_by === "manual") {
        return (rank.get(a.id) ?? Infinity) - (rank.get(b.id) ?? Infinity) || 0;
      }
      if (this.config.sort_by === "name") {
        return (a.task_name || chats.displayName(a)).localeCompare(b.task_name || chats.displayName(b));
      }
      const field = this.config.sort_by === "created" ? "created_at" : "last_message";
      return timestamp(b[field] || b.created_at) - timestamp(a[field] || a.created_at);
    });
  },

  isPinnedRow(kind, row, children) {
    return this.family(row, kind, children).some((member) => pins.isPinned(kind, member.id));
  },

  pinnedRows(kind, roots = this.roots(kind), children = kind === "chat" ? this.childIndex() : null) {
    const rows = roots.filter((row) => this.isPinnedRow(kind, row, children));
    if (this.config.sort_by !== "manual") return pins.sortItems(kind, rows);
    const rank = new Map(this.order[kind].map((id, index) => [id, index]));
    return rows.sort((a, b) => (rank.get(a.id) ?? Infinity) - (rank.get(b.id) ?? Infinity) || 0);
  },

  sections(kind, previous) {
    const rows = this.roots(kind);
    const children = kind === "chat" ? this.childIndex() : null;
    const pinned = this.pinnedRows(kind, rows, children);
    const folders = this.groups(kind, rows, children);
    const sections = pinned.length ? [{ id: null, pinned: true, rows: pinned }, ...folders] : folders;
    if (previous?.length === sections.length && sections.every((group, index) => {
      const current = previous[index];
      return ["id", "pinned", "title", "color", "hasPinned"].every((key) => group[key] === current[key])
        && group.rows.length === current.rows.length
        && group.rows.every((row, rowIndex) => row === current.rows[rowIndex]);
    })) return previous;
    return sections;
  },

  groups(kind, rows = this.roots(kind), children = kind === "chat" ? this.childIndex() : null) {
    const groups = new Map(projects.projectList.map((project) => [project.name, {
      id: project.name, title: project.title || project.name, color: project.color, rows: [],
    }]));
    groups.set("", { id: "", title: "No project", color: "", rows: [] });
    for (const row of rows) {
      const id = row.project?.name || "";
      if (!groups.has(id)) groups.set(id, { id, title: row.project.title || id, color: row.project.color, rows: [] });
      if (this.isPinnedRow(kind, row, children)) groups.get(id).hasPinned = true;
      else groups.get(id).rows.push(row);
    }
    const rank = new Map(this.order.project.map((id, index) => [id, index]));
    return [...groups.values()].filter((group) => {
      if (this.config.project_filter !== "*" && group.id !== this.config.project_filter) return false;
      return group.rows.length || (kind === "chat" && this.config.status_filter === "all" && this.config.activity_filter === "all");
    }).sort((a, b) => {
      const aPinned = pins.isProjectPinned(a.id);
      const bPinned = pins.isProjectPinned(b.id);
      if (aPinned !== bPinned) return aPinned ? -1 : 1;
      return (rank.get(a.id) ?? Infinity) - (rank.get(b.id) ?? Infinity)
        || (aPinned ? Number(!b.id) - Number(!a.id) : Number(!a.id) - Number(!b.id))
        || a.title.localeCompare(b.title);
    });
  },

  isOpen(kind, id) {
    return this.collapsed[`${kind}:${id}`] === false || (!id && this.collapsed[`${kind}:${id}`] !== true);
  },

  toggleFolder(kind, id) {
    this.collapsed = { ...this.collapsed, [`${kind}:${id}`]: this.isOpen(kind, id) };
    this.saveCollapsed();
  },

  saveCollapsed() {
    try {
      localStorage.setItem("sidebarFoldersCollapsed", JSON.stringify(this.collapsed));
    } catch (error) {
      console.error("Could not save sidebar folders", error);
    }
  },

  revealSelection(kind, selected) {
    const row = kind === "chat" ? this.rootChat(selected) : tasks.tasks.find((item) => item.id === selected);
    if (!row) return;
    const id = row.project?.name || "";
    const pinned = this.isPinnedRow(kind, row);
    const key = `${selected}:${id}:${pinned}`;
    if (this.lastSelection[kind] === key) return;
    this.lastSelection[kind] = key;
    if (!pinned && !this.isOpen(kind, id)) this.toggleFolder(kind, id);
  },

  openMenu(menu, trigger, project = "") {
    if (this.menu === menu && this.menuProject === project) return this.closeMenu();
    this.cancelMenuExit();
    sidebar.rowMenuClose();
    this.menu = menu;
    this.menuProject = project;
    this.menuTrigger = trigger;
    const rect = trigger.getBoundingClientRect();
    this.menuStyle = {
      left: `${Math.max(8, Math.min(rect.right - 232, window.innerWidth - 240))}px`,
      top: `${rect.bottom + 6}px`,
      maxHeight: `${window.innerHeight - 16}px`,
    };
    Alpine.nextTick(() => {
      const element = document.querySelector(`[data-folder-menu="${menu}"]`);
      if (!element || this.menu !== menu) return;
      this.menuStyle.top = `${Math.max(8, Math.min(rect.bottom + 6, window.innerHeight - element.offsetHeight - 8))}px`;
      element.querySelector("button, select")?.focus({ preventScroll: true });
    });
  },

  closeMenu() {
    this.cancelMenuExit();
    if (document.activeElement?.closest(".sidebar-folders-menu")) this.menuTrigger?.focus({ preventScroll: true });
    this.menu = "";
    this.menuTrigger = null;
  },

  menuScope() {
    const rowMenu = sidebar.rowMenuOpenId;
    if (!rowMenu && !this.menu) return null;
    const trigger = rowMenu
      ? document.querySelector('#left-panel :is(.chat-container, .task-container) button[aria-haspopup="menu"][aria-expanded="true"]')
      : this.menuTrigger;
    return {
      key: rowMenu || `${this.menu}:${this.menuProject}`,
      owner: trigger?.closest(".chat-container, .task-container, .sidebar-folder-row, .section-header-row"),
      menu: document.querySelector(rowMenu ? '.sidebar-shell > [x-ref="rowActionsMenu"]' : `[data-folder-menu="${this.menu}"]`),
    };
  },

  cancelMenuExit() {
    clearTimeout(menuExitTimer);
    menuExitTimer = null;
  },

  dismissMenus() {
    const active = document.activeElement;
    if (active?.closest(".sidebar-folders-menu, .sidebar-row-actions-menu")) active.blur();
    this.closeMenu();
    sidebar.rowMenuClose();
  },

  menuPointer(event) {
    if (event.pointerType !== "mouse") return;
    const scope = this.menuScope();
    if (!scope) return this.cancelMenuExit();
    const target = event.type === "pointerout" ? event.relatedTarget : event.target;
    if (scope.owner?.contains(target) || scope.menu?.contains(target)) return this.cancelMenuExit();
    if (menuExitTimer) return;
    menuExitTimer = setTimeout(() => {
      menuExitTimer = null;
      const current = this.menuScope();
      if (current?.key === scope.key && ![current.owner, current.menu].some((element) => element?.matches(":hover"))) {
        this.dismissMenus();
      }
    }, 180);
  },

  menuFocus(event) {
    const scope = this.menuScope();
    if (scope && !scope.owner?.contains(event.target) && !scope.menu?.contains(event.target)) this.dismissMenus();
  },

  menuScroll(event) {
    const scope = this.menuScope();
    if (scope && event.target?.contains?.(scope.owner)) this.dismissMenus();
  },

  async newChat(project) {
    const id = await chats.newChat(project);
    if (id && !this.isOpen("chat", project)) this.toggleFolder("chat", project);
    this.closeMenu();
  },

  async editProject() {
    const name = this.menuProject;
    this.closeMenu();
    try {
      await projects.openEditModal(name);
      await projects.loadProjectsList();
    } catch (error) {
      this.report(error);
    }
  },

  async openProjectFiles() {
    const name = this.menuProject;
    this.closeMenu();
    const { store: browser } = await import("/components/modals/file-browser/file-browser-store.js");
    await browser.open(`/a0/usr/projects/${name}`);
  },

  startDrag(event, kind, id, project = "") {
    if (this.busy || event.target.closest("button:not(.sidebar-folder-toggle)")) {
      event.preventDefault();
      return;
    }
    this.closeMenu();
    const row = kind === "project" ? null : this.roots(kind).find((item) => item.id === id);
    this.drag = { kind, id, project, pinned: !!row && this.isPinnedRow(kind, row) };
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", id || "No project");
  },

  endDrag() {
    this.drag = null;
    this.dropTarget = null;
  },

  dropClass(kind, project, item = null) {
    const target = this.dropTarget;
    return target?.kind === kind && target.project === project && target.id === item?.id
      ? `folder-drop-${target.side}` : "";
  },

  dragOverFolder(event, kind, group, sections = null) {
    if (this.drag?.kind !== "project" && !event.target.closest(".sidebar-folder-row")) {
      const rows = [...event.currentTarget.querySelectorAll(".sidebar-folder-thread")];
      const row = rows.find((row) => event.clientY < row.getBoundingClientRect().bottom) || rows.at(-1);
      if (row) {
        const item = group.rows.find((item) => item.id === row.dataset.folderThread);
        return this.dragOver(event, kind, group.id, item, row, group.rows);
      }
    }
    if (group.pinned) {
      this.dropTarget = null;
      return;
    }
    this.dragOver(event, kind, group.id, null, event.currentTarget, sections?.filter((section) => !section.pinned));
  },

  dragOver(event, kind, project, item = null, element = event.currentTarget, rows = null) {
    const target = this.findDropTarget(event, kind, project, item, element, rows);
    const previous = this.dropTarget;
    if (target?.kind !== previous?.kind || target?.project !== previous?.project
      || target?.id !== previous?.id || target?.side !== previous?.side) this.dropTarget = target;
    event.dataTransfer.dropEffect = target ? "move" : "none";
    if (target) {
      event.preventDefault();
      event.stopPropagation();
    }
  },

  findDropTarget(event, kind, project, item, element, rows) {
    const drag = this.drag;
    if (!drag || this.busy) return null;
    if (drag.kind !== "project" && drag.kind !== kind) return null;
    if (drag.kind === "task" && project !== null && drag.project !== project) return null;
    if (drag.kind === "project" && item) return null;
    if (item && !!drag.pinned !== (project === null)) return null;
    if (!item && drag.kind !== "project") {
      return { kind, project, side: "inside" };
    }
    rows ??= item
      ? project === null ? this.pinnedRows(kind) : this.groups(kind).find((group) => group.id === project)?.rows || []
      : this.groups(kind);
    const id = item ? item.id : project;
    if (id === drag.id) return null;
    const to = rows.findIndex((row) => row.id === id);
    if (to < 0) return null;
    const rect = element.getBoundingClientRect();
    let after = event.clientY > rect.top + rect.height / 2;
    if (!item || project === null || drag.project === project) {
      const from = rows.findIndex((row) => row.id === drag.id);
      // For neighbors, show the insertion edge that changes their order.
      if (from >= 0 && Math.abs(from - to) === 1) after = from < to;
    }
    if (drag.kind === "project") {
      const pinnedCount = rows.filter((row) => pins.isProjectPinned(row.id)).length;
      const index = to + Number(after);
      if (pins.isProjectPinned(drag.id) ? index > pinnedCount : index < pinnedCount) return null;
    }
    // Both sides of a gap use the following row's top edge.
    const anchor = after && rows[to + 1] ? rows[to + 1] : rows[to];
    if (anchor.id === drag.id) return null;
    return {
      kind, project: item ? project : anchor.id, id: item ? anchor.id : undefined,
      side: after && !rows[to + 1] ? "after" : "before",
    };
  },

  async drop(event, kind, project, item = null) {
    const drag = this.drag;
    const target = this.dropTarget;
    if (!drag || !target || target.kind !== kind || this.busy) return;
    if (drag.kind !== "project" && drag.kind !== kind) return;
    if (drag.kind === "task" && project !== null && drag.project !== project) return;
    if (drag.kind === "project" && item) return;
    event.preventDefault();
    event.stopPropagation();
    project = target.project === null ? drag.project : target.project;
    item = target.id === undefined ? null : this.roots(kind).find((row) => row.id === target.id);
    this.endDrag();
    this.busy = true;
    try {
      if (drag.kind === "project") {
        if (drag.id !== project) await this.reorder("project", drag.id, project, target.side === "after", this.groups(kind));
      } else {
        if (drag.kind === "chat" && drag.project !== project) await this.moveChat(drag.id, project);
        if (item?.id !== drag.id && (item || !drag.pinned)) {
          const rows = this.roots(kind);
          const anchor = item || rows.find((row) => row.id !== drag.id && (row.project?.name || "") === project && !this.isPinnedRow(kind, row));
          await this.reorder(kind, drag.id, anchor?.id, !!item && target.side === "after", rows);
        }
        if (!drag.pinned && !this.isOpen(kind, project)) this.toggleFolder(kind, project);
      }
    } catch (error) {
      this.report(error);
    } finally {
      this.busy = false;
    }
  },

  async reorder(kind, id, target, after, rows) {
    const ids = [...new Set([...rows.map((row) => row.id), ...this.order[kind]])].filter((item) => item !== id);
    const index = target === undefined ? ids.length : ids.indexOf(target);
    ids.splice(index < 0 ? ids.length : index + Number(after), 0, id);
    const result = await callJsonApi(`/plugins/${PLUGIN}/layout`, { action: "save", kind, ids });
    this.order = result.order;
    if (this.config.sort_by !== "manual") {
      const config = { ...this.config, sort_by: "manual" };
      const saved = await callJsonApi("plugins", { action: "save_config", plugin_name: PLUGIN, settings: config });
      if (!saved.ok) throw new Error(saved.error || "Could not save manual sorting");
      this.config = config;
    }
  },

  async moveChat(id, project) {
    const result = await callJsonApi(`/plugins/${PLUGIN}/move_chat`, { context_id: id, project_name: project });
    // Apply the server result immediately; the normal state push remains authoritative.
    for (const context of chats.contexts) {
      if (result.context_ids.includes(context.id)) context.project = result.project;
    }
  },

  report(error, background = false) {
    if (background) {
      // Background refresh failures (tab-focus reload) are expected noise; log, don't toast.
      console.warn("Sidebar Folders background refresh failed:", error);
      return;
    }
    void toastFrontendError(error?.message || "Could not update sidebar folders", "Sidebar Folders");
  },
});
