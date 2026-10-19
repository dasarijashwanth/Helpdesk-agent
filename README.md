# helpdesk-agent

An AI helpdesk agent for the fictional SaaS company StyleDesk, built end to
end: retrieval over the company knowledge base, grounded answers with
citations, guardrails, human handoff, and rollback.

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
pip install -r requirements.txt
uvicorn app.main:app --reload
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
pytest -q
```

## Roadmap

Day 2: guardrails + human handoff + rollback. Day 3: end to end wiring.
Day 4: failure-mode fixes + cost-aware routing. Day 5: full README + demo.
