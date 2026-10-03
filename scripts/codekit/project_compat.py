"""Explicitly registered compatibility loader for historical project state."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from . import protocols


class LegacyCompatibilityError(ValueError):
    def __init__(self, code: str, message: str = "legacy compatibility rejected") -> None:
        self.code = code
        super().__init__(message)


def load_registered_legacy_state(path: str | Path, *, registration: Mapping[str, Any]) -> dict[str, Any]:
    """Read a historical state only when an explicit byte registration exists."""
    required = {"source_class", "registered", "sha256"}
    if set(registration) != required or registration.get("source_class") != "legacy" or registration.get("registered") is not True:
        raise LegacyCompatibilityError("E_LEGACY_REGISTRATION", "legacy source requires explicit registration")
    expected = registration.get("sha256")
    if type(expected) is not str or len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise LegacyCompatibilityError("E_LEGACY_REGISTRATION", "legacy sha256 is invalid")
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise LegacyCompatibilityError("E_LEGACY_MISSING", "legacy state unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != expected:
        raise LegacyCompatibilityError("E_LEGACY_DRIFT", "legacy bytes changed")
    try:
        value = protocols.strict_json_loads(raw)
    except protocols.ProtocolError as exc:
        raise LegacyCompatibilityError("E_LEGACY_JSON", "legacy state is not strict JSON") from exc
    if type(value) is not dict:
        raise LegacyCompatibilityError("E_LEGACY_STATE", "legacy state object required")
    return value


__all__ = ["LegacyCompatibilityError", "load_registered_legacy_state"]
