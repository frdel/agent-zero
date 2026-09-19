### notify_user
send an out-of-band notification without ending the current task
args: `message`, optional `title`, `detail`, `type`, `priority`, `timeout`
types: `info`, `success`, `warning`, `error`, `progress`
priority values: `20` high urgency, `10` normal urgency; omit for high
normal note/notification -> set `type: "info"` and `priority: 10`
use `success` only for a completed success message, not for a generic note
use for progress or alerts, not as the final answer
