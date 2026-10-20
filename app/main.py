"""helpdesk-agent: FastAPI service with an approval-first support pipeline.

Day 1: POST /tickets/answer answers support tickets from the StyleDesk KB.
Day 2: every answer becomes a DRAFT in a persistent SQLite approval queue.
Nothing is auto-sent. Reviewers approve, edit, requeue, assign, supersede,
or invalidate each item, and every state change is logged with a reason.
Guardrails (prompt-injection detection, PII redaction, claim and evidence
checks) run inside the pipeline before anything is stored.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from . import queue as queue_store
from .answer import pipeline_ticket
from .kb import KnowledgeBase

app = FastAPI(title="helpdesk-agent", version="0.2.0")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WHITELIST_PATH = DATA_DIR / "auto_whitelist.json"


@lru_cache(maxsize=1)
def get_kb() -> KnowledgeBase:
    return KnowledgeBase.load()


@lru_cache(maxsize=1)
def get_whitelist() -> dict:
    with open(WHITELIST_PATH, encoding="utf-8") as f:
        return json.load(f)


NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class TicketRequest(BaseModel):
    ticket_id: NonEmptyString
    subject: NonEmptyString
    body: NonEmptyString
    # Testing hook for timeout drills; never set in production use.
    simulate_delay_s: float = Field(default=0.0, ge=0.0, le=30.0)


class TicketResponse(BaseModel):
    ticket_id: str
    answer: str
    citations: list[dict]
    confidence: float
    action: str
    handoff_reason: str | None = None
    queue_id: int
    duplicate: bool = False
    auto_sendable: bool = False
    routing_reason: str
    needs_review: bool = False


class EditRequest(BaseModel):
    text: str = Field(min_length=1)


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=1)


class AssignRequest(BaseModel):
    assignee: str = Field(min_length=1)


def _not_found(queue_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"queue item {queue_id} not found")


@app.get("/health")
def health() -> dict:
    kb = get_kb()
    return {"status": "ok", "kb_articles": len(kb.articles), "service": "helpdesk-agent"}


@app.post("/tickets/answer", response_model=TicketResponse)
def tickets_answer(ticket: TicketRequest) -> TicketResponse:
    """Run the pipeline and store the result as a draft in the approval queue.

    The response keeps the Day 1 fields and adds the queue id plus the
    routing metadata. Duplicate intake returns the existing queue id.
    """
    result = pipeline_ticket(
        get_kb(),
        ticket.subject,
        ticket.body,
        whitelist=get_whitelist(),
        simulate_delay_s=ticket.simulate_delay_s,
    )
    store = queue_store.get_store()
    queue_id, duplicate = store.create_draft(
        {
            "ticket_id": ticket.ticket_id,
            "subject": ticket.subject,
            "body": ticket.body,
            "body_redacted": result["body_redacted"],
            "retrieved": result["retrieved"],
            "draft": result["answer"],
            "routing_reason": result["routing_reason"],
            "confidence": result["confidence"],
            "provider_version": result["provider_version"],
            "prompt_version": result["prompt_version"],
            "retrieval_ms": result["retrieval_ms"],
            "generation_ms": result["generation_ms"],
            "auto_sendable": result["auto_sendable"],
            "needs_review": result["needs_review"],
            "needs_review_reason": result["needs_review_reason"],
            "pii_redacted": result["pii_redacted"],
        }
    )
    return TicketResponse(
        ticket_id=ticket.ticket_id,
        answer=result["answer"],
        citations=result["citations"],
        confidence=result["confidence"],
        action=result["action"],
        handoff_reason=result["handoff_reason"],
        queue_id=queue_id,
        duplicate=duplicate,
        auto_sendable=result["auto_sendable"],
        routing_reason=result["routing_reason"],
        needs_review=result["needs_review"],
    )


@app.get("/queue")
def queue_list() -> dict:
    """List open queue items (pending, requeued, edited)."""
    return {"items": queue_store.get_store().list_open()}


@app.get("/queue/{queue_id}")
def queue_detail(queue_id: int) -> dict:
    item = queue_store.get_store().get(queue_id)
    if item is None:
        raise _not_found(queue_id)
    return item


@app.get("/queue/{queue_id}/handoff")
def queue_handoff(queue_id: int) -> dict:
    """Structured handoff summary for human takeover."""
    try:
        return queue_store.get_store().handoff_summary(queue_id)
    except ValueError:
        raise _not_found(queue_id)


def _transition(queue_id: int, op: str, reason: str | None = None,
                revised_text: str | None = None) -> dict:
    try:
        return queue_store.get_store().transition(
            queue_id, op, reason=reason, revised_text=revised_text
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message:
            raise _not_found(queue_id)
        raise HTTPException(status_code=400, detail=message)


@app.post("/queue/{queue_id}/approve")
def queue_approve(queue_id: int) -> dict:
    return _transition(queue_id, "approve")


@app.post("/queue/{queue_id}/send")
def queue_send(queue_id: int) -> dict:
    """Mark an approved draft as sent (delivery is simulated)."""
    return _transition(queue_id, "send")


@app.post("/queue/{queue_id}/edit")
def queue_edit(queue_id: int, payload: EditRequest) -> dict:
    return _transition(queue_id, "edit", revised_text=payload.text)


@app.post("/queue/{queue_id}/requeue")
def queue_requeue(queue_id: int, payload: ReasonRequest) -> dict:
    return _transition(queue_id, "requeue", reason=payload.reason)


@app.post("/queue/{queue_id}/assign")
def queue_assign(queue_id: int, payload: AssignRequest) -> dict:
    try:
        return queue_store.get_store().assign(queue_id, payload.assignee)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message:
            raise _not_found(queue_id)
        raise HTTPException(status_code=400, detail=message)


@app.post("/queue/{queue_id}/supersede")
def queue_supersede(queue_id: int, payload: ReasonRequest) -> dict:
    """Withdraw a sent reply and reopen the ticket as a pending draft."""
    return _transition(queue_id, "supersede", reason=payload.reason)


@app.post("/queue/{queue_id}/invalidate")
def queue_invalidate(queue_id: int, payload: ReasonRequest) -> dict:
    """Discard a draft before sending."""
    return _transition(queue_id, "invalidate", reason=payload.reason)
