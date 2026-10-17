"""Static compiler for built-in task recipes.

The compiler produces a check-plan artifact and a receipt describing the
mapping from business ports to the existing 07 stage kinds.  It never submits
the resulting plan to the dispatcher and therefore remains reference-only.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .builtin_artifacts import ArtifactError, canonical_bytes, digest, resource_ref, validate_artifact


CHECK_PLAN_RECORD_TYPE = "check-plan"
BUSINESS_KINDS = {"analysis", "change", "freeze", "check", "review"}
STAGE_MAP = {"analysis": "execute", "change": "execute", "freeze": "freeze", "check": "check", "review": "verdict"}
RECEIPT_RECORD_TYPE = "compile-receipt"
_ID_RE = re.compile(r"^[a-z][a-z0-9._:-]{0,127}$")
_PLUGIN_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_MUTABLE_ALIASES = frozenset({"latest", "head", "current", "stable", "default", "main", "master", "dev", "tip"})
_DYNAMIC_MARKERS = ("$", "`", ";", "&&", "||", "|", ">", "<", "eval(", "exec(", "__import__", "importlib")
_NETWORK_TOOLS = {"curl", "wget", "nc", "netcat", "ssh", "scp", "pip", "npm", "cargo"}
_MAX_SAFE_INTEGER = 2**53 - 1


def _fail(code: str, path: str, message: str) -> None:
    raise ArtifactError(code, path, message)


def _id(value: Any, path: str) -> str:
    if type(value) is not str or not _ID_RE.fullmatch(value):
        _fail("E_RECIPE_ID", path, "lowercase logical id required")
    if value.lower() in {"latest", "head", "current"}:
        _fail("E_RECIPE_VERSION", path, "mutable alias is forbidden")
    return value


def _plugin_id(value: Any, path: str) -> str:
    if type(value) is not str or not _PLUGIN_ID_RE.fullmatch(value):
        _fail("E_RECIPE_ID", path, "lowercase plugin id required")
    if value.lower() in _MUTABLE_ALIASES:
        _fail("E_RECIPE_VERSION", path, "mutable alias is forbidden")
    return value


def _plugin_version(value: Any, path: str, *, code: str = "E_RECIPE_VERSION") -> str:
    if type(value) is not str or not _VERSION_RE.fullmatch(value):
        _fail(code, path, "exact semantic version required")
    return value


def _text_list(value: Any, path: str, message: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("E_RECIPE_SCHEMA", path, message)
    values = list(value)
    if any(type(item) is not str or not item or any(
            ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF
            for ch in item) for item in values):
        _fail("E_RECIPE_SCHEMA", path, message)
    return values


def _mutable_alias_in_command(value: str) -> bool:
    lowered = value.lower()
    return any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lowered) for alias in _MUTABLE_ALIASES)


def _command(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or not value or any(
            type(item) is not str or not item or any(
                ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF
                for ch in item) for item in value):
        _fail("E_RECIPE_COMMAND", path, "non-empty argv array required")
    flat = " ".join(value).lower()
    if any(marker in flat for marker in _DYNAMIC_MARKERS) or any(
            scheme in flat for scheme in ("http://", "https://", "file://")):
        _fail("E_RECIPE_COMMAND", path, "dynamic shell expression is forbidden")
    # A path-qualified executable (``/usr/bin/curl`` or ``tools\\wget.exe``)
    # is still a network command.  Compare normalized basenames as well as
    # the literal argv tokens so callers cannot bypass the offline policy by
    # spelling the executable with a path.
    tokens = []
    for item in value:
        token = item.replace("\\", "/").rsplit("/", 1)[-1].lower()
        tokens.append(token[:-4] if token.endswith(".exe") else token)
    if any(token in _NETWORK_TOOLS for token in tokens) or any(token in _NETWORK_TOOLS for token in flat.split()):
        _fail("E_RECIPE_COMMAND", path, "external command is forbidden in offline recipe")
    if _mutable_alias_in_command(flat):
        _fail("E_RECIPE_VERSION", path, "mutable latest alias is forbidden")
    return list(value)


def _steps(recipe: Mapping[str, Any]) -> Tuple[list[Dict[str, Any]], Tuple[str, ...]]:
    steps = recipe.get("steps")
    if not isinstance(steps, list) or not steps:
        _fail("E_RECIPE_SCHEMA", "/steps", "non-empty step array required")
    by_id: Dict[str, Dict[str, Any]] = {}
    for index, raw in enumerate(steps):
        field = f"/steps/{index}"
        if not isinstance(raw, Mapping):
            _fail("E_RECIPE_SCHEMA", field, "step object required")
        allowed = {"id", "kind", "depends_on", "command", "deterministic", "inputs", "outputs", "plugin_step_ref"}
        if set(raw) - allowed or {"id", "kind", "depends_on", "command", "deterministic"} - set(raw):
            _fail("E_RECIPE_SCHEMA", field, "closed recipe step required")
        step_id = _id(raw["id"], f"{field}/id")
        if step_id in by_id:
            _fail("E_RECIPE_DUPLICATE", f"{field}/id", "duplicate step id")
        kind = raw["kind"]
        if type(kind) is not str or kind not in BUSINESS_KINDS:
            _fail("E_RECIPE_KIND", f"{field}/kind", "unsupported business step kind")
        deps = raw["depends_on"]
        if not isinstance(deps, list) or any(type(item) is not str for item in deps) or len(set(deps)) != len(deps):
            _fail("E_RECIPE_DEPENDENCY", f"{field}/depends_on", "unique dependency id array required")
        deterministic = raw["deterministic"]
        if type(deterministic) is not bool or not deterministic:
            _fail("E_RECIPE_DETERMINISM", f"{field}/deterministic", "recipe steps must be deterministic")
        command = _command(raw["command"], f"{field}/command")
        normalized: Dict[str, Any] = {"id": step_id, "kind": kind, "depends_on": list(deps), "command": command, "deterministic": True}
        for key in ("inputs", "outputs"):
            if key in raw:
                if not isinstance(raw[key], list) or any(type(item) is not str or not item for item in raw[key]):
                    _fail("E_RECIPE_SCHEMA", f"{field}/{key}", "string array required")
                normalized[key] = list(raw[key])
        if "plugin_step_ref" in raw:
            normalized["plugin_step_ref"] = resource_ref(raw["plugin_step_ref"], f"{field}/plugin_step_ref")
        by_id[step_id] = normalized
    for step_id, step in by_id.items():
        for dependency in step["depends_on"]:
            if dependency not in by_id:
                _fail("E_RECIPE_DEPENDENCY", f"/steps/{step_id}/depends_on", f"missing dependency {dependency}")
    ordered: list[str] = []
    visiting, visited = set(), set()

    def visit(step_id: str) -> None:
        if step_id in visiting:
            _fail("E_RECIPE_CYCLE", "/steps", f"dependency cycle includes {step_id}")
        if step_id in visited:
            return
        visiting.add(step_id)
        for dep in sorted(by_id[step_id]["depends_on"]):
            visit(dep)
        visiting.remove(step_id); visited.add(step_id); ordered.append(step_id)

    for step_id in sorted(by_id):
        visit(step_id)
    return [by_id[item] for item in ordered], tuple(ordered)


def validate_recipe(recipe: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(recipe, Mapping):
        _fail("E_RECIPE_SCHEMA", "/", "recipe object required")
    allowed = {"record_type", "schema_version", "recipe_id", "recipe_version", "plugin_id", "plugin_version", "steps"}
    if set(recipe) != allowed:
        _fail("E_RECIPE_SCHEMA", "/", "closed recipe required")
    if recipe["record_type"] != "builtin-task-recipe" or recipe["schema_version"] != 1:
        _fail("E_RECIPE_VERSION", "/record_type", "recipe schema version 1 required")
    _id(recipe["recipe_id"], "/recipe_id")
    if (type(recipe["recipe_version"]) is not int or not 1 <= recipe["recipe_version"] <= _MAX_SAFE_INTEGER):
        _fail("E_RECIPE_VERSION", "/recipe_version", "positive integer required")
    _plugin_id(recipe["plugin_id"], "/plugin_id")
    _plugin_version(recipe["plugin_version"], "/plugin_version")
    steps, _ = _steps(recipe)
    normalized = copy.deepcopy(dict(recipe)); normalized["steps"] = steps
    return normalized


def _receipt(*, receipt_id: str, recipe: Mapping[str, Any], ordered_ids: Sequence[str], status: str,
             errors: Sequence[str]) -> Dict[str, Any]:
    if type(status) is not str or status not in {"REFERENCE_ONLY", "BLOCKED", "FAIL"}:
        _fail("E_RECIPE_STATUS", "/status", "compile receipt cannot claim production success")
    by_id = {step["id"]: step for step in recipe["steps"]}
    error_values = _text_list(errors, "/errors", "string error array required")
    receipt = {"record_type": RECEIPT_RECORD_TYPE, "schema_version": 1, "receipt_id": receipt_id,
               "recipe_id": recipe["recipe_id"], "recipe_version": recipe["recipe_version"],
               "plugin_id": recipe["plugin_id"], "plugin_version": recipe["plugin_version"],
               "ordered_step_ids": list(ordered_ids), "stage_kinds": [STAGE_MAP[next(s["kind"] for s in recipe["steps"] if s["id"] == item)] for item in ordered_ids],
               "step_dependencies": {item: list(by_id[item]["depends_on"]) for item in ordered_ids},
               "recipe_sha256": digest(recipe),
               "status": status, "errors": error_values, "dispatcher_submitted": False}
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def validate_compile_receipt(receipt: Mapping[str, Any], *, recipe: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    required = {"record_type", "schema_version", "receipt_id", "recipe_id", "recipe_version", "plugin_id", "plugin_version", "ordered_step_ids", "stage_kinds", "step_dependencies", "recipe_sha256", "status", "errors", "dispatcher_submitted", "receipt_sha256"}
    if not isinstance(receipt, Mapping) or set(receipt) != required:
        _fail("E_RECIPE_RECEIPT", "/", "closed compile receipt required")
    copy_value = dict(receipt); supplied = copy_value.pop("receipt_sha256")
    if supplied != digest(copy_value):
        _fail("E_RECIPE_DRIFT", "/receipt_sha256", "receipt bytes do not match")
    if receipt["record_type"] != RECEIPT_RECORD_TYPE or receipt["schema_version"] != 1 or type(receipt["status"]) is not str or receipt["status"] not in {"REFERENCE_ONLY", "BLOCKED", "FAIL"}:
        _fail("E_RECIPE_RECEIPT", "/", "invalid receipt header")
    if type(receipt["receipt_id"]) is not str or not receipt["receipt_id"]:
        _fail("E_RECIPE_RECEIPT", "/receipt_id", "non-empty receipt id required")
    _id(receipt["recipe_id"], "/recipe_id")
    _plugin_id(receipt["plugin_id"], "/plugin_id")
    _plugin_version(receipt["plugin_version"], "/plugin_version", code="E_RECIPE_RECEIPT")
    if (type(receipt["recipe_version"]) is not int
            or not 1 <= receipt["recipe_version"] <= _MAX_SAFE_INTEGER):
        _fail("E_RECIPE_RECEIPT", "/recipe_version", "positive integer required")
    if not isinstance(receipt["ordered_step_ids"], list) or not isinstance(receipt["stage_kinds"], list) or len(receipt["ordered_step_ids"]) != len(receipt["stage_kinds"]):
        _fail("E_RECIPE_RECEIPT", "/ordered_step_ids", "step and stage arrays must align")
    if any(type(item) is not str or not item for item in receipt["ordered_step_ids"]):
        _fail("E_RECIPE_RECEIPT", "/ordered_step_ids", "step ids must be non-empty strings")
    for index, item in enumerate(receipt["ordered_step_ids"]):
        _id(item, f"/ordered_step_ids/{index}")
    if len(set(receipt["ordered_step_ids"])) != len(receipt["ordered_step_ids"]):
        _fail("E_RECIPE_RECEIPT", "/ordered_step_ids", "duplicate step id")
    if any(type(item) is not str or item not in {"execute", "freeze", "check", "verdict"} for item in receipt["stage_kinds"]):
        _fail("E_RECIPE_RECEIPT", "/stage_kinds", "invalid dispatcher stage")
    if not isinstance(receipt["step_dependencies"], Mapping) or set(receipt["step_dependencies"]) != set(receipt["ordered_step_ids"]):
        _fail("E_RECIPE_RECEIPT", "/step_dependencies", "dependency map must bind every step")
    positions = {step_id: index for index, step_id in enumerate(receipt["ordered_step_ids"])}
    for step_id, dependencies in receipt["step_dependencies"].items():
        if not isinstance(dependencies, list) or len(set(dependencies)) != len(dependencies) or any(type(dep) is not str or dep not in positions or positions[dep] >= positions[step_id] for dep in dependencies):
            _fail("E_RECIPE_RECEIPT", "/step_dependencies", "dependencies must precede their step")
    if not isinstance(receipt["recipe_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", receipt["recipe_sha256"]):
        _fail("E_RECIPE_RECEIPT", "/recipe_sha256", "recipe digest required")
    if not isinstance(receipt["errors"], list) or any(type(item) is not str for item in receipt["errors"]):
        _fail("E_RECIPE_RECEIPT", "/errors", "string error array required")
    if receipt["dispatcher_submitted"] is not False:
        _fail("E_RECIPE_RECEIPT", "/dispatcher_submitted", "offline compiler cannot submit to dispatcher")
    if recipe is not None:
        normalized_recipe = validate_recipe(recipe)
        _, order = _steps(normalized_recipe)
        expected = _receipt(receipt_id=receipt["receipt_id"], recipe=normalized_recipe, ordered_ids=order,
                            status=receipt["status"], errors=receipt["errors"])
        if dict(receipt) != expected:
            _fail("E_RECIPE_RECEIPT", "/recipe_sha256", "receipt does not bind the supplied recipe")
    return copy.deepcopy(dict(receipt))


def compile_recipe(recipe: Mapping[str, Any], *, artifact_id: str, producer: Mapping[str, Any],
                   source_refs: Sequence[Mapping[str, Any]], candidate_ref: Optional[Mapping[str, Any]],
                   environment_ref: Optional[Mapping[str, Any]], status: str = "REFERENCE_ONLY") -> Dict[str, Any]:
    if type(status) is not str or status not in {"REFERENCE_ONLY", "BLOCKED", "FAIL"}:
        _fail("E_RECIPE_STATUS", "/status", "compile receipt cannot claim production success")
    if not isinstance(producer, Mapping):
        _fail("E_RECIPE_SCHEMA", "/producer", "producer object required")
    if not isinstance(source_refs, Sequence) or isinstance(source_refs, (str, bytes, bytearray)):
        _fail("E_RECIPE_SCHEMA", "/source_refs", "source refs sequence required")
    normalized = validate_recipe(recipe)
    steps, order = _steps(normalized)
    stages = []
    for number, step in enumerate(steps):
        stages.append({"id": step["id"], "kind": STAGE_MAP[step["kind"]], "business_kind": step["kind"],
                       "order": number, "depends_on": list(step["depends_on"]), "command": list(step["command"]),
                       "deterministic": True, "dispatcher_stage": False})
    payload = {"recipe_id": normalized["recipe_id"], "recipe_version": normalized["recipe_version"],
               "plugin_id": normalized["plugin_id"], "plugin_version": normalized["plugin_version"],
               "execution_mode": "deterministic_check", "production_ready": False,
               "stages": stages, "mapping": {item["id"]: STAGE_MAP[item["kind"]] for item in steps},
               "compile_receipt_id": f"{artifact_id}.receipt"}
    plan = {"record_type": CHECK_PLAN_RECORD_TYPE, "schema_version": 1, "artifact_id": artifact_id,
            "producer": copy.deepcopy(dict(producer)), "status": status, "source_refs": [resource_ref(x, f"/source_refs/{i}") for i, x in enumerate(source_refs)],
            "candidate_ref": None if candidate_ref is None else resource_ref(candidate_ref, "/candidate_ref"),
            "environment_ref": None if environment_ref is None else resource_ref(environment_ref, "/environment_ref"), "payload": payload}
    plan = validate_check_plan(plan)
    receipt = _receipt(receipt_id=f"{artifact_id}.receipt", recipe=normalized, ordered_ids=order, status=status, errors=[])
    return {"check_plan": plan, "compile_receipt": validate_compile_receipt(receipt, recipe=normalized)}


def validate_check_plan(record: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = validate_artifact(record)
    if normalized["record_type"] != CHECK_PLAN_RECORD_TYPE:
        _fail("E_RECIPE_PLAN", "/record_type", "check-plan required")
    if normalized["status"] in {"READY", "PASS"}:
        _fail("E_RECIPE_PLAN", "/status", "offline check-plan cannot claim production readiness")
    producer = normalized["producer"]
    if producer["kind"] == "builtin-plugin":
        _plugin_id(producer["id"], "/producer/id")
        _plugin_version(producer["version"], "/producer/version", code="E_RECIPE_PLAN")
    payload = normalized["payload"]
    required = {"recipe_id", "recipe_version", "plugin_id", "plugin_version", "execution_mode", "production_ready", "stages", "mapping", "compile_receipt_id"}
    if set(payload) != required:
        _fail("E_RECIPE_PLAN", "/payload", "closed check-plan payload required")
    if payload["execution_mode"] != "deterministic_check" or payload["production_ready"] is not False:
        _fail("E_RECIPE_PLAN", "/payload", "plan must remain deterministic reference-only")
    _id(payload["recipe_id"], "/payload/recipe_id")
    if type(payload["recipe_version"]) is not int or payload["recipe_version"] < 1:
        _fail("E_RECIPE_PLAN", "/payload/recipe_version", "positive integer required")
    _plugin_id(payload["plugin_id"], "/payload/plugin_id")
    _plugin_version(payload["plugin_version"], "/payload/plugin_version", code="E_RECIPE_PLAN")
    _id(payload["compile_receipt_id"], "/payload/compile_receipt_id")
    if not isinstance(payload["stages"], list) or not payload["stages"]:
        _fail("E_RECIPE_PLAN", "/payload/stages", "stage array required")
    ids = set()
    for index, stage in enumerate(payload["stages"]):
        if not isinstance(stage, Mapping) or set(stage) != {"id", "kind", "business_kind", "order", "depends_on", "command", "deterministic", "dispatcher_stage"}:
            _fail("E_RECIPE_PLAN", f"/payload/stages/{index}", "closed stage required")
        _id(stage["id"], f"/payload/stages/{index}/id")
        if stage["id"] in ids:
            _fail("E_RECIPE_PLAN", f"/payload/stages/{index}/id", "duplicate stage id")
        ids.add(stage["id"])
        if type(stage["order"]) is not int or stage["order"] != index:
            _fail("E_RECIPE_PLAN", f"/payload/stages/{index}/order", "stage order must be contiguous")
        if (type(stage["kind"]) is not str or stage["kind"] not in {"execute", "freeze", "check", "verdict"}
                or type(stage["business_kind"]) is not str or stage["business_kind"] not in BUSINESS_KINDS):
            _fail("E_RECIPE_PLAN", f"/payload/stages/{index}", "unsupported stage mapping")
        if STAGE_MAP[stage["business_kind"]] != stage["kind"] or stage["deterministic"] is not True or stage["dispatcher_stage"] is not False:
            _fail("E_RECIPE_PLAN", f"/payload/stages/{index}", "invalid stage mapping flags")
        _command(stage["command"], f"/payload/stages/{index}/command")
        dependencies = stage["depends_on"]
        if (not isinstance(dependencies, list)
                or any(type(item) is not str or item not in ids or item == stage["id"] for item in dependencies)
                or len(set(dependencies)) != len(dependencies)):
            _fail("E_RECIPE_PLAN", f"/payload/stages/{index}/depends_on", "unknown stage dependency")
    expected_mapping = {stage["id"]: stage["kind"] for stage in payload["stages"]}
    if not isinstance(payload["mapping"], Mapping) or payload["mapping"] != expected_mapping:
        _fail("E_RECIPE_PLAN", "/payload/mapping", "stage mapping drift")
    return normalized


__all__ = ["CHECK_PLAN_RECORD_TYPE", "compile_recipe", "validate_recipe", "validate_check_plan", "validate_compile_receipt"]
