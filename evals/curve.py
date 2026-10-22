"""Day 4: quality-vs-coverage curve over the golden set.

Day 3 picked one operating point (max coverage at answered precision
>= 95 percent). Day 4 publishes the whole tradeoff: for every candidate
threshold, how much the agent answers (coverage), how often those
answers cite the right article (answered precision), and how often the
overall routing decision matches the label (action accuracy).

The confidence is a normalized BM25 score, not a calibrated
probability, so the curve is an operating-characteristic curve for a
policy knob, not a reliability diagram. Points come from real pipeline
runs over data/golden_set.json; nothing is interpolated.
"""

from __future__ import annotations

from app.kb import KnowledgeBase

from .calibrate import SWEEP_THRESHOLDS, sweep_thresholds
from .golden import load_golden_set

PRECISION_FLOOR = 0.95


def build_curve(
    kb: KnowledgeBase,
    cases: list[dict],
    thresholds: list[float] = SWEEP_THRESHOLDS,
) -> list[dict]:
    """One curve point per threshold, straight from the Day 3 sweep."""
    rows = sweep_thresholds(kb, cases, thresholds)
    return [
        {
            "threshold": r["threshold"],
            "coverage": r["coverage"],
            "answered_precision": r["answered_precision"],
            "action_accuracy": r["action_accuracy"],
            "answered": r["answered"],
            "answered_correct": r["answered_correct"],
        }
        for r in rows
    ]


def curve_highlights(rows: list[dict]) -> dict:
    """Summarize the shape of the curve for reporting.

    - best_precision: highest answered precision (ties: most coverage).
    - max_coverage_at_floor: most coverage with precision >= floor.
    - steepest_drop: largest coverage loss between adjacent points,
      i.e. where the score clustering makes the knob touchy.
    """
    best_precision = max(
        rows, key=lambda r: (r["answered_precision"], r["coverage"])
    )
    at_floor = [r for r in rows if r["answered_precision"] >= PRECISION_FLOOR]
    max_cov = max(at_floor, key=lambda r: r["coverage"]) if at_floor else None
    steepest = None
    for prev, cur in zip(rows, rows[1:]):
        drop = prev["coverage"] - cur["coverage"]
        if steepest is None or drop > steepest["coverage_drop"]:
            steepest = {
                "from_threshold": prev["threshold"],
                "to_threshold": cur["threshold"],
                "coverage_drop": round(drop, 4),
            }
    return {
        "precision_floor": PRECISION_FLOOR,
        "best_precision_point": best_precision,
        "max_coverage_at_floor": max_cov,
        "steepest_coverage_drop": steepest,
    }
