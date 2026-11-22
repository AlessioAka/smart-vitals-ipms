# ADR 2 · What runs on the edge and what runs in the cloud?

**Status:** draft. **The decision and reasoning are yours.**

## Context
Wearables and phones have little battery and an unreliable network (Week 4 constraints: battery/compute, memory,
network/latency, privacy). The four Week 4 questions: needs history? cheap? urgent? must raw data leave?

## Options considered
A. Everything in the cloud · B. Range check + early warning + buffer on the edge, model in the cloud (this build) ·
C. A small model on the edge too.

## Evidence (notebook 03, `docs/results/fault_report.md`, same simulated feed)
| | Edge range check OFF | Edge range check ON |
|---|---|---|
| Glitched readings (impossible value) | refused with 422: **whole reading lost** (10 of 10 in notebook 03) | stored with the bad value blanked (10 of 10) |
| Messages answered 422 in the notebook run | 13 | 0 |

The early-warning rule (`simulator/edge.py`) needs no network, model or history. The edge keeps a bounded buffer and retries
with backoff; the API never sees a retry storm because 4xx are not retried (`tests/test_edge.py`).

## Decision
*YOUR TURN.*

## Consequences and limits
*YOUR TURN: what does the edge now need to be trusted with? (a tampered phone), what are you not measuring (battery, traffic)?*
