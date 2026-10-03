"""Deterministic bounded source scanning for the 10 recovery pipeline."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Any

from .project_events import canonical_bytes
from .project_sources import SourceVerificationError


class SourceScanError(ValueError):
    def __init__(self, code: str, message: str = "source scan rejected") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class SourceScanReport:
    scan_id: str
    complete: bool
    cutoff_ns: int
    max_entries: int
    items: tuple[dict[str, Any], ...]
    issues: tuple[str, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {"scan_id": self.scan_id, "complete": self.complete, "cutoff_ns": self.cutoff_ns,
                "max_entries": self.max_entries, "items": [dict(x) for x in self.items],
                "issues": list(self.issues)}


def scan_source_tree(root: str | Path, *, cutoff_ns: int, max_entries: int = 1000,
                     kind: str = "fixture-source") -> SourceScanReport:
    if type(cutoff_ns) is not int or cutoff_ns < 0:
        raise SourceScanError("E_CUTOFF", "non-negative cutoff_ns required")
    if type(max_entries) is not int or not 1 <= max_entries <= 100_000:
        raise SourceScanError("E_LIMIT", "bounded max_entries required")
    root_path = Path(root)
    try:
        root_resolved = root_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SourceScanError("E_ROOT", "source root unavailable") from exc
    if not root_resolved.is_dir():
        raise SourceScanError("E_ROOT", "source root must be a directory")
    items: list[dict[str, Any]] = []
    issues: list[str] = []
    truncated = False

    def visit(directory: Path, relative: str) -> None:
        nonlocal truncated
        if truncated:
            return
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except PermissionError:
            issues.append("access_denied:" + relative); return
        except OSError:
            issues.append("read_incomplete:" + relative); return
        for entry in entries:
            if len(items) >= max_entries:
                truncated = True
                issues.append("entry_limit")
                return
            rel = entry.name if not relative else relative + "/" + entry.name
            path = Path(entry.path)
            try:
                if entry.is_symlink():
                    issues.append("symlink:" + rel); continue
                if entry.is_dir(follow_symlinks=False):
                    visit(path, rel); continue
                if not entry.is_file(follow_symlinks=False):
                    issues.append("unsupported:" + rel); continue
                stat = entry.stat(follow_symlinks=False)
                if stat.st_mtime_ns > cutoff_ns:
                    issues.append("after_cutoff:" + rel); continue
                raw = path.read_bytes()
            except PermissionError:
                issues.append("access_denied:" + rel); continue
            except OSError:
                issues.append("read_incomplete:" + rel); continue
            digest = hashlib.sha256(raw).hexdigest()
            items.append({"path": rel, "sha256": digest, "byte_length": len(raw),
                          "kind": kind, "id": "path:" + rel})

    visit(root_resolved, "")
    if issues:
        # A bounded or partial walk is evidence, but not a complete snapshot.
        complete = False
    else:
        complete = True
    body = {"cutoff_ns": cutoff_ns, "max_entries": max_entries,
            "items": items, "issues": issues}
    scan_id = hashlib.sha256(canonical_bytes(body)).hexdigest()
    return SourceScanReport(scan_id, complete, cutoff_ns, max_entries,
                            tuple(items), tuple(issues))


__all__ = ["SourceScanError", "SourceScanReport", "scan_source_tree"]
