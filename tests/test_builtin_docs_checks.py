import sys
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from codekit.builtin_artifacts import ArtifactError
from codekit.builtin_docs_checks import Snapshot, build_docs_check, docs_check, local_target, markdown_facts

class DocsChecksTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = Snapshot({
            "docs/index.md": b"# Index\n<a id=\"intro\"></a>\n[Guide](guide.md#go) [External](https://example.test/x) ![pic](img.png)\n`` `[bad](gone.md)` ``\n",
            "docs/guide.md": b"# Guide\n<a id=\"go\"></a>\n",
            "docs/img.png": b"png",
        })

    def test_ast_facts_skip_code_and_keep_external_unchecked(self):
        links, anchors, unsupported = markdown_facts(self.snapshot.read("docs/index.md"))
        self.assertIn("guide.md#go", links)
        self.assertIn("https://example.test/x", links)
        self.assertNotIn("gone.md", links)
        self.assertIn("intro", anchors)

    def test_local_target_classifies_without_network(self):
        self.assertEqual(local_target("docs/index.md", "guide.md#go")[0], "LOCAL")
        self.assertEqual(local_target("docs/index.md", "https://example.test")[0], "NOT_CHECKED_EXTERNAL")
        self.assertEqual(local_target("docs/index.md", "javascript:alert(1)")[0], "FORBIDDEN_SCHEME")
        self.assertEqual(local_target("docs/index.md", "../../secret")[0], "FORBIDDEN_PATH")

    def test_docs_check_reports_links_and_drift(self):
        result = docs_check(self.snapshot, ["docs/index.md"])
        statuses = [f["status"] for f in result["findings"]]
        self.assertIn("LOCAL_OK", statuses)
        self.assertIn("NOT_CHECKED_EXTERNAL", statuses)
        self.assertEqual(result["local_status"], "SATISFIED")
        record = build_docs_check(self.snapshot, ["docs/index.md"], source_refs=[self.snapshot.ref("docs/index.md")])
        self.assertEqual(record["record_type"], "docs-check")
        drift = dict(self.snapshot.ref("docs/index.md")); drift["sha256"] = "0" * 64
        with self.assertRaisesRegex(ArtifactError, "E_DOC_RESOURCE_DRIFT"):
            build_docs_check(self.snapshot, ["docs/index.md"], source_refs=[drift])

    def test_bad_local_fragment_and_html_are_failures(self):
        snap = Snapshot({"a.md": b"<div id='x'></div>\n[bad](a.md#missing)"})
        result = docs_check(snap, ["a.md"])
        self.assertEqual(result["local_status"], "FAILED_OR_INCOMPLETE")
        self.assertTrue(any(x["status"] == "UNSUPPORTED_HTML" for x in result["findings"]))
        plain = docs_check(Snapshot({"a.md": b"[bad](a.md#missing)"}), ["a.md"])
        self.assertTrue(any(x["status"] == "BROKEN_FRAGMENT" for x in plain["findings"]))
        plain = docs_check(Snapshot({"a.md": b"[bad](a.md#missing)"}), ["a.md"])
        self.assertTrue(any(x["status"] == "BROKEN_FRAGMENT" for x in plain["findings"]))
if __name__ == "__main__": unittest.main()

