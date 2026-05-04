"""End-to-end markdown tests against real PDFs.

Gated by NLM_E2E=1 because they require a running Tika server. Run with:

    NLM_E2E=1 python -m unittest tests.test_markdown_e2e
"""

import os
import unittest

from nlm_ingestor.ingestor import pdf_ingestor

E2E_ENABLED = os.environ.get("NLM_E2E") == "1"
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "files", "pdf")


@unittest.skipUnless(E2E_ENABLED, "set NLM_E2E=1 (and run a Tika server) to enable")
class TestMarkdownE2E(unittest.TestCase):
    def _ingest(self, filename, render_format):
        path = os.path.join(FIXTURE_DIR, filename)
        ingestor = pdf_ingestor.PDFIngestor(
            path,
            {
                "render_format": render_format,
                "use_new_indent_parser": True,
                "parse_pages": (),
                "apply_ocr": False,
            },
        )
        return ingestor.return_dict

    def test_credit_aon_renders_markdown(self):
        result = self._ingest("credit_aon.pdf", "markdown")
        md = result["result"]
        self.assertIsInstance(md, str)
        self.assertIn("---", md)  # frontmatter delimiter
        self.assertRegex(md, r"^## ", "expected at least one ## heading")

    def test_8k_table_pdf_has_non_empty_headers(self):
        result = self._ingest("8k.pdf", "markdown")
        md = result["result"]
        self.assertIsInstance(md, str)
        # Tables should not have completely empty header rows.
        for line in md.split("\n"):
            if line.startswith("| ") and "---" not in line:
                # A header / data row — should have at least one non-empty cell
                cells = [c.strip() for c in line.strip("|").split("|")]
                self.assertTrue(
                    any(cells),
                    f"row with all empty cells: {line!r}",
                )

    def test_chunks_by_page_length_matches_num_pages(self):
        result = self._ingest("credit_aon.pdf", "markdown_chunks_by_page")
        chunks = result["result"]
        self.assertIsInstance(chunks, list)
        # num_pages from the response is len(pages) - 1, so chunks should be that+1
        self.assertEqual(len(chunks), result["num_pages"] + 1)

    def test_chunks_by_section_returns_list(self):
        result = self._ingest("credit_aon.pdf", "markdown_chunks_by_section")
        chunks = result["result"]
        self.assertIsInstance(chunks, list)
        self.assertGreaterEqual(len(chunks), 1)


if __name__ == "__main__":
    unittest.main()
