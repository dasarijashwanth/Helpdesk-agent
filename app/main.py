"""helpdesk-agent Day 1: FastAPI scaffold answering support tickets."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import FastAPI
from pydantic import BaseModel, StringConstraints

from .answer import answer_ticket
from .kb import KnowledgeBase

app = FastAPI(title="helpdesk-agent", version="0.1.0")

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


@lru_cache(maxsize=1)
def get_kb() -> KnowledgeBase:
    return KnowledgeBase.load()


class TicketRequest(BaseModel):
    ticket_id: NonEmptyString
    subject: NonEmptyString
    body: NonEmptyString


class TicketResponse(BaseModel):
    ticket_id: str
    answer: str
    citations: list[dict]
    confidence: float
    action: str
    handoff_reason: str | None = None


@app.get("/health")
def health() -> dict:
    kb = get_kb()
    return {"status": "ok", "kb_articles": len(kb.articles), "service": "helpdesk-agent"}


@app.post("/tickets/answer", response_model=TicketResponse)
def tickets_answer(ticket: TicketRequest) -> TicketResponse:
    result = answer_ticket(get_kb(), ticket.subject, ticket.body)
    return TicketResponse(ticket_id=ticket.ticket_id, **result)
