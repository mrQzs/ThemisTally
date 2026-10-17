"""Validate actual built-in fixture instances against the published schemas.

These are structural checks only.  Dependency graphs, content hashes and
cross-field authorization remain the responsibility of their runtime validators.
"""

import copy
import json
import os
import sys
import unittest
from pathlib import Path

try:
    from jsonschema import Draft202012Validator, ValidationError
except ImportError:
    Draft202012Validator = None
    ValidationError = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from codekit.builtin_catalog import load_builtin_catalog, load_builtin_recipes


SCHEMAS = {
    "catalog": "schemas/builtin-task-artifacts/catalog.schema.json",
    "recipes": "schemas/builtin-task-artifacts/recipes.schema.json",
    "lock": "schemas/plugin-lock-v1.schema.json",
}
PLUGIN_IDS = {
    "repo-analysis", "code-change", "python-checks", "docs-change",
    "docs-checks", "regression-tests", "mutation-review",
}


def load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def load_from_repository(loader):
    # The catalog's ResourceRefs must remain repository-relative.  Passing an
    # absolute root to the loader would change the instance being validated.
    previous = Path.cwd()
    try:
        os.chdir(ROOT)
        return loader()
    finally:
        os.chdir(previous)


@unittest.skipIf(Draft202012Validator is None, "jsonschema is not installed; run with the existing WSL Python environment")
class BuiltinSchemaInstanceTests(unittest.TestCase):
    def validator(self, name):
        schema = load_json(SCHEMAS[name])
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)

    def test_seven_plugin_catalog_loader_output_satisfies_schema(self):
        catalog = load_from_repository(load_builtin_catalog)
        self.assertEqual(len(catalog["plugins"]), 7)
        self.assertEqual({row["plugin_id"] for row in catalog["plugins"]}, PLUGIN_IDS)
        self.validator("catalog").validate(catalog)

    def test_all_seven_checked_in_locks_satisfy_schema(self):
        validator = self.validator("lock")
        for plugin_id in sorted(PLUGIN_IDS):
            with self.subTest(plugin_id=plugin_id):
                lock = load_json("plugins/" + plugin_id + "/lock.json")
                self.assertEqual([row["plugin_id"] for row in lock["plugins"]], [plugin_id])
                validator.validate(lock)

    def test_three_recipe_loader_output_satisfies_schema_without_rewriting(self):
        recipes = load_from_repository(load_builtin_recipes)
        self.assertEqual(len(recipes["recipes"]), 3)
        self.assertEqual({row["recipe_id"] for row in recipes["recipes"]}, {"repair", "docs", "regression"})
        # Keep the loader's record_type unchanged: a schema/producer mismatch
        # must fail here rather than being normalized away by the test.
        self.validator("recipes").validate(recipes)

    def test_catalog_rejects_scalar_plugin_row(self):
        catalog = load_from_repository(load_builtin_catalog)
        catalog["plugins"] = [123]
        with self.assertRaises(ValidationError) as raised:
            self.validator("catalog").validate(catalog)
        self.assertEqual(list(raised.exception.absolute_path), ["plugins", 0])

    def test_recipes_reject_scalar_recipe_row(self):
        schema = load_json(SCHEMAS["recipes"])
        # This isolated structural negative case uses the schema's header, so
        # a loader/header mismatch cannot mask a permissive items definition.
        recipes = {"record_type": schema["properties"]["record_type"]["const"],
                   "schema_version": 1, "recipes": [123]}
        with self.assertRaises(ValidationError) as raised:
            self.validator("recipes").validate(recipes)
        self.assertEqual(list(raised.exception.absolute_path), ["recipes", 0])

    def test_lock_rejects_scalar_plugin_row(self):
        lock = load_json("plugins/repo-analysis/lock.json")
        lock["plugins"] = [123]
        with self.assertRaises(ValidationError) as raised:
            self.validator("lock").validate(lock)
        self.assertEqual(list(raised.exception.absolute_path), ["plugins", 0])

    def test_catalog_and_lock_rows_reject_missing_or_extra_fields(self):
        instances = {
            "catalog": load_from_repository(load_builtin_catalog),
            "lock": load_json("plugins/repo-analysis/lock.json"),
        }
        for family, original in instances.items():
            for mutation in ("missing", "extra"):
                with self.subTest(family=family, mutation=mutation):
                    value = copy.deepcopy(original)
                    row = value["plugins"][0]
                    if mutation == "missing":
                        del row["plugin_id"]
                    else:
                        row["unknown"] = True
                    with self.assertRaises(ValidationError) as raised:
                        self.validator(family).validate(value)
                    self.assertEqual(list(raised.exception.absolute_path), ["plugins", 0])


if __name__ == "__main__":
    unittest.main()
