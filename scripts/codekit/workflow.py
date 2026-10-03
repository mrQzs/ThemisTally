"""Static validation for the Code-Kit v2 workflow-definition record.

This module deliberately stops at the static boundary.  It validates a frozen
workflow definition and its task/stage graph, but it never starts a process,
calls a provider, reads Git state, reserves budget, or changes a caller-owned
object.  Runtime readiness, claims, acceptance, and accounting belong to the
later 07 work packages.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from . import protocols

WORKFLOW_RECORD_TYPE = "workflow-definition"
WORKFLOW_SCHEMA_VERSION = 1
MAX_WORKFLOW_NODES = 1_000
MAX_WORKFLOW_EDGES = 10_000
MAX_MAPPING_ENTRIES = 128
MAX_AMOUNT_SCALE = 9
STAGE_KINDS = frozenset(("execute", "freeze", "check", "verdict"))
STAGE_ROLES = frozenset(("executor", "core", "independent-review", "supervisor"))
SCOPE_KINDS = frozenset(("tree", "file"))
_MONEY_RE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_PORT_RE = re.compile(r"[a-z0-9][a-z0-9._:-]{0,127}\Z")


@dataclass(frozen=True)
class WorkflowDefinition:
    """Immutable view returned by :func:`validate_workflow`.

    Direct construction is unsupported and does not validate its arguments;
    callers should obtain instances through :func:`parse_workflow` or
    :func:`validate_workflow`.
    """

    record: Mapping[str, Any]
    task_order: tuple[str, ...]

    @property
    def workflow_id(self) -> str:
        return self.record["workflow_id"]

    @property
    def workflow_version(self) -> int:
        return self.record["workflow_version"]

    @property
    def tasks(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.record["nodes"])


def parse_workflow(raw: bytes, *, max_bytes: int = protocols.DEFAULT_MAX_BYTES) -> WorkflowDefinition:
    """Strictly decode and validate one workflow-definition JSON document."""
    return validate_workflow(protocols.strict_json_loads(raw, max_bytes=max_bytes))


def validate_workflow(document: Any) -> WorkflowDefinition:
    """Validate a Python JSON value and return an immutable validated view.

    The input must already have passed :func:`protocols.strict_json_loads` when
    it came from bytes.  Direct Python callers still receive the same strict
    type, range, and closed-object checks; the input is deep-copied before it
    is exposed through the returned view.
    """
    protocols.check_json_value(document, max_bytes=protocols.DEFAULT_MAX_BYTES)
    root = _expect_dict(document, "", "workflow")
    _closed(root, {
        "record_type", "schema_version", "workflow_id", "workflow_version", "request_id", "repo_id",
        "platforms", "plugin_lock_ref", "nodes", "max_parallel_tasks",
    }, "")
    _expect_const(root, "record_type", WORKFLOW_RECORD_TYPE)
    protocols.require_schema_version(root, {WORKFLOW_SCHEMA_VERSION})
    protocols.validate_logical_id(root.get("workflow_id"), field="/workflow_id")
    _expect_int(root.get("workflow_version"), "/workflow_version", minimum=1)
    protocols.validate_request_id(root.get("request_id"), field="/request_id")
    protocols.validate_logical_id(root.get("repo_id"), field="/repo_id")
    _validate_platforms(root.get("platforms"))
    _validate_ref(root.get("plugin_lock_ref"), "/plugin_lock_ref")
    _expect_int(root.get("max_parallel_tasks"), "/max_parallel_tasks", minimum=1)

    nodes = _expect_list(root.get("nodes"), "/nodes", nonempty=True, max_items=MAX_WORKFLOW_NODES)
    ids: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    edge_count = 0
    for index, node in enumerate(nodes):
        field = f"/nodes/{index}"
        parsed = _validate_node(node, field)
        task_id = parsed["id"]
        if task_id in by_id:
            _error("E_SCHEMA_FIELDS", f"{field}/id", "duplicate_task_id")
        by_id[task_id] = parsed
        ids.append(task_id)
        edge_count += len(parsed["depends_on"])
        if edge_count > MAX_WORKFLOW_EDGES:
            _error("E_JSON_LIMIT", "/nodes", "workflow_edge_limit_exceeded")

    for task_id, node in by_id.items():
        for dep_index, dependency in enumerate(node["depends_on"]):
            if dependency not in by_id:
                _error("E_SCHEMA_FIELDS", f"/nodes/{ids.index(task_id)}/depends_on/{dep_index}", "unknown_task_dependency")
            if dependency == task_id:
                _error("E_SCHEMA_FIELDS", f"/nodes/{ids.index(task_id)}/depends_on/{dep_index}", "self_task_dependency")
        _validate_task_bindings(node, by_id, ids.index(task_id))

    order = _topological_order(by_id, ids, field="/nodes")
    copied = _freeze(copy.deepcopy(root))
    return WorkflowDefinition(copied, order)


def topological_order(workflow: WorkflowDefinition | Mapping[str, Any]) -> tuple[str, ...]:
    """Return the deterministic task order of a validated workflow."""
    if isinstance(workflow, WorkflowDefinition):
        return workflow.task_order
    return validate_workflow(workflow).task_order


def schema_ref_identity(ref: Mapping[str, Any]) -> tuple[str, str, str]:
    """Return the fixed schema identity tuple ``(kind, id, sha256)``.

    ``path`` is a locator and is deliberately excluded.  The public helper
    validates the reference before returning the tuple; it never reads or
    hashes the referenced resource.
    """
    if not isinstance(ref, Mapping):
        _error("E_SCHEMA_TYPE", "/schema_ref", "resource_ref_object_required")
    normalized = dict(ref)
    _validate_ref(normalized, "/schema_ref")
    return (normalized["kind"], normalized["id"], normalized["sha256"])


def schema_refs_compatible(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Compare two schema references by identity, ignoring their locator paths."""
    return schema_ref_identity(left) == schema_ref_identity(right)


