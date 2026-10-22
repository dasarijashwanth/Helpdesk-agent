"""Day 4 evaluation CLI: curve, cost-aware routing, reviewer effort.

Usage:
    python -m evals.run_day4

Writes, from real pipeline runs over the golden set:
- evals/results_day4_curve.json / .md   quality-vs-coverage curve
- evals/results_day4_cost.json / .md    cost-aware operating point
- evals/results_day4_effort.json / .md  reviewer-effort measurement
"""

from __future__ import annotations

import json
from pathlib import Path

from app import answer as answer_module
from app.kb import KnowledgeBase

from .cost_routing import (
    COST_MINUTES,
    USD_PER_MINUTE,
    choose_cost_operating_point,
    sweep_costs,
)
from .curve import build_curve, curve_highlights
from .golden import load_golden_set
from .reviewer_effort import effort_at_threshold

OUT_DIR = Path(__file__).resolve().parent


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def build_reports() -> dict:
    kb = KnowledgeBase.load()
    cases = load_golden_set()

    curve = build_curve(kb, cases)
    highlights = curve_highlights(curve)

    cost_rows = sweep_costs(kb, cases)
    cost_choice = choose_cost_operating_point(cost_rows)

    shipped = answer_module.CONFIDENCE_THRESHOLD
    effort_shipped = effort_at_threshold(kb, cases, shipped)
    effort_cost_point = effort_at_threshold(kb, cases, cost_choice["threshold"])

    return {
        "curve": {"points": curve, "highlights": highlights},
        "cost": {
            "model_minutes": COST_MINUTES,
            "usd_per_minute": USD_PER_MINUTE,
            "rows": cost_rows,
            "chosen_operating_point": cost_choice,
        },
        "effort": {
            "at_shipped_threshold": effort_shipped,
            "at_cost_optimal_threshold": effort_cost_point,
        },
    }


