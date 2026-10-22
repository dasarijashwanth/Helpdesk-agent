"""Day 4: reviewer-effort measurement at an operating point.

The workflow is approval-first: every drafted answer gets a human skim
before it can be sent, handoffs are handled from scratch, escalations
go to a senior. This module counts that human effort on the golden set
under explicit per-outcome minute assumptions, and compares it with
the fully manual baseline (a human handles every ticket from scratch).

Assumptions (same rates as evals/cost_routing.py):

- skim review of a drafted answer: 1.0 minute
- extra rework when a drafted answer is wrong (correct it, re-review,
  follow up with the customer): 20.0 minutes on top of the skim
- handoff handled from scratch: 8.0 minutes
- escalation, senior handling: 10.0 minutes
- fully manual baseline: 8.0 minutes for every ticket

Effort saved is measured against that baseline on the same 100
tickets. It is an estimate from labeled data, not a time study.
"""

from __future__ import annotations

from app.kb import KnowledgeBase

from .golden import run_cases

SKIM_MINUTES = 1.0
REWORK_EXTRA_MINUTES = 20.0
HANDOFF_MINUTES = 8.0
ESCALATE_MINUTES = 10.0
MANUAL_MINUTES_PER_TICKET = 8.0


def effort_for_results(results: list[dict]) -> dict:
    """Human-effort breakdown for one batch of per-case results."""
    answered = [r for r in results if r["action"] == "answered"]
    wrong = [r for r in answered if not r["answer_correct"]]
    handoffs = [r for r in results if r["action"] == "handoff"]
    escalations = [r for r in results if r["action"] == "escalate"]

    reviewer_minutes = len(answered) * SKIM_MINUTES + len(wrong) * REWORK_EXTRA_MINUTES
    handling_minutes = len(handoffs) * HANDOFF_MINUTES + len(escalations) * ESCALATE_MINUTES
    total_minutes = reviewer_minutes + handling_minutes
    baseline_minutes = len(results) * MANUAL_MINUTES_PER_TICKET
    return {
        "total_tickets": len(results),
        "drafts_needing_review": len(answered),
        "wrong_drafts": len(wrong),
        "handoffs": len(handoffs),
        "escalations": len(escalations),
        "reviewer_minutes": round(reviewer_minutes, 2),
        "handling_minutes": round(handling_minutes, 2),
        "total_human_minutes": round(total_minutes, 2),
        "fully_manual_baseline_minutes": round(baseline_minutes, 2),
        "minutes_saved": round(baseline_minutes - total_minutes, 2),
        "effort_saved_pct": (
            round((baseline_minutes - total_minutes) / baseline_minutes * 100, 1)
            if baseline_minutes
            else 0.0
        ),
    }


def effort_at_threshold(
    kb: KnowledgeBase, cases: list[dict], threshold: float
) -> dict:
    """Effort breakdown for the pipeline run at one threshold."""
    effort = effort_for_results(run_cases(kb, cases, threshold=threshold))
    return {"threshold": threshold, **effort}
