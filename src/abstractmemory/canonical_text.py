"""Shared canonical-text rendering for assertions (single source of truth).

WHY this exists: the store backends and the reconstruction pipeline must
share ONE text form (embedding input / stored text column / keyword-scan
surface) or the retrieval space silently splits from the digest space. The
stores now import from here (their `_canonical_text` names are aliases kept
for golden-test compatibility).

v2 (realistic-data fix, live-embedder finding): RECORD digest assertions
(attributes.record_kind present) render as clean prose —
"{title}\\n{digest literal}\\nkeywords: …" — WITHOUT the
"ex:… dcterms:abstract" subject/predicate prefix that polluted embeddings
and keyword scans with graph-id tokens. Ordinary assertions keep the v1
"s p o" + attribute-hints shape.

CANONICAL_TEXT_VERSION participates in the embedding-space integrity story
(backlog 0014): the rendered text is part of the embedding space, so any
change to this rendering invalidates stored vectors and MUST bump the version
and ride a re-embed migration — never change the output silently. (v1→v2
ships pre-release with no stored spaces to migrate.)
"""

from __future__ import annotations

from .models import TripleAssertion

CANONICAL_TEXT_VERSION = 2

# Bound mirrored from the store implementations: canonical text is a
# retrieval/preview surface, not archival storage — full context stays in
# `attributes` and is never lost by this preview cap.
_CONTEXT_PREVIEW_MAX = 400

# Preview title bound shared by handle titles (reconstruct) and snapshot
# display rows (system): one constant so the two surfaces can never drift.
_TITLE_MAX = 120


def display_title(a: TripleAssertion) -> str:
    """Preview title "s p o", bounded at 120 chars (digest carries the full text)."""
    title = f"{a.subject} {a.predicate} {a.object}"
    if len(title) > _TITLE_MAX:
        title = title[: _TITLE_MAX - 1] + "…"  #[WARNING:TRUNCATION] title preview bounded at 120 chars (digest carries the full text)
    return title


def token_estimate(text: str) -> int:
    """Crude labeled 4-chars/token estimate shared by shelf fill and snapshot
    display (a real estimator is a later backlog item); +1 floors zero-length
    text so nothing ever costs zero tokens."""
    return len(text) // 4 + 1


def is_record_digest(a: TripleAssertion) -> bool:
    """True for formed-record digest assertions (records.py encoding)."""
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    return isinstance(attrs.get("record_kind"), str) and bool(attrs.get("record_kind"))


def is_record_edge(a: TripleAssertion) -> bool:
    """True for formed-record edge assertions: graph structure, never
    embedded and never a shelf member (they conduct spreading only)."""
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    return bool(attrs.get("record_edge"))


def handle_digest(a: TripleAssertion) -> str:
    """The serialize-ready digest a handle/payload carries: the clean digest
    LITERAL for formed records (title travels separately on the handle),
    the full canonical text for ordinary assertions."""
    return a.object if is_record_digest(a) else canonical_text(a)


def canonical_text(a: TripleAssertion) -> str:
    """Render the stable, information-rich text form of one assertion
    (embedding input + keyword-scan surface; version-pinned, see module
    docstring).

    v2: record digest assertions render "{title}\\n{digest}\\nkeywords: …" —
    clean prose, no graph-id/predicate tokens. Ordinary assertions render
    the v1 "s p o" surface form plus typed-term hints, extractor evidence,
    and a bounded context preview.
    """
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    if is_record_digest(a):
        title = str(attrs.get("title") or "").strip()
        parts = [p for p in (title, a.object) if p]
        keywords = attrs.get("keywords")
        if isinstance(keywords, (list, tuple)) and keywords:
            parts.append("keywords: " + ", ".join(str(k) for k in keywords))
        return "\n".join(parts)

    base = f"{a.subject} {a.predicate} {a.object}".strip()

    parts: list[str] = [base]
    st = attrs.get("subject_type")
    ot = attrs.get("object_type")
    if isinstance(st, str) and st.strip():
        parts.append(f"subject_type: {st.strip()}")
    if isinstance(ot, str) and ot.strip():
        parts.append(f"object_type: {ot.strip()}")

    eq = attrs.get("evidence_quote")
    if isinstance(eq, str) and eq.strip():
        parts.append(f"evidence: {eq.strip()}")

    ctx = attrs.get("original_context")
    if isinstance(ctx, str) and ctx.strip():
        ctx2 = ctx.strip()
        if len(ctx2) > _CONTEXT_PREVIEW_MAX:
            ctx2 = ctx2[:_CONTEXT_PREVIEW_MAX] + "…"  #[WARNING:TRUNCATION] bounded canonical-text context preview (full context remains in attributes)
        parts.append(f"context: {ctx2}")

    return "\n".join(parts)
