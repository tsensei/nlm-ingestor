import copy
import unittest

from nlm_ingestor.ingestor.visual_ingestor import table_parser
from nlm_ingestor.ingestor.visual_ingestor.block_renderer import (
    BlockRenderer,
    MarkdownOptions,
    _md_escape_cell,
    _slugify,
)


class FakeDoc:
    """Minimal Doc stand-in: BlockRenderer only reads .blocks."""

    def __init__(self, blocks):
        self.blocks = blocks


def _block(block_type, text="", level=0, page_idx=0, idx=0, **extra):
    base = {
        "block_type": block_type,
        "block_text": text,
        "level": level,
        "page_idx": page_idx,
        "block_idx": idx,
    }
    base.update(extra)
    return base


def _render(blocks, **opts):
    base_opts = {
        "frontmatter": False,
        "page_markers": False,
        "retag_numbered": False,
    }
    base_opts.update(opts)
    return BlockRenderer(FakeDoc(blocks)).render_markdown(MarkdownOptions(**base_opts))


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_slugify("Section 2: Compensation"), "section-2-compensation")

    def test_strip_punct(self):
        self.assertEqual(_slugify("Hello, World!"), "hello-world")

    def test_collapse_whitespace(self):
        self.assertEqual(_slugify("  multiple   spaces  "), "multiple-spaces")


class TestEscapeCell(unittest.TestCase):
    def test_pipe_escaped(self):
        self.assertEqual(_md_escape_cell("a|b"), "a\\|b")

    def test_newline_collapsed(self):
        self.assertEqual(_md_escape_cell("a\nb"), "a b")


class TestHeadings(unittest.TestCase):
    def test_level_zero_becomes_h2_when_h1_reserved(self):
        out = _render([_block("header", "Title", level=0)])
        self.assertIn("## Title", out)

    def test_level_zero_becomes_h1_when_not_reserved(self):
        out = _render(
            [_block("header", "Title", level=0)], h1_reserved_for_title=False
        )
        self.assertTrue(out.lstrip().startswith("# Title"))

    def test_clamps_at_h6(self):
        out = _render([_block("header", "Deep", level=10)])
        self.assertIn("###### Deep", out)
        self.assertNotIn("####### Deep", out)


class TestParagraphsAndLists(unittest.TestCase):
    def test_para(self):
        out = _render([_block("para", "Hello.")])
        self.assertIn("Hello.", out)

    def test_list_item_indented_by_level(self):
        out = _render([_block("list_item", "Item", level=2)])
        self.assertIn("    - Item", out)

    def test_numbered_list_item(self):
        out = _render([_block("numbered_list_item", "Step", level=0)])
        self.assertIn("1. Step", out)

    def test_hr(self):
        out = _render([_block("hr")])
        self.assertIn("---", out)


class TestPageMarkers(unittest.TestCase):
    def test_marker_inserted_at_boundary(self):
        blocks = [
            _block("para", "p1", page_idx=0, idx=0),
            _block("para", "p2", page_idx=1, idx=1),
        ]
        out = _render(blocks, page_markers=True)
        self.assertIn("<!-- page 1 -->", out)

    def test_no_marker_before_first_page(self):
        blocks = [_block("para", "first", page_idx=0)]
        out = _render(blocks, page_markers=True)
        self.assertNotIn("<!-- page 0 -->", out)

    def test_marker_flushes_open_table_at_page_boundary(self):
        # If a table is mid-render and the next block is on a new page, we
        # must emit the table before injecting the page marker (otherwise
        # the marker lands inside the table and breaks GFM rendering).
        blocks = [
            _block(
                "table_row",
                idx=0,
                page_idx=0,
                cell_values=["A", "1"],
                is_table_start=True,
                is_header=True,
            ),
            _block(
                "table_row",
                idx=1,
                page_idx=0,
                cell_values=["B", "2"],
                is_table_end=True,
            ),
            _block("para", "next page text", page_idx=1, idx=2),
        ]
        out = _render(blocks, page_markers=True)
        table_close = out.rindex("| B | 2 |")
        marker = out.index("<!-- page 1 -->")
        self.assertLess(table_close, marker)


