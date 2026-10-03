"""Deterministic regression target collection for built-in task plugins.

This is an offline artifact builder.  It records test selection semantics and
never executes a command or grants a dispatch decision.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, Sequence

from .builtin_artifacts import ArtifactError, validate_artifact

_ALLOWED_RESULT = {"PASS", "FAIL", "SKIP", "XFAIL", "XPASS", "BLOCKED", "NOT_RUN"}


def _err(code: str, message: str) -> None:
    raise ArtifactError(code, "/regression", message)


def collect_targets(spec: Mapping[str, Any], available: Iterable[str] | None = None) -> dict[str, Any]:
    """Normalize a closed target spec into a deterministic selection record.

    ``available`` is an optional offline inventory.  Unknown targets become
    ``NOT_RUN`` rather than being silently invented.
    """
    if not isinstance(spec, Mapping) or set(spec) - {"targets", "skip", "xfail"}:
        _err("E_REGRESSION_SPEC", "unknown fields in target spec")
    targets = spec.get("targets", [])
    if not isinstance(targets, list) or any(type(x) is not str or not x for x in targets):
        _err("E_REGRESSION_SPEC", "targets must be a list of non-empty strings")
    if len(set(targets)) != len(targets):
        _err("E_REGRESSION_SPEC", "duplicate target")
    skip = spec.get("skip", [])
    xfail = spec.get("xfail", [])
    for name, values in (("skip", skip), ("xfail", xfail)):
        if not isinstance(values, list) or any(type(x) is not str or not x for x in values):
            _err("E_REGRESSION_SPEC", f"{name} must be a list of non-empty strings")
        if len(set(values)) != len(values):
            _err("E_REGRESSION_SPEC", f"duplicate {name} target")
    all_names = sorted(set(targets))
    if set(skip) & set(xfail) or set(skip) - set(all_names) or set(xfail) - set(all_names):
        _err("E_REGRESSION_SPEC", "skip/xfail target must be declared in targets")
    if available is not None:
        if isinstance(available, (str, bytes)):
            _err("E_REGRESSION_SPEC", "available inventory must be an iterable of names")
        try:
            available_values = list(available)
        except TypeError as exc:
            raise ArtifactError("E_REGRESSION_SPEC", "/regression", "available inventory must be iterable") from exc
        if any(type(name) is not str or not name for name in available_values):
            _err("E_REGRESSION_SPEC", "available inventory names must be non-empty strings")
        inventory = set(available_values)
    else:
        inventory = None
    selected = [x for x in all_names if x not in set(skip) and x not in set(xfail)]
    missing = [] if inventory is None else [x for x in selected if x not in inventory]
    return {
        "targets": all_names,
        "selected": selected,
        "skipped": sorted(set(skip)),
        "expected_failures": sorted(set(xfail)),
        "missing": missing,
        "zero_tests": len(all_names) == 0,
    }


def summarize_results(plan: Mapping[str, Any], results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Reduce target results with explicit skip/xfail/zero-test semantics."""
    if not isinstance(plan, Mapping) or set(plan) != {"targets", "selected", "skipped", "expected_failures", "missing", "zero_tests"}:
        _err("E_REGRESSION_PLAN", "invalid target plan")
    targets = plan["targets"]
    if (not isinstance(targets, list) or targets != sorted(set(targets)) or
            any(type(name) is not str or not name for name in targets)):
        _err("E_REGRESSION_PLAN", "targets are not canonical")
    if (not isinstance(plan.get("selected"), list) or not isinstance(plan["skipped"], list)
            or not isinstance(plan["expected_failures"], list) or not isinstance(plan["missing"], list)
            or type(plan.get("zero_tests")) is not bool):
        _err("E_REGRESSION_PLAN", "derived arrays are required")
    for field in ("skipped", "expected_failures", "missing"):
        values = plan[field]
        if any(type(name) is not str or not name for name in values):
            _err("E_REGRESSION_PLAN", "derived arrays contain invalid target")
        if values != sorted(set(values)):
            _err("E_REGRESSION_PLAN", "derived arrays are not canonical")
    if any(name not in targets for name in plan["skipped"] + plan["expected_failures"] + plan["missing"]):
        _err("E_REGRESSION_PLAN", "derived target is unknown")
    if set(plan["skipped"]) & set(plan["expected_failures"]):
        _err("E_REGRESSION_PLAN", "skip and xfail overlap")
    expected_selected = sorted(set(targets) - set(plan["skipped"]) - set(plan["expected_failures"]))
    if plan["selected"] != expected_selected or plan["zero_tests"] is not (len(targets) == 0):
        _err("E_REGRESSION_PLAN", "derived selection is not canonical")
    if len(set(plan["missing"])) != len(plan["missing"]) or any(name not in expected_selected for name in plan["missing"]):
        _err("E_REGRESSION_PLAN", "missing target list is invalid")
    expected = set(plan["targets"])
    seen: dict[str, str] = {}
    if not isinstance(results, Sequence) or isinstance(results, (str, bytes)):
        _err("E_REGRESSION_RESULT", "result sequence required")
    for row in results:
        if not isinstance(row, Mapping) or set(row) != {"target", "status"}:
            _err("E_REGRESSION_RESULT", "result rows are closed target/status objects")
        target, status = row["target"], row["status"]
        if type(target) is not str or target not in expected or type(status) is not str or status not in _ALLOWED_RESULT:
            _err("E_REGRESSION_RESULT", "unknown target or status")
        if target in seen:
            _err("E_REGRESSION_RESULT", "duplicate target result")
        seen[target] = status
    missing_results = sorted(expected - set(seen))
    failures = sorted(name for name, status in seen.items() if status in {"FAIL", "XPASS"})
    blocked = sorted(name for name, status in seen.items() if status in {"BLOCKED", "NOT_RUN"})
    selected = set(plan["selected"])
    expected_failures = set(plan["expected_failures"])
    bad_xfail = sorted(name for name in expected_failures if seen.get(name) != "XFAIL")
    bad_skip = sorted(name for name in set(plan["skipped"]) if seen.get(name) not in {"SKIP", None})
    unexpected_pass = sorted(name for name in expected_failures if seen.get(name) == "PASS")
    if plan["zero_tests"]:
        outcome = "NOT_RUN"
    elif missing_results or plan["missing"] or blocked:
        outcome = "NOT_RUN" if not failures else "FAIL"
    elif failures or bad_xfail or bad_skip or unexpected_pass:
        outcome = "FAIL"
    elif selected and all(seen.get(name) == "PASS" for name in selected):
        outcome = "PASS"
    else:
        outcome = "NOT_RUN"
    return {"outcome": outcome, "results": deepcopy(dict(sorted(seen.items()))),
            "missing_results": missing_results, "failures": failures,
            "blocked": blocked, "bad_xfail": bad_xfail,
            "unexpected_pass": unexpected_pass}