def resource_conflicts(workflow: WorkflowDefinition | Mapping[str, Any]) -> tuple[tuple[str, str, str, str], ...]:
    """Return deterministic cross-task scope and exclusive-key conflicts.

    Each tuple is ``(left_task_id, right_task_id, source, identifier)``.
    ``source`` is ``"write_scope"`` or ``"resource_key"``.  Scope paths use
    segment-aware tree/file semantics; keys are exclusive because the v1
    definition has no read/write mode.  This is a pure declaration check: it
    does not resolve platform aliases, inspect symlinks, acquire locks, or
    create ledger records.
    """
    validated = workflow if isinstance(workflow, WorkflowDefinition) else validate_workflow(workflow)
    tasks = sorted(validated.tasks, key=lambda task: task["id"])
    conflicts: set[tuple[str, str, str, str]] = set()
    for left_index, left in enumerate(tasks):
        for right in tasks[left_index + 1:]:
            left_scopes = sorted(left["write_scope"], key=lambda item: (item["path"], item["kind"]))
            right_scopes = sorted(right["write_scope"], key=lambda item: (item["path"], item["kind"]))
            for left_scope in left_scopes:
                for right_scope in right_scopes:
                    if _scope_conflicts(left_scope, right_scope):
                        paths = sorted((left_scope["path"], right_scope["path"]))
                        conflicts.add((left["id"], right["id"], "write_scope", "|".join(paths)))
            for key in sorted(set(left["resource_keys"]) & set(right["resource_keys"])):
                conflicts.add((left["id"], right["id"], "resource_key", key))
    return tuple(sorted(conflicts))


