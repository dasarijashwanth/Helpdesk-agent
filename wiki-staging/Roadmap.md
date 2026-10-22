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

## Day 4 (done 2026-10-22)

- Quality-vs-coverage curve published (`evals/results_day4_curve.md`): precision 88.2 percent at 0.35, 95.2 percent at 0.94, 100 percent at 0.96; steepest coverage drop (34 points) between 0.97 and 0.98.
- Cost-aware routing (`evals/results_day4_cost.md`): outcomes priced in human minutes; cost-optimal threshold 0.96 at 4.22 expected minutes per ticket, 0.11 min from the shipped 0.94 point.
- Reviewer-effort measurement (`evals/results_day4_effort.md`): 433 human minutes per 100 tickets at 0.94 against an 800-minute fully manual baseline, 45.9 percent saved.
- 49/49 tests passing.

## Day 5 (next)

- Full READMEs with the automation policy written out explicitly.
- Demo story with before/after numbers.
- Final eval report.
