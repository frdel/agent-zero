### durable_plan:
Read or update the current chat's typed plan when local durability is enabled.
This plan is separate from scheduler tasks and arbitrary agent memory.
Use `action: "read"` to get `value` and `revision`.
Use `action: "replace"`, `expected_revision`, and a complete `value` to update it.
Value shape: `{"title":"Plan","items":[{"id":"step-1","text":"Do the work","done":false}]}`.
Keep item IDs stable and unique. Maximum 100 items and 64 KiB total.
Concurrent edits require re-reading and reconciling the current revision; never
repeat an external action to repair a plan conflict.