def amount_to_units(amount: str, scale: int) -> int:
    """Convert a nonnegative decimal string to exact integer units.

    The caller supplies the scale; no currency default, exponent, sign,
    rounding, FX conversion, reservation, or ledger update is performed.
    """
    scale = protocols.require_int(scale, field="/scale", minimum=0, maximum=MAX_AMOUNT_SCALE)
    if type(amount) is not str or len(amount) > 64 or _MONEY_RE.fullmatch(amount) is None:
        _error("E_SCHEMA_FIELDS", "/amount", "money_syntax")
    whole, separator, fraction = amount.partition(".")
    if separator and len(fraction) > scale:
        _error("E_SCHEMA_FIELDS", "/amount", "money_precision")
    units = int(whole) * (10 ** scale)
    if fraction:
        units += int(fraction.ljust(scale, "0"))
    if units > protocols.MAX_SAFE_INTEGER:
        _error("E_INTEGER_RANGE", "/amount", "amount_units_out_of_range")
    return units


def _validate_node(node: Any, field: str) -> dict[str, Any]:
    obj = _expect_dict(node, field, "task")
    _closed(obj, {
        "id", "depends_on", "inputs", "input_bindings", "outputs", "stages", "write_scope", "resource_keys",
        "contract_ref", "baseline_ref", "budget", "retry_policy", "priority",
    }, field)
    task_id = protocols.validate_task_id(obj.get("id"), field=f"{field}/id")
    dependencies = _validate_id_list(obj.get("depends_on"), f"{field}/depends_on", "task_dependency")
    inputs = _validate_ports(obj.get("inputs"), f"{field}/inputs", input_port=True)
    bindings = _expect_dict(obj.get("input_bindings"), f"{field}/input_bindings", "input_bindings")
    if len(bindings) > MAX_MAPPING_ENTRIES:
        _error("E_JSON_LIMIT", f"{field}/input_bindings", "mapping_limit_exceeded")
    outputs = _validate_ports(obj.get("outputs"), f"{field}/outputs", input_port=False)
    stages = _validate_stages(obj.get("stages"), f"{field}/stages")
    _validate_scope(obj.get("write_scope"), f"{field}/write_scope")
    _validate_resource_keys(obj.get("resource_keys"), f"{field}/resource_keys")
    _validate_optional_ref(obj.get("contract_ref"), f"{field}/contract_ref")
    _validate_optional_ref(obj.get("baseline_ref"), f"{field}/baseline_ref")
    _validate_budget(obj.get("budget"), f"{field}/budget")
    _validate_retry(obj.get("retry_policy"), f"{field}/retry_policy")
    _expect_int(obj.get("priority"), f"{field}/priority", minimum=0)
    return {
        "id": task_id,
        "depends_on": dependencies,
        "inputs": inputs,
        "input_bindings": bindings,
        "outputs": outputs,
        "stages": stages,
        "write_scope": obj["write_scope"],
        "resource_keys": obj["resource_keys"],
        "contract_ref": obj["contract_ref"],
        "baseline_ref": obj["baseline_ref"],
        "budget": obj["budget"],
        "retry_policy": obj["retry_policy"],
        "priority": obj["priority"],
    }


def _validate_task_bindings(node: Mapping[str, Any], all_nodes: Mapping[str, Mapping[str, Any]], node_index: int) -> None:
    inputs = node["inputs"]
    bindings = node["input_bindings"]
    for name, port in inputs.items():
        field = f"/nodes/{node_index}/input_bindings/{_escape(name)}"
        if port["required"] and name not in bindings:
            _error("E_SCHEMA_FIELDS", field, "required_input_binding_missing")
        if name in bindings:
            _validate_binding(bindings[name], field, node, all_nodes, port["schema_ref"])
    for name in bindings:
        if name not in inputs:
            _error("E_SCHEMA_FIELDS", f"/nodes/{node_index}/input_bindings/{_escape(name)}", "unknown_input_port")

    stage_ids = {stage["id"] for stage in node["stages"]}
    for output_name, output in node["outputs"].items():
        if output["stage_id"] not in stage_ids:
            _error("E_SCHEMA_FIELDS", f"/nodes/{node_index}/outputs/{_escape(output_name)}/stage_id", "unknown_output_stage")


