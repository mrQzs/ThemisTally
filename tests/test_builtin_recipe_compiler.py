import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.builtin_artifacts import ArtifactError
from codekit.builtin_recipe_compiler import compile_recipe, validate_compile_receipt, validate_recipe


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

    def test_receipt_drift_is_rejected(self):
        result = compile_recipe(recipe(), artifact_id="plan-1", producer={"kind": "builtin-plugin", "id": "code-change", "version": "1.0.0"},
                                source_refs=[ref()], candidate_ref=None, environment_ref=None)
        receipt = copy.deepcopy(result["compile_receipt"]); receipt["ordered_step_ids"].reverse()
        with self.assertRaisesRegex(ArtifactError, "E_RECIPE_DRIFT"):
            validate_compile_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
