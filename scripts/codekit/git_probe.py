"""Git probe planning, bounded execution, and result interpretation for 07-T2B-G.

The layer accepts only a validated BaselineBinding and a separately trusted
repository identity.  The optional adapter executes only the fixed plan with
an injected or built-in runner, then returns an observation that keeps
verified, blocked, and unknown states distinct.  It never verifies
authorization, acceptance, content coverage, or currentness.
"""
from __future__ import annotations

import re
import os
import subprocess
import threading
from dataclasses import dataclass, replace
from types import MappingProxyType
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import protocols
from .baseline_binding import BaselineBinding, validate_baseline_binding

GIT_REDIRECT_VARS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX",
)
GIT_ENV_SET = (
    ("GIT_TERMINAL_PROMPT", "0"),
    ("GCM_INTERACTIVE", "never"),
    ("GIT_OPTIONAL_LOCKS", "0"),
    ("GIT_NO_REPLACE_OBJECTS", "1"),
    ("GIT_NO_LAZY_FETCH", "1"),
)
PROBE_OUTPUT_LIMIT = 1_048_576
PROBE_TIMEOUT_SECONDS = 30
LFS_SCAN_LIMIT = 1_048_576
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"

META = "repo_meta"
BASE_TYPE = "base_type"
BASE_BODY = "base_body"
TREE_TYPE = "tree_type"
REPLACEMENTS = "replacement_refs"
GRAFTS = "grafts_path"
PARTIAL_CLONE = "partial_clone_config"
PROMISOR = "promisor_config"
ALTERNATES = "alternates_path"
TREE_ENTRIES = "tree_entries"
PROBE_COMMANDS = (
    META, BASE_TYPE, BASE_BODY, TREE_TYPE, REPLACEMENTS, GRAFTS,
    PARTIAL_CLONE, PROMISOR, ALTERNATES, TREE_ENTRIES,
)
@dataclass(frozen=True)
class TrustedRepositoryIdentity:
    """Enrollment supplied by a trusted layer; never derived from the binding."""

    repo_id: str
    environment_id: str
    worktree_root: str
    git_dir: str
    common_dir: str
    object_format: str
    identity_version: int = 1


@dataclass(frozen=True)
class ProbePlan:
    """Fixed argv and environment policy for the read-only adapter."""

    identity: TrustedRepositoryIdentity
    base_sha: str
    tree_sha: str
    commands: tuple[tuple[str, ...], ...]
    environment_remove: tuple[str, ...] = GIT_REDIRECT_VARS
    environment_set: tuple[tuple[str, str], ...] = GIT_ENV_SET
    timeout_seconds: int = PROBE_TIMEOUT_SECONDS
    max_output_bytes: int = PROBE_OUTPUT_LIMIT


@dataclass(frozen=True)
class RawResult:
    """Bounded runner output; stderr is deliberately ignored by the interpreter."""

    returncode: int | None
    stdout: bytes
    stderr: bytes = b""
    timed_out: bool = False
    truncated: bool = False
    path_exists: bool | None = None


ProbeRunner = Callable[[Sequence[str], str, Mapping[str, str], int, int], RawResult]


@dataclass(frozen=True)
class GitProbeObservation:
    """Local Git observation with separate verified, blocked, and unknown data."""

    facts: Mapping[str, bool | None]
    verified: bool
    blocked_reasons: tuple[str, ...]
    unknown_reasons: tuple[str, ...]
    authorization_verified: bool = False
    coverage_verified: bool = False


def build_probe_plan(binding: BaselineBinding | Mapping[str, Any],
                     identity: TrustedRepositoryIdentity) -> ProbePlan:
    """Build a fixed, shell-free command plan after binding/identity checks."""
    validated = binding if isinstance(binding, BaselineBinding) else validate_baseline_binding(binding)
    _validate_identity(identity)
    if validated.repo_id != identity.repo_id:
        _error("E_CONTEXT_BINDING", "/repo_id", "repository_identity_mismatch")
    if validated.environment_id != identity.environment_id:
        _error("E_CONTEXT_BINDING", "/environment_id", "environment_identity_mismatch")
    if validated.object_format != identity.object_format:
        _error("E_CONTEXT_BINDING", "/object_format", "object_format_identity_mismatch")

    commands = _probe_commands(identity, validated.base_sha, validated.tree_sha)
    return ProbePlan(identity, validated.base_sha, validated.tree_sha, commands)


