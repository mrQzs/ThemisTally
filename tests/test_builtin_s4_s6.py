import sys
import tempfile
import unittest
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.builtin_artifacts import ArtifactError
from codekit.builtin_regression import collect_targets, summarize_results
from codekit.builtin_mutation import build_mutation_plan, reduce_mutation_results
from codekit.builtin_regression_reduction import reduce_regression_and_mutation
from codekit.deterministic_check import build_check_artifact, check_execution_id, make_check_evidence
from codekit.builtin_platform import classify_failure, make_platform_observation, reconcile_failure
from codekit.builtin_catalog import build_catalog, load_builtin_catalog, load_builtin_recipes, project_catalog_readiness
from codekit.builtin_projections import CursorProjection, ProjectionEvent, project_state, render_brief
from codekit.projection_store import PersistentProjectionStore


def ref(name):
    return {"kind": "file", "id": name, "path": "fixtures/" + name + ".json", "sha256": "a" * 64}

class S4RegressionMutationTests(unittest.TestCase):
    def test_target_semantics_are_deterministic_and_zero_is_not_pass(self):
        plan = collect_targets({"targets": ["b", "a", "skip"], "skip": ["skip"], "xfail": ["b"]})
        self.assertEqual(plan["selected"], ["a"])
        self.assertEqual(summarize_results(plan, [{"target": "a", "status": "PASS"}, {"target": "b", "status": "XFAIL"}, {"target": "skip", "status": "SKIP"}])["outcome"], "PASS")
        empty = collect_targets({"targets": []})
        self.assertEqual(summarize_results(empty, [])['outcome'], "NOT_RUN")

    def test_mutation_requires_baseline_and_kills_every_mutant(self):
        plan = build_mutation_plan([{"id": "m2", "path": "tests/x.py", "description": "flip"}, {"id": "m1", "path": "scripts/x.py", "description": "delete"}], baseline_id="base")
        self.assertEqual([x["id"] for x in plan["mutations"]], ["m1", "m2"])
        self.assertEqual(reduce_mutation_results(plan, "PASS", [{"id": "m1", "status": "FAIL"}, {"id": "m2", "status": "FAIL"}])["outcome"], "PASS")
        self.assertEqual(reduce_mutation_results(plan, "PASS", [{"id": "m1", "status": "PASS"}, {"id": "m2", "status": "FAIL"}])["outcome"], "FAIL")
        self.assertEqual(reduce_mutation_results(plan, "NOT_RUN", [{"id": "m1", "status": "FAIL"}, {"id": "m2", "status": "FAIL"}])["outcome"], "BLOCKED")

    def test_reduction_does_not_use_best_of(self):
        self.assertEqual(reduce_regression_and_mutation({"outcome": "PASS"}, {"outcome": "BLOCKED"})["outcome"], "BLOCKED")
        self.assertEqual(reduce_regression_and_mutation({"outcome": "FAIL"}, {"outcome": "PASS"})["outcome"], "FAIL")

class S5ExecutionTests(unittest.TestCase):
    def test_deterministic_evidence_is_reference_only_without_dispatcher(self):
        a = check_execution_id(check_plan_id="cp", candidate_digest="c", environment_digest="e")
        b = check_execution_id(check_plan_id="cp", candidate_digest="c", environment_digest="e")
        self.assertEqual(a, b)
        self.assertEqual(make_check_evidence(check_plan_id="cp", candidate_digest="c", environment_digest="e", status="PASS")["status"], "REFERENCE_ONLY")
        with self.assertRaisesRegex(ArtifactError, "E_CHECK_RECEIPT"):
            make_check_evidence(check_plan_id="cp", candidate_digest="c", environment_digest="e", status="PASS", dispatcher_connected=True)
        receipt = {"check_execution_id": a, "check_plan_id": "cp", "candidate_digest": "c", "environment_digest": "e", "status": "PASS"}
        self.assertEqual(make_check_evidence(check_plan_id="cp", candidate_digest="c", environment_digest="e", status="PASS", dispatcher_connected=True, dispatcher_receipt=receipt)["status"], "REFERENCE_ONLY")

    def test_check_artifact_rejects_mismatched_dispatcher_receipt(self):
        evidence = make_check_evidence(check_plan_id="cp", candidate_digest="c", environment_digest="e", status="PASS",
                                       dispatcher_connected=True,
                                       dispatcher_receipt={"check_execution_id": check_execution_id(check_plan_id="cp", candidate_digest="c", environment_digest="e"),
                                                           "check_plan_id": "cp", "candidate_digest": "c", "environment_digest": "e", "status": "PASS"})
        forged = dict(evidence); forged["dispatcher_receipt"] = {**evidence["dispatcher_receipt"], "status": "FAIL"}
        with self.assertRaisesRegex(ArtifactError, "E_CHECK_EVIDENCE"):
            build_check_artifact(artifact_id="check", producer={"kind": "builtin-plugin", "id": "python-checks", "version": "1.0.0"},
                                 candidate_ref=None, environment_ref=None, source_refs=[], plan={}, evidence=forged)

    def test_platform_failures_reconcile_conservatively(self):
        obs = make_platform_observation(os_name="windows", adapter_id="native-windows")
        failure = classify_failure(kind="start_unknown", detail="no process receipt")
        result = reconcile_failure(obs, failure)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertFalse(result["production_ready"])
        with self.assertRaises(ArtifactError):
            classify_failure(kind="drift", expected_generation=2, observed_generation=2)

