"""Day 4 tests: curve shape, cost model math, reviewer-effort math."""

import pytest

from app import answer as answer_module
from app.kb import KnowledgeBase
from evals.cost_routing import (
    choose_cost_operating_point,
    expected_cost,
    outcome_key,
    sweep_costs,
)
from evals.curve import build_curve, curve_highlights
from evals.golden import load_golden_set
from evals.reviewer_effort import effort_at_threshold, effort_for_results


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase.load()


@pytest.fixture(scope="module")
def cases():
    return load_golden_set()


def _result(action, answer_correct=False, action_correct=False):
    return {
        "action": action,
        "answer_correct": answer_correct,
        "action_correct": action_correct,
    }


def test_outcome_key():
    assert outcome_key(_result("answered", answer_correct=True)) == "answered_correct"
    assert outcome_key(_result("answered", answer_correct=False)) == "answered_wrong"
    assert outcome_key(_result("handoff")) == "handoff"
    assert outcome_key(_result("escalate")) == "escalate"


def test_expected_cost_math():
    results = (
        [_result("answered", answer_correct=True, action_correct=True)] * 10
        + [_result("answered", answer_correct=False)] * 2
        + [_result("handoff", action_correct=True)] * 5
        + [_result("escalate", action_correct=True)] * 1
    )
    cost = expected_cost(results)
    # 10*1 + 2*21 + 5*8 + 1*10 = 102 minutes over 18 tickets.
    assert cost["total_minutes"] == 102.0
    assert cost["expected_minutes_per_ticket"] == round(102 / 18, 4)
    assert cost["answered_precision"] == 10 / 12


def test_choose_cost_point_respects_precision_floor():
    rows = [
        {"threshold": 0.5, "answered_precision": 0.90,
         "expected_minutes_per_ticket": 2.0, "coverage": 0.8},
        {"threshold": 0.9, "answered_precision": 0.97,
         "expected_minutes_per_ticket": 3.0, "coverage": 0.6},
        {"threshold": 0.95, "answered_precision": 0.99,
         "expected_minutes_per_ticket": 4.0, "coverage": 0.5},
    ]
    chosen = choose_cost_operating_point(rows)
    assert chosen["threshold"] == 0.9
    assert chosen["precision_floor_met"] is True


def test_effort_math():
    results = (
        [_result("answered", answer_correct=True)] * 10
        + [_result("answered", answer_correct=False)] * 1
        + [_result("handoff")] * 4
        + [_result("escalate")] * 1
    )
    effort = effort_for_results(results)
    # Reviewer: 11 skims + 1 rework extra = 11 + 20 = 31.
    # Handling: 4*8 + 1*10 = 42. Baseline: 16 * 8 = 128.
    assert effort["drafts_needing_review"] == 11
    assert effort["reviewer_minutes"] == 31.0
    assert effort["handling_minutes"] == 42.0
    assert effort["total_human_minutes"] == 73.0
    assert effort["fully_manual_baseline_minutes"] == 128.0
    assert effort["effort_saved_pct"] == round((128 - 73) / 128 * 100, 1)


def test_curve_covers_shipped_threshold(kb, cases):
    rows = build_curve(kb, cases)
    by_threshold = {r["threshold"]: r for r in rows}
    shipped = answer_module.CONFIDENCE_THRESHOLD
    assert shipped in by_threshold
    row = by_threshold[shipped]
    # Day 3 measurements at the shipped point.
    assert row["answered_precision"] >= 0.95
    assert row["action_accuracy"] >= 0.95
    assert 0.0 < row["coverage"] < 1.0


def test_curve_highlights_consistent(kb, cases):
    rows = build_curve(kb, cases)
    highlights = curve_highlights(rows)
    maxcov = highlights["max_coverage_at_floor"]
    assert maxcov is not None
    assert maxcov["answered_precision"] >= highlights["precision_floor"]
    for r in rows:
        if r["answered_precision"] >= highlights["precision_floor"]:
            assert r["coverage"] <= maxcov["coverage"]


def test_cost_optimal_point_meets_floor_and_beats_old_threshold(kb, cases):
    rows = sweep_costs(kb, cases)
    chosen = choose_cost_operating_point(rows)
    assert chosen["precision_floor_met"] is True
    assert chosen["answered_precision"] >= 0.95
    by_threshold = {r["threshold"]: r for r in rows}
    # The pre-calibration 0.35 point must not be cheaper under the floor:
    # it fails the precision floor, and the chosen point is the cheapest
    # qualifying one by construction.
    assert by_threshold[0.35]["answered_precision"] < 0.95
    for r in rows:
        if r["answered_precision"] >= 0.95:
            assert r["expected_minutes_per_ticket"] >= chosen["expected_minutes_per_ticket"]


def test_effort_at_shipped_threshold_saves_vs_manual(kb, cases):
    effort = effort_at_threshold(kb, cases, answer_module.CONFIDENCE_THRESHOLD)
    assert effort["total_tickets"] == 100
    assert effort["total_human_minutes"] < effort["fully_manual_baseline_minutes"]
    assert effort["effort_saved_pct"] > 0
    assert (
        effort["drafts_needing_review"] + effort["handoffs"] + effort["escalations"]
        == 100
    )