class TestFrontmatter(unittest.TestCase):
    def test_includes_title_and_pages(self):
        out = _render(
            [_block("para", "x")],
            frontmatter=True,
            title="My Doc",
            num_pages=3,
        )
        # Title is YAML-quoted to survive special chars in PDF text.
        self.assertIn('title: "My Doc"', out)
        self.assertIn("num_pages: 3", out)

    def test_title_with_special_chars_escaped(self):
        # PDF text containing colons, quotes, or newlines must NOT inject
        # extra YAML keys or break out of the frontmatter block.
        out = _render(
            [_block("para", "x")],
            frontmatter=True,
            title='Pwned\n---\nmalicious: true\nstill_title: "yep',
        )
        # The injection attempt must remain inside one quoted scalar.
        self.assertNotIn("\nmalicious: true", out)
        self.assertIn("Pwned", out)

    def test_handles_missing_title(self):
        out = _render([_block("para", "x")], frontmatter=True)
        self.assertIn("---", out)
        self.assertNotIn("title:", out)

    def test_first_level_headings_emitted(self):
        out = _render(
            [_block("para", "x")],
            frontmatter=True,
            title_page_fonts={"first_level": ["Heading One", "Heading Two"]},
        )
        self.assertIn("first_level_headings:", out)
        self.assertIn('- "Heading One"', out)


class TestTables(unittest.TestCase):
    def _build_table_blocks(self):
        return [
            _block("table_row", is_table_start=True, idx=0),
            _block(
                "table_row",
                idx=1,
                cell_values=["Tier", "Volume Range", "Commission"],
                col_spans=[1, 2, 1],
                **{table_parser.header_group_key: True},
            ),
            _block(
                "table_row",
                idx=2,
                cell_values=["Name", "Min", "Max", "Rate"],
                **{table_parser.header_key: True},
            ),
            _block("table_row", idx=3, cell_values=["Bronze", "0", "10k", "5%"]),
            _block(
                "table_row",
                idx=4,
                cell_values=["Premium tiers"],
                col_span=4,
                **{table_parser.row_group_key: True},
            ),
            _block(
                "table_row",
                idx=5,
                cell_values=["Gold", "50k", "250k", "12%"],
                is_table_end=True,
            ),
        ]

    def test_colspan_repeats_header_value(self):
        out = _render(self._build_table_blocks())
        # The header row should have "Volume Range" appearing twice
        header_line = [l for l in out.split("\n") if "Tier" in l and "Volume Range" in l][0]
        self.assertEqual(header_line.count("Volume Range"), 2)

    def test_separator_matches_column_count(self):
        out = _render(self._build_table_blocks())
        sep = [l for l in out.split("\n") if l.startswith("| ---")][0]
        self.assertEqual(sep.count("---"), 4)

    def test_full_row_span_emitted_as_italic(self):
        out = _render(self._build_table_blocks())
        self.assertIn("*Premium tiers*", out)

    def test_secondary_header_emitted_as_bold(self):
        out = _render(self._build_table_blocks())
        self.assertIn("**Name**", out)
        self.assertIn("**Rate**", out)

    def test_table_with_no_header_row_emits_empty_header(self):
        # When the parser doesn't tag any row as header, GFM still requires
        # a header row + separator. Renderer falls back to empty cells.
        blocks = [
            _block(
                "table_row",
                idx=0,
                cell_values=["Alabama", "$1,900", "On Approval"],
                is_table_start=True,
            ),
            _block(
                "table_row",
                idx=1,
                cell_values=["Alaska", "$2,300", "On Approval"],
                is_table_end=True,
            ),
        ]
        out = _render(blocks)
        # Empty header row + separator + 2 data rows
        self.assertIn("|  |  |  |", out)
        self.assertIn("| --- | --- | --- |", out)
        self.assertIn("| Alabama | $1,900 | On Approval |", out)

    def test_is_table_start_block_carries_header_row(self):
        # Regression: foreclosure.pdf had a single block tagged with BOTH
        # is_table_start AND is_header. An earlier `continue` on
        # is_table_start meant the header row was dropped and the table
        # rendered with an empty `|  |  |` header.
        blocks = [
            _block(
                "table_row",
                idx=0,
                cell_values=["State", "Non-Judicial", "Judicial"],
                is_table_start=True,
                **{table_parser.header_key: True},
            ),
            _block("table_row", idx=1, cell_values=["Alabama", "$1,900", "On Approval"]),
            _block(
                "table_row",
                idx=2,
                cell_values=["Alaska", "$2,300", "On Approval"],
                is_table_end=True,
            ),
        ]
        out = _render(blocks)
        # The first row's cell_values must end up as the header.
        self.assertIn("| State | Non-Judicial | Judicial |", out)
        # The empty-header fallback must NOT appear.
        self.assertNotIn("|  |  |  |", out)


