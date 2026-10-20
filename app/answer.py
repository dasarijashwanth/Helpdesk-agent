"""Answer pipeline: retrieval + guardrails + deterministic extractive mock provider.

No paid API keys. The mock provider answers from the top retrieved
StyleDesk article. Confidence is a normalized BM25 score; below the
threshold the ticket hands off to a human instead of guessing.

Day 2: the pipeline runs guardrails (prompt-injection detection, PII
redaction, claim and evidence checks) and selective-automation routing
before anything is stored. Use pipeline_ticket() for the full record;
answer_ticket() keeps the Day 1 return shape for compatibility.
"""

from __future__ import annotations

import time

from .guardrails import (
    EVIDENCE_OVERLAP_THRESHOLD,
    check_claims,
    check_evidence_conflict,
    classify,
    detect_injection,
    evidence_overlap,
    match_whitelist,
    redact_pii,
)
from .kb import KnowledgeBase

CONFIDENCE_THRESHOLD = 0.35
PROVIDER_VERSION = "mock-extractive-0.2.0"
PROMPT_VERSION = "styledesk-prompt-v2"


def confidence_from_score(score: float) -> float:
    """Map a raw BM25 score into [0, 1). Zero score -> zero confidence."""
    return score / (score + 1.0)


def _excerpt(body: str, max_chars: int = 280) -> str:
    text = " ".join(body.split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut + "..."


def answer_ticket(kb: KnowledgeBase, subject: str, body: str) -> dict:
    """Day 1 compatibility wrapper: returns the legacy five-field result."""
    result = pipeline_ticket(kb, subject, body)
    return {
        "answer": result["answer"],
        "citations": result["citations"],
        "confidence": result["confidence"],
        "action": result["action"],
        "handoff_reason": result["handoff_reason"],
    }


def pipeline_ticket(
    kb: KnowledgeBase,
    subject: str,
    body: str,
    whitelist: dict | None = None,
    simulate_delay_s: float = 0.0,
) -> dict:
    """Run the full Day 2 pipeline and return every field the queue stores.

    Steps: guardrail routing -> retrieval -> confidence gate -> evidence
    conflict check -> draft -> claim check -> whitelist match -> PII
    redaction. simulate_delay_s is a testing hook for timeout drills.
    """
    if simulate_delay_s > 0:
        time.sleep(simulate_delay_s)

    text = f"{subject} {body}".strip()

    started = time.perf_counter()
    # Top 5 retrieved for the conflict check; top 3 used for citations.
    results = kb.search(text, top_k=5)
    retrieval_ms = (time.perf_counter() - started) * 1000.0

    retrieved = [
        {
            "article_id": article["id"],
            "title": article["title"],
            "category": article["category"],
            "score": round(float(score), 4),
        }
        for article, score in results[:3]
    ]
    conflict_ids = [article["id"] for article, _ in results[:5]]
    top_article = results[0][0] if results else None
    top_score = float(results[0][1]) if results else 0.0

    # 1. Selective-automation routing (injection -> escalate inside classify).
    action, routing_reason = classify(text, top_article)

    # 2. Retrieval confidence gate (BM25 score only).
    confidence = confidence_from_score(top_score) if top_score > 0 else 0.0
    if action != "escalate":
        if not results or top_score <= 0:
            action, routing_reason = "handoff", "low_retrieval_confidence"
        elif confidence < CONFIDENCE_THRESHOLD:
            action, routing_reason = "handoff", "low_retrieval_confidence"

    # 3. Contradictory evidence forces a human handoff. This runs before the
    # overlap gate: a ticket invoking two conflicting policies is ambiguous,
    # not evidence-free, and deserves the more informative reason.
    conflict_reason = None
    if action == "answered":
        conflict_reason = check_evidence_conflict(conflict_ids, text)
        if conflict_reason:
            action, routing_reason = "handoff", "contradictory_policy"

    # 4. Evidence-overlap gate: BM25 can match generic words ("app", "tool")
    # while no article is actually about the ticket. Only applies when the
    # pipeline still intends to answer, so earlier routing reasons stand.
    if (
        action == "answered"
        and top_article is not None
        and evidence_overlap(text, top_article) < EVIDENCE_OVERLAP_THRESHOLD
    ):
        action, routing_reason = "handoff", "low_retrieval_confidence"

    # 5. Draft generation (timed).
    gen_started = time.perf_counter()
    if action == "answered" and top_article is not None:
        answer = (
            f"Based on our help article '{top_article['title']}': "
            f"{_excerpt(top_article['body'])}"
        )
        citations = [
            {"article_id": article["id"], "title": article["title"]}
            for article, score in results[:3]
            if score > 0
        ]
    else:
        answer = ""
        citations = []
    generation_ms = (time.perf_counter() - gen_started) * 1000.0

    # 6. Unsupported-claim check on the draft.
    needs_review = False
    needs_review_reason = None
    if action == "answered":
        problems = check_claims(
            answer, [article for article, _ in results]
        )
        if problems:
            needs_review = True
            needs_review_reason = (
                "unsupported claims: " + ", ".join(problems[:5])
            )

    # 7. Whitelist: auto_sendable only for documented how-tos.
    auto_sendable = False
    matched_intent = None
    if action == "answered" and not needs_review and whitelist:
        top_id = retrieved[0]["article_id"] if retrieved else None
        matched_intent = match_whitelist(text, top_id, whitelist)
        auto_sendable = (
            matched_intent is not None and confidence >= CONFIDENCE_THRESHOLD
        )

    # 8. PII redaction before anything is stored.
    body_redacted, pii_in_body = redact_pii(f"{subject}\n{body}")
    draft_redacted, pii_in_draft = redact_pii(answer)

    handoff_reason = None
    if action == "escalate":
        handoff_reason = "suspected_prompt_injection"
    elif action == "handoff":
        handoff_reason = routing_reason

    return {
        "action": action,
        "answer": draft_redacted,
        "citations": citations,
        "confidence": round(confidence, 4),
        "handoff_reason": handoff_reason,
        "routing_reason": routing_reason,
        "auto_sendable": auto_sendable,
        "matched_intent": matched_intent,
        "needs_review": needs_review,
        "needs_review_reason": needs_review_reason,
        "pii_redacted": bool(pii_in_body or pii_in_draft),
        "body_redacted": body_redacted,
        "retrieved": retrieved,
        "retrieval_ms": round(retrieval_ms, 3),
        "generation_ms": round(generation_ms, 3),
        "provider_version": PROVIDER_VERSION,
        "prompt_version": PROMPT_VERSION,
    }