def build_git_env(source: Mapping[str, str]) -> dict[str, str]:
    """Return the probe environment policy without mutating the caller's env."""
    if not isinstance(source, Mapping):
        _error("E_SCHEMA_TYPE", "/environment", "mapping_required")
    result: dict[str, str] = {}
    for key, value in source.items():
        if type(key) is not str or type(value) is not str:
            _error("E_SCHEMA_TYPE", "/environment", "string_key_value_required")
        # Git has a large family of environment overrides. Keeping even a
        # non-redirect GIT_* variable (for example GIT_CONFIG_COUNT or
        # GIT_CONFIG_GLOBAL) lets the caller change object/config resolution.
        # The probe owns all Git policy and re-adds only the fixed settings.
        if key.upper().startswith("GIT_") or key.upper() == "GCM_INTERACTIVE":
            continue
        result[key] = value
    result.update(dict(GIT_ENV_SET))
    return result


def run_probe(plan: ProbePlan, *, runner: ProbeRunner | None = None,
              source_env: Mapping[str, str] | None = None) -> GitProbeObservation:
    """Run the fixed plan through a bounded, injectable, read-only runner.

    The default runner uses shell=False, an empty stdin, the enrolled worktree
    as cwd, and the environment policy from build_git_env. It never invokes
    fetch, checkout, or user-provided argv. The adapter does not resolve LFS,
    authorization, or coverage, so the resulting observation remains
    blocked/unknown until those facts arrive from a separate trusted layer.
    """
    if not isinstance(plan, ProbePlan):
        _error("E_SCHEMA_TYPE", "/plan", "probe_plan_required")
    _validate_probe_plan(plan)
    env = build_git_env(dict(os.environ) if source_env is None else source_env)
    execute = _run_subprocess if runner is None else runner
    results: dict[str, RawResult] = {}
    for name, argv in zip(PROBE_COMMANDS, plan.commands):
        result = execute(argv, plan.identity.worktree_root, env,
                         plan.timeout_seconds, plan.max_output_bytes)
        if not _raw_result_shape(result):
            _error("E_SCHEMA_TYPE", f"/results/{name}", "raw_result_required")
        if name in (GRAFTS, ALTERNATES):
            result = replace(result, path_exists=_path_exists_within_common_dir(
                result, plan.identity.common_dir))
        results[name] = result
    return interpret_probe(plan, results)


