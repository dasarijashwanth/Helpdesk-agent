# Day 4: cost-aware routing

Outcome costs in human minutes (see evals/cost_routing.py for the
full assumptions): answered and correct 1.0 min skim review, answered and wrong 21.0 min with rework, handoff 8.0 min, escalate 10.0 min. Dollars use $0.50 per minute ($30/hour loaded).

| Threshold | Coverage | Answered precision | Expected min/ticket | Expected $/ticket |
| --- | --- | --- | --- | --- |
| 0.0 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.1 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.2 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.3 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.35 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.4 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.5 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.6 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.7 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.8 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.85 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.9 | 68.0% | 88.2% | 4.98 | $2.49 |
| 0.91 | 66.0% | 90.9% | 4.72 | $2.36 |
| 0.92 | 66.0% | 90.9% | 4.72 | $2.36 |
| 0.93 | 64.0% | 93.8% | 4.46 | $2.23 |
| 0.94 | 63.0% | 95.2% | 4.33 | $2.17 |
| 0.95 | 61.0% | 96.7% | 4.27 | $2.13 |
| 0.96 | 56.0% | 100.0% | 4.22 | $2.11 |
| 0.97 | 40.0% | 100.0% | 5.34 | $2.67 |
| 0.98 | 6.0% | 100.0% | 7.72 | $3.86 |

## Chosen operating point

- Threshold 0.96: expected 4.22 human minutes per ticket ($2.11), coverage 56.0%, answered precision 100.0%, action accuracy 96.0%. Cheapest threshold whose answered precision stays at or above 95 percent: yes.

Regenerate with: `python -m evals.run_day4`
