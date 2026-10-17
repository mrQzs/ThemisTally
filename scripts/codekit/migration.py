"""Offline, deterministic migration planning and selection ledger.

This module is deliberately a reference seam for module 12.  It validates
caller supplied immutable records and applies a single in-memory selection
change with generation/CAS and idempotency fencing.  It does not inspect the
user's worktree, copy files, launch a process, read credentials, or authorize
production migration.  A successful operation therefore means only that the
supplied offline facts are internally consistent.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from .project_events import validate_resource_ref
from . import protocols


class MigrationError(ValueError):
    """Structured input, currentness, or offline ledger error."""

    def __init__(self, code: str, field: str = "", message: str = "migration rejected") -> None:
        self.code = code
        self.field = field
        super().__init__(f"{code} {field}: {message}" if field else f"{code}: {message}")


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IDENTITY_RE = re.compile(r"^[a-z][a-z0-9._:-]{0,127}$")
PATH_RE = re.compile(r"^[^/\\\x00][^\x00]*$")
PREFLIGHT_STATUSES = frozenset({"READY", "BLOCKED", "UNKNOWN", "NOT_APPLICABLE"})
MIGRATION_STATES = frozenset({
    "DISCOVERED", "PREFLIGHTED", "BACKUP_VERIFIED", "PLAN_REVIEWED",
    "DRAINING", "STAGED", "SWITCHED", "VERIFYING", "ACCEPTED", "HOLD",
    "FAILED", "ROLLING_BACK", "ROLLED_BACK",
})
OPERATION_KINDS = frozenset({"stage_resource", "verify_resource", "switch_selection", "verify_history"})
REQUIRED_GUARDS = frozenset({"authorized", "quiescent", "backup_verified", "rules_current", "inputs_current"})


def _text(value: Any, field: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if type(value) is not str or not value or any(
            ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F
            or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise MigrationError("E_TEXT", field, "non-empty safe text required")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise MigrationError("E_ID", field, "invalid identifier")
    return value


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        raise MigrationError("E_HASH", field, "lowercase SHA-256 required")
    return value


def _generation(value: Any, field: str = "/generation") -> int:
    if type(value) is not int or not 1 <= value <= protocols.MAX_SAFE_INTEGER:
        raise MigrationError("E_GENERATION", field, "positive safe integer required")
    return value


def canonical_bytes(value: Any) -> bytes:
    """Canonical JSON bytes used for record and operation fingerprints."""
    try:
        protocols.check_json_value(value, max_bytes=protocols.DEFAULT_MAX_BYTES - 1)
        return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (protocols.ProtocolError, TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise MigrationError("E_JSON", message="strict bounded JSON required") from exc


def digest_bytes(value: bytes) -> str:
    if not isinstance(value, bytes):
        raise MigrationError("E_BYTES", message="bytes required")
    return hashlib.sha256(value).hexdigest()


def record_digest(value: Mapping[str, Any]) -> str:
    if not isinstance(value, Mapping):
        raise MigrationError("E_RECORD", message="mapping required")
    return digest_bytes(canonical_bytes(dict(value)))


def _ref(value: Any, field: str, *, require_path: bool = False) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MigrationError("E_RESOURCE", field, "ResourceRef object required")
    try:
        ref = validate_resource_ref(dict(value), field=field)
    except (ValueError, TypeError) as exc:
        code = getattr(exc, "code", "E_RESOURCE")
        raise MigrationError(code, field, "invalid ResourceRef") from exc
    if require_path and "path" not in ref:
        raise MigrationError("E_RESOURCE_PATH", field, "path is required for file inventory")
    if "path" in ref:
        path = ref["path"]
        if type(path) is not str or PATH_RE.fullmatch(path) is None:
            raise MigrationError("E_PATH", f"{field}/path", "relative path required")
        normalized = path.replace("\\", "/")
        parts = normalized.split("/")
        if normalized.startswith("/") or any(part in {"", ".", ".."} for part in parts):
            raise MigrationError("E_PATH", f"{field}/path", "normalized relative path required")
        ref["path"] = normalized
    return ref


def _refs(value: Any, field: str, *, unique: bool = True) -> tuple[dict[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise MigrationError("E_REFS", field, "reference sequence required")
    result = tuple(_ref(item, f"{field}/{index}") for index, item in enumerate(value))
    if unique and len({(item["kind"], item["id"], item["sha256"], item.get("path")) for item in result}) != len(result):
        raise MigrationError("E_DUPLICATE", field, "duplicate ResourceRef")
    return result


def _closed(value: Any, fields: set[str], field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise MigrationError("E_FIELDS", field, "closed object required")
    return dict(value)


@dataclass(frozen=True)
class PreflightCheck:
    """One read-only migration preflight observation."""

    check_id: str
    status: str
    source_ref: dict[str, Any] | None = None
    remediation: str | None = None
    requires_write: bool = False
    requires_network: bool = False
    requires_cost: bool = False

    def __post_init__(self) -> None:
        _text(self.check_id, "/check_id", pattern=IDENTITY_RE)
        if self.status not in PREFLIGHT_STATUSES:
            raise MigrationError("E_STATUS", "/status", "unsupported preflight status")
        if self.source_ref is not None:
            object.__setattr__(self, "source_ref", _ref(self.source_ref, "/source_ref"))
        for field, value in (("requires_write", self.requires_write),
                             ("requires_network", self.requires_network),
                             ("requires_cost", self.requires_cost)):
            if type(value) is not bool:
                raise MigrationError("E_BOOL", f"/{field}", "boolean required")
        if self.remediation is not None:
            _text(self.remediation, "/remediation")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id, "status": self.status,
            "source_ref": None if self.source_ref is None else dict(self.source_ref),
            "remediation": self.remediation, "requires_write": self.requires_write,
            "requires_network": self.requires_network, "requires_cost": self.requires_cost,
        }


@dataclass(frozen=True)
class MigrationPreflight:
    migration_id: str
    repository_id: str
    request_id: str
    checks: tuple[PreflightCheck, ...]
    state: str = "DISCOVERED"
    offline_only: bool = True

    def __post_init__(self) -> None:
        for field, value in (("migration_id", self.migration_id), ("repository_id", self.repository_id),
                             ("request_id", self.request_id)):
            _text(value, f"/{field}", pattern=IDENTITY_RE)
        if type(self.checks) is not tuple or not self.checks or any(type(item) is not PreflightCheck for item in self.checks):
            raise MigrationError("E_CHECKS", "/checks", "non-empty PreflightCheck tuple required")
        ids = [item.check_id for item in self.checks]
        if len(set(ids)) != len(ids):
            raise MigrationError("E_DUPLICATE", "/checks", "check ids must be unique")
        if self.state not in MIGRATION_STATES:
            raise MigrationError("E_STATE", "/state", "unsupported migration state")
        if self.state not in {"DISCOVERED", "PREFLIGHTED", "HOLD", "FAILED"}:
            raise MigrationError("E_STATE", "/state", "preflight cannot claim an applied state")
        if self.offline_only is not True:
            raise MigrationError("E_OFFLINE", "/offline_only", "offline reference must be explicit")

    @property
    def status(self) -> str:
        statuses = {item.status for item in self.checks}
        if "BLOCKED" in statuses:
            return "BLOCKED"
        if "UNKNOWN" in statuses:
            return "UNKNOWN"
        if statuses <= {"NOT_APPLICABLE"}:
            return "NOT_APPLICABLE"
        return "READY"

    @property
    def blocking_checks(self) -> tuple[str, ...]:
        return tuple(sorted(item.check_id for item in self.checks if item.status in {"BLOCKED", "UNKNOWN"}))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "record_type": "migration-preflight", "schema_version": 1,
            "migration_id": self.migration_id, "repository_id": self.repository_id,
            "request_id": self.request_id, "checks": [item.to_mapping() for item in self.checks],
            "status": self.status, "state": self.state, "offline_only": self.offline_only,
        }

    @property
    def digest(self) -> str:
        return record_digest(self.to_mapping())


@dataclass(frozen=True)
class MigrationOperation:
    operation_id: str
    kind: str
    target_ref: dict[str, Any]
    precondition_ref: dict[str, Any]
    compensation_ref: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _text(self.operation_id, "/operation_id", pattern=IDENTITY_RE)
        if self.kind not in OPERATION_KINDS:
            raise MigrationError("E_OPERATION_KIND", "/kind", "unsupported migration operation")
        object.__setattr__(self, "target_ref", _ref(self.target_ref, "/target_ref"))
        object.__setattr__(self, "precondition_ref", _ref(self.precondition_ref, "/precondition_ref"))
        if self.compensation_ref is not None:
            object.__setattr__(self, "compensation_ref", _ref(self.compensation_ref, "/compensation_ref"))
        if self.kind == "switch_selection" and self.compensation_ref is None:
            raise MigrationError("E_COMPENSATION", "/compensation_ref", "selection switch requires compensation")

    def to_mapping(self) -> dict[str, Any]:
        return {"operation_id": self.operation_id, "kind": self.kind,
                "target_ref": dict(self.target_ref), "precondition_ref": dict(self.precondition_ref),
                "compensation_ref": None if self.compensation_ref is None else dict(self.compensation_ref)}


@dataclass(frozen=True)
class MigrationPlan:
    migration_id: str
    repository_id: str
    request_id: str
    preflight_ref: dict[str, Any]
    backup_ref: dict[str, Any]
    maintenance_authorization_ref: dict[str, Any]
    expected_generation: int
    before_selection_ref: dict[str, Any]
    after_selection_ref: dict[str, Any]
    operations: tuple[MigrationOperation, ...]
    state: str = "PREFLIGHTED"
    online_calls_allowed: bool = False

    def __post_init__(self) -> None:
        for field, value in (("migration_id", self.migration_id), ("repository_id", self.repository_id),
                             ("request_id", self.request_id)):
            _text(value, f"/{field}", pattern=IDENTITY_RE)
        for field in ("preflight_ref", "backup_ref", "maintenance_authorization_ref",
                      "before_selection_ref", "after_selection_ref"):
            object.__setattr__(self, field, _ref(getattr(self, field), f"/{field}"))
        _generation(self.expected_generation, "/expected_generation")
        if type(self.operations) is not tuple or not self.operations:
            raise MigrationError("E_OPERATIONS", "/operations", "non-empty operation tuple required")
        if any(type(item) is not MigrationOperation for item in self.operations):
            raise MigrationError("E_OPERATIONS", "/operations", "MigrationOperation tuple required")
        ids = [item.operation_id for item in self.operations]
        if len(set(ids)) != len(ids):
            raise MigrationError("E_DUPLICATE", "/operations", "operation ids must be unique")
        if self.state not in MIGRATION_STATES:
            raise MigrationError("E_STATE", "/state", "unsupported migration state")
        if self.online_calls_allowed is not False:
            raise MigrationError("E_ONLINE", "/online_calls_allowed", "offline plan forbids online calls")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "record_type": "migration-plan", "schema_version": 1,
            "migration_id": self.migration_id, "repository_id": self.repository_id,
            "request_id": self.request_id, "preflight_ref": dict(self.preflight_ref),
            "backup_ref": dict(self.backup_ref),
            "maintenance_authorization_ref": dict(self.maintenance_authorization_ref),
            "expected_generation": self.expected_generation,
            "before_selection_ref": dict(self.before_selection_ref),
            "after_selection_ref": dict(self.after_selection_ref),
            "operations": [item.to_mapping() for item in self.operations],
            "state": self.state, "online_calls_allowed": self.online_calls_allowed,
        }

    @property
    def digest(self) -> str:
        return record_digest(self.to_mapping())


@dataclass(frozen=True)
class MigrationReceipt:
    migration_id: str
    operation_id: str
    idempotency_key: str
    plan_sha256: str
    from_generation: int
    to_generation: int
    before_selection_ref: dict[str, Any]
    after_selection_ref: dict[str, Any]
    status: str
    replayed: bool
    currently_selected: bool
    current_generation: int
    current_selection_ref: dict[str, Any]

    def __post_init__(self) -> None:
        for field, value in (("migration_id", self.migration_id), ("operation_id", self.operation_id),
                             ("idempotency_key", self.idempotency_key)):
            _text(value, f"/{field}", pattern=IDENTITY_RE)
        _sha(self.plan_sha256, "/plan_sha256")
        _generation(self.from_generation, "/from_generation")
        _generation(self.to_generation, "/to_generation")
        if self.to_generation != self.from_generation + 1:
            raise MigrationError("E_GENERATION", "/to_generation", "receipt generation must advance by one")
        for field in ("before_selection_ref", "after_selection_ref", "current_selection_ref"):
            object.__setattr__(self, field, _ref(getattr(self, field), f"/{field}"))
        if self.status not in {"APPLIED", "REPLAYED", "ROLLED_BACK"}:
            raise MigrationError("E_STATUS", "/status", "unsupported receipt status")
        for field, value in (("replayed", self.replayed), ("currently_selected", self.currently_selected)):
            if type(value) is not bool:
                raise MigrationError("E_BOOL", f"/{field}", "boolean required")
        _generation(self.current_generation, "/current_generation")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "record_type": "migration-receipt", "schema_version": 1,
            "migration_id": self.migration_id, "operation_id": self.operation_id,
            "idempotency_key": self.idempotency_key, "plan_sha256": self.plan_sha256,
            "from_generation": self.from_generation, "to_generation": self.to_generation,
            "before_selection_ref": dict(self.before_selection_ref),
            "after_selection_ref": dict(self.after_selection_ref), "status": self.status,
            "replayed": self.replayed, "currently_selected": self.currently_selected,
            "current_generation": self.current_generation,
            "current_selection_ref": dict(self.current_selection_ref),
        }


@dataclass(frozen=True)
class HistoryIntegrityReport:
    status: str
    unchanged: tuple[str, ...]
    missing: tuple[str, ...]
    changed: tuple[str, ...]
    unplanned_added: tuple[str, ...]
    unreadable: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "BLOCKED", "UNKNOWN"}:
            raise MigrationError("E_STATUS", "/status", "unsupported integrity status")
        for field in ("unchanged", "missing", "changed", "unplanned_added", "unreadable"):
            values = getattr(self, field)
            if type(values) is not tuple or any(type(value) is not str for value in values):
                raise MigrationError("E_INTEGRITY", f"/{field}", "sorted text tuple required")

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "history-integrity-report", "schema_version": 1,
                "status": self.status, "unchanged": list(self.unchanged),
                "missing": list(self.missing), "changed": list(self.changed),
                "unplanned_added": list(self.unplanned_added), "unreadable": list(self.unreadable)}


@dataclass(frozen=True)
class BackupSnapshot:
    backup_id: str
    entries: tuple[tuple[str, str], ...]
    source_generation: int
    verified: bool = True

    def __post_init__(self) -> None:
        _text(self.backup_id, "/backup_id", pattern=IDENTITY_RE)
        _generation(self.source_generation, "/source_generation")
        if type(self.entries) is not tuple:
            raise MigrationError("E_ENTRIES", "/entries", "entry tuple required")
        paths = [path for path, _digest in self.entries]
        if paths != sorted(paths) or len(set(paths)) != len(paths):
            raise MigrationError("E_ENTRIES", "/entries", "entries must be sorted and unique")
        for path, entry_digest in self.entries:
            _text(path, "/entries/path")
            _sha(entry_digest, "/entries/sha256")
        if self.verified is not True:
            raise MigrationError("E_BACKUP", "/verified", "offline snapshot must be verified")

    @property
    def digest(self) -> str:
        return record_digest(self.to_mapping())

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "backup-snapshot", "schema_version": 1,
                "backup_id": self.backup_id,
                "entries": [{"path": path, "sha256": digest} for path, digest in self.entries],
                "source_generation": self.source_generation, "verified": self.verified}


def create_backup_snapshot(backup_id: str, entries: Mapping[str, bytes], *, source_generation: int) -> BackupSnapshot:
    """Create a hash-only backup manifest from caller-supplied bytes.

    The function intentionally does not read or write files.  Callers may use
    it with a disposable fixture and must provide the production backup API
    separately when a real migration is authorized.
    """
    if not isinstance(entries, Mapping) or not entries:
        raise MigrationError("E_ENTRIES", "/entries", "non-empty bytes mapping required")
    normalized: list[tuple[str, str]] = []
    for path, payload in entries.items():
        _text(path, "/entries/path")
        normalized_path = path.replace("\\", "/")
        if normalized_path.startswith("/") or any(part in {"", ".", ".."} for part in normalized_path.split("/")):
            raise MigrationError("E_PATH", "/entries/path", "relative normalized path required")
        if not isinstance(payload, bytes):
            raise MigrationError("E_BYTES", "/entries/payload", "bytes required")
        normalized.append((normalized_path, digest_bytes(payload)))
    return BackupSnapshot(backup_id, tuple(sorted(normalized)), source_generation)


def compare_history_inventory(before: Mapping[str, str], after: Mapping[str, str], *, allowed_new: Iterable[str] = (),
                              unreadable: Iterable[str] = ()) -> HistoryIntegrityReport:
    """Compare hash inventories without rewriting old evidence or hashes."""
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise MigrationError("E_INVENTORY", message="before/after hash maps required")
    before_map: dict[str, str] = {}; after_map: dict[str, str] = {}
    for target, output in ((before, before_map), (after, after_map)):
        for path, value in target.items():
            _text(path, "/inventory/path")
            output[path.replace("\\", "/")] = _sha(value, "/inventory/sha256")
    allowed: set[str] = set()
    for path in allowed_new:
        _text(path, "/allowed_new")
        allowed.add(path.replace("\\", "/"))
    unreadable_set = set()
    for path in unreadable:
        _text(path, "/unreadable")
        unreadable_set.add(path.replace("\\", "/"))
    missing = tuple(sorted(set(before_map) - set(after_map)))
    changed = tuple(sorted(path for path in set(before_map) & set(after_map) if before_map[path] != after_map[path]))
    unplanned = tuple(sorted(set(after_map) - set(before_map) - allowed))
    unchanged = tuple(sorted(set(before_map) & set(after_map) - set(changed)))
    status = "PASS" if not (missing or changed or unplanned or unreadable_set) else "BLOCKED"
    return HistoryIntegrityReport(status, unchanged, missing, changed, unplanned, tuple(sorted(unreadable_set)))


class MigrationLedger:
    """A disposable single-selection ledger with CAS and idempotent receipts."""

    def __init__(self, *, generation: int = 1, target_ref: Mapping[str, Any] | None = None) -> None:
        _generation(generation)
        self._generation = generation
        self._target: dict[str, Any] | None = None if target_ref is None else _ref(target_ref, "/target_ref")
        self._receipts: dict[str, MigrationReceipt] = {}
        self._fingerprints: dict[str, str] = {}

    def current(self) -> tuple[int, dict[str, Any]]:
        if self._target is None:
            raise MigrationError("E_UNINITIALIZED", message="selection is not initialized")
        return self._generation, dict(self._target)

    @property
    def receipts(self) -> tuple[MigrationReceipt, ...]:
        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def initialize(self, target_ref: Mapping[str, Any]) -> None:
        target = _ref(target_ref, "/target_ref")
        if self._target is not None:
            raise MigrationError("E_INITIALIZED", message="selection already initialized")
        self._target = target

    @staticmethod
    def _fingerprint(*, migration_id: str, operation: MigrationOperation, plan_sha256: str,
                     expected_generation: int, before_ref: Mapping[str, Any], after_ref: Mapping[str, Any],
                     idempotency_key: str) -> str:
        return record_digest({"migration_id": migration_id, "operation": operation.to_mapping(),
                              "plan_sha256": plan_sha256, "expected_generation": expected_generation,
                              "before_ref": dict(before_ref), "after_ref": dict(after_ref),
                              "idempotency_key": idempotency_key})

    @staticmethod
    def _check_guards(guards: Mapping[str, Any]) -> None:
        if not isinstance(guards, Mapping) or set(guards) != REQUIRED_GUARDS \
                or any(type(value) is not bool or value is not True for value in guards.values()):
            raise MigrationError("E_GUARD", "/guards", "all migration guards must be true")

    def apply(self, *, migration_id: str, plan: MigrationPlan, operation: MigrationOperation,
              idempotency_key: str, expected_generation: int, before_ref: Mapping[str, Any],
              after_ref: Mapping[str, Any], guards: Mapping[str, Any],
              lose_response: bool = False, crash_before_commit: bool = False,
              _allow_inverse: bool = False) -> MigrationReceipt:
        _text(migration_id, "/migration_id", pattern=IDENTITY_RE)
        if migration_id != plan.migration_id:
            raise MigrationError("E_MIGRATION", "/migration_id", "plan migration mismatch")
        if type(idempotency_key) is not str or IDENTITY_RE.fullmatch(idempotency_key) is None:
            raise MigrationError("E_ID", "/idempotency_key", "valid idempotency key required")
        if operation.kind != "switch_selection":
            raise MigrationError("E_OPERATION_KIND", "/operation/kind", "only switch_selection has an apply effect")
        _generation(expected_generation, "/expected_generation")
        before = _ref(before_ref, "/before_ref"); after = _ref(after_ref, "/after_ref")
        if not _allow_inverse:
            declared = {item.operation_id: item for item in plan.operations}.get(operation.operation_id)
            if declared is None or declared.to_mapping() != operation.to_mapping():
                raise MigrationError("E_OPERATION_BINDING", "/operation", "operation is not in immutable plan")
            if before != plan.before_selection_ref or after != plan.after_selection_ref:
                raise MigrationError("E_PLAN_BINDING", message="selection refs do not match immutable plan")
        if before != operation.precondition_ref or after != operation.target_ref:
            raise MigrationError("E_OPERATION_BINDING", message="operation refs do not match apply refs")
        plan_sha = plan.digest
        fingerprint = self._fingerprint(migration_id=migration_id, operation=operation, plan_sha256=plan_sha,
                                        expected_generation=expected_generation, before_ref=before, after_ref=after,
                                        idempotency_key=idempotency_key)
        prior = self._receipts.get(idempotency_key)
        if prior is not None:
            if self._fingerprints[idempotency_key] != fingerprint:
                raise MigrationError("E_IDEMPOTENCY_CONFLICT", "/idempotency_key", "key reused with different request")
            receipt = MigrationReceipt(prior.migration_id, prior.operation_id, prior.idempotency_key,
                                       prior.plan_sha256, prior.from_generation, prior.to_generation,
                                       prior.before_selection_ref, prior.after_selection_ref, "REPLAYED", True,
                                       self._target == prior.after_selection_ref and self._generation == prior.to_generation,
                                       self._generation, self.current()[1])
            if lose_response:
                raise MigrationError("E_RESPONSE_LOST", message="response intentionally withheld after replay")
            return receipt
        self._check_guards(guards)
        if crash_before_commit:
            raise MigrationError("E_PRECOMMIT_FAILURE", message="simulated pre-commit failure")
        current_generation, current = self.current()
        if current_generation != expected_generation or current != before:
            raise MigrationError("E_CAS_CONFLICT", message="selection changed")
        next_generation = expected_generation + 1
        # Capture a receipt before mutating so an invalid construction cannot
        # leave a partially applied selection in this disposable ledger.
        receipt = MigrationReceipt(migration_id, operation.operation_id, idempotency_key, plan_sha,
                                   expected_generation, next_generation, before, after, "APPLIED", False,
                                   True, next_generation, after)
        self._target = after
        self._generation = next_generation
        self._receipts[idempotency_key] = receipt
        self._fingerprints[idempotency_key] = fingerprint
        if lose_response:
            raise MigrationError("E_RESPONSE_LOST", message="response intentionally withheld after commit")
        return receipt

    def rollback(self, *, migration_id: str, plan: MigrationPlan, operation: MigrationOperation,
                 idempotency_key: str, expected_generation: int, current_ref: Mapping[str, Any],
                 guards: Mapping[str, Any], lose_response: bool = False) -> MigrationReceipt:
        """Apply the declared compensation as a new generation and operation."""
        if operation.compensation_ref is None:
            raise MigrationError("E_COMPENSATION", message="operation has no compensation")
        current = _ref(current_ref, "/current_ref")
        if current != operation.target_ref:
            raise MigrationError("E_ROLLBACK_USER_EDIT", message="current selection is not this operation postimage")
        inverse = MigrationOperation(
            operation_id=f"{operation.operation_id}:rollback", kind="switch_selection",
            target_ref=operation.compensation_ref, precondition_ref=operation.target_ref,
            compensation_ref=operation.target_ref,
        )
        receipt = self.apply(migration_id=migration_id, plan=plan, operation=inverse,
                             idempotency_key=idempotency_key, expected_generation=expected_generation,
                             before_ref=operation.target_ref, after_ref=operation.compensation_ref,
                             guards=guards, lose_response=lose_response, _allow_inverse=True)
        return MigrationReceipt(receipt.migration_id, receipt.operation_id, receipt.idempotency_key,
                                receipt.plan_sha256, receipt.from_generation, receipt.to_generation,
                                receipt.before_selection_ref, receipt.after_selection_ref, "ROLLED_BACK",
                                receipt.replayed, receipt.currently_selected, receipt.current_generation,
                                receipt.current_selection_ref)


def preflight_ref(preflight: MigrationPreflight) -> dict[str, Any]:
    if type(preflight) is not MigrationPreflight:
        raise MigrationError("E_PREFLIGHT", message="MigrationPreflight required")
    return {"kind": "migration-preflight", "id": preflight.migration_id, "sha256": preflight.digest}


def backup_ref(snapshot: BackupSnapshot) -> dict[str, Any]:
    if type(snapshot) is not BackupSnapshot:
        raise MigrationError("E_BACKUP", message="BackupSnapshot required")
    return {"kind": "backup-snapshot", "id": snapshot.backup_id, "sha256": snapshot.digest}


__all__ = [
    "BackupSnapshot", "HistoryIntegrityReport", "MigrationError", "MigrationLedger",
    "MigrationOperation", "MigrationPlan", "MigrationPreflight", "MigrationReceipt",
    "OPERATION_KINDS", "PREFLIGHT_STATUSES", "PreflightCheck", "REQUIRED_GUARDS",
    "backup_ref", "canonical_bytes", "compare_history_inventory", "create_backup_snapshot",
    "digest_bytes", "preflight_ref", "record_digest",
]