def render_curve_md(reports: dict) -> str:
    curve = reports["curve"]
    hl = curve["highlights"]
    lines = [
        "# Day 4: quality-vs-coverage curve",
        "",
        "Every point is a real pipeline run over the 100-ticket golden set.",
        "Confidence is a normalized BM25 score, not a calibrated probability,",
        "so this is an operating-characteristic curve for the threshold knob.",
        "",
        "| Threshold | Answered | Coverage | Answered precision | Action accuracy |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in curve["points"]:
        lines.append(
            f"| {r['threshold']} | {r['answered']} | {_pct(r['coverage'])} | "
            f"{_pct(r['answered_precision'])} | {_pct(r['action_accuracy'])} |"
        )
    best = hl["best_precision_point"]
    maxcov = hl["max_coverage_at_floor"]
    drop = hl["steepest_coverage_drop"]
    lines += [
        "",
        "## Reading the curve",
        "",
        f"- Best answered precision: {_pct(best['answered_precision'])} at "
        f"threshold {best['threshold']} (coverage {_pct(best['coverage'])}).",
        f"- Most coverage with precision at or above "
        f"{_pct(hl['precision_floor'])}: threshold {maxcov['threshold']} at "
        f"{_pct(maxcov['coverage'])} coverage.",
        f"- Steepest coverage drop: {_pct(drop['coverage_drop'])} between "
        f"thresholds {drop['from_threshold']} and {drop['to_threshold']}. "
        "Answered-ticket scores cluster in a narrow band, so small moves "
        "near the top of the range swing coverage a lot.",
        "",
        "Regenerate with: `python -m evals.run_day4`",
        "",
    ]
    return "\n".join(lines)


def render_cost_md(reports: dict) -> str:
    cost = reports["cost"]
    chosen = cost["chosen_operating_point"]
    lines = [
        "# Day 4: cost-aware routing",
        "",
        "Outcome costs in human minutes (see evals/cost_routing.py for the",
        "full assumptions): answered and correct "
        f"{cost['model_minutes']['answered_correct']} min skim review, "
        f"answered and wrong {cost['model_minutes']['answered_wrong']} min "
        f"with rework, handoff {cost['model_minutes']['handoff']} min, "
        f"escalate {cost['model_minutes']['escalate']} min. Dollars use "
        f"${cost['usd_per_minute']:.2f} per minute ($30/hour loaded).",
        "",
        "| Threshold | Coverage | Answered precision | Expected min/ticket | Expected $/ticket |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in cost["rows"]:
        lines.append(
            f"| {r['threshold']} | {_pct(r['coverage'])} | "
            f"{_pct(r['answered_precision'])} | "
            f"{r['expected_minutes_per_ticket']:.2f} | "
            f"${r['expected_usd_per_ticket']:.2f} |"
        )
    lines += [
        "",
        "## Chosen operating point",
        "",
        f"- Threshold {chosen['threshold']}: expected "
        f"{chosen['expected_minutes_per_ticket']:.2f} human minutes per "
        f"ticket (${chosen['expected_usd_per_ticket']:.2f}), coverage "
        f"{_pct(chosen['coverage'])}, answered precision "
        f"{_pct(chosen['answered_precision'])}, action accuracy "
        f"{_pct(chosen['action_accuracy'])}. Cheapest threshold whose "
        f"answered precision stays at or above 95 percent: "
        f"{'yes' if chosen['precision_floor_met'] else 'no threshold met the floor; cheapest overall shown'}.",
        "",
        "Regenerate with: `python -m evals.run_day4`",
        "",
    ]
    return "\n".join(lines)


def _effort_block(title: str, effort: dict) -> list[str]:
    return [
        f"## {title} (threshold {effort['threshold']})",
        "",
        f"- Drafts needing reviewer skim: {effort['drafts_needing_review']} "
        f"({effort['wrong_drafts']} of them wrong, needing rework)",
        f"- Handoffs handled from scratch: {effort['handoffs']}",
        f"- Escalations (senior): {effort['escalations']}",
        f"- Reviewer minutes: {effort['reviewer_minutes']:.0f}; handling "
        f"minutes: {effort['handling_minutes']:.0f}; total human minutes: "
        f"{effort['total_human_minutes']:.0f} per {effort['total_tickets']} tickets",
        f"- Fully manual baseline: {effort['fully_manual_baseline_minutes']:.0f} "
        f"minutes. Saved: {effort['minutes_saved']:.0f} minutes "
        f"({effort['effort_saved_pct']:.1f} percent)",
        "",
    ]


def render_effort_md(reports: dict) -> str:
    effort = reports["effort"]
    lines = [
        "# Day 4: reviewer-effort measurement",
        "",
        "Assumptions (evals/reviewer_effort.py): skim review of a draft 1 min,",
        "rework of a wrong draft +20 min, handoff from scratch 8 min,",
        "escalation 10 min, fully manual baseline 8 min for every ticket.",
        "An estimate from labeled data, not a time study.",
        "",
    ]
    lines += _effort_block("Shipped operating point", effort["at_shipped_threshold"])
    lines += _effort_block("Cost-optimal operating point", effort["at_cost_optimal_threshold"])
    lines += ["Regenerate with: `python -m evals.run_day4`", ""]
    return "\n".join(lines)


def main() -> None:
    reports = build_reports()
    (OUT_DIR / "results_day4_curve.json").write_text(
        json.dumps(reports["curve"], indent=2), encoding="utf-8"
    )
    (OUT_DIR / "results_day4_curve.md").write_text(
        render_curve_md(reports), encoding="utf-8"
    )
    (OUT_DIR / "results_day4_cost.json").write_text(
        json.dumps(reports["cost"], indent=2), encoding="utf-8"
    )
    (OUT_DIR / "results_day4_cost.md").write_text(
        render_cost_md(reports), encoding="utf-8"
    )
    (OUT_DIR / "results_day4_effort.json").write_text(
        json.dumps(reports["effort"], indent=2), encoding="utf-8"
    )
    (OUT_DIR / "results_day4_effort.md").write_text(
        render_effort_md(reports), encoding="utf-8"
    )
    chosen = reports["cost"]["chosen_operating_point"]
    effort = reports["effort"]["at_shipped_threshold"]
    print(f"curve points: {len(reports['curve']['points'])}")
    print(
        f"cost-optimal threshold: {chosen['threshold']} "
        f"({chosen['expected_minutes_per_ticket']:.2f} min/ticket, "
        f"precision {chosen['answered_precision']:.3f})"
    )
    print(
        f"effort at shipped threshold: {effort['total_human_minutes']:.0f} min "
        f"vs {effort['fully_manual_baseline_minutes']:.0f} baseline "
        f"({effort['effort_saved_pct']:.1f}% saved)"
    )


if __name__ == "__main__":
    main()