def _validate_binding(binding: Any, field: str, node: Mapping[str, Any], all_nodes: Mapping[str, Mapping[str, Any]],
                     expected_schema: Mapping[str, Any]) -> None:
    obj = _expect_dict(binding, field, "binding")
    kind = obj.get("kind")
    if kind == "external":
        _closed(obj, {"kind", "artifact_ref", "schema_ref"}, field)
        _validate_ref(obj.get("artifact_ref"), f"{field}/artifact_ref")
        _validate_ref(obj.get("schema_ref"), f"{field}/schema_ref")
        if not _same_schema_ref(obj["schema_ref"], expected_schema):
            _error("E_SCHEMA_FIELDS", f"{field}/schema_ref", "input_schema_mismatch")
        return
    if kind == "task-output":
        _closed(obj, {"kind", "task_id", "port"}, field)
        source_task = protocols.validate_task_id(obj.get("task_id"), field=f"{field}/task_id")
        protocols.validate_logical_id(obj.get("port"), field=f"{field}/port")
        if source_task not in node["depends_on"]:
            _error("E_SCHEMA_FIELDS", f"{field}/task_id", "binding_source_not_dependency")
        source = all_nodes.get(source_task)
        if source is None or obj["port"] not in source["outputs"]:
            _error("E_SCHEMA_FIELDS", f"{field}/port", "unknown_source_output")
        if not _same_schema_ref(source["outputs"][obj["port"]]["schema_ref"], expected_schema):
            _error("E_SCHEMA_FIELDS", f"{field}/port", "input_schema_mismatch")
        return
    _error("E_SCHEMA_FIELDS", f"{field}/kind", "unknown_binding_kind")


def _validate_ports(value: Any, field: str, *, input_port: bool) -> dict[str, dict[str, Any]]:
    obj = _expect_dict(value, field, "ports")
    if len(obj) > MAX_MAPPING_ENTRIES:
        _error("E_JSON_LIMIT", field, "port_limit_exceeded")
    result: dict[str, dict[str, Any]] = {}
    for name, port in obj.items():
        if type(name) is not str or _PORT_RE.fullmatch(name) is None:
            _error("E_SCHEMA_FIELDS", f"{field}/{_escape(str(name))}", "port_name_syntax")
        port_field = f"{field}/{_escape(name)}"
        item = _expect_dict(port, port_field, "port")
        required = {"schema_ref", "required"} if input_port else {"schema_ref", "stage_id"}
        _closed(item, required, port_field)
        _validate_ref(item.get("schema_ref"), f"{port_field}/schema_ref")
        if input_port:
            if type(item.get("required")) is not bool:
                _error("E_SCHEMA_TYPE", f"{port_field}/required", "boolean_required")
            result[name] = {"schema_ref": item["schema_ref"], "required": item["required"]}
        else:
            protocols.validate_logical_id(item.get("stage_id"), field=f"{port_field}/stage_id")
            result[name] = {"schema_ref": item["schema_ref"], "stage_id": item["stage_id"]}
    return result


