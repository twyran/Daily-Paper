import unittest

from foundation_paper import append_missing_progress


class FoundationProgressTests(unittest.TestCase):
    def test_reroll_preserves_read_state_and_adds_new_paper_once(self):
        original = "# Progress\n- [x] Read paper <!-- foundation_id:read -->\n"
        batch = [{"id": "read", "title": "Read paper"},
                 {"id": "new", "title": "New paper"}]
        updated = append_missing_progress(original, batch)
        self.assertIn("- [x] Read paper <!-- foundation_id:read -->", updated)
        self.assertIn("- [ ] **已读：New paper** <!-- foundation_id:new -->", updated)
        self.assertEqual(updated.count("foundation_id:read"), 1)
        self.assertEqual(append_missing_progress(updated, batch), updated)


if __name__ == "__main__":
    unittest.main()
