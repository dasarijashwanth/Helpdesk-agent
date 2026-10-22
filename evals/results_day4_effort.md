# Day 4: reviewer-effort measurement

Assumptions (evals/reviewer_effort.py): skim review of a draft 1 min,
rework of a wrong draft +20 min, handoff from scratch 8 min,
escalation 10 min, fully manual baseline 8 min for every ticket.
An estimate from labeled data, not a time study.

## Shipped operating point (threshold 0.94)

- Drafts needing reviewer skim: 63 (3 of them wrong, needing rework)
- Handoffs handled from scratch: 30
- Escalations (senior): 7
- Reviewer minutes: 123; handling minutes: 310; total human minutes: 433 per 100 tickets
- Fully manual baseline: 800 minutes. Saved: 367 minutes (45.9 percent)

## Cost-optimal operating point (threshold 0.96)

- Drafts needing reviewer skim: 56 (0 of them wrong, needing rework)
- Handoffs handled from scratch: 37
- Escalations (senior): 7
- Reviewer minutes: 56; handling minutes: 366; total human minutes: 422 per 100 tickets
- Fully manual baseline: 800 minutes. Saved: 378 minutes (47.2 percent)

Regenerate with: `python -m evals.run_day4`
