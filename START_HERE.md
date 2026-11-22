# START HERE

## What is already built (and tested here)
- Simulator with on-purpose faults, edge node, cleaning pipeline, model comparison, API, clinician login and
  access control, per-patient thresholds, alerts with escalation, dashboard with trend charts.
- 94 automated tests, all passing at hand-over; three notebooks that run end to end.
- Docker files and `docker-compose.yml` (**written but not run**: I had no Docker).
- VS Code settings, launch configurations and tasks (`.vscode/`).

## What only YOU can do (these are where the marks for thinking are)
1. ☐ **Run everything on your own machine** (see README) and fix anything that differs.
2. ☐ **Read and understand every file.** The brief says you must be able to explain every line you hand in.
3. ☐ **Complete `docs/ai-use-declaration.md`** truthfully, and check the university's AI rules / ask your tutor.
4. ☐ **Make it yours**: change the simulator (more problems, your own risk rule), try to beat the model's Critical recall
   (it is 0.899 against a 0.90 target: why, and what would you try?), add or replace an extra feature.
5. ☐ **Write** `docs/design-plan.md`, the decisions in `docs/adr/`, `docs/approaches.md`,
   `docs/ethics-security-checklist.md`, the report (`docs/report/`) and the presentation. None of these are written for you.
6. ☐ **Evidence**: run `docker compose up --build`, take screenshots for every test in `docs/test-plan.md`,
   record `docker images` sizes, two-clinician demo.
7. ☐ **Rehearse** the 10-minute demo with a timer (`docs/report/demo-plan.md`).
8. ☐ **Push to GitHub** with the commands in the module's starter guide; commit weekly; tag `v0.1` at Week 9.

## Known limits of this hand-over
- Data and labels are simulated; metrics here are not clinical evidence.
- Labels come from a rule, so the model largely re-learns it.
- Tests were run with a plain-Python runner (`tools/run_tests.py`) because pytest was not installable here;
  they are written as pytest-compatible functions, so run `python -m pytest` too.
- Notebooks were executed with `tools/run_notebooks.py` (no Jupyter here); open them in VS Code and Run All.
- Weeks 6, 9, 10, 12 slides were not available, so MQTT, the dashboard design and the threat model follow the brief
  and the Week 8 contract only. Check them against your own notes.
