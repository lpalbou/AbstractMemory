"""ONE home for text tokenization (the 2026-07-10 adversarial-review fix).

The package had FOUR text-normalization implementations with materially
different rules — channels.tokenize (NFKD accent-fold, len>=4), the
maintenance near-dup token set (no accent fold, len>=3), the maintenance
title key, and consolidation's facet tokens (any script, whitespace split).
Same disease canonical_text.py and vector_scoring.py were created to cure:
copies drift ("café" produced three different tokens across the package,
and accented FR near-duplicates were invisible to the tending pass while
keyword recall matched them).

Rules now live HERE; consumers import. The variants are DECLARED, not
accidental:

- `tokenize(...)`   — recall keyword semantics: NFKD accent-folded latin
  alnum tokens, minimum length as a stopword surrogate (no language lists —
  fork ADR rule; length is the measurable proxy).
- `token_set(...)`  — evidence-set semantics (near-dup Jaccard): same
  folding, lower default floor (3: dedup evidence may keep short content
  tokens recall deliberately drops — the 0002 regression only bit recall).
- `title_key(...)`  — normalized duplicate-title identity: the folded
  tokens joined by single spaces (punctuation/case/accents never make two
  titles "different").
- `facet_tokens(...)` — the fork's facet rule kept VERBATIM as a declared
  variant: any-script tokens (CJK runs survive whole), whitespace/comma
  split, edge punctuation stripped. Participants and non-Latin facets are
  the reason this variant exists; do not "unify" it into the regex rule.
- `jaccard(...)`    — the one set-overlap definition.

Behavior notes (deliberate, test-pinned at adoption): near-dup token sets
gained NFKD accent folding (café ≈ cafe now dedups); duplicate-title
grouping converged on `title_key` everywhere (previously structural_report
used whole-title casefold while maintenance used regex tokens — one report,
two duplicate definitions).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Sequence, Set

__all__ = [
    "TOKEN_RE",
    "TRUNCATION_MARK",
    "bounded_label",
    "facet_tokens",
    "fold_text",
    "jaccard",
    "title_key",
    "token_set",
    "tokenize",
    "truncation_meta",
]

TOKEN_RE = re.compile(r"[a-z0-9]+")

# Recall keyword floor: 4, not 3 (0002 decay regression) — 3 admits the
# highest-frequency English function words ("the", "for", "was", "and");
# at 4 the worst offenders drop while content tokens survive. Documented
# limits: 4-char function words still pass; real 3-char content tokens
# ("tax", "aws", "gpu") need another channel — FTS5 (0019) is the honest
# fix for both. Evidence sets (near-dup) keep floor 3 deliberately.
RECALL_MIN_TOKEN_LEN = 4
EVIDENCE_MIN_TOKEN_LEN = 3

# The one in-band marker for a lossy cut. Greppable, and stable across every
# surface that can cut content.
TRUNCATION_MARK = "#TRUNCATION"


def bounded_label(text: str, cap: int) -> str:
    """A display label cut to `cap`, the cut shown by a bare "…".

    Labels and titles carry a hard length contract and always travel beside
    the id of the record they name, so a reader can open the source for the
    rest. Counts would overflow the very bound they describe; when a caller
    genuinely needs them, they belong out-of-band via `truncation_meta`.
    """
    body = str(text or "")
    if cap <= 0:              # a bound of zero means nothing, never "unlimited"
        return ""
    return body if len(body) <= cap else body[: cap - 1] + "…"


def truncation_meta(kept: int, total: int, *, unit: str = "chars") -> Dict[str, Any]:
    """The out-of-band record of a lossy cut. ONE shape, package-wide.

    Framework ADR-0026 §1 forbids SILENT truncation and accepts three channels
    for the warning: a marker in the text, runtime metadata, or a logged event.
    This package uses the first two TOGETHER and never a counted marker alone —
    cut text keeps a bare "…" so the reader sees that words are missing, and
    the counts ride here, in a sibling field.

    The counts must stay OUT of the text, because cut strings here are rarely
    inert. A record digest is the embedding and keyword surface rendered by
    `canonical_text`, so a marker's own words ("chars", "source", "truncation")
    become tokens shared by every truncated record and inflate near-duplicate
    Jaccard between documents that have nothing to do with each other. A dream
    fragment carries a documented <=200 bound that `replay` relies on to serve
    the signal stream verbatim. In both cases a marker spliced into the text
    corrupts the very thing it was meant to describe.
    """
    return {"mark": TRUNCATION_MARK, "kept": int(kept), "of": int(total), "unit": unit}


def fold_text(text: str) -> str:
    """Casefold + NFKD accent-fold ('café' -> 'cafe' — audit f6)."""
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def tokenize(text: str, *, min_len: int = RECALL_MIN_TOKEN_LEN) -> List[str]:
    """Unique folded alnum tokens, first-seen order (recall semantics).
    Non-Latin scripts produce zero tokens — the CALLER must label that
    degradation (run_keyword_channel does); FTS5 (0019) is the real fix."""
    return list(dict.fromkeys(
        t for t in TOKEN_RE.findall(fold_text(text)) if len(t) >= int(min_len)))


def token_set(text: str, *, min_len: int = EVIDENCE_MIN_TOKEN_LEN) -> Set[str]:
    """Folded token SET (evidence semantics: near-dup Jaccard fingerprints).
    Same folding as recall so dedup evidence and recall evidence agree on
    what a word is; lower length floor by design (see module doc)."""
    return {t for t in TOKEN_RE.findall(fold_text(text)) if len(t) >= int(min_len)}


def title_key(title: str) -> str:
    """The ONE normalized duplicate-title identity (folded tokens joined) —
    'Foo, Bar' == 'foo bar' == 'Foo  Bar'. Empty when no tokens survive."""
    return " ".join(TOKEN_RE.findall(fold_text(title)))


def jaccard(left: Set[str], right: Set[str]) -> float:
    """Set-overlap score; empty-vs-anything is 0.0 (never a division error)."""
    if not left or not right:
        return 0.0
    union = len(left | right)
    return (len(left & right) / union) if union else 0.0


def facet_tokens(values: Sequence[str], *, min_len: int = EVIDENCE_MIN_TOKEN_LEN) -> Set[str]:
    """The fork's facet rule, verbatim (declared variant — see module doc):
    lowercase, comma->space, whitespace split, edge punctuation stripped,
    ANY script kept (CJK facet runs survive whole; participants keep their
    namespaced forms elsewhere — this only serves keyword/intent/outcome
    facet lists)."""
    out: Set[str] = set()
    for value in values or ():
        for token in str(value).lower().replace(",", " ").split():
            token = token.strip(".;:!?()[]\"'")
            if len(token) >= int(min_len):
                out.add(token)
    return out
