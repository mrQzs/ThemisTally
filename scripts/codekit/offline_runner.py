"""Deterministic, offline-only command evidence for 08 regression/mutation checks.

The runner accepts explicit argv arrays and an explicit working directory.  It
does not invoke a shell, install packages, contact providers, or register a
dispatcher execution.  Its records therefore remain reference evidence until
the core dispatcher supplies a trusted receipt.
"""
from __future__ import annotations

from hashlib import sha256
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import monotonic
from typing import Any, Mapping, Sequence

from .builtin_artifacts import ArtifactError, canonical_bytes, resource_ref
from .deterministic_check import check_execution_id


def _err(code: str, message: str) -> None:
    raise ArtifactError(code, "/offline_runner", message)


def _digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def _identity(value: Any, name: str) -> str:
    if type(value) is not str or not value or len(value) > 256 or any(
            ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        _err("E_RUNNER_ID", f"{name} must be bounded text")
    return value


def _argv(command: Sequence[str]) -> list[str]:
    if isinstance(command, (str, bytes)) or not isinstance(command, Sequence) or not command:
        _err("E_RUNNER_ARGV", "command must be a non-empty argv sequence")
    for index, item in enumerate(command):
        # Empty arguments after argv[0] are meaningful and must survive the
        # shell-free adapter.  The executable itself remains non-empty.
        if type(item) is not str or (index == 0 and not item):
            _err("E_RUNNER_ARGV", "argv[0] must be a non-empty string")
        if "\x00" in item or any(0xD800 <= ord(ch) <= 0xDFFF for ch in item):
            _err("E_RUNNER_ARGV", "argv contains NUL or a non-Unicode scalar")
        if index == 0 and ("\r" in item or "\n" in item):
            _err("E_RUNNER_ARGV", "executable contains a line break")
    return list(command)


def _workspace_path(cwd: str | Path, relative: str | Path | None = None) -> tuple[Path, Path | None]:
    try:
        root = Path(cwd).resolve()
    except (TypeError, ValueError, OSError):
        _err("E_RUNNER_CWD", "working directory must be a valid path")
    if not root.is_dir():
        _err("E_RUNNER_CWD", "working directory must exist")
    if relative is None:
        return root, None
    try:
        candidate = (root / Path(relative)).resolve()
    except (TypeError, ValueError, OSError):
        _err("E_RUNNER_PATH", "target path must be a valid relative path")
    try:
        candidate.relative_to(root)
    except ValueError:
        _err("E_RUNNER_PATH", "target path escapes working directory")
    if not candidate.is_file():
        _err("E_RUNNER_PATH", "target path must be an existing file")
    return root, candidate


def _environment_digest(*, cwd: Path, env: Mapping[str, str]) -> str:
    payload = {
        "cwd": str(cwd),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "env": {str(key): str(env[key]) for key in sorted(env)},
    }
    return _digest(canonical_bytes(payload))


def _safe_environment(overrides: Mapping[str, str]) -> dict[str, str]:
    """Keep only explicit runtime basics; never pass the ambient environment wholesale."""
    if not isinstance(overrides, Mapping):
        _err("E_RUNNER_ENV", "environment overrides must be a mapping")
    blocked = ("TOKEN", "KEY", "SECRET", "PASSWORD", "CREDENTIAL", "COOKIE", "AUTH")
    if any(type(key) is not str or type(value) is not str for key, value in overrides.items()):
        _err("E_RUNNER_ENV", "environment names and values must be strings")
    if any(any(ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF
               for ch in key + value)
           for key, value in overrides.items()):
        _err("E_RUNNER_ENV", "environment names and values must be safe text")
    unsafe_overrides = [key for key in overrides if any(part in key.upper() for part in blocked)]
    if unsafe_overrides:
        _err("E_RUNNER_ENV", "credential-like environment overrides are forbidden")
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE",
               "LANG", "LC_ALL", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PYTHONIOENCODING"}
    # Environment names are intentionally case-sensitive here.  Accepting
    # ``path`` on POSIX while retaining ambient ``PATH`` would produce two
    # different runtime values and an ambiguous digest.
    invalid_overrides = [key for key in overrides if key not in allowed]
    if invalid_overrides:
        _err("E_RUNNER_ENV", "environment override is not allowlisted")
    canonical_names = {key.upper(): key for key in allowed}
    result: dict[str, str] = {}
    for key, value in os.environ.items():
        canonical = canonical_names.get(key.upper())
        if canonical is not None and canonical not in result:
            result[canonical] = value
    result.update(overrides)
    return result


def _status(returncode: int | None, *, timed_out: bool, error: str | None) -> tuple[str, str | None]:
    if timed_out:
        return "BLOCKED", "TIMEOUT"
    if error:
        return "BLOCKED", error
    if returncode == 0:
        return "PASS", None
    return "FAIL", "NONZERO_EXIT"


def run_command(*, target: str, command: Sequence[str], cwd: str | Path,
                check_plan_id: str, candidate_digest: str,
                environment_digest: str | None = None,
                environment: Mapping[str, str] | None = None,
                target_path: str | Path | None = None,
                candidate_ref: Mapping[str, str] | None = None,
                timeout_seconds: float = 30.0) -> dict[str, Any]:
    """Run one explicit local command and return a closed evidence record."""
    if type(target) is not str or not target or any(
            ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF for ch in target):
        _err("E_RUNNER_TARGET", "target is required")
    argv = _argv(command)
    _identity(check_plan_id, "check_plan_id")
    _identity(candidate_digest, "candidate_digest")
    if type(timeout_seconds) not in (int, float) or not math.isfinite(float(timeout_seconds)) or timeout_seconds <= 0:
        _err("E_RUNNER_TIMEOUT", "positive timeout required")
    if environment is not None and not isinstance(environment, Mapping):
        _err("E_RUNNER_ENV", "environment overrides must be a mapping")
    env_overrides = {} if environment is None else dict(environment)
    env = _safe_environment(env_overrides)
    if any(not k or "=" in k for k in env):
        _err("E_RUNNER_ENV", "environment names must be non-empty")
    root, path = _workspace_path(cwd, target_path)
    normalized_candidate_ref = None
    if candidate_ref is not None:
        try:
            normalized_candidate_ref = resource_ref(candidate_ref, "/candidate_ref")
        except ArtifactError as exc:
            _err("E_RUNNER_CANDIDATE", str(exc))
        if normalized_candidate_ref["sha256"] != candidate_digest:
            _err("E_RUNNER_CANDIDATE", "candidate_ref sha256 differs from candidate_digest")
    env_digest = _environment_digest(cwd=root, env=env)
    if environment_digest is not None and environment_digest != env_digest:
        _err("E_RUNNER_ENV", "environment digest differs from the actual runtime environment")
    target_bytes_digest = _digest(path.read_bytes()) if path is not None else _digest(target.encode("utf-8"))
    execution_id = check_execution_id(check_plan_id=check_plan_id, candidate_digest=candidate_digest,
                                      environment_digest=env_digest)
    runner_identity = f"offline-subprocess:{platform.system().lower()}:{sys.executable}:{sys.version.split()[0]}"
    started = monotonic()
    stdout = b""
    stderr = b""
    returncode: int | None = None
    error: str | None = None
    timed_out = False
    try:
        completed = subprocess.run(argv, cwd=root, env=env, shell=False,
                                   capture_output=True, timeout=float(timeout_seconds), check=False)
        returncode, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
    except (FileNotFoundError, PermissionError, OSError) as exc:
        error = type(exc).__name__
    duration_ms = int((monotonic() - started) * 1000)
    status, reason = _status(returncode, timed_out=timed_out, error=error)
    failure_class = None
    if status == "FAIL":
        text = stderr.decode("utf-8", errors="replace")
        failure_class = "SYNTAX" if "SyntaxError" in text else "IMPORT" if "ImportError" in text or "ModuleNotFoundError" in text else "COMMAND"
    return {
        "execution_mode": "deterministic_check",
        "check_execution_id": execution_id,
        "check_plan_id": check_plan_id,
        "candidate_digest": candidate_digest,
        "candidate_ref": normalized_candidate_ref,
        "environment_digest": env_digest,
        "target": target,
        "command": argv,
        "runner_identity": runner_identity,
        "target_bytes_sha256": target_bytes_digest,
        "status": status,
        "returncode": returncode,
        "stdout_sha256": _digest(stdout),
        "stderr_sha256": _digest(stderr),
        "duration_ms": duration_ms,
        "reason": reason,
        "failure_class": failure_class,
    }


def run_repeated(*, repeat: int = 1, **kwargs: Any) -> dict[str, Any]:
    if type(repeat) is not int or repeat < 1 or repeat > 20:
        _err("E_RUNNER_REPEAT", "repeat must be between 1 and 20")
    records = [run_command(**kwargs) for _ in range(repeat)]
    statuses = [row["status"] for row in records]
    # A repeated check is deterministic only when its observable evidence is
    # identical.  Duration is expected to vary, but output/error hashes,
    # return code and failure classification must not be reduced to a status
    # vote (which would hide a flaky command that always exits zero).
    def stable_key(row: Mapping[str, Any]) -> bytes:
        return canonical_bytes({key: value for key, value in row.items() if key != "duration_ms"})
    stable = len({stable_key(row) for row in records}) == 1 and len(set(statuses)) == 1
    status = statuses[0] if stable else "BLOCKED"
    return {"status": status, "flaky": not stable, "runs": records}


def run_mutation_commands(*, baseline: Mapping[str, Any], mutations: Sequence[Mapping[str, Any]],
                          repeat: int = 1) -> dict[str, Any]:
    """Run a baseline and explicit mutant commands; no best-of reduction."""
    if not isinstance(baseline, Mapping) or not isinstance(mutations, Sequence) or isinstance(mutations, (str, bytes)) or not mutations:
        _err("E_MUTATION_RUN", "baseline and mutation commands are required")
    mutation_ids = [mutation.get("id") if isinstance(mutation, Mapping) else None for mutation in mutations]
    if any(type(value) is not str or not value for value in mutation_ids) or len(set(mutation_ids)) != len(mutation_ids):
        _err("E_MUTATION_RUN", "mutation ids must be unique non-empty strings")
    command_fields = {"target", "command", "cwd", "check_plan_id", "candidate_digest", "environment_digest",
                      "environment", "target_path", "candidate_ref", "timeout_seconds"}
    required_fields = {"target", "command", "cwd", "check_plan_id", "candidate_digest"}
    for item in [baseline, *mutations]:
        if not isinstance(item, Mapping) or set(item) - command_fields - {"id"} or not required_fields.issubset(item):
            _err("E_MUTATION_RUN", "closed baseline and mutation command records are required")
    if "id" in baseline:
        _err("E_MUTATION_RUN", "baseline must not have a mutation id")
    baseline_result = run_repeated(repeat=repeat, **dict(baseline))
    rows = []
    for mutation in sorted(mutations, key=lambda row: row.get("id", "")):
        if not isinstance(mutation, Mapping) or type(mutation.get("id")) is not str or not mutation["id"]:
            _err("E_MUTATION_RUN", "mutation id is required")
        result = run_repeated(repeat=repeat, **{k: v for k, v in mutation.items() if k != "id"})
        rows.append({"id": mutation["id"], "status": result["status"], "flaky": result["flaky"], "runs": result["runs"]})
    baseline_status = baseline_result["status"]
    if baseline_status != "PASS":
        outcome = "BLOCKED" if baseline_status in {"BLOCKED", "NOT_RUN"} else "FAIL"
    elif any(row["flaky"] or row["status"] in {"BLOCKED", "NOT_RUN"} for row in rows):
        outcome = "BLOCKED"
    elif any(row["status"] == "PASS" for row in rows):
        outcome = "FAIL"
    elif all(row["status"] == "FAIL" for row in rows):
        outcome = "PASS"
    else:
        outcome = "NOT_RUN"
    return {"outcome": outcome, "baseline": baseline_result, "results": rows,
            "policy": "baseline_pass_and_every_mutation_fail", "execution_mode": "deterministic_check"}


__all__ = ["run_command", "run_mutation_commands", "run_repeated"]