def _validate_stages(value: Any, field: str) -> list[dict[str, Any]]:
    stages = _expect_list(value, field, max_items=MAX_MAPPING_ENTRIES)
    if len(stages) < 4:
        _error("E_SCHEMA_FIELDS", field, "stage_profile_incomplete")
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    edge_count = 0
    for index, stage in enumerate(stages):
        item_field = f"{field}/{index}"
        obj = _expect_dict(stage, item_field, "stage")
        _closed(obj, {"id", "kind", "role", "depends_on", "plugin_step_ref"}, item_field)
        stage_id = protocols.validate_logical_id(obj.get("id"), field=f"{item_field}/id")
        if stage_id in ids:
            _error("E_SCHEMA_FIELDS", f"{item_field}/id", "duplicate_stage_id")
        ids.add(stage_id)
        kind = obj.get("kind")
        if type(kind) is not str or kind not in STAGE_KINDS:
            _error("E_SCHEMA_FIELDS", f"{item_field}/kind", "unknown_stage_kind")
        role = obj.get("role")
        if type(role) is not str or role not in STAGE_ROLES:
            _error("E_SCHEMA_FIELDS", f"{item_field}/role", "unknown_stage_role")
        depends_on = _validate_logical_id_list(obj.get("depends_on"), f"{item_field}/depends_on", "stage_dependency")
        edge_count += len(depends_on)
        _validate_optional_ref(obj.get("plugin_step_ref"), f"{item_field}/plugin_step_ref")
        result.append({"id": stage_id, "kind": kind, "role": role, "depends_on": depends_on,
                       "plugin_step_ref": obj["plugin_step_ref"]})
    by_id = {item["id"]: item for item in result}
    if edge_count > MAX_WORKFLOW_EDGES:
        _error("E_JSON_LIMIT", field, "stage_edge_limit_exceeded")
    for index, item in enumerate(result):
        for dep_index, dependency in enumerate(item["depends_on"]):
            if dependency not in by_id:
                _error("E_SCHEMA_FIELDS", f"{field}/{index}/depends_on/{dep_index}", "unknown_stage_dependency")
            if dependency == item["id"]:
                _error("E_SCHEMA_FIELDS", f"{field}/{index}/depends_on/{dep_index}", "self_stage_dependency")
    _topological_order(by_id, [item["id"] for item in result], field=field)
    # The first release uses one fixed stage profile: one freeze and one verdict,
    # at least one execute and check, with explicit ordering between them.
    ancestors = _ancestors(by_id)
    freeze_ids = {item["id"] for item in result if item["kind"] == "freeze"}
    check_ids = {item["id"] for item in result if item["kind"] == "check"}
    execute_ids = {item["id"] for item in result if item["kind"] == "execute"}
    verdict_ids = {item["id"] for item in result if item["kind"] == "verdict"}
    if not execute_ids or len(freeze_ids) != 1 or not check_ids or len(verdict_ids) != 1:
        _error("E_SCHEMA_FIELDS", field, "stage_profile_incomplete")
    freeze_id = next(iter(freeze_ids))
    verdict_id = next(iter(verdict_ids))
    if not execute_ids <= ancestors[freeze_id]:
        _error("E_SCHEMA_FIELDS", field, "stage_order_invalid")
    for item in result:
        if item["kind"] == "check" and freeze_id not in ancestors[item["id"]]:
            _error("E_SCHEMA_FIELDS", f"{field}/{result.index(item)}/depends_on", "check_before_freeze")
        if item["kind"] == "check" and item["id"] not in ancestors[verdict_id]:
            _error("E_SCHEMA_FIELDS", f"{field}/{result.index(item)}/depends_on", "verdict_before_all_checks")
    return result


def _validate_scope(value: Any, field: str) -> None:
    items = _expect_list(value, field, max_items=MAX_MAPPING_ENTRIES)
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(items):
        item_field = f"{field}/{index}"
        obj = _expect_dict(item, item_field, "write_scope")
        _closed(obj, {"path", "kind"}, item_field)
        path = protocols.validate_business_path(obj.get("path"), field=f"{item_field}/path")
        kind = obj.get("kind")
        if type(kind) is not str or kind not in SCOPE_KINDS:
            _error("E_SCHEMA_FIELDS", f"{item_field}/kind", "unknown_scope_kind")
        key = (path, kind)
        if key in seen:
            _error("E_SCHEMA_FIELDS", item_field, "duplicate_write_scope")
        seen.add(key)


