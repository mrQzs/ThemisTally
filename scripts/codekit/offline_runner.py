"""Deterministic, offline-only command evidence for 08 regression/mutation checks.

The runner accepts explicit argv arrays and an explicit working directory.  It
does not invoke a shell, install packages, contact providers, or register a
dispatcher execution.  Its records therefore remain reference evidence until
the core dispatcher supplies a trusted receipt.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import monotonic
from typing import Any, Mapping, Sequence

from .builtin_artifacts import ArtifactError, canonical_bytes
from .deterministic_check import check_execution_id


def _err(code: str, message: str) -> None:
    raise ArtifactError(code, "/offline_runner", message)


def _digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def _argv(command: Sequence[str]) -> list[str]:
    if isinstance(command, (str, bytes)) or not isinstance(command, Sequence) or not command:
        _err("E_RUNNER_ARGV", "command must be a non-empty argv sequence")
    if any(type(item) is not str or not item for item in command):
        _err("E_RUNNER_ARGV", "argv entries must be non-empty strings")
    return list(command)


def _workspace_path(cwd: str | Path, relative: str | Path | None = None) -> tuple[Path, Path | None]:
    root = Path(cwd).resolve()
    if not root.is_dir():
        _err("E_RUNNER_CWD", "working directory must exist")
    if relative is None:
        return root, None
    candidate = (root / Path(relative)).resolve()
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
    blocked = ("TOKEN", "KEY", "SECRET", "PASSWORD", "CREDENTIAL", "COOKIE", "AUTH")
    unsafe_overrides = [key for key in overrides if any(part in key.upper() for part in blocked)]
    if unsafe_overrides:
        _err("E_RUNNER_ENV", "credential-like environment overrides are forbidden")
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE",
               "LANG", "LC_ALL", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PYTHONIOENCODING"}
    result = {key: value for key, value in os.environ.items() if key.upper() in allowed}
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
    if type(target) is not str or not target:
        _err("E_RUNNER_TARGET", "target is required")
    argv = _argv(command)
    if type(check_plan_id) is not str or not check_plan_id or type(candidate_digest) is not str or not candidate_digest:
        _err("E_RUNNER_ID", "check plan and candidate digest are required")
    if type(timeout_seconds) not in (int, float) or timeout_seconds <= 0:
        _err("E_RUNNER_TIMEOUT", "positive timeout required")
    env_overrides = {str(k): str(v) for k, v in (environment or {}).items()}
    env = _safe_environment(env_overrides)
    if any(not k or "=" in k for k in env):
        _err("E_RUNNER_ENV", "environment names must be non-empty")
    root, path = _workspace_path(cwd, target_path)
    env_digest = environment_digest or _environment_digest(cwd=root, env=env)
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
        "candidate_ref": dict(candidate_ref) if candidate_ref is not None else None,
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
    stable = len(set(statuses)) == 1
    status = statuses[0] if stable else "BLOCKED"
    return {"status": status, "flaky": not stable, "runs": records}


def run_mutation_commands(*, baseline: Mapping[str, Any], mutations: Sequence[Mapping[str, Any]],
                          repeat: int = 1) -> dict[str, Any]:
    """Run a baseline and explicit mutant commands; no best-of reduction."""
    if not isinstance(baseline, Mapping) or not isinstance(mutations, Sequence) or isinstance(mutations, (str, bytes)):
        _err("E_MUTATION_RUN", "baseline and mutation commands are required")
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
