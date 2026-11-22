# ADR 3 · API design, services and containers (Week 8, Milestone 1 D)

**Status:** draft. **The decision and reasoning are yours.**

## Context
The model must sit behind an API (R11). Decide how many services, whether the model is loaded once or per request,
and how it is packaged.

## Options considered
1. Monolith: one API that validates, classifies, stores, alerts and serves the dashboard (this build).
2. Microservices: validate / classify / store / alert as separate services. 3. Modular monolith.
For the model: load once at start-up (design C) vs on every request (design D).

## Evidence (notebook 03, this machine; yours will differ: say what you used)
| Serving design | p50 per request | p95 per request |
|---|---|---|
| C: model loaded once | 52.1 ms | 55.3 ms |
| D: model loaded every request | 134.3 ms | 148.9 ms |

Measured on this Mac (Intel, 4 cores, 8 GB, Python 3.14) on 22 November 2026, with the API also running.
An earlier run on the build machine gave C 27.3 / 28.2 ms and D 83.9 / 101.8 ms: the ratio (about 2.5–3×) is what matters.

Full-feed timing and correctness: `docs/results/fault_report.md`. Two API copies sharing a database behave the same (stateless; `tests/test_api.py`).
Containers: `app/Dockerfile`, `simulator/Dockerfile`, `docker-compose.yml` (**not run during the build: run them and record
`docker images` sizes**). The simulator needs only numpy; the API image carries scikit-learn, pandas and matplotlib.

## Decision
*YOUR TURN: why a monolith (or not) at 20 patients? What would make you split it? (Week 8: the Amazon Prime Video example.)*

## Consequences and limits
*YOUR TURN: Flask development server, SQLite, one node: what breaks first at 20,000 patients?*
