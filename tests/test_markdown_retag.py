import os
import unittest

from nlm_ingestor.ingestor.markdown_retag import (
    _detect_marker,
    retag_numbered_items,
)


def _para(text, level=0, idx=0):
    return {"block_type": "para", "block_text": text, "level": level, "block_idx": idx}


class TestDetectMarker(unittest.TestCase):
    def test_parenthesised_letter(self):
        self.assertEqual(_detect_marker("(a) First obligation."), (1, "a"))
        self.assertEqual(_detect_marker("(b) Second."), (1, "b"))

    def test_parenthesised_roman(self):
        self.assertEqual(_detect_marker("(i) Roman one."), (1, "i"))
        self.assertEqual(_detect_marker("(iii) Roman three."), (1, "iii"))

    def test_decimal(self):
        self.assertEqual(_detect_marker("1.1 Some terms."), (0, "1.1"))
        self.assertEqual(_detect_marker("1.1.1 Sub-terms."), (0, "1.1.1"))
        self.assertEqual(_detect_marker("2.4.1.3 Deep."), (0, "2.4.1.3"))

    def test_bare_number(self):
        # Bare digit. allowed — unambiguous list marker.
        self.assertEqual(_detect_marker("1. First step."), (2, "1"))
        self.assertEqual(_detect_marker("23. Twenty-third."), (2, "23"))

    def test_bare_letter_or_roman_rejected(self):
        # Bare 'a.' / 'i.' / 'v.' look like prose, not list markers.
        # Adversarial-review fix: reject to avoid retagging real sentences.
        self.assertIsNone(_detect_marker("a. Letter step."))
        self.assertIsNone(_detect_marker("i. think this is true."))
        self.assertIsNone(_detect_marker("v. important note."))

    def test_invalid_roman_rejected(self):
        # 'vix', 'iiii', 'vvv' are not valid Roman numerals and must not match.
        self.assertIsNone(_detect_marker("(vix) bad roman."))
        self.assertIsNone(_detect_marker("(iiii) bad roman."))
        self.assertIsNone(_detect_marker("(vvv) bad roman."))

    def test_false_positive_prose_no_closing_punct(self):
        # The closing-punctuation guard prevents prose from being retagged.
        self.assertIsNone(_detect_marker("the Court (a U.S. district court) held the matter"))
        self.assertIsNone(_detect_marker("(a) without ending punctuation"))

    def test_false_positive_marker_only(self):
        self.assertIsNone(_detect_marker(""))
        self.assertIsNone(_detect_marker("(a)"))


class TestRetag(unittest.TestCase):
    def test_retag_basic(self):
        blocks = [_para("(a) First.", idx=0)]
        result = retag_numbered_items(blocks)
        self.assertEqual(result[0]["block_type"], "list_item")

    def test_decimal_increases_level(self):
        blocks = [_para("1.1 X.", level=0, idx=0), _para("1.1.1 Y.", level=0, idx=1)]
        result = retag_numbered_items(blocks)
        self.assertEqual(result[0]["level"], 1)
        self.assertEqual(result[1]["level"], 2)

    def test_does_not_mutate_input(self):
        blocks = [_para("(a) First.", idx=0)]
        retag_numbered_items(blocks)
        self.assertEqual(blocks[0]["block_type"], "para")
        self.assertEqual(blocks[0]["level"], 0)

    def test_skips_non_para_blocks(self):
        # A header that happens to start with "1." must NOT be retagged.
        block = {"block_type": "header", "block_text": "1. Definitions", "level": 0, "block_idx": 0}
        result = retag_numbered_items([block])
        self.assertEqual(result[0]["block_type"], "header")

    def test_kill_switch(self):
        os.environ["NLM_DISABLE_RETAG"] = "1"
        try:
            blocks = [_para("(a) First.", idx=0)]
            result = retag_numbered_items(blocks)
            self.assertEqual(result[0]["block_type"], "para")
        finally:
            del os.environ["NLM_DISABLE_RETAG"]

    def test_court_prose_regression(self):
        # The canonical false-positive case from eng review.
        blocks = [_para("the Court (a U.S. district court) held the matter")]
        result = retag_numbered_items(blocks)
        self.assertEqual(result[0]["block_type"], "para")


if __name__ == "__main__":
    unittest.main()
