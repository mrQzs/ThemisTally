import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.codekit.project_views import ViewPackageStore, make_read_receipt, render_project_brief
from scripts.codekit.read_receipts import ReadReceiptError, ReadReceiptStore
from tests.test_project_views import STATE


class ReadReceiptTests(unittest.TestCase):
    def test_receipt_is_bound_to_brief_and_persistently_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); store = ViewPackageStore(root / "views"); manifest = store.publish(STATE, render_project_brief(STATE), generation=1, cursor=2)
            receipt = make_read_receipt(manifest, observer_ref="observer-1", read_cursor=2)
            receipts = ReadReceiptStore(root / "receipts.jsonl")
            self.assertFalse(receipts.append(receipt).replayed); self.assertTrue(receipts.append(receipt).replayed)
            self.assertEqual(receipt.to_mapping()["brief_sha256"], manifest.brief_sha256)

    def test_malformed_tail_is_not_repaired_implicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipts.jsonl"; path.write_bytes(b'{"record_type":"brief-read-receipt"}')
            with self.assertRaisesRegex(ReadReceiptError, "truncated"):
                ReadReceiptStore(path).append(make_read_receipt(ViewPackageStore(Path(tmp) / "v").publish(STATE, render_project_brief(STATE), generation=1, cursor=2), observer_ref="o", read_cursor=2))


if __name__ == "__main__":
    unittest.main()
