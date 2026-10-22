"""The sandbox mirror must not look like a payment."""

import unittest

from watcher.mirror import mirror_release


class MirrorTests(unittest.TestCase):
    def test_record_is_labeled_sandbox_and_moves_nothing(self):
        record = mirror_release("0xabc", "kabonyo-kanyagwal", 50_000_000_000_000_000)
        self.assertEqual(record["label"], "SANDBOX")
        self.assertFalse(record["moved_kes"])
        self.assertEqual(record["zone"], "kabonyo-kanyagwal")

    def test_blank_trigger_is_rejected(self):
        with self.assertRaises(ValueError):
            mirror_release("", "ahero", 1)


if __name__ == "__main__":
    unittest.main()
