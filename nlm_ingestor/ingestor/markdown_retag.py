"""Pre-pass that converts numbered/lettered paragraph blocks into list_items.

Detects patterns like "(a) Foo.", "1.1 Bar.", "i. Baz." at the start of a
para block and retags them. Operates on a deep copy so JSON/HTML outputs
emitted from the same block tree remain unchanged.

Set the env var NLM_DISABLE_RETAG=1 to bypass.
"""

import copy
import os
import re

# Each pattern requires the marker at the very start of a stripped block_text
# AND the block must end with a closing punctuation (., ;, :) so prose like
# "the Court (a U.S. district court) held the matter" is NOT retagged.
#
# Group 1 captures the marker for level computation.
# Roman numerals must be valid 1-39 forms (i..xxxix). Single-letter `i`/`v`/`x`
# accepted only inside `(...)` because bare `i. think...` / `v. important...` is
# almost always English prose, not a list marker.
_ROMAN_VALID = r"(?:i{1,3}|iv|v|vi{0,3}|ix|x{1,3}(?:i{1,3}|iv|v|vi{0,3}|ix)?)"

_PATTERNS = (
    # Decimal: 1.1, 1.1.1 ... — must come before the bare-number variant.
    re.compile(r"^([0-9]+(?:\.[0-9]+)+)\s+.+[.;:]\s*$"),
    # Parenthesised letter / valid roman: (a), (b), (i), (ii), (xiv).
    # Single letter is fine here because the parens disambiguate from prose.
    re.compile(rf"^\(([a-z]|{_ROMAN_VALID})\)\s+.+[.;:]\s*$", re.IGNORECASE),
    # Bare number followed by dot: 1., 23.
    # Bare letter and bare roman are EXCLUDED — too high a false-positive rate
    # on prose like "a. bad idea." or "i. think we should..." or "v. important."
    re.compile(r"^([0-9]+)\.\s+.+[.;:]\s*$"),
)


def _detect_marker(text: str):
    """Return (matched_pattern_index, marker) or None."""
    stripped = text.strip()
    for idx, pat in enumerate(_PATTERNS):
        m = pat.match(stripped)
        if m:
            return idx, m.group(1)
    return None


def retag_numbered_items(blocks):
    """Return a deep copy of blocks with eligible 'para' blocks retagged.

    The original list and its contents are untouched.
    """
    if os.getenv("NLM_DISABLE_RETAG") == "1":
        return blocks

    result = copy.deepcopy(blocks)
    for block in result:
        if block.get("block_type") != "para":
            continue
        text = block.get("block_text", "")
        match = _detect_marker(text)
        if not match:
            continue
        pattern_idx, marker = match
        block["block_type"] = "list_item"
        # Decimal markers like "1.1" or "1.1.1" imply nesting depth. Level
        # equals the number of dots (1.1 → +1, 1.1.1 → +2). Other patterns
        # don't carry depth information; keep their existing level.
        if pattern_idx == 0 and "." in marker:
            block["level"] = (block.get("level", 0) or 0) + marker.count(".")
    return result
