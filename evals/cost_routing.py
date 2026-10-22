"""Day 4: cost-aware routing over the golden set.

Day 3 chose the operating point on quality alone (max coverage subject
to answered precision >= 95 percent). Day 4 prices every outcome in
human minutes and picks the threshold that minimizes expected human
cost under the same quality floor.

Cost model (assumptions, stated so they can be argued with):

- answered and correct: the draft still gets the approval-first skim
  review every answer gets in this workflow: 1.0 minute.
- answered and wrong: the skim (1.0) plus rework: a corrected reply, a
  follow-up contact, and senior handling of the fallout: 21.0 minutes
  total. A wrong auto-answer is the expensive failure mode, priced at
  roughly 2.6x a full manual handling on purpose.
- handoff: a human handles the ticket from scratch: 8.0 minutes.
- escalate: senior handling of a suspected injection or sensitive
  case: 10.0 minutes.

Minutes convert to dollars at a loaded support rate of $30/hour
($0.50/minute). These are planning numbers for comparing thresholds on
the same golden set, not accounting figures.
"""

from __future__ import annotations

from app.kb import KnowledgeBase

from .calibrate import SWEEP_THRESHOLDS
from .golden import run_cases

COST_MINUTES = {
    "answered_correct": 1.0,
    "answered_wrong": 21.0,
    "handoff": 8.0,
    "escalate": 10.0,
}
USD_PER_MINUTE = 0.50
PRECISION_FLOOR = 0.95


def outcome_key(result: dict) -> str:
    if result["action"] == "answered":
        return "answered_correct" if result["answer_correct"] else "answered_wrong"
    if result["action"] == "escalate":
        return "escalate"
    return "handoff"


def expected_cost(results: list[dict]) -> dict:
    """Expected human cost of one batch of per-case pipeline results."""
    counts = {key: 0 for key in COST_MINUTES}
    for result in results:
        counts[outcome_key(result)] += 1
    total_minutes = sum(counts[k] * COST_MINUTES[k] for k in counts)
    total = len(results)
    answered = [r for r in results if r["action"] == "answered"]
    correct = [r for r in answered if r["answer_correct"]]
    return {
        "total": total,
        "counts": counts,
        "total_minutes": round(total_minutes, 2),
        "expected_minutes_per_ticket": round(total_minutes / total, 4) if total else 0.0,
        "expected_usd_per_ticket": round(total_minutes / total * USD_PER_MINUTE, 4) if total else 0.0,
        "coverage": len(answered) / total if total else 0.0,
        "answered_precision": len(correct) / len(answered) if answered else 0.0,
        "action_accuracy": (
            sum(1 for r in results if r["action_correct"]) / total if total else 0.0
        ),
    }


def sweep_costs(
    kb: KnowledgeBase,
    cases: list[dict],
    thresholds: list[float] = SWEEP_THRESHOLDS,
) -> list[dict]:
    """Expected cost at every candidate threshold, from real runs."""
    rows = []
    for threshold in thresholds:
        cost = expected_cost(run_cases(kb, cases, threshold=threshold))
        rows.append({"threshold": threshold, **cost})
    return rows


def choose_cost_operating_point(
    rows: list[dict], precision_floor: float = PRECISION_FLOOR
) -> dict:
    """Cheapest threshold whose answered precision clears the floor.

    Ties break toward higher coverage. Falls back to the cheapest row
    overall (flagged) when no threshold clears the floor, so the caller
    always gets a point plus an honest note about the constraint.
    """
    qualifying = [r for r in rows if r["answered_precision"] >= precision_floor]
    pool = qualifying if qualifying else rows
    best = min(
        pool,
        key=lambda r: (r["expected_minutes_per_ticket"], -r["coverage"]),
    )
    return {**best, "precision_floor_met": bool(qualifying)}
