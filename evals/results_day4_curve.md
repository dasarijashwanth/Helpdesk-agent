# Day 4: quality-vs-coverage curve

Every point is a real pipeline run over the 100-ticket golden set.
Confidence is a normalized BM25 score, not a calibrated probability,
so this is an operating-characteristic curve for the threshold knob.

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

## Reading the curve

- Best answered precision: 100.0% at threshold 0.96 (coverage 56.0%).
- Most coverage with precision at or above 95.0%: threshold 0.94 at 63.0% coverage.
- Steepest coverage drop: 34.0% between thresholds 0.97 and 0.98. Answered-ticket scores cluster in a narrow band, so small moves near the top of the range swing coverage a lot.

Regenerate with: `python -m evals.run_day4`
