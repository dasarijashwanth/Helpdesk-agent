"""Threshold operating-point sweep over the golden set.

Honest framing: the pipeline confidence is a normalized BM25 score
(score / (score + 1)). It is NOT a calibrated probability, and nothing
here turns it into one. What the sweep produces is an operating point:
for each candidate threshold, how many tickets the agent would answer
(coverage) and how often those answers cite the right article
(precision). The chosen threshold is the one that maximizes coverage
while keeping answered precision at or above a stated target, which is
a policy choice, not a statistical guarantee.
"""

from __future__ import annotations

from app.kb import KnowledgeBase

from .golden import run_cases, summarize

# Coarse grid while nothing changes, finer grid in the 0.90 to 0.98 band
# where the normalized BM25 scores of real tickets actually land and the
# tradeoff starts to bite.
SWEEP_THRESHOLDS = [
    0.0, 0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85,
    0.9, 0.91, 0.92, 0.93, 0.94, 0.95, 0.96, 0.97, 0.98,
]
PRECISION_TARGET = 0.95


def sweep_thresholds(
    kb: KnowledgeBase,
    cases: list[dict],
    thresholds: list[float] = SWEEP_THRESHOLDS,
) -> list[dict]:
    """Run the golden set once per candidate threshold."""
    rows = []
    for threshold in thresholds:
        summary = summarize(run_cases(kb, cases, threshold=threshold))
        rows.append({"threshold": threshold, **summary})
    return rows


def choose_operating_point(
    rows: list[dict], precision_target: float = PRECISION_TARGET
) -> dict:
    """Pick max coverage subject to answered precision >= target.

    Falls back to the highest-precision row (ties broken by coverage)
    when no threshold reaches the target, so the function always
    returns a defensible operating point.
    """
    qualifying = [
        r for r in rows if r["answered_precision"] >= precision_target
    ]
    if qualifying:
        return max(qualifying, key=lambda r: r["coverage"])
    return max(
        rows, key=lambda r: (r["answered_precision"], r["coverage"])
    )
