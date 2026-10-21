# Day 3 evaluation results

Golden set: 100 human-reviewed tickets (60 covered, 15 KB gaps, 10 policy-routing handoffs, 8 contradictory-policy cases, 7 prompt injections).

## Headline numbers

- Retrieval recall@5 on covered cases: 100.0%
- At the shipped threshold (0.94): coverage 63.0%, answered precision 95.2%, action accuracy 97.0%
- Chosen operating point: threshold 0.94 with coverage 63.0% and answered precision 95.2%

## What the threshold is and is not

Confidence is a normalized BM25 score (score / (score + 1)). It is not a calibrated probability: a confidence of 0.4 does not mean a 40 percent chance of being right. The sweep below picks an operating point, the threshold with the highest coverage whose answered precision stays at or above 95.0%. That is a policy choice measured on this golden set, not a guarantee about future tickets.

## Threshold sweep

| Threshold | Answered | Coverage | Answered precision | Action accuracy |
| --- | --- | --- | --- | --- |
| 0.0 | 68 | 68.0% | 88.2% | 92.0% |
| 0.1 | 68 | 68.0% | 88.2% | 92.0% |
| 0.2 | 68 | 68.0% | 88.2% | 92.0% |
| 0.3 | 68 | 68.0% | 88.2% | 92.0% |
| 0.35 | 68 | 68.0% | 88.2% | 92.0% |
| 0.4 | 68 | 68.0% | 88.2% | 92.0% |
| 0.5 | 68 | 68.0% | 88.2% | 92.0% |
| 0.6 | 68 | 68.0% | 88.2% | 92.0% |
| 0.7 | 68 | 68.0% | 88.2% | 92.0% |
| 0.8 | 68 | 68.0% | 88.2% | 92.0% |
| 0.85 | 68 | 68.0% | 88.2% | 92.0% |
| 0.9 | 68 | 68.0% | 88.2% | 92.0% |
| 0.91 | 66 | 66.0% | 90.9% | 94.0% |
| 0.92 | 66 | 66.0% | 90.9% | 94.0% |
| 0.93 | 64 | 64.0% | 93.8% | 96.0% |
| 0.94 | 63 | 63.0% | 95.2% | 97.0% |
| 0.95 | 61 | 61.0% | 96.7% | 97.0% |
| 0.96 | 56 | 56.0% | 100.0% | 96.0% |
| 0.97 | 40 | 40.0% | 100.0% | 80.0% |
| 0.98 | 6 | 6.0% | 100.0% | 46.0% |

## Action accuracy by label (shipped threshold)

| Label | Cases | Action correct |
| --- | --- | --- |
| account_action | 3 | 3 |
| billing_dispute | 4 | 4 |
| bug_incident | 3 | 3 |
| contradiction | 8 | 7 |
| covered | 60 | 60 |
| kb_gap | 15 | 13 |
| prompt_injection | 7 | 7 |
