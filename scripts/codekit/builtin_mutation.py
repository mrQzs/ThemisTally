"""Controlled mutation plans and deterministic reduction rules."""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping, Sequence
from .builtin_artifacts import ArtifactError, validate_artifact

_ALLOWED = {"FAIL", "PASS", "BLOCKED", "NOT_RUN"}

def _err(code: str, msg: str) -> None:
    raise ArtifactError(code, "/mutation", msg)

def build_mutation_plan(mutations: Sequence[Mapping[str, Any]], *, baseline_id: str) -> dict[str, Any]:
    if type(baseline_id) is not str or not baseline_id:
        _err("E_MUTATION_PLAN", "baseline_id required")
    if not isinstance(mutations, Sequence) or isinstance(mutations, (str, bytes)) or not mutations:
        _err("E_MUTATION_PLAN", "at least one mutation required")
    rows = []
    ids = set()
    for row in mutations:
        if not isinstance(row, Mapping) or set(row) != {"id", "path", "description"}:
            _err("E_MUTATION_PLAN", "mutation rows are closed id/path/description objects")
        if any(type(row[k]) is not str or not row[k] for k in row):
            _err("E_MUTATION_PLAN", "mutation fields must be non-empty strings")
        if row["id"] in ids or row["path"].replace("\\", "/").startswith("/") or ".." in row["path"].replace("\\", "/").split("/"):
            _err("E_MUTATION_PLAN", "duplicate id or unsafe path")
        ids.add(row["id"]); rows.append(dict(row))
    rows.sort(key=lambda x: x["id"])
    return {"baseline_id": baseline_id, "mutations": rows, "policy": "baseline_pass_and_every_valid_mutation_fail"}

def reduce_mutation_results(plan: Mapping[str, Any], baseline_status: str, results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(plan, Mapping) or set(plan) != {"baseline_id", "mutations", "policy"} or plan["policy"] != "baseline_pass_and_every_valid_mutation_fail":
        _err("E_MUTATION_PLAN", "invalid mutation plan")
    if baseline_status not in _ALLOWED:
        _err("E_MUTATION_RESULT", "invalid baseline status")
    wanted = {row["id"] for row in plan["mutations"]}
    got: dict[str, str] = {}
    for row in results:
        if not isinstance(row, Mapping) or set(row) != {"id", "status"} or row["id"] not in wanted or row["status"] not in _ALLOWED:
            _err("E_MUTATION_RESULT", "invalid mutation result")
        if row["id"] in got:
            _err("E_MUTATION_RESULT", "duplicate mutation result")
        got[row["id"]] = row["status"]
    if baseline_status != "PASS":
        outcome = "BLOCKED" if baseline_status in {"BLOCKED", "NOT_RUN"} else "FAIL"
    elif set(got) != wanted:
        outcome = "NOT_RUN"
    elif any(status in {"PASS"} for status in got.values()):
        outcome = "FAIL"
    elif any(status in {"BLOCKED", "NOT_RUN"} for status in got.values()):
        outcome = "BLOCKED"
    else:
        outcome = "PASS"
    return {"outcome": outcome, "baseline_status": baseline_status,
            "results": deepcopy(dict(sorted(got.items()))),
            "surviving": sorted(k for k,v in got.items() if v == "PASS"),
            "unavailable": sorted(k for k,v in got.items() if v in {"BLOCKED", "NOT_RUN"})}

def build_mutation_artifact(*, artifact_id: str, producer: Mapping[str, str], candidate_ref: Mapping[str, str] | None,
                            environment_ref: Mapping[str, str] | None, source_refs: Sequence[Mapping[str, str]],
                            plan: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    return validate_artifact({"record_type": "mutation-review", "schema_version": 1, "artifact_id": artifact_id,
      "producer": dict(producer), "status": summary["outcome"], "source_refs": list(source_refs),
      "candidate_ref": candidate_ref, "environment_ref": environment_ref,
      "payload": {"plan": deepcopy(dict(plan)), "summary": deepcopy(dict(summary))}})

__all__ = ["build_mutation_artifact", "build_mutation_plan", "reduce_mutation_results"]