def interpret_probe(plan: ProbePlan, results: Mapping[str, RawResult], *, lfs_status: bool | None = None
                    ) -> GitProbeObservation:
    """Interpret bounded command results without executing or authorizing anything."""
    if not isinstance(plan, ProbePlan):
        _error("E_SCHEMA_TYPE", "/plan", "probe_plan_required")
    _validate_probe_plan(plan)
    if lfs_status is not None and type(lfs_status) is not bool:
        _error("E_SCHEMA_TYPE", "/lfs_status", "boolean_or_null_required")
    if not isinstance(results, Mapping):
        _error("E_SCHEMA_TYPE", "/results", "mapping_required")
    unknown_result_names = set(results) - set(PROBE_COMMANDS)
    if unknown_result_names:
        _error("E_SCHEMA_FIELDS", "/results", "unknown_probe_result")
    blocked: set[str] = set()
    unknown: set[str] = set()
    facts: dict[str, bool | None] = {
        "repository_identity_match": None,
        "object_format_match": None,
        "base_commit_present": None,
        "base_tree_present": None,
        "base_tree_matches_binding": None,
        "hazards_clear": None,
    }

    meta = _result(results, META, unknown)
    if meta is not None and _usable(meta):
        lines = _lines(meta.stdout)
        if lines is None or len(lines) != 6:
            unknown.add("repository_metadata_malformed")
        else:
            identity = plan.identity
            facts["repository_identity_match"] = (
                lines[0] == identity.worktree_root
                and lines[1] == identity.git_dir
                and lines[2] == identity.common_dir
            )
            facts["object_format_match"] = lines[3] == identity.object_format
            if not facts["repository_identity_match"]:
                blocked.add("repository_identity_mismatch")
            if not facts["object_format_match"]:
                blocked.add("object_format_mismatch")
            if lines[4] != "true":
                blocked.add("not_inside_worktree")
            if lines[5] == "true":
                blocked.add("shallow_repository")
            elif lines[5] != "false":
                unknown.add("shallow_status_unknown")
    else:
        unknown.add("repository_metadata_unavailable")

    base_type = _result(results, BASE_TYPE, unknown)
    if base_type is not None and _usable(base_type):
        facts["base_commit_present"] = base_type.returncode == 0 and base_type.stdout.rstrip(b"\r\n") == b"commit"
        if base_type.returncode != 0:
            blocked.add("base_commit_missing")
        elif not facts["base_commit_present"]:
            blocked.add("base_object_not_commit")

    base_body = _result(results, BASE_BODY, unknown)
    if base_body is not None and _usable(base_body):
        tree = _first_tree_oid(base_body.stdout, plan.identity.object_format)
        if tree is None:
            unknown.add("base_commit_tree_unreadable")
        else:
            facts["base_tree_matches_binding"] = tree == plan.tree_sha
            if not facts["base_tree_matches_binding"]:
                blocked.add("base_tree_mismatch")

    tree_type = _result(results, TREE_TYPE, unknown)
    if tree_type is not None and _usable(tree_type):
        facts["base_tree_present"] = tree_type.returncode == 0 and tree_type.stdout.rstrip(b"\r\n") == b"tree"
        if tree_type.returncode != 0:
            blocked.add("base_tree_missing")
        elif not facts["base_tree_present"]:
            blocked.add("base_object_not_tree")

    _interpret_ref_list(results, REPLACEMENTS, "replacement_refs_present", "replacement_probe_unknown", blocked, unknown)
    _interpret_config(results, PARTIAL_CLONE, "partial_clone_present", "partial_clone_probe_unknown", blocked, unknown)
    _interpret_config(results, PROMISOR, "promisor_config_present", "promisor_probe_unknown", blocked, unknown)
    _interpret_path(results, GRAFTS, "grafts_present", "grafts_probe_unknown", blocked, unknown)
    _interpret_path(results, ALTERNATES, "alternates_present", "alternates_probe_unknown", blocked, unknown)
    _interpret_tree_entries(results, blocked, unknown)

    if lfs_status is True:
        blocked.add("lfs_entries_present")
    elif lfs_status is None:
        unknown.add("lfs_status_unknown")

    hazard_names = {
        "replacement_refs_present", "partial_clone_present", "promisor_config_present", "grafts_present",
        "alternates_present", "submodule_gitlink_present", "gitmodules_present", "lfs_entries_present",
    }
    hazard_prefixes = (
        "replacement_", "partial_clone_", "promisor_", "grafts_", "alternates_",
        "tree_entries_", "shallow_", "lfs_",
    )
    hazard_unknown = {
        name for name in unknown
        if name == "lfs_status_unknown" or name.startswith(hazard_prefixes)
    }
    facts["hazards_clear"] = not (blocked & hazard_names) and not hazard_unknown
    if facts["hazards_clear"] is False:
        blocked.add("repository_hazard_detected") if blocked & hazard_names else None

    object_keys = ("repository_identity_match", "object_format_match", "base_commit_present",
                   "base_tree_present", "base_tree_matches_binding", "hazards_clear")
    verified = not blocked and not unknown and all(facts[key] is True for key in object_keys)
    return GitProbeObservation(MappingProxyType(dict(facts)), verified,
                               tuple(sorted(blocked)), tuple(sorted(unknown)))


