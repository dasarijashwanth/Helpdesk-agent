![Helpdesk Agent workflow banner](assets/helpdesk-agent-banner.png)

# helpdesk-agent

An AI helpdesk workflow for the fictional SaaS company StyleDesk.
It explores how customer-support automation can retrieve company knowledge,
produce evidence-backed answers, decide when a human should take over, and
recover from incorrect or unsafe actions while preserving accountability.

An AI helpdesk agent for the fictional SaaS company StyleDesk, built end to
end: retrieval over the company knowledge base, grounded answers with
citations, guardrails, an approval-first human queue, and rollback with
full recovery.

## Automation policy

Selective automation, approval-based copilot first. Every answer the agent
produces becomes a DRAFT in a persistent queue. Nothing is auto-sent.

- Only 5 documented how-to intents (`data/auto_whitelist.json`) may ever be
  marked `auto_sendable`, and even those default to draft.
- Billing disputes, bug incidents, and account actions route to a human with
  an explicit `routing_reason` stored on the queue item.
- Prompt-injection attempts escalate; nothing in the ticket is followed.
- Every state change is logged with timestamp, actor, and reason.

## Day 1 scope

- FastAPI service with `GET /health` and `POST /tickets/answer`
- Knowledge base: 30 StyleDesk help articles (`data/tickets.json`) covering
  billing, account, product bugs, and how-tos
- BM25 retrieval baseline (`app/kb.py`)
- Deterministic extractive mock provider (`app/answer.py`): answers from the
  top retrieved article, no paid API keys
- Confidence gate: below the threshold the ticket hands off to a human with
  `handoff_reason: low_retrieval_confidence`

## Day 2 scope

- Approval queue (`app/queue.py`, SQLite at `data/helpdesk.db`): every answer
  stored as a draft with retrieved evidence, routing reason, confidence,
  model/prompt versions, and timings. Endpoints: `GET /queue`,
  `GET /queue/{id}`, `POST /queue/{id}/approve|send|edit|requeue|assign|supersede|invalidate`,
  `GET /queue/{id}/handoff` (structured takeover summary).
- Guardrails (`app/guardrails.py`): prompt-injection detection, PII redaction
  (emails, phones, card-like sequences) before storage, unsupported-claim
  checks against retrieved articles, evidence-overlap gate for weak
  retrieval, and contradictory-policy detection (b4 vs b6).
- Recovery: `supersede` withdraws a sent reply and reopens the ticket as a
  pending draft; history is preserved on both items. `invalidate` discards
  unsent drafts.
- Duplicate intake: identical ticket text within 10 minutes returns the
  existing queue id, making client retries idempotent.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

If startup reports `ModuleNotFoundError: No module named 'rank_bm25'`,
install the requirements and launch the server with the same virtual
environment interpreter:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload
```

## Usage

```bash
curl -X POST http://localhost:8000/tickets/answer -H "Content-Type: application/json" -d '{
  "ticket_id": "T-1001",
  "subject": "How do I update my credit card?",
  "body": "My card expired and I need to replace the payment method."
}'
```

Response: `ticket_id`, `answer`, `citations`, `confidence`,
`action` (`answered`, `handoff`, or `escalate`), `handoff_reason`,
`queue_id`, `auto_sendable`, `routing_reason`, and `needs_review`.

Review a draft:

```bash
curl http://localhost:8000/queue                 # open items
curl -X POST http://localhost:8000/queue/1/approve
curl -X POST http://localhost:8000/queue/1/send
curl http://localhost:8000/queue/1/handoff       # takeover summary
```

## Tests

```bash
python -m pytest -q
```

Using `python -m pytest` ensures pytest runs with the same Python interpreter
and installed dependencies as the application.

## Roadmap

Day 2: guardrails + human handoff + rollback (done). Day 3: golden set to
100 tickets + failure demos wired into CI. Day 4: quality-vs-coverage
curve + cost-aware routing + reviewer-effort measurement. Day 5: full
README + demo story with before/after numbers.