class S6ProjectionTests(unittest.TestCase):
    def test_catalog_readiness_and_dispatch_boundary(self):
        catalog = build_catalog(plugins=[{"plugin_id": "docs", "version": "1.0.0", "manifest_ref": ref("manifest"), "lock_ref": ref("lock")}])
        ready = project_catalog_readiness(catalog, requested=["docs"])
        self.assertEqual(ready["status"], "READY")
        self.assertEqual(ready["dispatch_eligibility"], "not_evaluated")
        self.assertEqual(project_catalog_readiness(catalog, requested=["missing"])["status"], "BLOCKED")

    def test_checked_in_seven_plugin_and_three_recipe_fixtures(self):
        catalog = load_builtin_catalog()
        self.assertEqual({row["plugin_id"] for row in catalog["plugins"]}, {"repo-analysis", "code-change", "python-checks", "docs-change", "docs-checks", "regression-tests", "mutation-review"})
        recipes = load_builtin_recipes()
        self.assertEqual({row["recipe_id"] for row in recipes["recipes"]}, {"repair", "docs", "regression"})

    def test_cursor_dedup_gap_and_rebuild(self):
        p = CursorProjection()
        event = ProjectionEvent(1, "s", "x", {"v": 1})
        self.assertEqual(p.consume([event], generation=1), "APPLIED")
        self.assertEqual(p.consume([event], generation=1), "REPLAY")
        with self.assertRaisesRegex(ArtifactError, "E_EVENT_GAP"):
            p.consume([ProjectionEvent(3, "s", "z", {})], generation=1)
        p.rebuild([{"id": "authority"}], generation=1)
        self.assertEqual(p.cursor, 0)

    def test_state_and_brief_are_read_only_projections(self):
        state = project_state(cursor=2, source_vector={"s": 2}, status="PASS")
        self.assertEqual(state["health"], "healthy")
        brief = render_brief(state)
        self.assertEqual(brief["dispatch_eligibility"], "not_evaluated")

    def test_persistent_projection_recovers_tail_and_fences_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "projection.jsonl"
            store = PersistentProjectionStore(path)
            event = ProjectionEvent(1, "authority", "ready", {"id": "r1"})
            self.assertEqual(store.consume([event], generation=1), "APPLIED")
            store.handoff(new_generation=2, expected_generation=1)
            self.assertEqual(store.consume([ProjectionEvent(2, "authority", "done", {})], generation=2), "APPLIED")
            with path.open("ab") as handle:
                handle.write(b'{"kind":"event"')
            recovered = PersistentProjectionStore(path)
            self.assertEqual(recovered.recovery, "TRUNCATED_TAIL")
            self.assertEqual(recovered.generation, 2)
            self.assertEqual(recovered.cursor, 2)
            self.assertTrue(recovered.reconcile(expected_generation=2, expected_cursor=2)["ok"])
            with self.assertRaisesRegex(ArtifactError, "E_RECOVERY"):
                recovered.consume([ProjectionEvent(3, "authority", "later", {})], generation=2)

    def test_persistent_projection_rebuild_uses_cursor_cas(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PersistentProjectionStore(Path(tmp) / "projection.jsonl")
            with self.assertRaisesRegex(ArtifactError, "E_CAS"):
                store.rebuild([], generation=1, expected_cursor=1)
            store.rebuild([{"id": "authority"}], generation=1, expected_cursor=0)
            reopened = PersistentProjectionStore(store.path)
            self.assertEqual(reopened.cursor, 0)
            self.assertEqual(reopened.events["authority"]["payload"]["rows"], [{"id": "authority"}])

    def test_persistent_projection_rejects_forged_checkpoint_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "projection.jsonl"
            store = PersistentProjectionStore(path)
            store.consume([ProjectionEvent(1, "authority", "ready", {"id": "r1"})], generation=1)
            valid = {"kind": "checkpoint", "generation": 1, "cursor": store.cursor,
                     "source_vector": store.source_vector, "events": store.events}
            path.write_text(json.dumps(valid, separators=(",", ":")) + "\n", encoding="utf-8")
            self.assertEqual(PersistentProjectionStore(path).cursor, 1)
            for changed, code in (
                ({**valid, "extra": True}, "E_JOURNAL_CORRUPT"),
                ({**valid, "source_vector": {}}, "E_JOURNAL_CORRUPT"),
                ({**valid, "events": {"forged": next(iter(valid["events"].values()))}}, "E_EVENT_ID"),
            ):
                path.write_text(json.dumps(changed, separators=(",", ":")) + "\n", encoding="utf-8")
                with self.subTest(code=code):
                    with self.assertRaisesRegex(ArtifactError, code):
                        PersistentProjectionStore(path)

if __name__ == "__main__":
    unittest.main()