def inspect_lfs_evidence(attributes: Mapping[str, bytes], blobs: Mapping[str, bytes], *, complete: bool,
                         max_bytes: int = LFS_SCAN_LIMIT) -> tuple[bool | None, tuple[str, ...]]:
    """Inspect bounded, caller-supplied Git blob bytes for LFS markers.

    The caller must obtain the exact blob set from the fixed base tree.  This
    function never invokes git-lfs and never treats an incomplete scan as a
    clean repository.  A positive marker blocks immediately; otherwise the
    result is clean only when the caller declares the scan complete.
    """
    if not isinstance(attributes, Mapping):
        _error("E_SCHEMA_TYPE", "/attributes", "mapping_required")
    if not isinstance(blobs, Mapping):
        _error("E_SCHEMA_TYPE", "/blobs", "mapping_required")
    if type(complete) is not bool:
        _error("E_SCHEMA_TYPE", "/complete", "boolean_required")
    protocols.require_int(max_bytes, field="/max_bytes", minimum=1)
    reasons: set[str] = set()
    for path, raw in attributes.items():
        if type(path) is not str or type(raw) is not bytes:
            reasons.add("lfs_attributes_unreadable")
            continue
        if len(raw) > max_bytes:
            reasons.add("lfs_attributes_oversize")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            reasons.add("lfs_attributes_unreadable")
            continue
        if re.search(r"(?m)(?:^|\s)filter=lfs(?:\s|$)", text):
            return True, ("lfs_filter_present",)

    for path, raw in blobs.items():
        if type(path) is not str or type(raw) is not bytes:
            reasons.add("lfs_blob_unreadable")
            continue
        if len(raw) > max_bytes:
            reasons.add("lfs_blob_oversize")
            continue
        if raw.startswith(LFS_POINTER_PREFIX):
            lines = raw.splitlines()
            if (len(lines) >= 3 and re.fullmatch(rb"oid sha256:[0-9a-f]{64}", lines[1])
                    and re.fullmatch(rb"size [0-9]+", lines[2])):
                return True, ("lfs_pointer_present",)
            reasons.add("lfs_pointer_malformed")

    if reasons:
        return None, tuple(sorted(reasons))
    if not complete:
        return None, ("lfs_scan_incomplete",)
    return False, ()


def _validate_identity(identity: TrustedRepositoryIdentity) -> None:
    if not isinstance(identity, TrustedRepositoryIdentity):
        _error("E_SCHEMA_TYPE", "/identity", "trusted_identity_required")
    protocols.validate_logical_id(identity.repo_id, field="/identity/repo_id")
    protocols.validate_logical_id(identity.environment_id, field="/identity/environment_id")
    if identity.object_format not in ("sha1", "sha256"):
        _error("E_GIT_FORMAT_UNSUPPORTED", "/identity/object_format", "object_format_unsupported")
    protocols.require_int(identity.identity_version, field="/identity/identity_version", minimum=1)
    for name in ("worktree_root", "git_dir", "common_dir"):
        value = getattr(identity, name)
        if type(value) is not str or not value or "\x00" in value:
            _error("E_SCHEMA_FIELDS", f"/identity/{name}", "nonempty_path_required")


def _result(results: Mapping[str, RawResult], name: str, unknown: set[str]) -> RawResult | None:
    value = results.get(name)
    if value is None:
        unknown.add(f"{name}_missing")
        return None
    if not isinstance(value, RawResult):
        unknown.add(f"{name}_invalid")
        return None
    return value


def _usable(result: RawResult) -> bool:
    if (result.timed_out or result.truncated or type(result.timed_out) is not bool
            or type(result.truncated) is not bool):
        return False
    if (result.returncode is not None and type(result.returncode) is not int):
        return False
    if type(result.stdout) is not bytes or type(result.stderr) is not bytes:
        return False
    return result.path_exists is None or type(result.path_exists) is bool


def _raw_result_shape(result: Any) -> bool:
    return (
        isinstance(result, RawResult)
        and (result.returncode is None or type(result.returncode) is int)
        and type(result.stdout) is bytes
        and type(result.stderr) is bytes
        and type(result.timed_out) is bool
        and type(result.truncated) is bool
        and (result.path_exists is None or type(result.path_exists) is bool)
    )


