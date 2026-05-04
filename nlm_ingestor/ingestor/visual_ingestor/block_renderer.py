HTML_DEBUG = False

import re
from dataclasses import dataclass, field, replace
from typing import Optional

from nlm_ingestor.ingestor.visual_ingestor import (
    indent_parser,
    style_utils,
    table_parser,
)


@dataclass
class MarkdownOptions:
    """Options for BlockRenderer.render_markdown."""

    frontmatter: bool = True
    page_markers: bool = True
    h1_reserved_for_title: bool = True
    colspan_strategy: str = "repeat"  # "repeat" | "passthrough"
    retag_numbered: bool = True
    chunk_by: Optional[str] = None  # None | "page" | "section"
    title: Optional[str] = None
    num_pages: Optional[int] = None
    title_page_fonts: Optional[dict] = None


_MD_ANCHOR_PATTERN = re.compile(r"[^a-z0-9\s-]")


def _slugify(text: str) -> str:
    """GitHub-style heading anchor: lowercase, strip non-alnum, hyphens for spaces."""
    s = _MD_ANCHOR_PATTERN.sub("", text.lower())
    return re.sub(r"\s+", "-", s).strip("-")


def _md_escape_cell(text: str) -> str:
    """Escape pipe and newline so a cell stays on one row."""
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


