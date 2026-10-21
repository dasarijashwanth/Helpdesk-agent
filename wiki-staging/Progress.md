# Progress Log

Dated record of what was built, with the numbers that prove it.

## 2026-10-19 - Day 1

- Scaffolded FastAPI service with `POST /tickets/answer` and `GET /health`.
- BM25 retrieval (rank_bm25) over `data/tickets.json`: 30 fictional StyleDesk articles.
- Deterministic extractive mock provider; confidence = BM25 score normalized, threshold 0.35, below becomes `action: "handoff"`.
- 10 tests passing. Pushed to GitHub (commit 07665f19).

## 2026-10-19 - Day 2

- Added `app/queue.py`: SQLite approval queue. Every answer becomes a draft with evidence, routing reason, confidence, model/prompt versions, timings. State machine: pending, approved, sent, edited, requeued, superseded, invalidated. Append-only history per ticket.
- Added `app/guardrails.py`: prompt-injection detection, PII redaction (emails, phones, card-like numbers), unsupported-claim check, contradictory-policy detection (refund window vs downgrade timing).
- Added `data/auto_whitelist.json`: 5 how-to intents eligible for auto-send, only when the top retrieved article matches the intent's documented article.
- Added 9 queue endpoints: answer, list, approve, edit, requeue, assign, send, supersede, handoff summary.
- Results: 30/30 helpdesk tests pass.
- Judgment call: kept `POST /tickets/answer` response shape backward compatible (added queue_id, auto_sendable, routing_reason, needs_review).
- Known honest gap: confidence is still BM25-normalized, not calibrated. Threshold calibration from labeled data is Day 3 work.

## 2026-10-21 - Day 3

- Added `data/golden_set.json`: 100 human-reviewed tickets with labeled expected actions and source articles: 60 covered (2 per KB article), 15 intentional KB gaps, 10 policy-routing handoffs, 8 contradictory-policy cases, 7 prompt injections.
- Added `evals/` harness (`python -m evals.run_eval`): runs the real pipeline over the golden set, reports action accuracy and answered precision per label, and writes `evals/results_day3.json` and `evals/results_day3.md`.
- Retrieval recall@5 on covered cases: 100.0 percent.
- Threshold calibration: swept the BM25 confidence threshold on the golden set. Scores saturate (covered cases land between 0.9499 and 0.9828), so nothing changes until about 0.91. Chosen operating point 0.94, the highest coverage with answered precision at or above 95 percent: precision 88.2 to 95.2 percent, action accuracy 92 to 97 percent, coverage 68 to 63 percent. Shipped as the new `CONFIDENCE_THRESHOLD`. Framing stays honest: a normalized BM25 score is not a calibrated probability, so 0.94 is a measured operating point, not a probability.
- Calibration exposed a pipeline bug: the confidence gate overwrote policy routing reasons (billing dispute, account action) with `low_retrieval_confidence` whenever the score was low. Fixed so the gate only demotes answers; handoff actions are unchanged everywhere.
- One existing test updated: the Day 1 attachments phrasing ("40 MB video") scores 0.9347, just under the new operating point, so it now hands off. The test now uses the clearer documented phrasing for the answered case, and a new Day 3 test pins the original phrasing's handoff on purpose.
- Results: 41/41 tests pass (30 prior + 11 new). Remaining known failures at 0.94: 2 of 15 KB-gap tickets still answered from loosely related articles; 1 of 8 contradiction cases slips through when a policy article drops out of the top 5.

## 2026-10-20 - Day 1 fix PR merged, Day 2 pushed

- Contributor PR #1 (neehanthreddym) reviewed, verified locally (14/14 tests), and merged: whitespace-only ticket fields rejected with 422, padded input trimmed, venv/test commands fixed, pytest cache untracked, banner added.
- The PR's whitespace validation was folded into the Day 2 code so the push did not overwrite it. Local suite now 30/30 (26 Day 2 tests + 4 validation tests).
- Day 2 pushed to GitHub main via the web UI (GitHub App write access was returning 403; API reads unaffected). Commits 8e928e4, 8b3c264, 79b7e56, 34a334d, 13647df.
