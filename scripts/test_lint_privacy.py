"""Run with: python -m unittest discover -s scripts -p 'test_*.py'"""

import unittest

from lint_privacy import findings

# Made up, and split so this file passes its own lint.
ACCOUNT_ID = "Fake" + "Id0123456789AbCdEfGhIjKlMnOp"
POST_ID = "fake" + "post0123456789abcdefg"


class PrivacyLintTests(unittest.TestCase):
    def kinds(self, text, terms=()):
        return [what for _, what, _ in findings(text, list(terms))]

    def test_catches_what_real_use_leaves_behind(self):
        self.assertEqual(self.kinds(f'"accountId": "{ACCOUNT_ID}"'), ["account id"])
        self.assertEqual(self.kinds(f"post {POST_ID} failed"), ["post id"])
        self.assertEqual(self.kinds("see /Users/someone/notes.md"), ["home path"])  # privacy-lint: allow
        self.assertEqual(self.kinds("mail owner@brand.co"), ["email"])  # privacy-lint: allow
        self.assertEqual(self.kinds("Our Brand posted", ["our brand"]), ["private term"])

    def test_lets_ordinary_text_through(self):
        # A hex digest is one case, a camelCase key has no digits, a help-centre
        # link is public, and the published contact address is meant to be here.
        self.assertEqual(self.kinds("ab" * 32), [])
        self.assertEqual(self.kinds('"measuredDestinationsInSaves": 3'), [])
        self.assertEqual(self.kinds("https://help.instagram.com/362497417173378"), [])
        self.assertEqual(self.kinds("hello@vmgmsoftware.com, ops@example.com"), [])

    def test_masks_what_it_reports(self):
        # CI logs on a public repository are public.
        [(_, _, masked)] = findings(f"id {ACCOUNT_ID}", [])
        self.assertNotIn(ACCOUNT_ID, masked)

    def test_a_marked_line_is_skipped(self):
        self.assertEqual(self.kinds(f"{ACCOUNT_ID}  # privacy-lint: allow"), [])


if __name__ == "__main__":
    unittest.main()
