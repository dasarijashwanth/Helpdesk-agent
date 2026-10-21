"""Day 3 evaluation CLI.

Usage:
    python -m evals.run_eval

Writes evals/results_day3.json (machine-readable) and
evals/results_day3.md (human-readable report) and prints a summary.
"""

from __future__ import annotations

import json
from pathlib import Path

from app import answer as answer_module
from app.kb import KnowledgeBase

from .calibrate import PRECISION_TARGET, choose_operating_point, sweep_thresholds
from .golden import load_golden_set, recall_at_5, run_cases, summarize

OUT_DIR = Path(__file__).resolve().parent


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def build_report() -> dict:
    kb = KnowledgeBase.load()
    cases = load_golden_set()

    recall5 = recall_at_5(kb, cases)
    default_threshold = answer_module.CONFIDENCE_THRESHOLD
    default_summary = summarize(run_cases(kb, cases))
    rows = sweep_thresholds(kb, cases)
    chosen = choose_operating_point(rows)

    by_label: dict[str, dict] = {}
    default_results = run_cases(kb, cases)
    for result in default_results:
        bucket = by_label.setdefault(
            result["label"], {"total": 0, "action_correct": 0}
        )
        bucket["total"] += 1
        bucket["action_correct"] += int(result["action_correct"])

    return {
        "golden_set_size": len(cases),
        "recall_at_5": round(recall5, 4),
        "default_threshold": default_threshold,
        "default_summary": default_summary,
        "action_accuracy_by_label": by_label,
        "precision_target": PRECISION_TARGET,
        "sweep": rows,
        "chosen_operating_point": chosen,
        "failures_at_default": [
            r
            for r in default_results
            if not r["action_correct"] or (r["action"] == "answered" and not r["answer_correct"])
        ],
    }


def render_markdown(report: dict) -> str:
    chosen = report["chosen_operating_point"]
    default = report["default_summary"]
    lines = [
        "# Day 3 evaluation results",
        "",
        f"Golden set: {report['golden_set_size']} human-reviewed tickets "
        "(60 covered, 15 KB gaps, 10 policy-routing handoffs, "
        "8 contradictory-policy cases, 7 prompt injections).",
        "",
        "## Headline numbers",
        "",
        f"- Retrieval recall@5 on covered cases: {_pct(report['recall_at_5'])}",
        f"- At the shipped threshold ({report['default_threshold']}): "
        f"coverage {_pct(default['coverage'])}, answered precision "
        f"{_pct(default['answered_precision'])}, action accuracy "
        f"{_pct(default['action_accuracy'])}",
        f"- Chosen operating point: threshold {chosen['threshold']} with "
        f"coverage {_pct(chosen['coverage'])} and answered precision "
        f"{_pct(chosen['answered_precision'])}",
        "",
        "## What the threshold is and is not",
        "",
        "Confidence is a normalized BM25 score (score / (score + 1)). It is "
        "not a calibrated probability: a confidence of 0.4 does not mean a "
        "40 percent chance of being right. The sweep below picks an "
        "operating point, the threshold with the highest coverage whose "
        f"answered precision stays at or above {_pct(report['precision_target'])}. "
        "That is a policy choice measured on this golden set, not a "
        "guarantee about future tickets.",
        "",
        "## Threshold sweep",
        "",
        "| Threshold | Answered | Coverage | Answered precision | Action accuracy |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report["sweep"]:
        lines.append(
            f"| {row['threshold']} | {row['answered']} | "
            f"{_pct(row['coverage'])} | {_pct(row['answered_precision'])} | "
            f"{_pct(row['action_accuracy'])} |"
        )
    lines += [
        "",
        "## Action accuracy by label (shipped threshold)",
        "",
        "| Label | Cases | Action correct |",
        "| --- | --- | --- |",
    ]
    for label, bucket in sorted(report["action_accuracy_by_label"].items()):
        lines.append(
            f"| {label} | {bucket['total']} | {bucket['action_correct']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    report = build_report()
    (OUT_DIR / "results_day3.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "results_day3.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    chosen = report["chosen_operating_point"]
    print(f"golden set: {report['golden_set_size']} cases")
    print(f"recall@5: {report['recall_at_5']:.4f}")
    print(
        f"chosen threshold: {chosen['threshold']} "
        f"(coverage {chosen['coverage']:.3f}, "
        f"precision {chosen['answered_precision']:.3f})"
    )


if __name__ == "__main__":
    main()