class BlockRenderer:

    def __init__(self, doc):
        self.doc = doc

    def render_nested_block(self, block, block_idx, tag, sent_idx, html_str):
        block_sents = block["block_sents"]
        block_level = block["level"]
        block_page = block["page_idx"]
        margin_left_attr = (
            f"style='margin-left: {block_level * 20}px;' page_idx={block_page}"
        )
        block_class_attr = f"class=\"{block['block_class']}"
        sent_attrs = margin_left_attr + " " + block_class_attr
        if len(block_sents) == 1:
            html_str += (
                f'<{tag} {sent_attrs} nlm_sent_{sent_idx}">{block_sents[0]}</{tag}>'
            )
            sent_idx = sent_idx + 1
        else:
            block_attrs = (
                margin_left_attr
                + " "
                + block_class_attr
                + " nlm_block_"
                + str(block_idx)
            )
            html_str = html_str + " <" + tag + " " + block_attrs + '">'
            for sent in block_sents:
                html_str = (
                    html_str + f'<span class="nlm_sent_{sent_idx}">{sent} </span>'
                )
                sent_idx = sent_idx + 1
            html_str = html_str + "</" + tag + ">"
        return sent_idx, html_str

    def render_merged_cell(self, block, block_idx, tag, sent_idx, html_str):
        block_sents = block["block_sents"]
        margin_left_attr = f"style=''"
        block_class_attr = f"class=\"{block['block_class']}"
        sent_attrs = margin_left_attr + " " + block_class_attr
        if len(block_sents) == 1:
            html_str += (
                f'<{tag} {sent_attrs} nlm_sent_{sent_idx}">{block_sents[0]}</{tag}>'
            )
            sent_idx = sent_idx + 1
        else:
            block_attrs = (
                margin_left_attr
                + " "
                + block_class_attr
                + " nlm_block_"
                + str(block_idx)
            )
            html_str = html_str + " <" + tag + " " + block_attrs + "'>"
            for sent in block_sents:
                html_str = html_str + f'<p class="nlm_sent_{sent_idx}">{sent} </p>'
                sent_idx = sent_idx + 1
            html_str = html_str + "</" + tag + ">"
        return sent_idx, html_str

    def render_html(self):
        body_str = "<body>"
        is_rendering_table = False
        is_rendering_merged_cells = False

        html_str = ""
        sent_idx = 0
        nested_block_idx = 0
        prev_page_idx = -1

        for idx, block in enumerate(self.doc.blocks):
            if table_parser.TABLE_DEBUG:
                if "is_table_start" in block:
                    print("start>", idx)
                elif "is_table_end" in block:
                    print("</end>", idx)

            page_idx = block["page_idx"]
            if page_idx != prev_page_idx:
                if HTML_DEBUG:
                    html_str = html_str + f"<h7>---- {page_idx} ----</h7>"
                if page_idx > 0:
                    # html_str = html_str + f"<button>---- APPROVE ----</button>"
                    html_str += (
                        f'<br /><div><button class="ant-btn" button_type="approve-page" id="{page_idx - 1}" ">Approve Page {page_idx - 1} Above</button>'
                        f'<button class="ant-btn" button_type="flag-page" id="{page_idx - 1}">Flag Page {page_idx - 1}</button>'
                        f'<button class="ant-btn" button_type="undo-page-approval" id="{page_idx - 1}">Undo Approval</button>'
                        f'<button class="ant-btn" button_type="undo-page-flag" id="{page_idx - 1}">Undo Flag</button></div><br />'
                    )
                prev_page_idx = page_idx
            block_level = block["level"]
            block_page = block["page_idx"]
            margin_left_attr = (
                f"style='margin-left: {block_level * 20}px;' page_idx={block_page}"
            )
            block_class_attr = f"class=\"{block['block_class']} nlm_sent_{sent_idx}\""
            block_attrs = margin_left_attr + " " + block_class_attr
            block_type = block["block_type"]
            block_text = block["block_text"]
            if indent_parser.LEVEL_DEBUG:
                print(str(block["level"]) + " >> " + block_text)

            if "is_table_start" in block and block["is_table_start"]:
                top = block["box_style"][0] if "box_style" in block else 0
                left = block["box_style"][1] if "box_style" in block else 0
                name = block["header_text"] if "header_text" in block else ""
                body_str = f'<table {block_attrs} page_idx="{page_idx}" top="{top}" left="{left}" name="{name}"><tbody>'
                nested_block_idx = nested_block_idx + 1
                is_rendering_table = True
                if "has_merged_cells" in block:
                    is_rendering_merged_cells = True

            elif block_type == "header" and not is_rendering_table:
                html_str = html_str + f"<h4 {block_attrs}> {block_text} </h4>"
                sent_idx = sent_idx + 1
            elif block_type == "list_item" and not is_rendering_table:
                sent_idx, html_str = self.render_nested_block(
                    block,
                    nested_block_idx,
                    "li",
                    sent_idx,
                    html_str,
                )
                nested_block_idx = nested_block_idx + 1
            elif (
                block_type == "para" or block_type == "numbered_list_item"
            ) and not is_rendering_table:
                sent_idx, html_str = self.render_nested_block(
                    block,
                    nested_block_idx,
                    "p",
                    sent_idx,
                    html_str,
                )
                nested_block_idx = nested_block_idx + 1
            elif (
                "is_table_start" not in block
                and not is_rendering_table
                and block_type == "table_row"
            ):
                html_str = html_str + f"<p {block_attrs}> {block_text} </p>"
                sent_idx = sent_idx + 1

            elif block_type == "hr":
                html_str += "<hr>"

            if is_rendering_table:
                body_str = body_str + f"<tr {block_attrs}>"
                if table_parser.TABLE_DEBUG:
                    print("---->", block["block_text"][0:20], block["block_type"])
                if "cell_values" not in block:
                    print("!!!!!!!!", block["block_text"], "is_table_end" in block)
                    block["cell_values"] = [block["block_text"]]
                cell_values = block["cell_values"]
                n_cols = len(cell_values)
                if table_parser.row_group_key in block:
                    # print(">>>", cell_values)
                    body_str = (
                        body_str + f"<td {margin_left_attr} class='nlm_full_row' "
                        f"colspan={block['col_span']}>{cell_values[0]}</td>"
                    )

                elif table_parser.header_group_key in block:
                    col_spans = block["col_spans"]
                    for idx, val in enumerate(cell_values):
                        col_span = col_spans[idx] if idx < len(col_spans) else 1
                        # sent_idx = sent_idx + 1
                        body_str = (
                            body_str
                            + f"<th {margin_left_attr} colspan={col_span}>{val}</th>"
                        )

                elif table_parser.header_key in block:
                    # print(cell_values)
                    for val in cell_values:
                        # sent_idx = sent_idx + 1
                        body_str = body_str + f"<th {margin_left_attr}>{val}</th>"
                else:
                    # print(cell_values)
                    for cell_idx, val in enumerate(cell_values):
                        # sent_idx = sent_idx + 1
                        if (
                            is_rendering_merged_cells
                            and cell_idx == 1
                            and "effective_para" in block
                        ):
                            sent_idx, cell_html = self.render_merged_cell(
                                block["effective_para"],
                                block["block_idx"],
                                "p",
                                sent_idx,
                                "",
                            )
                            body_str = (
                                body_str + f"<td {margin_left_attr}>{cell_html}</td>"
                            )
                        else:
                            body_str = body_str + f"<td {margin_left_attr}>{val}</td>"
                body_str = body_str + "</tr>"

                sent_idx = sent_idx + 1

            if "is_table_end" in block:
                body_str = body_str + "</tbody></table>"
                body_str += (
                    f'<br /><div><button class="ant-btn" button_type="approve-table">Approve Table Above</button>'
                    f'<button class="ant-btn" button_type="flag-table">Flag Table Above</button>'
                    f'<button class="ant-btn" button_type="undo-table-approval">Undo Approval</button>'
                    f'<button class="ant-btn" button_type="undo-table-flag">Undo Flag</button>'
                    f"</div><br />"
                )
                is_rendering_table = False
                html_str = html_str + body_str

        css_str = "<style>\n"
        for style, class_name in self.doc.line_style_classes.items():
            if class_name in self.doc.class_levels:
                class_level = self.doc.class_levels[class_name]
            else:
                class_level = 0
            style_str = (
                f"font-family: {style[0]};"
                f"font-style: {style[1]};"
                f"font-size: {style[2] * style_utils.font_scale}px;"
                f"font-weight: {style[3]};"
                f"margin-left: {class_level * 20}px;"
                f"text-transform: {style[4]};text-align: {style[6]}"
            )
            css_str = css_str + "." + class_name + " {\n" + style_str + "\n}\n"
        css_str = css_str + "table {border-collapse: collapse; margin-top: 10px}"
        css_str = css_str + "table, th, td {border: 1px solid lightgray;padding: 5px;}"
        css_str = css_str + "th {background: #337ab773}"
        css_str = (
            css_str + "li {padding-left: 30px; list-style: none; margin-top: 10px}"
        )
        css_str = css_str + "li::first-letter {color: #5656a3}"
        css_str = css_str + "h4 {color: #337ab7}"
        css_str = (
            css_str
            + ".nlm_full_row {background: #dfe5e7; font-weight: 600; color: #5656a3}"
        )
        css_str = css_str + "</style>"
        html_str = (
            "<!DOCTYPE html><html><head>" + css_str + "</head>" + html_str + "</html>"
        )
        return html_str

    def get_styles_from_doc(self):
        """
        Retrieve styles from the document blocks
        :return: list of styles
        """
        styles = []
        for style, class_name in self.doc.line_style_classes.items():
            styles.append(
                {
                    "class_name": class_name,
                    "style": {
                        "font-family": style[0],
                        "font-style": style[1],
                        "font-size": style[2] * style_utils.font_scale,
                        "font-weight": style[3],
                        "text-transform": style[4],
                        "text-align": style[6],
                    },
                }
            )
        return styles

    def render_json(self):
        """
        Render the blocks as JSON Dictionary.
        :return: JSON Dictionary output of the blocks
        """
        is_rendering_table = False
        is_rendering_merged_cells = False
        prev_page_idx = -1

        # Retrieve styles from the doc
        render_dict = {
            "styles": self.get_styles_from_doc(),
            "blocks": [],
        }

        table_rows = []
        for idx, block in enumerate(self.doc.blocks):
            block_dict = None
            page_idx = block["page_idx"]
            if page_idx != prev_page_idx:
                prev_page_idx = page_idx

            block_type = block["block_type"]
            block_text = block["block_text"]

            if "is_table_start" in block and block["is_table_start"]:
                top = block["box_style"][0] if "box_style" in block else 0
                left = block["box_style"][1] if "box_style" in block else 0
                name = block["header_text"] if "header_text" in block else ""

                block_dict = {
                    "tag": "table",
                    "page_idx": block["page_idx"],
                    "block_class": block["block_class"],
                    "top": top,
                    "left": left,
                    "name": name,
                }
                is_rendering_table = True
                if "has_merged_cells" in block:
                    is_rendering_merged_cells = True

            elif block_type == "header" and not is_rendering_table:
                block_dict = {
                    "tag": block_type,
                    "page_idx": block["page_idx"],
                    "block_class": block["block_class"],
                    "sentences": [block_text],
                    "bbox": (
                        [
                            block["box_style"][1],
                            block["box_style"][0],
                            block["box_style"][1] + block["box_style"][3],
                            block["box_style"][0] + block["box_style"][4],
                        ]
                        if "box_style" in block
                        else []
                    ),
                }
            elif block_type == "list_item" and not is_rendering_table:
                block_dict = self.render_nested_block_as_dict(block, "list_item")
            elif (
                block_type == "para" or block_type == "numbered_list_item"
            ) and not is_rendering_table:
                block_dict = self.render_nested_block_as_dict(block, "para")
            elif (
                "is_table_start" not in block
                and not is_rendering_table
                and block_type == "table_row"
            ):
                block_dict = {
                    "tag": "para",
                    "page_idx": block["page_idx"],
                    "block_class": block["block_class"],
                    "sentences": [block_text],
                    "bbox": (
                        [
                            block["box_style"][1],
                            block["box_style"][0],
                            block["box_style"][1] + block["box_style"][3],
                            block["box_style"][0] + block["box_style"][4],
                        ]
                        if "box_style" in block
                        else []
                    ),
                }

            if block_dict:
                block_dict["block_idx"] = block["block_idx"]
                if "level" in block:
                    block_dict["level"] = block["level"]
                render_dict["blocks"].append(block_dict)

            if is_rendering_table:
                if "cell_values" not in block:
                    block["cell_values"] = [block["block_text"]]
                cell_values = block["cell_values"]

                if table_parser.row_group_key in block:
                    tab_row = {
                        "type": "full_row",
                        "col_span": block["col_span"],
                        "cell_value": cell_values[0],
                    }
                elif table_parser.header_group_key in block:
                    col_spans = block["col_spans"]
                    cells = []
                    for cell_idx, val in enumerate(cell_values):
                        col_span = (
                            col_spans[cell_idx] if cell_idx < len(col_spans) else 1
                        )
                        cells.append(
                            {
                                "col_span": col_span,
                                "cell_value": str(val),
                            }
                        )
                    tab_row = {
                        "type": "table_header",
                        "cells": cells,
                    }
                elif table_parser.header_key in block:
                    cells = []
                    for val in cell_values:
                        cells.append(
                            {
                                "cell_value": str(val),
                            }
                        )
                    tab_row = {
                        "type": "table_header",
                        "cells": cells,
                    }
                else:
                    cells = []
                    for cell_idx, val in enumerate(cell_values):
                        if (
                            is_rendering_merged_cells
                            and cell_idx == 1
                            and "effective_para" in block
                        ):
                            cells.append(
                                {
                                    "cell_value": self.render_nested_block_as_dict(
                                        block["effective_para"], "para"
                                    ),
                                }
                            )
                        else:
                            cells.append(
                                {
                                    "cell_value": str(val),
                                }
                            )
                    tab_row = {
                        "type": "table_data_row",
                        "cells": cells,
                    }
                if tab_row:
                    tab_row["block_idx"] = block["block_idx"]
                    table_rows.append(tab_row)

            if "is_table_end" in block and is_rendering_table:
                is_rendering_table = False
                table_block = render_dict["blocks"][-1]
                table_block["table_rows"] = table_rows
                table_block["bbox"] = (
                    [
                        table_block["left"],
                        table_block["top"],
                        table_block["left"] + block["box_style"][3],
                        table_block["top"] + block["box_style"][4],
                    ]
                    if "box_style" in block
                    else []
                )
                table_rows = []

        return render_dict

    def render_nested_block_as_dict(self, block, tag):
        """
        Convert the block object to the dict representation.
        :param block: Block element
        :param tag: Type of the block
        :return: Dictionary with all the sentences in the block and tag as specified
        """
        block_dict = {}
        if len(block["block_sents"]) > 0:
            block_dict = {
                "tag": tag,
                "page_idx": block["page_idx"],
                "block_class": block["block_class"],
                "sentences": [sent for sent in block["block_sents"]],
                "block_idx": block["block_idx"],
                "bbox": (
                    [
                        block["box_style"][1],
                        block["box_style"][0],
                        block["box_style"][1] + block["box_style"][3],
                        block["box_style"][0] + block["box_style"][4],
                    ]
                    if "box_style" in block
                    else []
                ),
            }
        return block_dict

    # ------------------------------------------------------------------
    # Markdown rendering
    # ------------------------------------------------------------------

    def render_markdown(self, opts: Optional[MarkdownOptions] = None):
        """Render the block tree as markdown.

        Returns either a single string (chunk_by=None) or a list of strings
        (chunk_by="page" or "section"). Walks self.doc.blocks directly so it
        does not depend on render_html or render_json output.
        """
        opts = opts or MarkdownOptions()
        blocks = self.doc.blocks
        if opts.retag_numbered:
            from nlm_ingestor.ingestor.markdown_retag import retag_numbered_items

            blocks = retag_numbered_items(blocks)

        if opts.chunk_by is None:
            return self._render_md_blocks(blocks, opts, include_frontmatter=opts.frontmatter)
        if opts.chunk_by == "page":
            return self._render_md_chunks_by_page(blocks, opts)
        if opts.chunk_by == "section":
            return self._render_md_chunks_by_section(blocks, opts)
        raise ValueError(f"Unknown chunk_by: {opts.chunk_by}")

    def _heading_depth(self, block, opts: MarkdownOptions) -> int:
        base = 2 if opts.h1_reserved_for_title else 1
        level = block.get("level", 0) or 0
        return min(6, max(base, base + level))

    @staticmethod
    def _yaml_scalar(value: str) -> str:
        """Escape a scalar so it survives YAML round-tripping.

        Wraps in double quotes and backslash-escapes embedded quotes/newlines
        so PDF text containing colons, hashes, leading dashes, or newlines
        cannot break out of the frontmatter or inject keys.
        """
        s = str(value).replace("\\", "\\\\").replace('"', '\\"')
        s = s.replace("\n", "\\n").replace("\r", "\\r")
        return f'"{s}"'

    def _frontmatter_lines(self, opts: MarkdownOptions) -> list:
        lines = ["---"]
        if opts.title:
            lines.append(f"title: {self._yaml_scalar(opts.title)}")
        if opts.num_pages is not None:
            lines.append(f"num_pages: {opts.num_pages}")
        if opts.title_page_fonts:
            first_level = opts.title_page_fonts.get("first_level") or []
            if first_level:
                lines.append("first_level_headings:")
                for h in first_level:
                    lines.append(f"  - {self._yaml_scalar(h)}")
        lines.append("---")
        return lines

    def _render_md_blocks(self, blocks, opts: MarkdownOptions, include_frontmatter: bool) -> str:
        # Sort defensively in case order_fixer broke page_idx monotonicity.
        page_indices = [b.get("page_idx", 0) for b in blocks]
        if page_indices != sorted(page_indices):
            blocks = sorted(blocks, key=lambda b: (b.get("page_idx", 0), b.get("block_idx", 0)))

        out = []
        if include_frontmatter:
            out.extend(self._frontmatter_lines(opts))
            out.append("")

        is_in_table = False
        table_rows = []  # accumulated rows: list of dicts {type, cells, col_span}
        prev_page_idx = -1

        for block in blocks:
            page_idx = block.get("page_idx", 0)
            if opts.page_markers and page_idx != prev_page_idx and prev_page_idx != -1:
                # Flush any open table before injecting the page marker
                if is_in_table:
                    out.extend(self._table_rows_to_md(table_rows))
                    out.append("")
                    table_rows = []
                    is_in_table = False
                out.append(f"<!-- page {page_idx} -->")
                out.append("")
            prev_page_idx = page_idx

            if block.get("is_table_start"):
                is_in_table = True
                table_rows = []
                # Fall through — is_table_start often coincides with the
                # first table row (header or data) and carries cell_values.

            if is_in_table:
                self._collect_table_row(block, table_rows)
                if block.get("is_table_end"):
                    out.extend(self._table_rows_to_md(table_rows))
                    out.append("")
                    table_rows = []
                    is_in_table = False
                continue

            block_type = block.get("block_type")
            text = block.get("block_text", "").strip()
            if not text and block_type != "hr":
                continue

            if block_type == "header":
                depth = self._heading_depth(block, opts)
                # Anchors derive from heading text via GFM auto-anchor convention
                # (lowercase, hyphenated). GitHub renders them client-side; we
                # don't emit explicit {#anchor} syntax (non-standard in pure GFM).
                out.append(f"{'#' * depth} {text}")
                out.append("")
            elif block_type == "list_item":
                level = block.get("level", 0) or 0
                indent = "  " * max(0, level)
                out.append(f"{indent}- {text}")
            elif block_type == "numbered_list_item":
                level = block.get("level", 0) or 0
                indent = "  " * max(0, level)
                out.append(f"{indent}1. {text}")
            elif block_type == "para" or block_type == "table_row":
                out.append(text)
                out.append("")
            elif block_type == "hr":
                out.append("---")
                out.append("")
            else:
                # Unknown block_type — emit as paragraph rather than dropping
                if text:
                    out.append(text)
                    out.append("")

        if is_in_table and table_rows:
            out.extend(self._table_rows_to_md(table_rows))
            out.append("")

        # Collapse runs of >2 blank lines.
        result = "\n".join(out).rstrip() + "\n"
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    def _collect_table_row(self, block, table_rows):
        # Compute cell_values locally; do NOT mutate the caller's block dict
        # (otherwise downstream renders that share the block tree see a
        # synthesized cell_values list and JSON output drifts).
        cell_values = block.get("cell_values") or [block.get("block_text", "")]
        if not cell_values:
            cell_values = [""]

        if table_parser.row_group_key in block:
            table_rows.append(
                {
                    "type": "full_row",
                    "col_span": block.get("col_span", 1),
                    "value": str(cell_values[0]),
                }
            )
        elif table_parser.header_group_key in block:
            col_spans = block.get("col_spans", [])
            cells = []
            for idx, val in enumerate(cell_values):
                col_span = col_spans[idx] if idx < len(col_spans) else 1
                cells.append({"value": str(val), "col_span": col_span})
            table_rows.append({"type": "header_group", "cells": cells})
        elif table_parser.header_key in block:
            table_rows.append(
                {"type": "header", "cells": [{"value": str(v), "col_span": 1} for v in cell_values]}
            )
        else:
            table_rows.append(
                {"type": "data", "cells": [{"value": str(v), "col_span": 1} for v in cell_values]}
            )

    def _table_rows_to_md(self, table_rows) -> list:
        """Render accumulated rows as a GFM pipe table.

        Strategy (colspan_strategy='repeat'): expand spanned header cells by
        repeating the value across each spanned column. Subsequent header
        rows (header_key) are emitted as bold first data rows.
        """
        if not table_rows:
            return []

        # Determine total column count from the widest expanded row.
        def expand(row):
            if row["type"] == "full_row":
                return [row["value"]] + [""] * (row["col_span"] - 1)
            cells = row.get("cells", [])
            expanded = []
            for c in cells:
                span = max(1, c.get("col_span", 1))
                expanded.extend([c["value"]] * span)
            return expanded

        expanded_rows = [(r["type"], expand(r)) for r in table_rows]
        n_cols = max((len(cells) for _, cells in expanded_rows), default=1)

        # Pad short rows.
        for i, (rtype, cells) in enumerate(expanded_rows):
            if len(cells) < n_cols:
                expanded_rows[i] = (rtype, cells + [""] * (n_cols - len(cells)))

        # Pick the markdown header row. Prefer the first header_group;
        # fall back to first header; fall back to a synthetic blank header.
        header_idx = None
        for i, (rtype, _) in enumerate(expanded_rows):
            if rtype in ("header_group", "header"):
                header_idx = i
                break

        out = []
        if header_idx is None:
            header_cells = [""] * n_cols
            out.append("| " + " | ".join(header_cells) + " |")
            out.append("| " + " | ".join(["---"] * n_cols) + " |")
            data_rows = expanded_rows
        else:
            header_cells = [_md_escape_cell(c) for c in expanded_rows[header_idx][1]]
            out.append("| " + " | ".join(header_cells) + " |")
            out.append("| " + " | ".join(["---"] * n_cols) + " |")
            data_rows = expanded_rows[:header_idx] + expanded_rows[header_idx + 1 :]

        for rtype, cells in data_rows:
            cells = [_md_escape_cell(c) for c in cells]
            if rtype == "header":
                # Secondary header row from header_key, emit as bold data row
                cells = [f"**{c}**" if c else "" for c in cells]
            elif rtype == "full_row":
                # Italicise full-row spans so they read as banners
                cells = [f"*{cells[0]}*" if i == 0 else "" for i, c in enumerate(cells)]
            out.append("| " + " | ".join(cells) + " |")
        return out

    def _render_md_chunks_by_page(self, blocks, opts: MarkdownOptions) -> list:
        if not blocks:
            return []
        max_page = max((b.get("page_idx", 0) for b in blocks), default=-1)
        chunks = []
        per_page_opts = replace(opts, page_markers=False, frontmatter=False, chunk_by=None)
        for page_idx in range(max_page + 1):
            page_blocks = [b for b in blocks if b.get("page_idx") == page_idx]
            if not page_blocks:
                chunks.append("")
                continue
            chunks.append(self._render_md_blocks(page_blocks, per_page_opts, include_frontmatter=False))
        return chunks

    def _render_md_chunks_by_section(self, blocks, opts: MarkdownOptions) -> list:
        if not blocks:
            return []
        sections = []
        current = []
        for block in blocks:
            is_top_header = (
                block.get("block_type") == "header"
                and (block.get("level", 0) or 0) == 0
            )
            if is_top_header and current:
                sections.append(current)
                current = []
            current.append(block)
        if current:
            sections.append(current)
        per_section_opts = replace(opts, page_markers=False, frontmatter=False, chunk_by=None)
        return [self._render_md_blocks(s, per_section_opts, include_frontmatter=False) for s in sections]
