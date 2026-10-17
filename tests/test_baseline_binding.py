#!/usr/bin/env python3
"""07-T2B-S structural baseline-binding tests."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit import protocols  # noqa: E402
from codekit.baseline_binding import (  # noqa: E402
    BaselineBinding,
    parse_baseline_binding,
    validate_baseline_binding,
)


BASE_SHA = "a" * 40
TREE_SHA = "b" * 40
REF = {"kind": "accepted-result", "id": "alpha-result", "sha256": "c" * 64, "path": "evidence/alpha.json"}


def sample() -> dict[str, object]:
    return {
        "record_type": "baseline-binding",
        "schema_version": 1,
        "repo_id": "code-kit",
        "environment_id": "windows-review",
        "object_format": "sha1",
        "base_sha": BASE_SHA,
        "tree_sha": TREE_SHA,
        "upstream_results": [copy.deepcopy(REF)],
        "coverage_mode": "exact_tree",
        "coverage_refs": [copy.deepcopy(REF)],
        "authorization_ref": {"kind": "authorization", "id": "baseline-use", "sha256": "d" * 64,
                              "path": "evidence/authorization.json"},
        "observation_ref": {"kind": "observation", "id": "git-observation", "sha256": "e" * 64,
                             "path": "evidence/git.json"},
        "guard_version": 1,
    }


class BaselineBindingTests(unittest.TestCase):
    def assertCode(self, code: str, value: object, field: str | None = None) -> None:
        with self.assertRaises(protocols.ProtocolError) as caught:
            validate_baseline_binding(value)
        self.assertEqual(caught.exception.code, code)
        if field is not None:
            self.assertEqual(caught.exception.field, field)

    def test_valid_binding_is_immutable_and_detached(self) -> None:
        value = sample()
        result = validate_baseline_binding(value)
        self.assertIsInstance(result, BaselineBinding)
        self.assertEqual(result.base_sha, BASE_SHA)
        value["repo_id"] = "changed"
        value["coverage_refs"][0]["path"] = "changed.json"  # type: ignore[index]
        self.assertEqual(result.repo_id, "code-kit")
        self.assertEqual(result.record["coverage_refs"][0]["path"], "evidence/alpha.json")
        with self.assertRaises(TypeError):
            result.record["repo_id"] = "changed"  # type: ignore[index]

    def test_parse_bytes_uses_strict_json(self) -> None:
        raw = json.dumps(sample(), separators=(",", ":")).encode("utf-8")
        self.assertEqual(parse_baseline_binding(raw).coverage_mode, "exact_tree")
        self.assertEqual(parse_baseline_binding(raw + b"\n").coverage_mode, "exact_tree")
        with self.assertRaises(protocols.ProtocolError) as caught:
            parse_baseline_binding(raw + b" trailing")
        self.assertEqual(caught.exception.code, "E_JSON_SYNTAX")

    def test_git_oid_must_match_declared_object_format(self) -> None:
        value = sample()
        value["object_format"] = "sha256"
        self.assertCode("E_GIT_OID_SYNTAX", value, "/base_sha")
        value = sample()
        value["base_sha"] = "A" * 40
        self.assertCode("E_GIT_OID_SYNTAX", value, "/base_sha")

    def test_coverage_mode_and_evidence_are_required(self) -> None:
        for mode in ("pinned_artifact_set", "revalidated_integration"):
            value = sample()
            value["coverage_mode"] = mode
            self.assertEqual(validate_baseline_binding(value).coverage_mode, mode)
        value = sample()
        value["coverage_mode"] = "branch"
        self.assertCode("E_SCHEMA_FIELDS", value, "/coverage_mode")
        value = sample()
        value["coverage_refs"] = []
        self.assertCode("E_SCHEMA_FIELDS", value, "/coverage_refs")

    def test_missing_or_unknown_fields_are_rejected(self) -> None:
        value = sample()
        del value["authorization_ref"]
        self.assertCode("E_SCHEMA_FIELDS", value)
        value = sample()
        value["base_sha_short"] = BASE_SHA
        self.assertCode("E_SCHEMA_FIELDS", value)

    def test_resource_refs_use_file_sha256_and_safe_paths(self) -> None:
        value = sample()
        value["observation_ref"] = copy.deepcopy(REF)
        value["observation_ref"]["path"] = "../git.json"  # type: ignore[index]
        self.assertCode("E_PATH_SYNTAX", value, "/observation_ref/path")
        value = sample()
        value["observation_ref"]["sha256"] = "F" * 64  # type: ignore[index]
        self.assertCode("E_ID_SYNTAX", value, "/observation_ref/sha256")

    def test_resource_refs_reject_mutable_aliases(self) -> None:
        value = sample()
        value["authorization_ref"]["id"] = "latest"  # type: ignore[index]
        self.assertCode("E_SCHEMA_FIELDS", value, "/authorization_ref/id")

    def test_upstream_results_can_be_empty_but_must_be_refs(self) -> None:
        value = sample()
        value["upstream_results"] = []
        self.assertEqual(validate_baseline_binding(value).record["upstream_results"], ())
        value = sample()
        value["upstream_results"] = [{"kind": "accepted-result"}]
        self.assertCode("E_SCHEMA_FIELDS", value, "/upstream_results/0")

    def test_guard_version_is_positive_exact_integer(self) -> None:
        for bad in (0, True, 1.0, "1"):
            value = sample()
            value["guard_version"] = bad
            self.assertCode("E_SCHEMA_TYPE" if bad is True or isinstance(bad, (float, str)) else "E_INTEGER_RANGE",
                            value, "/guard_version")

    def test_schema_declares_the_same_closed_record_family(self) -> None:
        schema = json.loads((ROOT / "schemas" / "baseline-binding-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "urn:codekit:baseline-binding:1")
        self.assertEqual(schema["properties"]["record_type"]["const"], "baseline-binding")
        self.assertEqual(set(schema["required"]), set(sample()))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["coverage_mode"]["enum"],
                         ["exact_tree", "pinned_artifact_set", "revalidated_integration"])
        self.assertEqual(schema["$defs"]["resourceRef"]["properties"]["id"]["$ref"], "#/$defs/immutableId")


if __name__ == "__main__":
    unittest.main(verbosity=2)
