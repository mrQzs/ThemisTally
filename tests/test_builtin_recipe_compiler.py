import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.builtin_artifacts import ArtifactError, digest
from codekit.builtin_recipe_compiler import compile_recipe, validate_check_plan, validate_compile_receipt, validate_recipe


def ref(name="source"):
    return {"kind": "file", "id": name, "path": f"recipes/{name}.json", "sha256": "a" * 64}


def recipe():
    return {"record_type": "builtin-task-recipe", "schema_version": 1, "recipe_id": "repair", "recipe_version": 1,
            "plugin_id": "code-change", "plugin_version": "1.0.0", "steps": [
                {"id": "analysis", "kind": "analysis", "depends_on": [], "command": ["python", "-m", "compileall"], "deterministic": True},
                {"id": "change", "kind": "change", "depends_on": ["analysis"], "command": ["python", "-m", "unittest"], "deterministic": True},
                {"id": "freeze", "kind": "freeze", "depends_on": ["change"], "command": ["python", "-c", "freeze"], "deterministic": True},
                {"id": "check", "kind": "check", "depends_on": ["freeze"], "command": ["python", "-m", "unittest"], "deterministic": True},
                {"id": "review", "kind": "review", "depends_on": ["check"], "command": ["python", "-c", "review"], "deterministic": True},
            ]}


class RecipeCompilerTests(unittest.TestCase):
    def test_compile_maps_business_ports_to_existing_stage_kinds(self):
        result = compile_recipe(recipe(), artifact_id="plan-1", producer={"kind": "builtin-plugin", "id": "code-change", "version": "1.0.0"},
                                source_refs=[ref()], candidate_ref=ref("candidate"), environment_ref=ref("environment"))
        plan, receipt = result["check_plan"], result["compile_receipt"]
        self.assertEqual([x["kind"] for x in plan["payload"]["stages"]], ["execute", "execute", "freeze", "check", "verdict"])
        self.assertFalse(plan["payload"]["production_ready"])
        self.assertFalse(receipt["dispatcher_submitted"])
        self.assertEqual(validate_compile_receipt(receipt)["receipt_id"], "plan-1.receipt")

    def test_missing_dependency_cycle_and_dynamic_command_rejected(self):
        bad = recipe(); bad["steps"][1]["depends_on"] = ["missing"]
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_DEPENDENCY"):
            validate_recipe(bad)
        bad = recipe(); bad["steps"][0]["depends_on"] = ["review"]
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_CYCLE"):
            validate_recipe(bad)
        bad = recipe(); bad["steps"][0]["command"] = ["sh", "-c", "echo $TOKEN"]
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_COMMAND"):
            validate_recipe(bad)
        bad = recipe(); bad["steps"][0]["kind"] = []
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_KIND"):
            validate_recipe(bad)

    def test_receipt_drift_is_rejected(self):
        result = compile_recipe(recipe(), artifact_id="plan-1", producer={"kind": "builtin-plugin", "id": "code-change", "version": "1.0.0"},
                                source_refs=[ref()], candidate_ref=None, environment_ref=None)
        receipt = copy.deepcopy(result["compile_receipt"]); receipt["ordered_step_ids"].reverse()
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_DRIFT"):
            validate_compile_receipt(receipt)

    def test_receipt_dependency_order_and_plan_order_are_bound(self):
        result = compile_recipe(recipe(), artifact_id="plan-1", producer={"kind": "builtin-plugin", "id": "code-change", "version": "1.0.0"},
                                source_refs=[ref()], candidate_ref=None, environment_ref=None)
        plan = copy.deepcopy(result["check_plan"])
        plan["payload"]["stages"][0]["order"] = 9
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_PLAN"):
            from codekit.builtin_recipe_compiler import validate_check_plan
            validate_check_plan(plan)
        receipt = copy.deepcopy(result["compile_receipt"])
        receipt["ordered_step_ids"].reverse()
        unsigned = dict(receipt); unsigned.pop("receipt_sha256")
        receipt["receipt_sha256"] = digest(unsigned)
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_RECEIPT"):
            validate_compile_receipt(receipt)

    def test_receipt_identity_and_status_types_are_closed(self):
        result = compile_recipe(recipe(), artifact_id="plan-1", producer={"kind": "builtin-plugin", "id": "code-change", "version": "1.0.0"},
                                source_refs=[ref()], candidate_ref=None, environment_ref=None)
        for field, value, error in (("status", [], "E_RECIPE_RECEIPT"), ("recipe_id", [], "E_RECIPE_ID"),
                                    ("plugin_id", [], "E_RECIPE_ID"), ("plugin_version", "latest", "E_RECIPE_RECEIPT")):
            receipt = copy.deepcopy(result["compile_receipt"])
            receipt[field] = value
            unsigned = dict(receipt); unsigned.pop("receipt_sha256")
            receipt["receipt_sha256"] = digest(unsigned)
            with self.assertRaisesRegex(ArtifactError, error):
                validate_compile_receipt(receipt)
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_STATUS"):
            compile_recipe(recipe(), artifact_id="plan-1", producer={"kind": "builtin-plugin", "id": "code-change", "version": "1.0.0"},
                           source_refs=[ref()], candidate_ref=None, environment_ref=None, status=[])

    def test_plan_rejects_mutable_plugin_identity_and_duplicate_dependencies(self):
        result = compile_recipe(recipe(), artifact_id="plan-1", producer={"kind": "builtin-plugin", "id": "code-change", "version": "1.0.0"},
                                source_refs=[ref()], candidate_ref=None, environment_ref=None)
        plan = copy.deepcopy(result["check_plan"])
        plan["payload"]["plugin_version"] = "latest"
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_PLAN"):
            validate_check_plan(plan)
        plan = copy.deepcopy(result["check_plan"])
        plan["payload"]["stages"][1]["depends_on"] = ["analysis", "analysis"]
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_PLAN"):
            validate_check_plan(plan)

    def test_compile_rejects_none_or_non_sequence_inputs(self):
        kwargs = {"artifact_id": "plan-1", "producer": {"kind": "builtin-plugin", "id": "code-change", "version": "1.0.0"},
                  "candidate_ref": None, "environment_ref": None}
        for source_refs in (None, "source", b"source"):
            with self.subTest(source_refs=type(source_refs).__name__):
                with self.assertRaisesRegex(ArtifactError, "E_RECIPE_SCHEMA"):
                    compile_recipe(recipe(), source_refs=source_refs, **kwargs)
        bad_kwargs = dict(kwargs)
        bad_kwargs["producer"] = None
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_SCHEMA"):
            compile_recipe(recipe(), source_refs=[], **bad_kwargs)


if __name__ == "__main__":
    unittest.main()