def build_regression_artifact(*, artifact_id: str, producer: Mapping[str, str], candidate_ref: Mapping[str, str] | None,
                              environment_ref: Mapping[str, str] | None, source_refs: Sequence[Mapping[str, str]],
                              plan: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(summary, Mapping) or set(summary) != {"outcome", "results", "missing_results", "failures", "blocked", "bad_xfail", "unexpected_pass"}:
        _err("E_REGRESSION_RESULT", "closed regression summary required")
    if not isinstance(summary["results"], Mapping):
        _err("E_REGRESSION_RESULT", "regression result map required")
    if type(summary.get("outcome")) is not str:
        _err("E_REGRESSION_RESULT", "regression outcome must be text")
    rows = [{"target": key, "status": value} for key, value in summary["results"].items()]
    expected = summarize_results(plan, rows)
    if dict(summary) != expected:
        _err("E_REGRESSION_RESULT", "regression summary does not match plan results")
    outcome = summary["outcome"]
    record_status = "REFERENCE_ONLY" if outcome == "PASS" else outcome
    record = {"record_type": "regression-plan", "schema_version": 1, "artifact_id": artifact_id,
              "producer": dict(producer), "status": record_status, "source_refs": list(source_refs),
              "candidate_ref": candidate_ref, "environment_ref": environment_ref,
              "payload": {"plan": deepcopy(dict(plan)), "summary": deepcopy(dict(summary))}}
    return validate_regression_artifact(record)


def validate_regression_artifact(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a regression artifact by replaying its target reduction.

    ``validate_artifact`` only knows the closed envelope.  A caller loading a
    persisted record must also prove that its plan, result rows and derived
    outcome still agree; otherwise an edited summary could look like a valid
    reference-only result.
    """
    normalized = validate_artifact(record)
    if normalized["record_type"] != "regression-plan":
        _err("E_REGRESSION_PLAN", "regression-plan artifact required")
    payload = normalized["payload"]
    if set(payload) != {"plan", "summary"} or not isinstance(payload["plan"], Mapping) or not isinstance(payload["summary"], Mapping):
        _err("E_REGRESSION_RESULT", "closed regression artifact payload required")
    summary = payload["summary"]
    required = {"outcome", "results", "missing_results", "failures", "blocked", "bad_xfail", "unexpected_pass"}
    if set(summary) != required or not isinstance(summary["results"], Mapping):
        _err("E_REGRESSION_RESULT", "closed regression summary required")
    rows = [{"target": key, "status": value} for key, value in summary["results"].items()]
    expected = summarize_results(payload["plan"], rows)
    if dict(summary) != expected:
        _err("E_REGRESSION_RESULT", "regression summary does not match plan results")
    expected_status = "REFERENCE_ONLY" if expected["outcome"] == "PASS" else expected["outcome"]
    if normalized["status"] != expected_status:
        _err("E_REGRESSION_STATUS", "artifact status does not match regression outcome")
    return normalized


__all__ = ["build_regression_artifact", "collect_targets", "summarize_results", "validate_regression_artifact"]
