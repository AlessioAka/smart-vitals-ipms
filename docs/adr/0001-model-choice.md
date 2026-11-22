# ADR 1 · Which model classifies a reading?

**Status:** draft. The evidence is filled in from real runs. **The decision and its reasoning are yours to write.**

## Context
R3 needs a trained model that labels each reading Normal / Warning / Critical. Missing a Critical is the costly
error, and Critical is rare (about 2 % of readings), so accuracy alone misleads.

## Options considered (all in `src/model.py`, compared by `python -m src.train`)
1. Always-Normal baseline · 2. Logistic regression (Week 2; simple, explainable) · 3. Random forest (non-parametric).

## Evidence (unseen test patients; simulated data, rule-made labels)
| Model | Accuracy | Recall Critical | Precision Critical | F1 Critical | Macro F1 |
|---|---|---|---|---|---|
| Baseline | 0.901 | 0.000 | 0.000 | 0.000 | 0.316 |
| Logistic regression | 0.953 | 0.798 | 0.598 | 0.684 | 0.807 |
| Random forest | 0.989 | 0.899 | 0.944 | 0.921 | 0.948 |

Random-row split (leaky) forest accuracy 0.995 vs 0.989 on a patient split. Full tables and confusion matrices:
`docs/results/model_comparison.md`. Target in the design-plan example: recall for Critical ≥ 0.90: **0.899 misses it by a hair**.
Do not round it up: discuss it.

## Decision
*YOUR TURN: which model, and why, against the alternatives? Which criteria matter most?*

## Consequences and limits
*YOUR TURN: include assumption A3 (rule-made labels) and what you would try next to reach the target.*
