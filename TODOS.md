# TODOs

## P0

### Fix pre-existing test failures (`tests.test_processor` and `tests.test_sent_tokenizer`)
- **What:** Two unit tests fail on a clean `main` checkout, unrelated to the markdown PR. `tests.test_processor` errors at import time (`unittest.loader._FailedTest`). `tests.test_sent_tokenizer.test_sentence_tokenizer` raises `AttributeError: 'PreProcessingTests' object has no attribute 'assertEquals'` — uses the deprecated `assertEquals` alias removed in Python 3.13+. Also throws `could not convert string to float: '½'` somewhere in pre-processing.
- **Why:** Pre-existing failures hide regressions. Every future `/ship` will have to triage and skip these. They mask any real failure that lands in those modules.
- **Pros:** Clean test run; future contributors don't lose 5 minutes wondering if they broke something.
- **Cons:** Requires touching pre-processing utility code that isn't core to current work.
- **Context:** Discovered during `/ship` for the markdown PR. Not caused by markdown changes — confirmed by stashing the diff and re-running on bare `main` (commit `5f0c1b9`).

## P1

### Normalize `ingestor_api.py` return_dict shape across all 5 ingestors
- **What:** Rewrite `nlm_ingestor/ingestor/ingestor_api.py:32-77` so every mime-type branch returns the same shape (`{result, page_dim, num_pages}`). Today some branches use `ingestor.return_dict` while others wrap `{"result": ingestor.json_dict}`.
- **Why:** Adding any new output format (markdown, markdown_chunks_by_page, markdown_chunks_by_section all just landed) requires conditional handling per branch. The next format will be even worse.
- **Pros:** Clean dispatch; smaller blast radius for future format additions; uniform consumer experience.
- **Cons:** Touches the daemon route consumer — need to update `ingestion_daemon/__main__.py` response handling to match. Small but visible behavior change.
- **Context:** Surfaced in the eng review for the markdown output PR. Bundling was considered but rejected per outside-voice critique that mixing API-shape changes with feature work increases revert difficulty.
- **Depends on / blocked by:** Markdown output PR landing first (so the new shapes are visible).

## P2

### Remove UI button cruft from block_renderer.py
- **What:** Strip the `<button class="ant-btn" button_type="approve-page|flag-page|approve-table|flag-table">` blocks emitted at `nlm_ingestor/ingestor/visual_ingestor/block_renderer.py:94-99` and `:215-221`.
- **Why:** UI artifacts (Ant Design buttons for human approval workflow) don't belong in a parser library's HTML output. Callers should inject UI separately; the parser should emit pure structural HTML.
- **Pros:** Clean separation of parsing from UI; smaller HTML output; no surprise markup for new consumers.
- **Cons:** May break a downstream UI that depends on these buttons being present. Verify no internal CaseMax tool relies on them before removing.
- **Context:** Surfaced in the eng review for the markdown output PR. The pre-clean for the original markdownify approach had to strip these explicitly; switching to a JSON-tree walker bypassed them, but they're still in the HTML path.

### Fix latent HTML emission bugs in render_html
- **What:** Audit `nlm_ingestor/ingestor/visual_ingestor/block_renderer.py:render_html` for malformed attribute quoting. The line 66 quote bug was patched as part of the markdown PR; there may be others (the rendering uses raw f-strings and string concatenation rather than a templater).
- **Why:** Malformed HTML mostly silently passes through browser rendering but fails strict parsers (BeautifulSoup with `lxml`, jsdom, screen readers).
- **Pros:** Correct HTML output everywhere.
- **Cons:** Requires writing tests against rendered HTML for every block type, which doesn't exist today.
- **Context:** Outside voice during the markdown PR eng review flagged the line 66 bug. We patched the one site we found but didn't audit comprehensively.

### Refactor `block_renderer.render_html` to use a templater
- **What:** Move from f-string concatenation to a small templater (Jinja2 or just `string.Template`). Eliminates entire class of attribute-quoting bugs.
- **Why:** Dependency-free string concatenation has produced bugs (line 66 in particular) and is hard to audit. Templates make the structure visible.
- **Pros:** Maintainability; bug class eliminated; easier to add new block types.
- **Cons:** Adds a dependency (or even string.Template adds a small refactor); rendering may be marginally slower.
- **Context:** Discovered while triaging the line 66 quote bug during the markdown PR.

### Preserve PDF superscripts through the Tika extraction layer
- **What:** Footnote superscripts in PDF tables (e.g., `$1,900¹`) are flattened by Tika to inline digits before our visual_ingestor or markdown renderer ever sees them. Tika emits them as `<p style='font-size:10.56px'>$1,9001</p>` — a single text node with uniform font-size, no `<sup>` tag, no font-size differential. Result: contract tables look like `$1,9001` and `$3,7504,5` in every output format (markdown, HTML, JSON), and the LLM has no way to know `1` is a footnote ref vs part of the dollar amount.
- **Why:** Affects readability and citation fidelity for legal/contract docs heavy on footnoted tables (rate cards, fee schedules). Comes up in the foreclosure exhibit PDF and almost any contract that pairs a table with footnote references.
- **Pros:** Recovered superscripts unlock proper footnote linking in RAG/extraction pipelines and human-readable rendered output.
- **Cons:** Probably requires either (a) swapping Tika for a parser that preserves font-size per character (PyMuPDF, pdfminer.six both do), (b) extending the custom `tika-server-standard-nlm-modified` jar to emit per-run font-size, or (c) a heuristic post-processor on numeric cells (risky — false positives on actual large numbers). Each path is a meaningful chunk of work and affects every output format, not just markdown.
- **Context:** Discovered while QA'ing the markdown output of `~/Downloads/foreclosure.pdf` after the markdown PR. Confirmed by inspecting Tika's raw HTML — the flattening happens at the Tika layer, before any of our code runs. Texas's `$1,900⁷` survives because that PDF used a Unicode superscript codepoint instead of a positioned-small-font glyph; PDFs use both techniques inconsistently.
- **Depends on / blocked by:** Decision on which fix path (parser swap vs. Tika modification vs. heuristic). All three need a separate design discussion.
