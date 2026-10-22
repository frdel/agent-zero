# Message Loop End Extensions DOX

## Purpose

- Own backend behavior that runs after a message loop completes.

## Ownership

- Ordered Python files own history organization and chat persistence at loop end.

## Local Contracts

- Preserve history consistency before saving chats.
- Do not skip persistence for successful loops unless the hook contract explicitly permits it.
- History compression that rewrites local history must clear the active Responses provider continuation while preserving stored response IDs for cleanup.
- Shared durability uses an encrypted detached prefix-summary job instead of mutating live history in a background task. The prompt-before hook applies its known result to a matching prefix while retaining later input; original records remain under the summary for cleanup.

## Work Guidance

- Coordinate changes with chat serialization, history organization, and WebUI refresh behavior.

## Verification

- Smoke-test sending a message, reloading the chat, and checking persisted history after changes.

## Child DOX Index

No child DOX files.
