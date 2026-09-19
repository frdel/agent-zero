# Scheduler

Provides the `scheduler` agent tool for managing saved tasks and schedules: listing, finding by name, showing, running, updating, deleting, and creating scheduled, ad-hoc, and planned tasks.

The Tasks UI (sidebar, modal) and scheduler API endpoints stay in core and share the framework `TaskScheduler` service; this plugin owns only the agent-facing tool.
