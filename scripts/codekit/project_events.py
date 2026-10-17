"""Strict, source-oriented project events for the 10 state index.

The module validates and identities records only.  It never turns an event
into approval, acceptance, budget usage, or dispatch permission.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from . import protocols


class ProjectEventError(ValueError):
    def __init__(self, code: str, message: str = "project event rejected") -> None:
        self.code = code
        super().__init__(message)


_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_KIND = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_RESOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_EVENT = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*){0,3}$")


def _fail(code: str, field: str, message: str) -> None:
    raise ProjectEventError(code, f"{field}: {message}")


def _text(value: Any, field: str, pattern: re.Pattern[str] | None = None) -> str:
    if type(value) is not str or not value or any(
            ord(ch) < 0x20 or 0x7f <= ord(ch) <= 0x9f
            or 0xd800 <= ord(ch) <= 0xdfff for ch in value):
        _fail("E_FIELD", field, "non-empty safe text required")
    if pattern is not None and pattern.fullmatch(value) is None:
        _fail("E_ID", field, "invalid identifier")
    return value


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _fail("E_RESOURCE", field, "sha256 required")
    return value


def canonical_bytes(value: Any) -> bytes:
    try:
        protocols.check_json_value(value, max_bytes=protocols.DEFAULT_MAX_BYTES)
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (protocols.ProtocolError, TypeError, ValueError, UnicodeEncodeError,
            RecursionError) as exc:
        raise ProjectEventError("E_JSON", "payload must be strict bounded JSON") from exc


def validate_resource_ref(ref: Any, *, field: str = "/source_ref") -> dict[str, Any]:
    if type(ref) is not dict:
        _fail("E_RESOURCE", field, "object required")
    allowed = {"kind", "id", "sha256", "path"}
    if set(ref) - allowed or not {"kind", "id", "sha256"} <= set(ref):
        _fail("E_RESOURCE", field, "closed ResourceRef required")
    _text(ref.get("kind"), f"{field}/kind", _KIND)
    _text(ref.get("id"), f"{field}/id", _RESOURCE_ID)
    _sha(ref.get("sha256"), f"{field}/sha256")
    if "path" in ref:
        try:
            protocols.validate_business_path(ref["path"], field=f"{field}/path")
        except protocols.ProtocolError as exc:
            _fail("E_RESOURCE", f"{field}/path", str(exc))
    return dict(ref)


@dataclass(frozen=True)
class SourceKey:
    repository_namespace: str
    producer_namespace: str
    source_record_id: str
    immutable_facet_id: str

    def __post_init__(self) -> None:
        _text(self.repository_namespace, "/source_key/repository_namespace", _ID)
        _text(self.producer_namespace, "/source_key/producer_namespace", _ID)
        _text(self.source_record_id, "/source_key/source_record_id", _RESOURCE_ID)
        _text(self.immutable_facet_id, "/source_key/immutable_facet_id", _RESOURCE_ID)

    def to_mapping(self) -> dict[str, str]:
        return {"repository_namespace": self.repository_namespace,
                "producer_namespace": self.producer_namespace,
                "source_record_id": self.source_record_id,
                "immutable_facet_id": self.immutable_facet_id}

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_bytes(self.to_mapping())).hexdigest()


def source_key_from(value: Any, *, field: str = "/source_key") -> SourceKey:
    if type(value) is not dict or set(value) != {
            "repository_namespace", "producer_namespace", "source_record_id", "immutable_facet_id"}:
        _fail("E_SOURCE_KEY", field, "closed SourceKey required")
    try:
        return SourceKey(value["repository_namespace"], value["producer_namespace"],
                         value["source_record_id"], value["immutable_facet_id"])
    except ProjectEventError:
        raise
    except (TypeError, ValueError) as exc:
        _fail("E_SOURCE_KEY", field, str(exc))


@dataclass(frozen=True)
class ProjectEvent:
    repository_namespace: str
    project_id: str
    request_id: str | None
    event_type: str
    subject: Mapping[str, Any]
    producer_namespace: str
    source_record_id: str
    immutable_facet_id: str
    source_ref: Mapping[str, Any]
    payload: Mapping[str, Any]
    producer_revision: int | None = None
    predecessor_refs: tuple[Mapping[str, Any], ...] = ()
    causes: tuple[Mapping[str, Any], ...] = ()
    occurred_at: str | None = None
    extractor_ref: Mapping[str, Any] | None = None
    recovered_from: Mapping[str, Any] | None = None
    event_id: str | None = None
    generation: int | None = None
    seq: int | None = None

    def __post_init__(self) -> None:
        _text(self.repository_namespace, "/repository_namespace", _ID)
        _text(self.project_id, "/project_id", _ID)
        if self.request_id is not None:
            _text(self.request_id, "/request_id", _ID)
        _text(self.event_type, "/event_type", _EVENT)
        if type(self.subject) is not dict:
            _fail("E_FIELD", "/subject", "object required")
        _text(self.producer_namespace, "/producer_namespace", _ID)
        _text(self.source_record_id, "/source_record_id", _RESOURCE_ID)
        _text(self.immutable_facet_id, "/immutable_facet_id", _RESOURCE_ID)
        validate_resource_ref(dict(self.source_ref))
        if type(self.payload) is not dict:
            _fail("E_FIELD", "/payload", "object required")
        for name, refs in (("predecessor_refs", self.predecessor_refs), ("causes", self.causes)):
            if type(refs) is not tuple or any(type(ref) is not dict for ref in refs):
                _fail("E_FIELD", f"/{name}", "tuple of objects required")
        if self.extractor_ref is not None:
            validate_resource_ref(dict(self.extractor_ref), field="/extractor_ref")
        if self.recovered_from is not None and type(self.recovered_from) is not dict:
            _fail("E_FIELD", "/recovered_from", "object required")
        if self.producer_revision is not None and (
                type(self.producer_revision) is not int or not 0 <= self.producer_revision <= protocols.MAX_SAFE_INTEGER):
            _fail("E_INTEGER", "/producer_revision", "safe non-negative integer required")
        if self.generation is not None and (
                type(self.generation) is not int or not 1 <= self.generation <= protocols.MAX_SAFE_INTEGER):
            _fail("E_INTEGER", "/cursor/generation", "positive safe integer required")
        if self.seq is not None and (
                type(self.seq) is not int or not 1 <= self.seq <= protocols.MAX_SAFE_INTEGER):
            _fail("E_INTEGER", "/cursor/seq", "positive safe integer required")
        canonical_bytes(self.to_mapping(include_identity=False))
        expected = self.derived_event_id
        if self.event_id is not None and self.event_id != expected:
            _fail("E_EVENT_ID", "/event_id", "does not match source and payload")

    @property
    def source_key(self) -> SourceKey:
        return SourceKey(self.repository_namespace, self.producer_namespace,
                         self.source_record_id, self.immutable_facet_id)

    @property
    def derived_event_id(self) -> str:
        value = {"source_key": self.source_key.to_mapping(),
                 "event_type": self.event_type,
                 "payload": dict(self.payload)}
        return hashlib.sha256(canonical_bytes(value)).hexdigest()

    def to_mapping(self, *, include_identity: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "record_type": "project-event", "schema_version": 1,
            "repository_namespace": self.repository_namespace, "project_id": self.project_id,
            "event_id": self.event_id or self.derived_event_id, "request_id": self.request_id,
            "event_type": self.event_type, "subject": dict(self.subject),
            "producer_namespace": self.producer_namespace, "source_record_id": self.source_record_id,
            "immutable_facet_id": self.immutable_facet_id, "source_ref": dict(self.source_ref),
            "producer_revision": self.producer_revision, "predecessor_refs": [dict(x) for x in self.predecessor_refs],
            "causes": [dict(x) for x in self.causes], "occurred_at": self.occurred_at,
            "extractor_ref": dict(self.extractor_ref) if self.extractor_ref is not None else None,
            "payload": dict(self.payload), "recovered_from": dict(self.recovered_from) if self.recovered_from else None,
        }
        if include_identity and self.generation is not None and self.seq is not None:
            value["cursor"] = {"generation": self.generation, "seq": self.seq}
        return value

    def assigned(self, generation: int, seq: int) -> "ProjectEvent":
        if self.generation is not None or self.seq is not None:
            _fail("E_IMMUTABLE", "/cursor", "event already assigned")
        return replace(self, generation=generation, seq=seq, event_id=self.derived_event_id)


def event_from_mapping(value: Any) -> ProjectEvent:
    if type(value) is not dict:
        _fail("E_EVENT", "/", "object required")
    required = {"record_type", "schema_version", "repository_namespace", "project_id", "event_id",
                "request_id", "event_type", "subject", "producer_namespace", "source_record_id",
                "immutable_facet_id", "source_ref", "producer_revision", "predecessor_refs", "causes",
                "occurred_at", "extractor_ref", "payload", "recovered_from", "cursor"}
    if set(value) != required:
        _fail("E_EVENT", "/", "closed ProjectEvent required")
    if value["record_type"] != "project-event" or value["schema_version"] != 1:
        _fail("E_EVENT", "/record_type", "unsupported record")
    cursor = value["cursor"]
    if type(cursor) is not dict or set(cursor) != {"generation", "seq"}:
        _fail("E_CURSOR", "/cursor", "generation and seq required")
    refs = value["predecessor_refs"]
    causes = value["causes"]
    if type(refs) is not list or type(causes) is not list:
        _fail("E_EVENT", "/predecessor_refs", "arrays required")
    return ProjectEvent(
        value["repository_namespace"], value["project_id"], value["request_id"], value["event_type"],
        value["subject"], value["producer_namespace"], value["source_record_id"], value["immutable_facet_id"],
        value["source_ref"], value["payload"], value["producer_revision"], tuple(refs), tuple(causes),
        value["occurred_at"], value["extractor_ref"], value["recovered_from"], value["event_id"],
        cursor["generation"], cursor["seq"])


__all__ = ["ProjectEvent", "ProjectEventError", "SourceKey", "canonical_bytes",
           "event_from_mapping", "source_key_from", "validate_resource_ref"]
