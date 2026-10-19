"""Answer composition: retrieval + deterministic extractive mock provider.

No paid API keys. The mock provider answers from the top retrieved
StyleDesk article. Confidence is a normalized BM25 score; below the
threshold the ticket hands off to a human instead of guessing.
"""

from __future__ import annotations

from .kb import KnowledgeBase

CONFIDENCE_THRESHOLD = 0.35


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
    query = f"{subject} {body}".strip()
    results = kb.search(query, top_k=3)

    if not results or results[0][1] <= 0:
        return {
            "answer": "",
            "citations": [],
            "confidence": 0.0,
            "action": "handoff",
            "handoff_reason": "low_retrieval_confidence",
        }

    top_article, top_score = results[0]
    confidence = confidence_from_score(top_score)

    if confidence < CONFIDENCE_THRESHOLD:
        return {
            "answer": "",
            "citations": [],
            "confidence": round(confidence, 4),
            "action": "handoff",
            "handoff_reason": "low_retrieval_confidence",
        }

    answer = (
        f"Based on our help article '{top_article['title']}': "
        f"{_excerpt(top_article['body'])}"
    )
    citations = [
        {"article_id": article["id"], "title": article["title"]}
        for article, _ in results
        if _ > 0
    ]
    return {
        "answer": answer,
        "citations": citations,
        "confidence": round(confidence, 4),
        "action": "answered",
        "handoff_reason": None,
    }
