import unittest

from foundation_paper import append_missing_progress, render_feishu_card


class FoundationProgressTests(unittest.TestCase):
    def test_reroll_card_keeps_exclusions_from_previous_batches(self):
        card = render_feishu_card("2026-09-29", [{"id": "third", "title": "Third paper"}],
                                  prior_exclude_ids={"first", "second"})
        button = next(action for element in card["elements"]
                      for action in element.get("actions", [])
                      if action.get("value", {}).get("action") == "reroll")
        self.assertEqual(button["value"]["exclude_ids"], "first,second,third")

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
