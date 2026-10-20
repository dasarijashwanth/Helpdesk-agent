"""Guardrails for the helpdesk-agent answer pipeline.

Three independent checks run on every ticket before a draft is stored:

1. Prompt-injection detection: instruction-override patterns force escalation.
2. PII redaction: emails, phone numbers, and card-like sequences are replaced
   with [REDACTED] in every stored copy. The original text is never persisted.
3. Claim and evidence checks: drafts containing numbers or names absent from
   the retrieved articles are flagged for review, and retrieved article sets
   known to contradict each other force a human handoff.

Routing classification implements selective automation: documented how-to
questions are answered, while bug incidents, account actions, and billing
disputes route to a human with an explicit routing reason.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Prompt-injection detection
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = [
    r"ignore (all |your |the )?previous instructions",
    r"disregard (all |your |the )?(previous |prior )?instructions",
    r"forget (your |all )?instructions",
    r"you are now ",
    r"system\s*:",
    r"override (your |the )?instructions",
    r"do not follow (your |the )?(previous |system )?instructions",
    r"bypass (your |the )?(safety|guardrails|filters)",
    r"\bjailbreak\b",
]
_INJECTION_RES = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def detect_injection(text: str) -> tuple[bool, str | None]:
    """Return (flagged, matched_pattern). Case-insensitive substring scan."""
    for pattern, compiled in zip(_INJECTION_PATTERNS, _INJECTION_RES):
        if compiled.search(text):
            return True, pattern
    return False, None


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")

_REDACTED = "[REDACTED]"

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# ---------------------------------------------------------------------------
# Evidence-overlap check
# ---------------------------------------------------------------------------


def redact_pii(text: str) -> tuple[str, bool]:
    """Replace emails, phone numbers, and card-like sequences.

    Returns (redacted_text, found_any). Always call this before persisting
    ticket text, drafts, or log lines.
    """
    redacted, n1 = _EMAIL_RE.subn(_REDACTED, text)
    redacted, n2 = _PHONE_RE.subn(_REDACTED, redacted)
    redacted, n3 = _CARD_RE.subn(_REDACTED, redacted)
    return redacted, bool(n1 + n2 + n3)


# ---------------------------------------------------------------------------
# Claim and evidence checks
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")
_NAME_RE = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b")
_FILLER_WORDS = {"Based"}


def check_claims(draft: str, articles: list[dict]) -> list[str]:
    """Find numbers/names in the draft that appear in no retrieved article.

    Returns the list of unsupported tokens (empty means all claims trace to
    the evidence). A citation alone does not prove the answer follows from
    it; this check enforces that link token by token.
    """
    evidence = " ".join(
        a.get("title", "") + " " + a.get("body", "") for a in articles
    ).lower()
    problems: list[str] = []
    for match in _NUMBER_RE.finditer(draft):
        token = match.group(0)
        if token.lower() not in evidence:
            problems.append(token)
    for match in _NAME_RE.finditer(draft):
        token = match.group(0)
        if token in _FILLER_WORDS:
            continue
        if token.lower() not in evidence:
            problems.append(token)
    return problems


# Article sets whose guidance contradicts each other. A set fires only when
# every article is retrieved AND the ticket text invokes both policies
# (one trigger phrase from each group). This keeps weak BM25 co-occurrence
# from flagging tickets that are really about one policy.
CONTRADICTORY_ARTICLE_SETS = [
    {
        "articles": {"b4", "b6"},
        "triggers": [["refund"], ["downgrade", "seats"]],
        "reason": "refund window (b4) conflicts with downgrade timing (b6)",
    },
]


def check_evidence_conflict(retrieved_ids: list[str], text: str) -> str | None:
    """Return the conflict reason if retrieved ids contain a contradictory set
    that the ticket text actually invokes."""
    retrieved = set(retrieved_ids)
    lowered = text.lower()
    for entry in CONTRADICTORY_ARTICLE_SETS:
        if entry["articles"] <= retrieved and all(
            any(phrase in lowered for phrase in group)
            for group in entry["triggers"]
        ):
            return entry["reason"]
    return None


# Tokens too generic to prove the article is really about the ticket.
_STOPWORDS = {
    "how", "what", "where", "when", "why", "who", "which", "can", "could",
    "would", "should", "do", "does", "did", "is", "are", "was", "were",
    "be", "been", "have", "has", "had", "will", "the", "a", "an", "to",
    "from", "of", "in", "on", "for", "with", "and", "or", "at", "by",
    "as", "it", "its", "this", "that", "these", "those", "i", "me",
    "my", "you", "your", "we", "our", "they", "their", "there", "here",
    "please", "want", "need", "get", "getting", "got", "every", "about",
    "into", "over", "under", "up", "out", "so", "if", "not", "no",
    "than", "then", "just", "like", "more", "most", "very", "also",
}

# Minimum share of the ticket's distinctive tokens that must appear in
# the top article. Below this, retrieval found words, not evidence.
EVIDENCE_OVERLAP_THRESHOLD = 0.25


def evidence_overlap(query: str, article: dict) -> float:
    """Fraction of the query's distinctive tokens present in the article."""
    query_tokens = {
        t for t in _TOKEN_RE.findall(query.lower()) if t not in _STOPWORDS
    }
    if not query_tokens:
        return 0.0
    article_tokens = set(_TOKEN_RE.findall(
        (article.get("title", "") + " " + article.get("body", "")).lower()
    ))
    return len(query_tokens & article_tokens) / len(query_tokens)

