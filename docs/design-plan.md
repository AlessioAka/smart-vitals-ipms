# Design plan (the same nine questions as the design plan form)

**This is yours to answer.** The module guide says your tutor checks that *your* plan covers the brief.
Below each question are **facts from this build** you may use or argue with. Do not paste them as your answer.

## 1 · Your two approaches to compare (Output 1)
*Your answer:*

Facts available: three models are compared in `src/train.py` (baseline, logistic regression, random forest);
edge-vs-cloud is demonstrated in notebook 03 (edge range check ON vs OFF).

## 2 · Data (R2, R7, R9)
*Your answer:*

Facts: `data/DATA_CARD.md`; faults are generated in `simulator/generator.py`.

## 3 · Your model (R3, Output 4)
*Your answer (inputs, models, main measure, target):*

Facts: features are in `src/pipeline.py::FEATURES`; results in `docs/results/model_comparison.md`.

## 4 · Architecture (R11)
*Your answer:*

Facts: `docs/architecture.png`, `docs/architecture.md`.

## 5 · Alerts, history, dashboard (R4, R6, R8, R10)
*Your answer:*

Facts: `docs/api.md`, `app/alerts.py`, `dashboard/`.

## 6 · Security and privacy (R5, R7)
*Your answer:*

Facts: `docs/ethics-security-checklist.md`, `tests/test_security.py`.

## 7 · The tension you will argue (Output 3)
*Your answer:* choose ONE trade-off you believe in and can defend with evidence. Examples of real tensions
in this system (pick, reject or replace): catching every Critical vs alarm fatigue; edge privacy vs cloud accuracy;
more history for better trends vs data minimisation; rich explanations vs clinician time.

## 8 · Architecture sketch
Attach `docs/architecture.png`, but redraw it in your own words and decide what you would change.

## 9 · Key assumptions, biggest risk and plan B
See `docs/assumptions.md`. *Your answer:*
