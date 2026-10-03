"""Immutable project view packages, current-pointer CAS, and read receipts."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from . import protocols
from .project_events import canonical_bytes
from .project_journal import WriterLock


class ProjectViewError(ValueError):
    def __init__(self, code: str, message: str = "project view rejected") -> None:
        self.code = code
        super().__init__(message)


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render_project_brief(state: Mapping[str, Any], *, max_bytes: int = 64 * 1024) -> str:
    """Render stable UTF-8 text; exceeding the budget is an explicit refusal."""
    if type(state) is not dict:
        raise ProjectViewError("E_BRIEF", "state object required")
    required = {"indexed_cursor", "applied_cursor", "source_coverage", "budget_coverage",
                "verification_ref", "as_of", "issues", "dispatch_eligibility"}
    if not required <= set(state):
        raise ProjectViewError("E_BRIEF", "state lacks required fields")
    lines = ["# Project brief", f"indexed_cursor: {state['indexed_cursor']}",
             f"applied_cursor: {state['applied_cursor']}",
             f"source_coverage: {state['source_coverage']}",
             f"budget_coverage: {state['budget_coverage']}",
             f"verification_ref: {state['verification_ref']}", f"as_of: {state['as_of']}",
             f"dispatch_eligibility: {state['dispatch_eligibility']}"]
    issues = state.get("issues", [])
    if type(issues) is not list or any(type(item) is not str or not item for item in issues):
        raise ProjectViewError("E_BRIEF", "issues must be non-empty strings")
    lines.append("issues:")
    lines.extend("- [issue] " + item for item in sorted(issues))
    def safe_display(value: Any, *, key: str = "") -> Any:
        if any(token in key.lower() for token in ("secret", "token", "password", "api_key", "authorization", "credential")):
            return "[REDACTED]"
        if isinstance(value, dict):
            return {str(name): safe_display(item, key=str(name)) for name, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
        if isinstance(value, list):
            return [safe_display(item, key=key) for item in value]
        if isinstance(value, str):
            return value.replace("\r", "\\r").replace("\n", "\\n").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        return value

    for section in ("tasks", "decisions", "budgets"):
        values = state.get(section, {})
        if type(values) is not dict:
            raise ProjectViewError("E_BRIEF", section + " must be object")
        lines.append(section + ":")
        for key in sorted(values):
            lines.append("- " + key + ": " + json.dumps(safe_display(values[key], key=key), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    brief = "\n".join(lines) + "\n"
    raw = brief.encode("utf-8")
    if type(max_bytes) is not int or max_bytes < 1 or len(raw) > max_bytes:
        raise ProjectViewError("E_BRIEF_LIMIT", "brief exceeds byte budget")
    return brief


@dataclass(frozen=True)
class ViewManifest:
    view_id: str
    generation: int
    cursor: int
    state_sha256: str
    brief_sha256: str
    manifest_sha256: str
    state_byte_length: int
    brief_byte_length: int
    displayed_item_count: int
    omitted_item_count: int

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "project-view-manifest", "schema_version": 1,
                "view_id": self.view_id, "generation": self.generation, "cursor": self.cursor,
                "state_sha256": self.state_sha256, "brief_sha256": self.brief_sha256,
                "manifest_sha256": self.manifest_sha256, "state_byte_length": self.state_byte_length,
                "brief_byte_length": self.brief_byte_length, "displayed_item_count": self.displayed_item_count,
                "omitted_item_count": self.omitted_item_count}


@dataclass(frozen=True)
class BriefReadReceipt:
    receipt_id: str
    view_id: str
    manifest_sha256: str
    brief_sha256: str
    observer_ref: str
    read_cursor: int
    outcome: str

    def __post_init__(self) -> None:
        if self.outcome not in {"READ", "REJECTED"}:
            raise ProjectViewError("E_RECEIPT", "unsupported outcome")
        body = {"view_id": self.view_id, "manifest_sha256": self.manifest_sha256,
                "brief_sha256": self.brief_sha256, "observer_ref": self.observer_ref,
                "read_cursor": self.read_cursor, "outcome": self.outcome}
        if self.receipt_id != _digest(canonical_bytes(body)):
            raise ProjectViewError("E_RECEIPT", "receipt id does not match binding")

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "brief-read-receipt", "schema_version": 1,
                "receipt_id": self.receipt_id, "view_id": self.view_id,
                "manifest_sha256": self.manifest_sha256, "brief_sha256": self.brief_sha256,
                "observer_ref": self.observer_ref,
                "read_cursor": self.read_cursor, "outcome": self.outcome}


def make_read_receipt(manifest: ViewManifest, *, observer_ref: str, read_cursor: int,
                      outcome: str = "READ") -> BriefReadReceipt:
    if type(observer_ref) is not str or not observer_ref or type(read_cursor) is not int or read_cursor < 0:
        raise ProjectViewError("E_RECEIPT", "observer and cursor required")
    if read_cursor != manifest.cursor:
        raise ProjectViewError("E_RECEIPT", "read cursor must match manifest cursor")
    if outcome not in {"READ", "REJECTED"}:
        raise ProjectViewError("E_RECEIPT", "unsupported outcome")
    body = {"view_id": manifest.view_id, "manifest_sha256": manifest.manifest_sha256,
            "brief_sha256": manifest.brief_sha256,
            "observer_ref": observer_ref, "read_cursor": read_cursor, "outcome": outcome}
    receipt_id = _digest(canonical_bytes(body))
    return BriefReadReceipt(receipt_id, manifest.view_id, manifest.manifest_sha256,
                            manifest.brief_sha256, observer_ref, read_cursor, outcome)


class ViewPackageStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.views = self.root / "views"
        self.current_path = self.root / "current.json"
        self.lock_path = self.root / "current.lock"

    def _write(self, path: Path, raw: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())

    def publish(self, state: Mapping[str, Any], brief: str, *, generation: int, cursor: int,
                expected_view_id: str | None = None) -> ViewManifest:
        if type(state) is not dict or type(brief) is not str:
            raise ProjectViewError("E_VIEW", "state object and brief text required")
        if type(generation) is not int or generation < 1 or type(cursor) is not int or cursor < 0:
            raise ProjectViewError("E_CURSOR", "invalid generation/cursor")
        try:
            protocols.check_json_value(state, max_bytes=protocols.DEFAULT_MAX_BYTES)
            state_raw = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        except (protocols.ProtocolError, TypeError, ValueError) as exc:
            raise ProjectViewError("E_STATE", "state must be strict JSON") from exc
        brief_raw = brief.encode("utf-8")
        if len(brief_raw) > 64 * 1024:
            raise ProjectViewError("E_BRIEF_LIMIT", "brief exceeds byte budget")
        item_count = sum(len(state.get(section, {})) for section in ("tasks", "decisions", "budgets")) + len(state.get("issues", []))
        view_body = {"generation": generation, "cursor": cursor, "state_sha256": _digest(state_raw),
                     "brief_sha256": _digest(brief_raw), "state_byte_length": len(state_raw),
                     "brief_byte_length": len(brief_raw), "displayed_item_count": item_count,
                     "omitted_item_count": 0}
        view_id = _digest(canonical_bytes(view_body))
        manifest_base = {"record_type": "project-view-manifest", "schema_version": 1,
                         "view_id": view_id, **view_body}
        manifest_sha256 = _digest(canonical_bytes(manifest_base))
        manifest = ViewManifest(view_id, generation, cursor, view_body["state_sha256"],
                                view_body["brief_sha256"], manifest_sha256, view_body["state_byte_length"],
                                view_body["brief_byte_length"], view_body["displayed_item_count"],
                                view_body["omitted_item_count"])
        package = self.views / view_id
        with WriterLock(self.lock_path):
            current = self._read_pointer()
            if expected_view_id is not None and (current is None or current.get("view_id") != expected_view_id):
                raise ProjectViewError("E_CAS", "current view changed")
            if current is not None:
                if current.get("generation", generation) > generation or (
                        current.get("generation") == generation and current.get("cursor", cursor) > cursor):
                    raise ProjectViewError("E_ROLLBACK", "new view would move current backwards")
            package.mkdir(parents=True, exist_ok=True)
            self._write(package / "state.json", state_raw)
            self._write(package / "brief.md", brief_raw)
            self._write(package / "manifest.json", json.dumps(manifest.to_mapping(), ensure_ascii=False,
                                                               sort_keys=True, separators=(",", ":")).encode("utf-8"))
            pointer = {"record_type": "project-current", "schema_version": 1,
                       "view_id": view_id, "generation": generation, "cursor": cursor,
                       "manifest_sha256": manifest_sha256}
            pointer_raw = (json.dumps(pointer, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            pointer_tmp = self.current_path.with_suffix(".tmp")
            self._write(pointer_tmp, pointer_raw)
            os.replace(pointer_tmp, self.current_path)
        return manifest

    def _read_pointer(self) -> dict[str, Any] | None:
        if not self.current_path.exists():
            return None
        try:
            value = protocols.strict_json_loads(self.current_path.read_bytes())
        except (OSError, protocols.ProtocolError) as exc:
            raise ProjectViewError("E_CURRENT", "current pointer invalid") from exc
        if type(value) is not dict or set(value) != {"record_type", "schema_version", "view_id", "generation", "cursor", "manifest_sha256"} or value.get("record_type") != "project-current":
            raise ProjectViewError("E_CURRENT", "closed current pointer required")
        return value

    def read_current(self) -> tuple[ViewManifest, dict[str, Any], str]:
        pointer = self._read_pointer()
        if pointer is None:
            raise ProjectViewError("E_CURRENT", "current view is not published")
        package = self.views / pointer["view_id"]
        try:
            manifest = protocols.strict_json_loads((package / "manifest.json").read_bytes())
            state_raw = (package / "state.json").read_bytes()
            brief_raw = (package / "brief.md").read_bytes()
        except (OSError, protocols.ProtocolError) as exc:
            raise ProjectViewError("E_VIEW_INCOMPLETE", "current package is incomplete") from exc
        if (_digest(state_raw) != manifest.get("state_sha256") or _digest(brief_raw) != manifest.get("brief_sha256")
                or len(state_raw) != manifest.get("state_byte_length") or len(brief_raw) != manifest.get("brief_byte_length")):
            raise ProjectViewError("E_VIEW_DRIFT", "view bytes do not match manifest")
        expected_manifest_fields = {"record_type", "schema_version", "view_id", "generation", "cursor",
                                    "state_sha256", "brief_sha256", "manifest_sha256", "state_byte_length",
                                    "brief_byte_length", "displayed_item_count", "omitted_item_count"}
        if set(manifest) != expected_manifest_fields or manifest.get("record_type") != "project-view-manifest":
            raise ProjectViewError("E_VIEW_INCOMPLETE", "closed manifest required")
        if (pointer["manifest_sha256"] != manifest.get("manifest_sha256") or
                pointer.get("generation") != manifest.get("generation") or pointer.get("cursor") != manifest.get("cursor")):
            raise ProjectViewError("E_CURRENT", "pointer does not match manifest")
        return (ViewManifest(manifest["view_id"], manifest["generation"], manifest["cursor"],
                             manifest["state_sha256"], manifest["brief_sha256"], manifest["manifest_sha256"],
                             manifest["state_byte_length"], manifest["brief_byte_length"],
                             manifest["displayed_item_count"], manifest["omitted_item_count"]),
                protocols.strict_json_loads(state_raw), brief_raw.decode("utf-8"))


__all__ = ["BriefReadReceipt", "ProjectViewError", "ViewManifest", "ViewPackageStore", "make_read_receipt", "render_project_brief"]