_INCIDENT_PATTERNS = [
    r"\bcrash(es|ed|ing)?\b",
    r"blank page",
    r"white screen",
    r"not loading",
    r"won't load",
    r"stopped working",
    r"\bbroken\b",
    r"\bfreez\w*\b",
    r"error 500",
]
_BILLING_DISPUTE_PATTERNS = [
    r"charged twice",
    r"duplicate (charge|invoice|payment)",
    r"wrong charge",
    r"unauthorized charge",
    r"invoice ?#\S+",
    r"\bdispute\b",
]
_ACCOUNT_ACTION_PATTERNS = [
    r"delete (my|the|this|that) account",
    r"remove .{0,60} from (the|our|my) workspace",
    r"change .{0,40} email to ",
    r"deactivate .{0,40} account",
]
_QUESTION_START = re.compile(
    r"^\s*(how|what|where|when|why|can|could|is|are|do|does|would|should|which)\b",
    re.IGNORECASE,
)


def _matches(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def is_question(text: str) -> bool:
    """Heuristic: questions ask how something works, commands request action."""
    stripped = text.strip()
    return bool(_QUESTION_START.match(stripped) or stripped.endswith("?"))


def classify(text: str, top_article: dict | None) -> tuple[str, str]:
    """Decide answered / handoff / escalate plus an explicit routing reason.

    The reason is stored on the queue item and is the portfolio evidence for
    the automation policy: every ticket carries why it was answered or not.
    """
    flagged, _ = detect_injection(text)
    if flagged:
        return "escalate", "suspected_prompt_injection"

    category = (top_article or {}).get("category", "")

    # Bug incidents route to humans in any category: the ticket describes a
    # malfunction that needs reproduction details, not a documented answer.
    # Genuine questions (ending in "?") still get answered from the docs.
    if not is_question(text) and _matches(_INCIDENT_PATTERNS, text):
        return "handoff", "bug_report_needs_repro"

    if _matches(_BILLING_DISPUTE_PATTERNS, text):
        return "handoff", "billing_dispute_requires_records"

    if (
        category == "account"
        and not is_question(text)
        and _matches(_ACCOUNT_ACTION_PATTERNS, text)
    ):
        return "handoff", "account_change_requires_auth"

    return "answered", "documented_answer"


def match_whitelist(
    text: str, top_article_id: str | None, whitelist: dict
) -> str | None:
    """Return the matched intent name, or None.

    An intent matches only when a keyword pattern appears in the ticket AND
    the top retrieved article is the intent's documented article. Strict on
    purpose: auto_sendable must never fire on a lucky keyword.
    """
    lowered = text.lower()
    for intent in whitelist.get("intents", []):
        if top_article_id != intent.get("article_id"):
            continue
        if any(p.lower() in lowered for p in intent.get("patterns", [])):
            return intent.get("intent")
    return None
