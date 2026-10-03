import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scripts.pi_dispatch as dispatch  # noqa: E402


class PlannerDispatchGateTests(unittest.TestCase):
    def test_planner_publication_requires_matching_current_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_dir = root / ".agent" / "publications"
            receipt_dir.mkdir(parents=True)
            md = b"# TASK: demo.v1\n"
            machine = b"{\"contract_family\":\"planner-v2\"}\n"
            receipt = {
                "record_type": "publication-receipt", "schema_version": 1,
                "publication_id": "pub-1", "candidate_id": "candidate-1",
                "task_id": "demo", "plan_version": 1,
                "members": {"markdown_sha256": hashlib.sha256(md).hexdigest(),
                            "json_sha256": hashlib.sha256(machine).hexdigest()},
                "review_ref": {"decision": "APPROVED", "approval_id": "approval-1"},
                "idempotency_key": "publish-1", "generation": 1,
                "state": "PUBLISHED", "outbox_seq": 1,
            }
            path = receipt_dir / "demo.v1.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            repo = dispatch.Repo(root)
            self.assertEqual(dispatch.verify_planner_publication(repo, "demo.v1", md, machine), [])
            bad = machine + b" "
            self.assertTrue(dispatch.verify_planner_publication(repo, "demo.v1", md, bad))

    def test_derive_json_refuses_planner_v2_downgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plans = root / ".agent" / "plans"; plans.mkdir(parents=True)
            (plans / "demo.v1.md").write_text(
                "# TASK: demo\n\n## Identity\n- plan_version: 1\n- contract_family: planner-v2\n",
                encoding="utf-8")
            fake = SimpleNamespace(root=root, plans_dir=plans,
                                   plan_paths=lambda key: (plans / (key + ".md"), plans / (key + ".json")))
            args = SimpleNamespace(repo=None, plan_key="demo.v1", title=None, force=True, print_only=False)
            with patch.object(dispatch.Repo, "discover", return_value=fake):
                with self.assertRaises(dispatch.DispatchError) as ctx:
                    dispatch.cmd_derive_json(args)
            self.assertEqual(ctx.exception.code, dispatch.EXIT_BLOCKED)


if __name__ == "__main__":
    unittest.main()
