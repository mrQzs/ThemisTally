import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.codekit.planner import (
    ContractIR, DraftStore, PlannerError, PlanningService, PublicationStore, build_candidate,
    make_resource_ref, render_contract_ir, validate_contract_candidate,
    validate_publication_receipt,
)
from scripts import pi_dispatch


def sample_ir():
    return {
        "task_id": "offline-contract", "plan_version": 1, "title": "Offline contract",
        "repository": "Code-Kit", "base_sha": "a" * 40, "risk_level": "low",
        "authorization": {"executor": ["local_edit", "local_test"], "integration": []},
        "executor": {"provider": "offline", "model": "stub", "thinking": "high",
                      "tools": ["bash"], "context_files": "project"},
        "scope": {"allowed_modified_files": [], "allowed_new_files": ["tests/fixtures/x.json"],
                  "allowed_deleted_files": [], "forbidden_paths": ["AGENTS.md"],
                  "dependency_changes": "forbidden"},
        "setup": [], "checks": [{"id": "V01", "argv": ["python", "-m", "compileall", "-q", "scripts/codekit"],
                                  "cwd": ".", "timeout_seconds": 60, "expected_exit_code": 0, "required": True}],
        "definition_of_done": [{"id": "D01", "text": "rendered", "evidence": ["V01"]}],
        "budget": {"max_attempts_total": 1, "max_wall_seconds_per_attempt": 60,
                   "max_wall_seconds_total": 60, "cost_budget": None},
    }