def _lines(raw: bytes) -> list[str] | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "\x00" in text:
        return None
    lines = text.splitlines()
    return lines if lines and all(line != "" for line in lines) else None


def _first_tree_oid(raw: bytes, object_format: str) -> str | None:
    lines = _lines(raw)
    if not lines:
        return None
    candidate = lines[0][5:] if lines[0].startswith("tree ") else lines[0]
    match = re.fullmatch(r"[0-9a-f]+", candidate)
    if match is None:
        return None
    try:
        return protocols.validate_git_oid(candidate, object_format, field="/tree_sha")
    except protocols.ProtocolError:
        return None


def _interpret_ref_list(results: Mapping[str, RawResult], name: str, present: str, unavailable: str,
                        blocked: set[str], unknown: set[str]) -> None:
    result = _result(results, name, unknown)
    if result is None:
        return
    if not _usable(result) or result.returncode != 0:
        unknown.add(unavailable)
        return
    if result.stdout not in (b"", b"\n", b"\r\n"):
        blocked.add(present)


def _interpret_config(results: Mapping[str, RawResult], name: str, present: str, unavailable: str,
                      blocked: set[str], unknown: set[str]) -> None:
    result = _result(results, name, unknown)
    if result is None:
        return
    if not _usable(result):
        unknown.add(unavailable)
        return
    if result.returncode not in (0, 1):
        unknown.add(unavailable)
    elif result.returncode == 0 and result.stdout.strip():
        blocked.add(present)


def _interpret_path(results: Mapping[str, RawResult], name: str, present: str, unavailable: str,
                    blocked: set[str], unknown: set[str]) -> None:
    result = _result(results, name, unknown)
    if result is None:
        return
    if (not _usable(result) or result.returncode != 0 or result.path_exists is None
            or type(result.path_exists) is not bool):
        unknown.add(unavailable)
    elif result.path_exists:
        blocked.add(present)


def _interpret_tree_entries(results: Mapping[str, RawResult], blocked: set[str], unknown: set[str]) -> None:
    result = _result(results, TREE_ENTRIES, unknown)
    if result is None:
        return
    if not _usable(result) or result.returncode != 0:
        unknown.add("tree_entries_probe_unknown")
        return
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        try:
            header, raw_path = entry.split(b"\t", 1)
            mode, _kind, _oid = header.split(b" ", 2)
            path = raw_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            unknown.add("tree_entries_malformed")
            return
        if mode == b"160000":
            blocked.add("submodule_gitlink_present")
        if path == ".gitmodules" or path.endswith("/.gitmodules"):
            blocked.add("gitmodules_present")


def _error(code: str, field: str, reason: str) -> None:
    raise protocols.ProtocolError(code, field=field, phase="git", reason=reason)


