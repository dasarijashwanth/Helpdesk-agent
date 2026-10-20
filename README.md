![Helpdesk Agent workflow banner](assets/helpdesk-agent-banner.png)

# helpdesk-agent

An AI helpdesk workflow for the fictional SaaS company StyleDesk.
It explores how customer-support automation can retrieve company knowledge,
produce evidence-backed answers, decide when a human should take over, and
recover from incorrect or unsafe actions while preserving accountability.

## Day 1 scope

- FastAPI service with `GET /health` and `POST /tickets/answer`
- Knowledge base: 30 StyleDesk help articles (`data/tickets.json`) covering
  billing, account, product bugs, and how-tos
- BM25 retrieval baseline (`app/kb.py`)
- Deterministic extractive mock provider (`app/answer.py`): answers from the
  top retrieved article, no paid API keys
- Confidence gate: below the threshold the ticket hands off to a human with
  `handoff_reason: low_retrieval_confidence`

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
`action` (`answered` or `handoff`), and `handoff_reason`.

## Tests

```bash
python -m pytest -q
```

Using `python -m pytest` ensures pytest runs with the same Python interpreter
and installed dependencies as the application.

## Roadmap

* Day 2: guardrails + human handoff + rollback.
* Day 3: end to end wiring.
* Day 4: failure-mode fixes + cost-aware routing.
* Day 5: full README + demo.