class PlannerPublicationTests(unittest.TestCase):
    def test_same_source_render_and_revision_cas(self):
        ir = ContractIR.from_mapping(sample_ir())
        md, raw = render_contract_ir(ir)
        contract, errors, _warnings = pi_dispatch.validate_contract(
            md.decode("utf-8"), json.loads(raw.decode("utf-8")), "offline-contract.v1")
        self.assertIsNotNone(contract)
        self.assertEqual(errors, [])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), hashlib.sha256(render_contract_ir(ir)[1]).hexdigest())
        store = DraftStore()
        first = store.create_draft("draft-1", ir.to_mapping())
        second = store.revise("draft-1", ir.to_mapping(), expected_head=1)
        self.assertEqual((first.revision, second.revision), (1, 2))
        with self.assertRaises(PlannerError) as ctx:
            store.revise("draft-1", ir.to_mapping(), expected_head=1)
        self.assertEqual(ctx.exception.code, "E_CAS_CONFLICT")

    def test_plan_version_slots_are_reserved_across_revisions(self):
        store = DraftStore()
        first = store.create_draft("draft-slot", sample_ir())
        changed = dict(sample_ir()); changed["plan_version"] = 2
        store.revise("draft-slot", changed, expected_head=first.revision)
        other = dict(sample_ir()); other["plan_version"] = 2
        with self.assertRaisesRegex(PlannerError, "E_VERSION_REUSED"):
            store.create_draft("other-slot", other)
        back = dict(sample_ir()); back["plan_version"] = 1
        with self.assertRaisesRegex(PlannerError, "E_VERSION_REUSED"):
            store.revise("draft-slot", back, expected_head=2)

    def test_candidate_requires_frozen_two_member_pair(self):
        ir = ContractIR.from_mapping(sample_ir()); md, raw = render_contract_ir(ir)
        draft = DraftStore().create_draft("draft-2", ir.to_mapping())
        candidate = build_candidate(candidate_id="candidate-1", draft=draft,
            source_ref=make_resource_ref("planner-input", "source-1", "inputs/source.json", raw=b"source"),
            target_ref=make_resource_ref("contract-target", "target-1", "contracts/target.json", raw=b"target"),
            md_bytes=md, json_bytes=raw)
        record = candidate.to_mapping()
        self.assertEqual({x["representation"] for x in record["members"]}, {"markdown", "json"})
        self.assertEqual(validate_contract_candidate(record)["candidate_id"], "candidate-1")
        swapped = dict(record); swapped["members"] = list(reversed(record["members"]))
        with self.assertRaisesRegex(PlannerError, "E_CANDIDATE_MEMBERS"):
            validate_contract_candidate(swapped)
        bad_ref = json.loads(json.dumps(record)); bad_ref["members"][0]["ref"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(PlannerError, "E_CANDIDATE_BYTES"):
            validate_contract_candidate(bad_ref)
        candidate.members[0]["bytes"] = b"mutated"
        with self.assertRaisesRegex(PlannerError, "E_CANDIDATE_MUTATED"):
            PublicationStore().publish(candidate, review_ref={"decision": "APPROVED", "approval_id": "a"},
                                       idempotency_key="mutated")
        with self.assertRaises(PlannerError) as ctx:
            build_candidate(candidate_id="candidate-2", draft=draft,
                source_ref=candidate.source_ref, target_ref=candidate.target_ref,
                md_bytes=md + b"x", json_bytes=raw)
        self.assertEqual(ctx.exception.code, "E_CANDIDATE_BYTES")

    def test_publication_registers_before_outbox_and_is_idempotent(self):
        ir = ContractIR.from_mapping(sample_ir()); md, raw = render_contract_ir(ir)
        draft = DraftStore().create_draft("draft-3", ir.to_mapping())
        candidate = build_candidate(candidate_id="candidate-3", draft=draft,
            source_ref=make_resource_ref("planner-input", "source-3", "inputs/source.json", raw=b"source"),
            target_ref=make_resource_ref("contract-target", "target-3", "contracts/target.json", raw=b"target"),
            md_bytes=md, json_bytes=raw)
        store = PublicationStore()
        receipt = store.publish(candidate, review_ref={"decision": "APPROVED", "approval_id": "approval-1"},
                                idempotency_key="publish-1")
        self.assertEqual(len(store.outbox), 1)
        self.assertEqual(store.publish(candidate, review_ref={"decision": "APPROVED", "approval_id": "approval-1"},
                                       idempotency_key="publish-1"), receipt)
        self.assertEqual(store.bytes_for(receipt.publication_id, "markdown"), md)
        self.assertEqual(validate_publication_receipt(receipt.to_mapping())["state"], "PUBLISHED")
        self.assertEqual(store.recover(receipt.publication_id), receipt)
        with self.assertRaises(PlannerError):
            store.publish(candidate, review_ref={"decision": "REVOKED", "approval_id": "approval-1"},
                          idempotency_key="publish-2")

    def test_service_publish_contract_projects_registered_pair(self):
        ir = ContractIR.from_mapping(sample_ir()); md, raw = render_contract_ir(ir)
        draft = DraftStore().create_draft("draft-project", ir.to_mapping())
        candidate = build_candidate(candidate_id="candidate-project", draft=draft,
            source_ref=make_resource_ref("planner-input", "source-project", "inputs/source.json", raw=b"source"),
            target_ref=make_resource_ref("contract-target", "target-project", "contracts/target.json", raw=b"target"),
            md_bytes=md, json_bytes=raw)
        service = PlanningService(); service.submit_plan_review(
            candidate, {"decision": "APPROVED", "approval_id": "approval-project"})
        with tempfile.TemporaryDirectory() as directory:
            receipt = service.publish_contract(candidate, repo_root=directory, idempotency_key="project-1")
            root = Path(directory)
            self.assertTrue((root / ".agent" / "plans" / "offline-contract.v1.md").is_file())
            self.assertTrue((root / ".agent" / "plans" / "offline-contract.v1.json").is_file())
            self.assertTrue((root / ".agent" / "publications" / "offline-contract.v1.json").is_file())
            self.assertEqual(pi_dispatch.verify_planner_publication(
                pi_dispatch.Repo(root), "offline-contract.v1", md, raw), [])
            self.assertEqual(receipt.state, "PUBLISHED")


if __name__ == "__main__":
    unittest.main()
