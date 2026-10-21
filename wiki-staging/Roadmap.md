# Roadmap

Week 3 plan for the helpdesk agent. Goal: FDE portfolio evidence first, learning second. Every day should produce a number or a demo.

## Day 1 (done 2026-10-19)

- FastAPI scaffold: `POST /tickets/answer`, `GET /health`.
- BM25 retrieval over 30 fictional StyleDesk KB articles.
- Deterministic extractive mock answer provider (no paid API keys).
- Confidence from normalized BM25 score, threshold 0.35, below goes to handoff.
- 10 tests passing. Pushed to GitHub.

## Day 2 (done 2026-10-19)

- Approval queue with assignee, routing reason, append-only history (SQLite).
- Guardrails: prompt injection, PII redaction, unsupported-claim check, contradictory-policy detection.
- Rollback and recovery: supersede sent replies, invalidate drafts, structured handoffs, duplicate-intake prevention.
- Golden set expanded 5 to 40 tickets; 6 automated failure demos.
- 26/26 tests passing.

## Day 3 (done 2026-10-21)

- Golden set at 100 tickets with intentional KB gaps and contradictions (60 covered, 15 gaps, 10 routing handoffs, 8 contradictions, 7 injections).
- Confidence threshold calibrated from labeled data: operating point 0.94 chosen by sweep (answered precision 95.2 percent, action accuracy 97 percent). BM25 normalization is still not a calibrated probability; the sweep reports the actual error rate per threshold.
- Retrieval recall@5 on covered cases: 100.0 percent.
- 41/41 tests passing.

## Day 4 (next)

- Quality-vs-coverage curve: show how answering more tickets changes the error rate.
- Cost-aware routing: cheap model triage, strong model for hard cases.
- Reviewer-effort measurement: compare manual handling time against draft review time.

## Day 5 (next)

- Full READMEs with the automation policy written out explicitly.
- Demo story with before/after numbers.
- Final eval report.
