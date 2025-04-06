/**
 * Task Scheduler Component for Settings Modal
 * Manages scheduled and ad-hoc tasks through a dedicated settings tab
 */

// Add a document ready event handler to ensure the scheduler tab can be clicked on first load
document.addEventListener('DOMContentLoaded', function() {
    // Setup scheduler tab click handling
    const setupSchedulerTab = () => {
        const settingsModal = document.getElementById('settingsModal');
        if (!settingsModal) {
            setTimeout(setupSchedulerTab, 100);
            return;
        }

        // Create a global event listener for clicks on the scheduler tab
        document.addEventListener('click', function(e) {
            // Find if the click was on the scheduler tab or its children
            const schedulerTab = e.target.closest('.settings-tab[title="Task Scheduler"]');
            if (!schedulerTab) return;

            e.preventDefault();
            e.stopPropagation();

            // Get the settings modal data
            try {
                const modalData = Alpine.$data(settingsModal);
                if (modalData.activeTab !== 'scheduler') {
                    // Directly call the modal's switchTab method
                    modalData.switchTab('scheduler');
                }
            } catch (err) {
                console.error('Error handling scheduler tab click:', err);
            }
        }, true); // Use capture phase to intercept before Alpine.js handlers
    };

    // Initialize the tab handling
    setupSchedulerTab();
});

