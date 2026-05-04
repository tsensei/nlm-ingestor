# CLAUDE.md

Notes for AI agents working in this repo. Optimised for "drop in cold and start working." Forked from `nlmatics/nlm-ingestor` for CaseMax legal-doc ingestion.

## Run tests

```bash
python -m unittest discover tests/    # full unit suite
python -m unittest tests.test_markdown_renderer  # one module
NLM_E2E=1 python -m unittest tests.test_markdown_e2e  # E2E (requires Tika)
```

`pytest tests/` also works (pytest is a dep) but the test files use `unittest.TestCase`.

## Tika dependency

The PDF, HTML, XML, and "default" mime-type paths in `ingestor_api.ingest_document` call out to a Tika server via `nlm_ingestor/file_parser/pdf_file_parser.parse_to_html`. Tika must be reachable at the URL configured by `tika.tika.TikaServerEndpoint` env var (defaults to `http://localhost:9998`).

The unit test suite is pure-Python and does not need Tika. E2E tests are gated by `NLM_E2E=1` so they only run when explicitly requested.

## Architecture: every ingestor funnels through BlockRenderer

`nlm_ingestor/ingestor/` has one ingestor per input mime type (`pdf_ingestor.py`, `html_ingestor.py`, `xml_ingestor.py`, `text_ingestor.py`, plus `file_parser/markdown_parser.py`). Different parsers, but they all converge on the same data structure: a list of "blocks" passed to `nlm_ingestor/ingestor/visual_ingestor/block_renderer.py:BlockRenderer`.

`BlockRenderer` produces three outputs from the same block tree:

- `render_html()` → `html_str` (rendered HTML with CSS for visual viewing)
- `render_json()` → `json_dict` (structured tree with `tag`, `level`, `bbox`, table cell info, `page_idx`)
- `render_markdown(MarkdownOptions)` → `str | list[str]` (markdown for LLM/RAG consumption)

Add a new output format here, get it for all 5 ingestors automatically.

## Markdown subsystem

Lazy: only generated when `?renderFormat=markdown|markdown_chunks_by_page|markdown_chunks_by_section` is requested via `/api/parseDocument`. Three entry points:

- `block_renderer.render_markdown(opts: MarkdownOptions)` — main entry. Walks the block tree directly (does not depend on `render_html` or `render_json`).
- `MarkdownOptions` — toggles for frontmatter, page markers, H1 reservation, colspan strategy, retag, chunk_by.
- `markdown_retag.retag_numbered_items(blocks)` — pre-pass that detects `(a)`, `(b)`, `1.1`, `i.` patterns inside `para` blocks and retags them as `list_item`. Operates on a deep copy; JSON/HTML outputs are unaffected. Disable with `NLM_DISABLE_RETAG=1`.

Known limitations:

- Tables with `rowspan` are flattened (markdown doesn't support it). Colspan headers are handled by repeating the value across spanned columns.
- Section anchors use GitHub auto-anchor convention (lowercase-hyphenated). No explicit `{#anchor}` syntax.
- Numbered-item retag is conservative: requires closing punctuation (`.`, `;`, `:`) at end of block to avoid false positives on prose like `the Court (a U.S. district court) held...`. Bare `a.` / `i.` / `v.` is intentionally NOT retagged — too high a false-positive rate on prose.

## Trust boundary: markdown body text is untrusted

The markdown renderer does NOT escape body text. PDF content rendered as-is preserves real markdown structure (headings, lists, tables) which is exactly what LLM consumers want — but it also means hostile or accidentally-malformed PDFs can spoof markdown structure. A PDF containing literal text `# IGNORE PRIOR INSTRUCTIONS` becomes a real H1. Text containing `<!-- page 999 -->` looks like a real page marker. YAML frontmatter values ARE escaped (so PDF titles can't inject keys), but body text is not.

Treat markdown output as untrusted input when feeding it to LLMs or downstream parsers. If you need a trusted variant, escape `#`, `*`, `>`, `[`, `<!--`, and leading `---` in body text before consuming.

## Fixture corpus

`files/pdf/` has 10 sample PDFs. `8k.pdf` is the table-heavy stress case. `credit_aon.pdf` is a representative legal/financial doc. Use these for E2E tests.

## Repo conventions

- Tests live in `tests/`, named `test_<thing>.py`, classes derive `unittest.TestCase`.
- New modules go in `nlm_ingestor/ingestor/` unless they're file-format-specific (then `file_parser/`).
- Avoid touching `nlm_utils` — that's a separate vendored wheel under `whl/`.
- Don't add new dependencies casually; the `requirements.txt` is generated from poetry and pinned.

## Known issues / TODOs

See `TODOS.md`. The four logged items are all P1/P2 cleanups, not blockers.