class TestChunking(unittest.TestCase):
    def test_chunks_by_page_length(self):
        blocks = [
            _block("para", "p1", page_idx=0, idx=0),
            _block("para", "p2", page_idx=1, idx=1),
            _block("para", "p3", page_idx=2, idx=2),
        ]
        chunks = _render(blocks, chunk_by="page")
        self.assertEqual(len(chunks), 3)
        self.assertIn("p1", chunks[0])
        self.assertIn("p2", chunks[1])
        self.assertIn("p3", chunks[2])

    def test_chunks_by_section_splits_on_top_headers(self):
        blocks = [
            _block("header", "Section A", level=0, idx=0),
            _block("para", "a body", idx=1),
            _block("header", "Section B", level=0, idx=2),
            _block("para", "b body", idx=3),
        ]
        chunks = _render(blocks, chunk_by="section")
        self.assertEqual(len(chunks), 2)
        self.assertIn("Section A", chunks[0])
        self.assertIn("Section B", chunks[1])

    def test_chunks_by_section_keeps_subheaders_with_parent(self):
        blocks = [
            _block("header", "A", level=0, idx=0),
            _block("header", "A.1", level=1, idx=1),
            _block("header", "B", level=0, idx=2),
        ]
        chunks = _render(blocks, chunk_by="section")
        self.assertEqual(len(chunks), 2)
        self.assertIn("A.1", chunks[0])

    def test_no_blocks_returns_empty_list(self):
        self.assertEqual(_render([], chunk_by="page"), [])
        self.assertEqual(_render([], chunk_by="section"), [])

    def test_invalid_chunk_by_raises(self):
        # Defensive: callers passing a typo should fail loudly, not silently.
        with self.assertRaises(ValueError):
            _render([_block("para", "x")], chunk_by="bogus")

    def test_unknown_block_type_emits_text_as_paragraph(self):
        # Future block types or bugs that emit unknown block_types should
        # still surface text in the output rather than silently dropping it.
        out = _render([_block("totally_new_kind", "Mystery content")])
        self.assertIn("Mystery content", out)


class TestAnchorDedup(unittest.TestCase):
    def test_duplicate_headings_get_unique_anchors(self):
        # Both headings render with the same visible text. Anchors should
        # increment for the second occurrence.
        blocks = [
            _block("header", "Definitions", level=0, idx=0),
            _block("header", "Definitions", level=0, idx=1),
        ]
        # Anchors are computed but not currently emitted in the markdown
        # text (GitHub auto-generates them on render). Verify the renderer
        # tracks them without raising and produces both headings.
        out = _render(blocks)
        self.assertEqual(out.count("## Definitions"), 2)


class TestPageOrdering(unittest.TestCase):
    def test_out_of_order_blocks_sorted_defensively(self):
        # order_fixer can produce non-monotonic page_idx; renderer should
        # sort defensively rather than emit page markers out of order.
        blocks = [
            _block("para", "from page 2", page_idx=2, idx=10),
            _block("para", "from page 0", page_idx=0, idx=0),
            _block("para", "from page 1", page_idx=1, idx=5),
        ]
        out = _render(blocks)
        i0 = out.index("from page 0")
        i1 = out.index("from page 1")
        i2 = out.index("from page 2")
        self.assertLess(i0, i1)
        self.assertLess(i1, i2)


class TestRegressionDeepCopy(unittest.TestCase):
    def test_retag_does_not_mutate_input_blocks(self):
        # The IRON RULE regression test: rendering markdown with retag
        # enabled must NOT mutate the underlying block list (otherwise
        # subsequent JSON / HTML renders would see changed block_types).
        blocks = [
            _block("para", "(a) First obligation.", idx=0),
            _block("para", "Plain prose.", idx=1),
        ]
        snapshot = copy.deepcopy(blocks)
        _render(blocks, retag_numbered=True)
        self.assertEqual(blocks, snapshot)


if __name__ == "__main__":
    unittest.main()
