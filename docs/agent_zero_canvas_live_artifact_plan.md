# Agent Zero Canvas: Live Artifact Streaming Panel — Implementation Plan

## Overview
This document describes how to implement a Claude/Gemini-style live artifact canvas for Agent Zero, with real-time streaming, code preview, and seamless UI integration. The canvas will display only artifacts linked to the selected chat, slide in from the right (not overlaying the chat), and provide syntax-highlighted, pretty output with preview capabilities.

---

## 1. Backend: Artifact Directory & WebSocket Streaming

- **Artifact Directory Structure:**
  - For each chat session, create a unique artifact directory, e.g., `artifacts/{chat_id}/`.
  - Each artifact (code, HTML, image, etc.) is saved as a file in this directory, with metadata linking it to the chat.

- **WebSocket Endpoint:**
  - Add a WebSocket endpoint (e.g., `/ws/artifacts`) using FastAPI or Flask.
  - Use `watchdog` to monitor the artifact directory for the current chat.
  - On file change, stream the new content (or diff) to the frontend, including artifact metadata (id, type, filename, etc.).

- **Artifact Metadata:**
  - Store artifact metadata (type, language, chat_id, timestamps) in a JSON file or database for quick lookup and filtering.

---

## 2. Frontend: Canvas UI Integration

- **Canvas Panel Placement:**
  - The canvas is a right-side panel, not an overlay.
  - When activated (by button or artifact creation), it slides in from the right, resizing the chat window (CSS flex or grid).
  - The chat context remains visible and interactive.

- **Canvas Button:**
  - Add a canvas button to the bottom frame, next to the nudge button.
  - Use a matching icon (e.g., a layered window or paint palette) and color scheme consistent with the UI.
  - Button toggles the canvas panel.

- **Artifact Filtering:**
  - When a chat is selected, only show artifacts from that chat’s artifact directory.
  - Canvas panel lists available artifacts (tabs or list), and clicking one streams its content live.

---

## 3. Live Streaming & Syntax Highlighting

- **WebSocket Client:**
  - When the canvas is open and an artifact is selected, connect to `/ws/artifacts?chat_id=...&artifact_id=...`.
  - As new content arrives, update the display in real time.

- **Syntax Highlighting:**
  - Use Prism.js or highlight.js for code/text artifacts.
  - Detect language from artifact metadata or file extension.
  - Style to match VS Code (dark/light themes).

- **Pretty Text:**
  - Ensure code, markdown, and text artifacts are rendered with proper formatting and color.

---

## 4. Preview & Execution

- **Preview Tab:**
  - For executable artifacts (HTML, JS, etc.), provide a “Preview” tab in the canvas.
  - Use an `<iframe>` or sandboxed environment to safely execute and display the artifact output.
  - For images, display directly; for code, show syntax-highlighted source.

---

## 5. UI/UX Details

- **Smooth Slide Animation:**
  - Use CSS transitions for the canvas panel to slide in/out smoothly.
  - Adjust chat window width dynamically.

- **Progress Indicators:**
  - Show a spinner or “writing…” indicator while the artifact is being updated.

- **Auto-Scroll:**
  - Optionally auto-scroll to the bottom as new content arrives.

- **Switching Artifacts:**
  - Allow switching between artifacts for the current chat, maintaining live updates.

---

## 6. Example Directory Structure

```
/artifacts/
  /{chat_id}/
    artifact1.py
    artifact2.html
    artifact3.png
    metadata.json
```

---

## 7. Implementation Steps

1. **Backend:**
   - Implement artifact directory creation per chat.
   - Add WebSocket endpoint and file watcher.
   - Stream artifact updates with metadata.

2. **Frontend:**
   - Refactor canvas panel to be a right-side sliding panel.
   - Add canvas button to bottom frame.
   - Implement WebSocket client for live streaming.
   - Integrate syntax highlighting and preview logic.
   - Filter artifacts by chat.

3. **UI Polish:**
   - Match button/icon style to existing UI.
   - Add smooth transitions and progress indicators.

---

## 8. References

- [Prism.js](https://prismjs.com/)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [Python Watchdog](https://python-watchdog.readthedocs.io/en/latest/)
- [Claude Artifacts Window Demo](https://www.anthropic.com/index/claude-3-artifacts)

---

**Summary:**
This plan will give Agent Zero a modern, Claude-style artifact canvas that live streams, previews, and colorizes artifacts per chat, with seamless UI integration and a maintainable codebase.
