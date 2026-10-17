"""Durable idempotent storage for exact brief read receipts."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import protocols
from .project_journal import WriterLock
from .project_views import BriefReadReceipt


class ReadReceiptError(ValueError):
    def __init__(self, code: str, message: str = "read receipt rejected") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ReceiptAppend:
    receipt: BriefReadReceipt
    replayed: bool


class ReadReceiptStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise ReadReceiptError("E_RECEIPT_TAIL", "receipt log has truncated tail")
        result: dict[str, dict[str, Any]] = {}
        for line in raw.splitlines():
            try:
                value = protocols.strict_json_loads(line)
            except protocols.ProtocolError as exc:
                raise ReadReceiptError("E_RECEIPT_CORRUPT", "receipt log is not strict JSON") from exc
            if type(value) is not dict or value.get("record_type") != "brief-read-receipt":
                raise ReadReceiptError("E_RECEIPT_CORRUPT", "closed read receipt required")
            receipt_id = value.get("receipt_id")
            if type(receipt_id) is not str:
                raise ReadReceiptError("E_RECEIPT_CORRUPT", "receipt id missing")
            prior = result.get(receipt_id)
            if prior is not None and prior != value:
                raise ReadReceiptError("E_RECEIPT_CONFLICT", "receipt id reused with different bytes")
            result[receipt_id] = value
        return result

    def append(self, receipt: BriefReadReceipt) -> ReceiptAppend:
        if type(receipt) is not BriefReadReceipt:
            raise ReadReceiptError("E_RECEIPT", "BriefReadReceipt required")
        value = receipt.to_mapping()
        encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        with WriterLock(self.lock_path):
            rows = self._load()
            prior = rows.get(receipt.receipt_id)
            if prior is not None:
                if prior != value:
                    raise ReadReceiptError("E_RECEIPT_CONFLICT", "receipt id reused with different bytes")
                return ReceiptAppend(receipt, True)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("ab") as handle:
                handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
            return ReceiptAppend(receipt, False)


__all__ = ["ReadReceiptError", "ReadReceiptStore", "ReceiptAppend"]