def _validate_resource_keys(value: Any, field: str) -> None:
    items = _expect_list(value, field, max_items=MAX_MAPPING_ENTRIES)
    seen: set[str] = set()
    for index, item in enumerate(items):
        protocols.validate_logical_id(item, field=f"{field}/{index}")
        if item in seen:
            _error("E_SCHEMA_FIELDS", f"{field}/{index}", "duplicate_resource_key")
        seen.add(item)


def _validate_budget(value: Any, field: str) -> None:
    obj = _expect_dict(value, field, "budget")
    _closed(obj, {"max_dispatches", "currency_caps"}, field)
    _expect_int(obj.get("max_dispatches"), f"{field}/max_dispatches", minimum=1)
    caps = _expect_dict(obj.get("currency_caps"), f"{field}/currency_caps", "currency_caps")
    if len(caps) > MAX_MAPPING_ENTRIES:
        _error("E_JSON_LIMIT", f"{field}/currency_caps", "mapping_limit_exceeded")
    for currency, amount in caps.items():
        if type(currency) is not str or re.fullmatch(r"[A-Z]{3}", currency) is None:
            _error("E_SCHEMA_FIELDS", f"{field}/currency_caps/{_escape(str(currency))}", "currency_syntax")
        if type(amount) is not str or _MONEY_RE.fullmatch(amount) is None:
            _error("E_SCHEMA_FIELDS", f"{field}/currency_caps/{_escape(str(currency))}", "money_syntax")
        try:
            if Decimal(amount) < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            _error("E_SCHEMA_FIELDS", f"{field}/currency_caps/{_escape(str(currency))}", "money_value")


def _validate_retry(value: Any, field: str) -> None:
    obj = _expect_dict(value, field, "retry_policy")
    _closed(obj, {"max_attempts_total", "min_backoff_seconds"}, field)
    _expect_int(obj.get("max_attempts_total"), f"{field}/max_attempts_total", minimum=1)
    _expect_int(obj.get("min_backoff_seconds"), f"{field}/min_backoff_seconds", minimum=0)


def _validate_ref(value: Any, field: str) -> None:
    obj = _expect_dict(value, field, "resource_ref")
    _closed(obj, {"kind", "id", "sha256", "path"}, field,
            required={"kind", "id", "sha256", "path"})
    protocols.validate_resource_kind(obj.get("kind"), field=f"{field}/kind")
    protocols.validate_logical_id(obj.get("id"), field=f"{field}/id")
    protocols.validate_sha256(obj.get("sha256"), field=f"{field}/sha256")
    protocols.validate_business_path(obj["path"], field=f"{field}/path")