def _run_subprocess(argv: Sequence[str], cwd: str, env: Mapping[str, str],
                    timeout: int, max_output: int) -> RawResult:
    """Execute one fixed Git argv while retaining at most max_output per stream."""
    stdout_state: dict[str, Any] = {"data": bytearray(), "truncated": False}
    stderr_state: dict[str, Any] = {"data": bytearray(), "truncated": False}

    def drain(stream: Any, state: dict[str, Any]) -> None:
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                data = state["data"]
                remaining = max_output - len(data)
                if remaining > 0:
                    data.extend(chunk[:remaining])
                if len(chunk) > max(remaining, 0):
                    state["truncated"] = True
        except OSError:
            state["truncated"] = True

    try:
        process = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        stdout_thread = threading.Thread(target=drain, args=(process.stdout, stdout_state), daemon=True)
        stderr_thread = threading.Thread(target=drain, args=(process.stderr, stderr_state), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait()
        stdout_thread.join()
        stderr_thread.join()
        process.stdout.close()
        process.stderr.close()
    except (OSError, ValueError):
        return RawResult(None, b"", b"")
    stdout = bytes(stdout_state["data"])
    stderr = bytes(stderr_state["data"])
    return RawResult(None if timed_out else process.returncode, stdout, stderr,
                     timed_out=timed_out,
                     truncated=stdout_state["truncated"] or stderr_state["truncated"])


def _path_exists_within_common_dir(result: RawResult, common_dir: str) -> bool | None:
    """Resolve a git-path response without treating an outside path as safe."""
    if not _usable(result) or result.returncode != 0:
        return None
    lines = _lines(result.stdout)
    if lines is None or len(lines) != 1:
        return None
    try:
        # The fixed command asks Git for an absolute path. Resolving an
        # injected relative path against the adapter process cwd would make a
        # malformed runner result look like a safe in-repository path.
        if not os.path.isabs(lines[0]):
            return None
        target = os.path.realpath(lines[0])
        root = os.path.realpath(common_dir)
        if os.path.commonpath((target, root)) != root:
            return True
        return Path(target).exists()
    except (OSError, ValueError):
        return None


def _probe_commands(identity: TrustedRepositoryIdentity, base_sha: str, tree_sha: str
                    ) -> tuple[tuple[str, ...], ...]:
    prefix = ("git", "-C", identity.worktree_root)
    return (
        prefix + ("rev-parse", "--path-format=absolute", "--show-toplevel", "--git-dir",
                   "--git-common-dir", "--show-object-format=storage", "--is-inside-work-tree",
                   "--is-shallow-repository"),
        prefix + ("cat-file", "-t", base_sha),
        prefix + ("rev-parse", "--verify", "--quiet", "--end-of-options", f"{base_sha}^{{tree}}"),
        prefix + ("cat-file", "-t", tree_sha),
        prefix + ("replace", "-l"),
        prefix + ("rev-parse", "--path-format=absolute", "--git-path", "info/grafts"),
        prefix + ("config", "--get", "extensions.partialClone"),
        prefix + ("config", "--get-regexp", r"^remote\..*\.promisor$"),
        prefix + ("rev-parse", "--path-format=absolute", "--git-path", "objects/info/alternates"),
        prefix + ("ls-tree", "-r", "-z", "--full-tree", base_sha),
    )


def _validate_probe_plan(plan: ProbePlan) -> None:
    """Reject hand-built plans that bypass the fixed read-only command set."""
    _validate_identity(plan.identity)
    protocols.validate_git_oid(plan.base_sha, plan.identity.object_format, field="/plan/base_sha")
    protocols.validate_git_oid(plan.tree_sha, plan.identity.object_format, field="/plan/tree_sha")
    if type(plan.commands) is not tuple or plan.commands != _probe_commands(
            plan.identity, plan.base_sha, plan.tree_sha):
        _error("E_SCHEMA_FIELDS", "/plan/commands", "fixed_probe_commands_required")
    if plan.environment_remove != GIT_REDIRECT_VARS:
        _error("E_SCHEMA_FIELDS", "/plan/environment_remove", "fixed_environment_policy_required")
    if plan.environment_set != GIT_ENV_SET:
        _error("E_SCHEMA_FIELDS", "/plan/environment_set", "fixed_environment_policy_required")
    protocols.require_int(plan.timeout_seconds, field="/plan/timeout_seconds", minimum=1)
    protocols.require_int(plan.max_output_bytes, field="/plan/max_output_bytes", minimum=1)


__all__ = [
    "ALTERNATES", "BASE_BODY", "BASE_TYPE", "GIT_ENV_SET", "GIT_REDIRECT_VARS", "GRAFTS", "LFS_POINTER_PREFIX",
    "LFS_SCAN_LIMIT", "META", "PARTIAL_CLONE", "PROMISOR", "PROBE_COMMANDS", "PROBE_OUTPUT_LIMIT",
    "PROBE_TIMEOUT_SECONDS",
    "REPLACEMENTS", "TREE_ENTRIES", "TREE_TYPE", "GitProbeObservation", "ProbePlan", "RawResult",
    "TrustedRepositoryIdentity", "build_git_env", "build_probe_plan", "inspect_lfs_evidence", "interpret_probe",
    "run_probe",
]