document.addEventListener('alpine:init', () => {
    // Register as an Alpine component
    Alpine.data('schedulerSettings', () => ({
        tasks: [],
        isLoading: true,
        selectedTask: null,
        expandedTaskId: null,
        sortField: 'name',
        sortDirection: 'asc',
        filterType: 'all',  // all, scheduled, adhoc
        filterState: 'all',  // all, idle, running, disabled, error
        pollingInterval: null,
        pollingActive: false, // Track if polling is currently active
        editingTask: null,
        isCreating: false,
        isEditing: false,
        showLoadingState: false,
        viewMode: 'list', // Controls whether to show list or detail view
        selectedTaskForDetail: null, // Task object for detail view

        // Initialize the component
        init() {
            // Initialize editingTask with default values but ensure we're not in editing mode
            this.editingTask = {
                name: '',
                type: 'scheduled',
                state: 'idle', // Initialize with idle state
                schedule: {
                    minute: '*',
                    hour: '*',
                    day: '*',
                    month: '*',
                    weekday: '*'
                },
                token: '',
                system_prompt: '',
                prompt: '',
                attachments: []
            };

            // Make sure we're in "list view" mode by default
            this.isCreating = false;
            this.isEditing = false;

            // Add a watcher for task type changes to initialize the appropriate properties
            this.$watch('editingTask.type', (newType) => {
                if (newType === 'scheduled' && !this.editingTask.schedule) {
                    // Initialize schedule if changing to scheduled type
                    this.editingTask.schedule = {
                        minute: '*',
                        hour: '*',
                        day: '*',
                        month: '*',
                        weekday: '*'
                    };
                } else if (newType === 'adhoc' && !this.editingTask.token) {
                    // Initialize token if changing to adhoc type
                    this.editingTask.token = this.generateRandomToken();
                }
            });

            // Use a small delay to ensure Alpine.js has fully initialized
            // before fetching tasks, which helps prevent layout shift
            setTimeout(() => {
                // Initial fetch to populate the list
                this.fetchTasks();

                // Only start polling if the modal is actually open
                const store = Alpine.store('root');
                if (store && store.isOpen === true) {
                    this.startPolling();
                }
            }, 100);

            // Initialize safe watchers with defensive checks
            this.$nextTick(() => {
                // Watch the modal state from the root store
                this.$watch('$store.root.isOpen', (isOpen) => {
                    // Only proceed if the value is not undefined
                    if (typeof isOpen !== 'undefined') {
                        if (isOpen === true) {
                            // Modal just opened
                            this.startPolling();
                        } else if (isOpen === false) {
                            // Modal closed, stop polling
                            this.stopPolling();
                        }
                    }
                });
            });
        },

        // Start polling for task updates
        startPolling() {
            // Don't start if already polling
            if (this.pollingInterval) {
                return;
            }

            this.pollingActive = true;

            // Fetch immediately, then set up interval for every 2 seconds
            this.fetchTasks();
            this.pollingInterval = setInterval(() => {
                if (this.pollingActive) {
                    this.fetchTasks();
                }
            }, 2000); // Poll every 2 seconds as requested
        },

        // Stop polling when tab is inactive
        stopPolling() {
            this.pollingActive = false;

            if (this.pollingInterval) {
                clearInterval(this.pollingInterval);
                this.pollingInterval = null;
            }
        },

        // Fetch tasks from API
        async fetchTasks() {
            // Don't fetch if polling is inactive (prevents race conditions)
            if (!this.pollingActive && this.pollingInterval) {
                return;
            }

            // Don't fetch while creating/editing a task
            if (this.isCreating || this.isEditing) {
                return;
            }

            this.isLoading = true;
            try {
                const response = await fetch('/scheduler_tasks_list', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                if (!response.ok) {
                    throw new Error('Failed to fetch tasks');
                }

                const data = await response.json();
                console.log('Tasks fetched from backend:', data.tasks);
                this.tasks = data.tasks || [];
            } catch (error) {
                console.error('Error fetching tasks:', error);
                // Only show toast for errors on manual refresh, not during polling
                if (!this.pollingInterval) {
                    showToast('Failed to fetch tasks: ' + error.message, 'error');
                }
            } finally {
                this.isLoading = false;
            }
        },

        // Computed property for filtered tasks
        get filteredTasks() {
            return this.tasks
                .filter(task => {
                    // Filter by type
                    if (this.filterType !== 'all') {
                        if (this.filterType === 'scheduled' && !task.schedule) return false;
                        if (this.filterType === 'adhoc' && !task.token) return false;
                    }

                    // Filter by state
                    if (this.filterState !== 'all' && task.state !== this.filterState) {
                        return false;
                    }

                    return true;
                })
                .sort((a, b) => {
                    // Handle sorting
                    let valueA, valueB;

                    switch (this.sortField) {
                        case 'name':
                            valueA = a.name.toLowerCase();
                            valueB = b.name.toLowerCase();
                            break;
                        case 'state':
                            valueA = a.state;
                            valueB = b.state;
                            break;
                        case 'last_run':
                            valueA = a.last_run ? new Date(a.last_run).getTime() : 0;
                            valueB = b.last_run ? new Date(b.last_run).getTime() : 0;
                            break;
                        default:
                            valueA = a.name.toLowerCase();
                            valueB = b.name.toLowerCase();
                    }

                    // Determine sort direction
                    const direction = this.sortDirection === 'asc' ? 1 : -1;

                    // Compare values
                    if (valueA < valueB) return -1 * direction;
                    if (valueA > valueB) return 1 * direction;
                    return 0;
                });
        },

        // Change sort field/direction
        changeSort(field) {
            if (this.sortField === field) {
                // Toggle direction if already sorting by this field
                this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                // Set new sort field and default to ascending
                this.sortField = field;
                this.sortDirection = 'asc';
            }
        },

        // Toggle expanded task row
        toggleTaskExpand(taskId) {
            if (this.expandedTaskId === taskId) {
                this.expandedTaskId = null;
            } else {
                this.expandedTaskId = taskId;
            }
        },

        // Show task detail view
        showTaskDetail(taskId) {
            const task = this.tasks.find(t => t.uuid === taskId);
            if (!task) {
                showToast('Task not found', 'error');
                return;
            }

            // Create a copy of the task to avoid modifying the original
            this.selectedTaskForDetail = JSON.parse(JSON.stringify(task));

            // Ensure attachments is always an array
            if (!this.selectedTaskForDetail.attachments) {
                this.selectedTaskForDetail.attachments = [];
            }

            this.viewMode = 'detail';
        },

        // Close detail view and return to list
        closeTaskDetail() {
            this.selectedTaskForDetail = null;
            this.viewMode = 'list';
        },

        // Format date for display
        formatDate(dateString) {
            if (!dateString) return 'Never';

            const date = new Date(dateString);
            return date.toLocaleString();
        },

        // Format schedule for display
        formatSchedule(task) {
            if (!task.schedule) return 'None';

            let schedule = '';
            if (typeof task.schedule === 'string') {
                schedule = task.schedule;
            } else if (typeof task.schedule === 'object') {
                schedule = `${task.schedule.minute || '*'} ${task.schedule.hour || '*'} ${task.schedule.day || '*'} ${task.schedule.month || '*'} ${task.schedule.weekday || '*'}`;
            }

            return schedule;
        },

        // Get CSS class for state badge
        getStateBadgeClass(state) {
            switch (state) {
                case 'idle': return 'scheduler-status-idle';
                case 'running': return 'scheduler-status-running';
                case 'disabled': return 'scheduler-status-disabled';
                case 'error': return 'scheduler-status-error';
                default: return '';
            }
        },

        // Create a new task
        startCreateTask() {
            this.isCreating = true;
            this.isEditing = false;
            document.querySelector('[x-data="schedulerSettings"]')?.setAttribute('data-editing-state', 'creating');
            this.editingTask = {
                name: '',
                type: 'scheduled',
                state: 'idle', // Initialize with idle state
                schedule: {
                    minute: '*',
                    hour: '*',
                    day: '*',
                    month: '*',
                    weekday: '*'
                },
                token: this.generateRandomToken(), // Generate token even for scheduled tasks to prevent undefined errors
                system_prompt: '',
                prompt: '',
                attachments: [], // Always initialize as an empty array
            };
        },

        // Edit an existing task
        async startEditTask(taskId) {
            const task = this.tasks.find(t => t.uuid === taskId);
            if (!task) {
                showToast('Task not found', 'error');
                return;
            }

            this.isCreating = false;
            this.isEditing = true;
            document.querySelector('[x-data="schedulerSettings"]')?.setAttribute('data-editing-state', 'editing');

            // Create a deep copy to avoid modifying the original
            this.editingTask = JSON.parse(JSON.stringify(task));

            // Debug log
            console.log('Task data for editing:', task);
            console.log('Attachments from task:', task.attachments);

            // Ensure state is set with a default if missing
            if (!this.editingTask.state) this.editingTask.state = 'idle';

            // Ensure attachments is always an array
            if (!this.editingTask.attachments) {
                this.editingTask.attachments = [];
            } else if (typeof this.editingTask.attachments === 'string') {
                // Handle case where attachments might be stored as a string
                this.editingTask.attachments = this.editingTask.attachments
                    .split('\n')
                    .map(line => line.trim())
                    .filter(line => line.length > 0);
            } else if (!Array.isArray(this.editingTask.attachments)) {
                // If not an array or string, set to empty array
                this.editingTask.attachments = [];
            }

            // Ensure appropriate properties are initialized based on task type
            if (this.editingTask.type === 'scheduled') {
                // Ensure proper structure for schedule
                if (typeof this.editingTask.schedule === 'string') {
                    const parts = this.editingTask.schedule.split(' ');
                    this.editingTask.schedule = {
                        minute: parts[0] || '*',
                        hour: parts[1] || '*',
                        day: parts[2] || '*',
                        month: parts[3] || '*',
                        weekday: parts[4] || '*'
                    };
                } else if (!this.editingTask.schedule) {
                    // Initialize schedule if it doesn't exist
                    this.editingTask.schedule = {
                        minute: '*',
                        hour: '*',
                        day: '*',
                        month: '*',
                        weekday: '*'
                    };
                }
                // Initialize token for scheduled tasks to prevent undefined errors if UI accesses it
                if (!this.editingTask.token) {
                    this.editingTask.token = '';
                }
            } else if (this.editingTask.type === 'adhoc') {
                // Initialize token if it doesn't exist
                if (!this.editingTask.token) {
                    this.editingTask.token = this.generateRandomToken();
                }
                // Initialize schedule for adhoc tasks to prevent undefined errors when UI accesses schedule properties
                if (!this.editingTask.schedule) {
                    this.editingTask.schedule = {
                        minute: '*',
                        hour: '*',
                        day: '*',
                        month: '*',
                        weekday: '*'
                    };
                }
            }
        },

        // Cancel editing
        cancelEdit() {
            // Reset to initial state but keep default values to prevent errors
            this.editingTask = {
                name: '',
                type: 'scheduled',
                state: 'idle', // Initialize with idle state
                schedule: {
                    minute: '*',
                    hour: '*',
                    day: '*',
                    month: '*',
                    weekday: '*'
                },
                token: '',
                system_prompt: '',
                prompt: '',
                attachments: [], // Always initialize as an empty array
            };
            this.isCreating = false;
            this.isEditing = false;
            document.querySelector('[x-data="schedulerSettings"]')?.removeAttribute('data-editing-state');
        },

        // Save task (create new or update existing)
        async saveTask() {
            // Validate task data
            if (!this.editingTask.name.trim()) {
                showToast('Task name is required', 'error');
                return;
            }

            try {
                let apiEndpoint, taskData;

                // Prepare task data
                taskData = {
                    name: this.editingTask.name,
                    system_prompt: this.editingTask.system_prompt || '',
                    prompt: this.editingTask.prompt || '',
                    state: this.editingTask.state || 'idle' // Include state in task data
                };

                // Process attachments - now always stored as array
                taskData.attachments = Array.isArray(this.editingTask.attachments)
                    ? this.editingTask.attachments
                        .map(line => typeof line === 'string' ? line.trim() : line)
                        .filter(line => line && line.trim().length > 0)
                    : [];

                // Handle schedule based on task type
                if (this.editingTask.type === 'scheduled') {
                    // Ensure schedule is properly formatted as an object
                    if (typeof this.editingTask.schedule === 'string') {
                        // Parse string schedule into object
                        const parts = this.editingTask.schedule.split(' ');
                        taskData.schedule = {
                            minute: parts[0] || '*',
                            hour: parts[1] || '*',
                            day: parts[2] || '*',
                            month: parts[3] || '*',
                            weekday: parts[4] || '*'
                        };
                    } else {
                        // Use object schedule directly
                        taskData.schedule = this.editingTask.schedule;
                    }
                    // Don't send token for scheduled tasks
                    delete taskData.token;
                } else {
                    // Ad-hoc task with token
                    taskData.token = this.editingTask.token;
                    // Don't send schedule for adhoc tasks
                    delete taskData.schedule;
                }

                // Determine if creating or updating
                if (this.isCreating) {
                    apiEndpoint = '/scheduler_task_create';
                } else {
                    apiEndpoint = '/scheduler_task_update';
                    taskData.task_id = this.editingTask.uuid;
                }

                // Make API request
                const response = await fetch(apiEndpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(taskData)
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to save task');
                }

                // Show success message
                showToast(this.isCreating ? 'Task created successfully' : 'Task updated successfully', 'success');

                // Refresh task list
                this.fetchTasks();

                // Reset form to default state without setting to null
                this.cancelEdit();
                document.querySelector('[x-data="schedulerSettings"]')?.removeAttribute('data-editing-state');
            } catch (error) {
                console.error('Error saving task:', error);
                showToast('Failed to save task: ' + error.message, 'error');
            }
        },

        // Run a task
        async runTask(taskId) {
            try {
                const response = await fetch('/scheduler_task_run', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ task_id: taskId })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to run task');
                }

                showToast('Task started successfully', 'success');

                // Refresh task list
                this.fetchTasks();
            } catch (error) {
                console.error('Error running task:', error);
                showToast('Failed to run task: ' + error.message, 'error');
            }
        },

        // Reset a task's state
        async resetTaskState(taskId) {
            try {
                const task = this.tasks.find(t => t.uuid === taskId);
                if (!task) {
                    showToast('Task not found', 'error');
                    return;
                }

                // Check if task is already in idle state
                if (task.state === 'idle') {
                    showToast('Task is already in idle state', 'info');
                    return;
                }

                this.showLoadingState = true;

                // Call API to update the task state
                const response = await fetch('/scheduler_task_update', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        task_id: taskId,
                        state: 'idle'  // Always reset to idle state
                    })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to reset task state');
                }

                showToast('Task state reset to idle', 'success');

                // Refresh task list
                await this.fetchTasks();
                this.showLoadingState = false;
            } catch (error) {
                console.error('Error resetting task state:', error);
                showToast('Failed to reset task state: ' + error.message, 'error');
                this.showLoadingState = false;
            }
        },

        // Delete a task
        async deleteTask(taskId) {
            // Confirm deletion
            if (!confirm('Are you sure you want to delete this task? This action cannot be undone.')) {
                return;
            }

            try {
                const response = await fetch('/scheduler_task_delete', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ task_id: taskId })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to delete task');
                }

                showToast('Task deleted successfully', 'success');

                // Refresh task list
                this.fetchTasks();

                // Close expanded view if this task was expanded
                if (this.expandedTaskId === taskId) {
                    this.expandedTaskId = null;
                }
            } catch (error) {
                console.error('Error deleting task:', error);
                showToast('Failed to delete task: ' + error.message, 'error');
            }
        },

        // Generate a random token for ad-hoc tasks
        generateRandomToken() {
            const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
            let token = '';
            for (let i = 0; i < 16; i++) {
                token += characters.charAt(Math.floor(Math.random() * characters.length));
            }
            return token;
        },

        // Computed property for attachments text representation
        get attachmentsText() {
            // Ensure we always have an array to work with
            const attachments = Array.isArray(this.editingTask.attachments)
                ? this.editingTask.attachments
                : [];

            console.log('attachmentsText getter called, source:', this.editingTask.attachments);

            // Join array items with newlines
            return attachments.join('\n');
        },

        // Setter for attachments text - preserves empty lines during editing
        set attachmentsText(value) {
            console.log('attachmentsText setter called with:', value);

            if (typeof value === 'string') {
                // Just split by newlines without filtering to preserve editing experience
                this.editingTask.attachments = value.split('\n');
            } else {
                // Fallback to empty array if not a string
                this.editingTask.attachments = [];
            }

            console.log('editingTask.attachments is now:', this.editingTask.attachments);
        }
    }));
});