def _same_schema_ref(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Compare schema identity; a path is a locator and is not part of identity."""
    return all(left.get(name) == right.get(name) for name in ("kind", "id", "sha256"))


def _scope_conflicts(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_parts = tuple(left["path"].split("/"))
    right_parts = tuple(right["path"].split("/"))
    if left_parts == right_parts:
        return True
    return ((left["kind"] == "tree" and right_parts[:len(left_parts)] == left_parts)
            or (right["kind"] == "tree" and left_parts[:len(right_parts)] == right_parts))


def _validate_optional_ref(value: Any, field: str) -> None:
    if value is not None:
        _validate_ref(value, field)


def _validate_platforms(value: Any) -> None:
    items = _expect_list(value, "/platforms", nonempty=True, max_items=3)
    seen: set[str] = set()
    for index, item in enumerate(items):
        protocols.validate_platform(item, field=f"/platforms/{index}")
        if item in seen:
            _error("E_SCHEMA_FIELDS", f"/platforms/{index}", "duplicate_platform")
        seen.add(item)


def _validate_id_list(value: Any, field: str, reason: str) -> list[str]:
    items = _expect_list(value, field, max_items=MAX_WORKFLOW_NODES)
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        protocols.validate_task_id(item, field=f"{field}/{index}")
        if item in seen:
            _error("E_SCHEMA_FIELDS", f"{field}/{index}", f"duplicate_{reason}")
        seen.add(item)
        result.append(item)
    return result


def _validate_logical_id_list(value: Any, field: str, reason: str) -> list[str]:
    items = _expect_list(value, field, max_items=MAX_MAPPING_ENTRIES)
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        protocols.validate_logical_id(item, field=f"{field}/{index}")
        if item in seen:
            _error("E_SCHEMA_FIELDS", f"{field}/{index}", f"duplicate_{reason}")
        seen.add(item)
        result.append(item)
    return result


def _topological_order(graph: Mapping[str, Mapping[str, Any]], source_order: Sequence[str], *, field: str) -> tuple[str, ...]:
    indegree = {name: len(item["depends_on"]) for name, item in graph.items()}
    dependents: dict[str, list[str]] = {name: [] for name in graph}
    for name, item in graph.items():
        for dependency in item["depends_on"]:
            if dependency not in graph:
                continue
            dependents[dependency].append(name)
    ready = sorted((name for name, degree in indegree.items() if degree == 0))
    result: list[str] = []
    while ready:
        current = ready.pop(0)
        result.append(current)
        for dependent in sorted(dependents[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
                ready.sort()
    if len(result) != len(graph):
        _error("E_SCHEMA_FIELDS", field, "dependency_cycle")
    return tuple(result)


def _ancestors(graph: Mapping[str, Mapping[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for name, item in graph.items():
        found: set[str] = set()
        stack = list(item["depends_on"])
        while stack:
            current = stack.pop()
            if current in found:
                continue
            found.add(current)
            stack.extend(graph[current]["depends_on"])
        result[name] = found
    return result


def _expect_dict(value: Any, field: str, phase: str) -> dict[str, Any]:
    if type(value) is not dict:
        _error("E_SCHEMA_TYPE", field or None, f"{phase}_object_required")
    return value


def _expect_list(value: Any, field: str, *, nonempty: bool = False, max_items: int | None = None) -> list[Any]:
    if type(value) is not list:
        _error("E_SCHEMA_TYPE", field, "array_required")
    if nonempty and not value:
        _error("E_SCHEMA_FIELDS", field, "nonempty_array_required")
    if max_items is not None and len(value) > max_items:
        _error("E_JSON_LIMIT", field, "array_limit_exceeded")
    return value


def _closed(obj: Mapping[str, Any], allowed: set[str], field: str, *, required: set[str] | None = None,
            optional: set[str] | None = None) -> None:
    required = allowed if required is None else required
    missing = required - set(obj)
    if missing:
        _error("E_SCHEMA_FIELDS", f"{field}/{_escape(sorted(missing)[0])}", "required_field_missing")
    unknown = set(obj) - allowed
    if unknown:
        _error("E_SCHEMA_FIELDS", f"{field}/{_escape(sorted(unknown)[0])}", "unknown_field")


def _expect_const(obj: Mapping[str, Any], name: str, expected: Any) -> None:
    if obj.get(name) != expected:
        _error("E_SCHEMA_RECORD_TYPE" if name == "record_type" else "E_SCHEMA_FIELDS", f"/{name}", "record_value_mismatch")


def _expect_int(value: Any, field: str, *, minimum: int, maximum: int = protocols.MAX_SAFE_INTEGER) -> int:
    return protocols.require_int(value, field=field, minimum=minimum, maximum=maximum)


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _error(code: str, field: str | None, reason: str) -> None:
    raise protocols.ProtocolError(code, field=field, phase="workflow", reason=reason)


__all__ = [
    "WORKFLOW_RECORD_TYPE", "WORKFLOW_SCHEMA_VERSION", "MAX_WORKFLOW_NODES", "MAX_WORKFLOW_EDGES",
    "MAX_MAPPING_ENTRIES", "MAX_AMOUNT_SCALE", "WorkflowDefinition", "parse_workflow", "validate_workflow",
    "topological_order", "schema_ref_identity", "schema_refs_compatible", "resource_conflicts", "amount_to_units",
]
