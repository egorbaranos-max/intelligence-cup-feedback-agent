"""Deterministic evidence spans: the model selects IDs, never rewrites quotes.

Sentence-like splitting is a convenience, not semantic parsing. The full text
is still supplied so negation and context outside a selected span remain visible.
Offsets always refer to the original Python Unicode string, without case folding,
normalization, punctuation repair or whitespace rewriting.
"""
from __future__ import annotations

import re


def source_spans(text: str) -> list[dict]:
    """Return nonempty exact spans in source order; IDs are local to one source.

Splitting only at punctuation followed by whitespace, or at a newline, keeps
URLs and decimal numbers intact in common cases. Abbreviations can split: this
does not assert separate intents, and models may select several adjacent spans.
Repeated text is unambiguous because each ID has its own trusted offsets.
"""
    boundaries = [0] + [m.end() for m in re.finditer(r"[.!?;](?:[ \t]+|\r?\n)|\r?\n", text)]
    if boundaries[-1] != len(text):
        boundaries.append(len(text))
    spans = []
    for begin, end in zip(boundaries, boundaries[1:]):
        while begin < end and text[begin].isspace():
            begin += 1
        while end > begin and text[end - 1].isspace():
            end -= 1
        if begin == end:
            continue
        spans.append({"span_id": f"span_{len(spans) + 1:04d}", "text": text[begin:end],
                      "start": begin, "end": end})
    return spans


def model_spans(text: str) -> list[dict]:
    """Allowlist only the IDs and exact text needed by the language model."""
    return [{"span_id": span["span_id"], "text": span["text"]} for span in source_spans(text)]
