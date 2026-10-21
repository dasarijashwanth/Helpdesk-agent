"""Golden-set evaluation: run the pipeline over labeled tickets and score it.

Definitions used everywhere in Day 3 reporting:

- action accuracy: pipeline action equals the labeled expected_action.
- correct answer: pipeline answered AND its top retrieved article is the
  labeled expected_article_id (only covered cases can be correct).
- recall@5: over covered cases, the share whose expected article appears
  in the top 5 BM25 results for the ticket text.
"""

from __future__ import annotations

import json
from pathlib import Path

from app import answer as answer_module
from app.answer import pipeline_ticket
from app.kb import KnowledgeBase

DATA_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "golden_set.json"
)

LABELS = {
    "covered",
    "kb_gap",
    "billing_dispute",
    "account_action",
    "bug_incident",
    "contradiction",
    "prompt_injection",
}


def load_golden_set(path: Path = DATA_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return payload["cases"]


def recall_at_5(kb: KnowledgeBase, cases: list[dict]) -> float:
    """Share of covered cases whose expected article is in the top 5."""
    covered = [c for c in cases if c["expected_article_id"]]
    if not covered:
        return 0.0
    hits = 0
    for case in covered:
        text = f"{case['subject']} {case['body']}".strip()
        top_ids = [a["id"] for a, _ in kb.search(text, top_k=5)]
        if case["expected_article_id"] in top_ids:
            hits += 1
    return hits / len(covered)


def run_cases(
    kb: KnowledgeBase,
    cases: list[dict],
    threshold: float | None = None,
) -> list[dict]:
    """Run the pipeline on every case, optionally at a given threshold.

    The threshold override patches app.answer.CONFIDENCE_THRESHOLD for the
    duration of the run and always restores it afterwards.
    """
    original = answer_module.CONFIDENCE_THRESHOLD
    if threshold is not None:
        answer_module.CONFIDENCE_THRESHOLD = threshold
    try:
        results = []
        for case in cases:
            outcome = pipeline_ticket(kb, case["subject"], case["body"])
            top_id = (
                outcome["retrieved"][0]["article_id"]
                if outcome["retrieved"]
                else None
            )
            answered = outcome["action"] == "answered"
            results.append(
                {
                    "id": case["id"],
                    "label": case["label"],
                    "expected_action": case["expected_action"],
                    "expected_article_id": case["expected_article_id"],
                    "action": outcome["action"],
                    "routing_reason": outcome["routing_reason"],
                    "confidence": outcome["confidence"],
                    "top_article_id": top_id,
                    "action_correct": outcome["action"]
                    == case["expected_action"],
                    "answer_correct": bool(
                        answered
                        and case["expected_article_id"] is not None
                        and top_id == case["expected_article_id"]
                    ),
                }
            )
        return results
    finally:
        answer_module.CONFIDENCE_THRESHOLD = original


def summarize(results: list[dict]) -> dict:
    """Aggregate per-case results into the headline Day 3 metrics."""
    total = len(results)
    answered = [r for r in results if r["action"] == "answered"]
    correct = [r for r in answered if r["answer_correct"]]
    return {
        "total": total,
        "answered": len(answered),
        "coverage": len(answered) / total if total else 0.0,
        "answered_correct": len(correct),
        "answered_precision": (
            len(correct) / len(answered) if answered else 0.0
        ),
        "answered_error_rate": (
            1.0 - len(correct) / len(answered) if answered else 0.0
        ),
        "action_accuracy": (
            sum(1 for r in results if r["action_correct"]) / total
            if total
            else 0.0
        ),
    }
