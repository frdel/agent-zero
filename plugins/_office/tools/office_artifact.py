from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from helpers.strings import truncate_text
from helpers.tool import Response, Tool
from plugins._office.helpers import artifact_editor, document_store, libreoffice

OFFICE_EXTENSIONS = document_store.OPEN_DOCUMENT_EXTENSIONS | document_store.OOXML_EXTENSIONS


class OfficeArtifact(Tool):
    async def execute(
        self,
        action: str = "",
        kind: str = "document",
        title: str = "Untitled",
        format: str = "",
        content: str = "",
        path: str = "",
        file_id: str = "",
        version_id: int | str | None = None,
        operation: str = "",
        find: str = "",
        replace: str = "",
        sheet: str = "",
        cells: Any = None,
        rows: Any = None,
        chart: Any = None,
        slides: Any = None,
        max_chars: int | str = 12000,
        open_in_canvas: bool = False,
        open_in_desktop: bool = False,
        **kwargs: Any,
    ) -> Response:
        action = str(action or "status").strip().lower().replace("-", "_")
        open_in_canvas = _truthy(
            open_in_canvas
            or kwargs.get("open_canvas")
            or kwargs.get("open_document")
        )
        open_in_desktop = _truthy(
            open_in_desktop
            or kwargs.get("open_desktop")
            or kwargs.get("desktop")
        )
        try:
            if action == "create":
                fmt = _default_office_format(kind, format)
                doc = document_store.create_document(
                    kind=kind,
                    title=title,
                    fmt=fmt,
                    content=content,
                    path=path,
                    context_id=self._context_id(),
                )
                if doc["extension"] in {"odt", "ods", "odp"}:
                    validation = libreoffice.validate_odf(doc["path"])
                    if not validation.get("ok"):
                        return Response(
                            message=f"{self.name} create failed: {validation.get('error')}",
                            break_loop=False,
                        )
                if doc["extension"] == "docx":
                    validation = libreoffice.validate_docx(doc["path"])
                    if not validation.get("ok"):
                        return Response(
                            message=f"{self.name} create failed: {validation.get('error')}",
                            break_loop=False,
                        )
                return self._document_response(
                    "Created office artifact.",
                    doc,
                    action=action,
                    open_in_canvas=open_in_canvas,
                    open_in_desktop=open_in_desktop,
                )
            if action == "open":
                doc = self._document_from_input(file_id=file_id, path=path)
                return self._document_response(
                    "Opened office artifact.",
                    doc,
                    action=action,
                    open_in_canvas=open_in_canvas,
                    open_in_desktop=open_in_desktop,
                )
            if action in {"read", "extract"}:
                doc = self._document_from_input(file_id=file_id, path=path)
                payload = {
                    "ok": True,
                    "action": "read",
                    "document": self._public_doc(doc),
                    "content": artifact_editor.read_artifact(doc, max_chars=int(max_chars or 12000)),
                }
                return self._json_response(
                    payload,
                    doc=doc,
                    action="read",
                    open_in_canvas=open_in_canvas,
                    open_in_desktop=open_in_desktop,
                )
            if action in {"edit", "update", "patch"}:
                doc = self._document_from_input(file_id=file_id, path=path)
                updated_doc, payload = artifact_editor.edit_artifact(
                    doc,
                    operation=operation,
                    content=content,
                    find=find,
                    replace=replace,
                    sheet=sheet,
                    cells=cells,
                    rows=rows,
                    chart=chart,
                    slides=slides,
                    **kwargs,
                )
                payload["document"] = self._public_doc(updated_doc)
                return self._json_response(
                    payload,
                    doc=updated_doc,
                    action="edit",
                    open_in_canvas=open_in_canvas,
                    open_in_desktop=open_in_desktop,
                )
            if action == "inspect":
                doc = self._document_from_input(file_id=file_id, path=path)
                return self._json_response(
                    {"ok": True, "action": action, "document": self._public_doc(doc)},
                    doc=doc,
                    action=action,
                    open_in_canvas=open_in_canvas,
                    open_in_desktop=open_in_desktop,
                )
            if action == "version_history":
                doc = self._document_from_input(file_id=file_id, path=path)
                versions = document_store.version_history(doc["file_id"])
                return self._json_response(
                    {"ok": True, "action": action, "versions": versions},
                    doc=doc,
                    action=action,
                    open_in_canvas=open_in_canvas,
                    open_in_desktop=open_in_desktop,
                )
            if action == "restore_version":
                if version_id is None or str(version_id).strip() == "":
                    return Response(message="version_id is required for restore_version.", break_loop=False)
                doc = self._document_from_input(file_id=file_id, path=path)
                restored = document_store.restore_version(doc["file_id"], int(version_id))
                _ensure_office_doc(restored)
                return self._document_response(
                    "Restored office artifact version.",
                    restored,
                    action=action,
                    open_in_canvas=open_in_canvas,
                    open_in_desktop=open_in_desktop,
                )
            if action == "export":
                doc = self._document_from_input(file_id=file_id, path=path)
                target_format = str(kwargs.get("target_format") or kwargs.get("export_format") or "").lower().lstrip(".")
                if target_format and target_format != doc["extension"]:
                    _ensure_office_format(target_format, "target_format")
                    result = libreoffice.convert_document(doc["path"], target_format)
                    if result.get("ok"):
                        payload = {
                            "ok": True,
                            "action": action,
                            "path": document_store.display_path(result["path"]),
                            "document": self._public_doc(doc),
                        }
                        return self._json_response(
                            payload,
                            doc=doc,
                            action=action,
                            open_in_canvas=open_in_canvas,
                            open_in_desktop=open_in_desktop,
                        )
                    return Response(
                        message=f"{self.name} export failed: {result.get('error')}",
                        break_loop=False,
                        additional=self._additional(
                            doc,
                            action=action,
                            open_in_canvas=open_in_canvas,
                            open_in_desktop=open_in_desktop,
                        ),
                    )
                return self._document_response(
                    "Office artifact export path is ready.",
                    doc,
                    action=action,
                    open_in_canvas=open_in_canvas,
                    open_in_desktop=open_in_desktop,
                )
            if action == "status":
                return self._json_response({"ok": True, "action": action, "status": libreoffice.collect_status()}, action=action)
            return Response(message=f"Unknown {self.name} action: {action}", break_loop=False)
        except Exception as exc:
            return Response(message=f"{self.name} {action} failed: {exc}", break_loop=False)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="tool",
            heading=self.get_heading(),
            content="",
            kvps={k: v for k, v in self.args.items() if k != "_tool_name"},
            _tool_name=self.name,
        )

    _HEADING_VERBS = {
        "create": "Creating",
        "open": "Opening",
        "read": "Reading",
        "extract": "Extracting",
        "edit": "Editing",
        "update": "Updating",
        "patch": "Patching",
        "inspect": "Inspecting",
        "version_history": "Listing versions",
        "restore_version": "Restoring version",
        "export": "Exporting",
        "status": "Checking status",
    }

    _VERBS_WITH_OBJECT = {
        "create", "open", "read", "extract", "edit", "update", "patch", "inspect", "restore_version", "export"
    }

    def get_heading(self):
        action = str(self.args.get("action") or "").strip().lower()
        verb = self._HEADING_VERBS.get(action, "Working on")
        text = f"Office: {verb}" if action else "Office"
        if action in self._VERBS_WITH_OBJECT:
            path = str(self.args.get("path") or "").strip()
            title = str(self.args.get("title") or "").strip()
            name = Path(path).name if path else title
            if name:
                text += f" {truncate_text(name, 60)}"
        return f"icon://description {text}"

    def _document_from_input(self, file_id: str = "", path: str = "") -> dict[str, Any]:
        if file_id:
            return _ensure_office_doc(document_store.get_document(file_id))
        if path:
            return _ensure_office_doc(document_store.register_document(path, context_id=self._context_id()))
        raise ValueError("file_id or path is required")

    def _context_id(self) -> str:
        return self.agent.context.id if self.agent and self.agent.context else ""

    def _document_response(
        self,
        message: str,
        doc: dict[str, Any],
        action: str = "",
        *,
        open_in_canvas: bool = False,
        open_in_desktop: bool = False,
    ) -> Response:
        payload = {"ok": True, "action": action, "message": message, "document": self._public_doc(doc)}
        return Response(
            message=json.dumps(payload, indent=2, ensure_ascii=False),
            break_loop=False,
            additional=self._additional(
                doc,
                action=action,
                open_in_canvas=open_in_canvas,
                open_in_desktop=open_in_desktop,
            ),
        )

    def _json_response(
        self,
        payload: dict[str, Any],
        doc: dict[str, Any] | None = None,
        action: str = "",
        *,
        open_in_canvas: bool = False,
        open_in_desktop: bool = False,
    ) -> Response:
        return Response(
            message=json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            break_loop=False,
            additional=self._additional(
                doc,
                action=action,
                open_in_canvas=open_in_canvas,
                open_in_desktop=open_in_desktop,
            ) if doc else {
                "_tool_name": self.name,
                "canvas_surface": "desktop",
                "action": action,
                "open_in_canvas": bool(open_in_canvas),
                "open_in_desktop": bool(open_in_desktop),
            },
        )

    def _additional(
        self,
        doc: dict[str, Any] | None,
        action: str = "",
        *,
        open_in_canvas: bool = False,
        open_in_desktop: bool = False,
    ) -> dict[str, Any]:
        if not doc:
            return {
                "_tool_name": self.name,
                "canvas_surface": "desktop",
                "action": action,
                "open_in_canvas": bool(open_in_canvas),
                "open_in_desktop": bool(open_in_desktop),
            }
        return {
            "_tool_name": self.name,
            "canvas_surface": "desktop",
            "action": action,
            "open_in_canvas": bool(open_in_canvas),
            "open_in_desktop": bool(open_in_desktop),
            "file_id": doc["file_id"],
            "title": doc["basename"],
            "format": doc["extension"],
            "path": document_store.display_path(doc["path"]),
            "version": document_store.item_version(doc),
        }

    def _public_doc(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "file_id": doc["file_id"],
            "path": document_store.display_path(doc["path"]),
            "basename": doc["basename"],
            "extension": doc["extension"],
            "size": doc["size"],
            "version": document_store.item_version(doc),
            "last_modified": doc["last_modified"],
            "exists": Path(doc["path"]).exists(),
        }


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _default_office_format(kind: str, fmt: str = "") -> str:
    normalized = str(fmt or "").strip().lower().lstrip(".")
    if not normalized:
        normalized_kind = str(kind or "").strip().lower()
        if normalized_kind in {"spreadsheet", "sheet", "calc"}:
            normalized = "ods"
        elif normalized_kind in {"presentation", "slides", "deck", "impress"}:
            normalized = "odp"
        else:
            normalized = "odt"
    return _ensure_office_format(normalized, "format")


def _ensure_office_format(fmt: str, label: str = "format") -> str:
    normalized = str(fmt or "").strip().lower().lstrip(".")
    if normalized not in OFFICE_EXTENSIONS:
        raise ValueError(
            f"{label} must be an Office format ({', '.join(sorted(OFFICE_EXTENSIONS))}); "
            "use text_editor for Markdown and plain text files."
        )
    return normalized


def _ensure_office_doc(doc: dict[str, Any]) -> dict[str, Any]:
    _ensure_office_format(str(doc.get("extension") or ""), "document extension")
    return doc
