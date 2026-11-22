# Smart Vitals · Intelligent Patient Monitoring System (CMS22301)

A prototype remote patient monitoring system for the fictional MedLink Community Health Trust.
Simulated wearables send vital signs to an API. A trained model labels each reading
**Normal / Warning / Critical**. A Critical reading raises an alert for the assigned clinician,
and a login-protected dashboard shows each clinician only their own patients, with trends and
per-patient alert thresholds.

> **All data is invented (simulator). No real patient data is used anywhere (R7).**

## Run it in VS Code (5 steps)

Open this folder in VS Code (**File → Open Folder**). Install the recommended extensions when prompted.
Open a terminal (**Terminal → New Terminal**) and run:

> **Python 3.12 or newer is required** (the pinned numpy does not install on 3.11). Check with
> `python --version`. On a Mac the first command is usually `python3 -m venv .venv` (or `python3.14 ...`);
> once the environment is activated, plain `python` works.

```bash
python -m venv .venv                 # 1. a private Python environment
# Windows:  .venv\Scripts\activate      Mac/Linux:  source .venv/bin/activate
pip install -r requirements-dev.txt  # 2. libraries
python -m simulator.make_dataset     # 3. make the invented data (already included; re-run to change it)
python -m src.train                  # 4. train + compare models, save the best (writes docs/results/)
python tools/run_tests.py            # 5. run every test  (or:  python -m pytest)
```

Then run the system (two terminals):

```bash
python -m app.main                   # terminal 1: the API + dashboard on http://localhost:8000
python -m simulator.run_simulator    # terminal 2: plays 150 minutes of messy readings into it (includes Critical episodes)
```

Open **http://localhost:8000/dashboard/login** and log in as `C01`, `C02`, `C03` or `C04`
(demo password: the value of `DEMO_PASSWORD` in `.env`; in the supplied file that is
`change-me-demo-password`. With no `.env` file at all the fallback is `demo-only-change-me`).
The API and the simulator both read `.env` themselves, so they always agree on the device key.
The API listens on this computer only (`127.0.0.1`); set `HOST=0.0.0.0` to open it to your network.
Each clinician sees only their own five patients.

**With Docker** (Docker Desktop installed): `cp .env.example .env`, then `docker compose up --build`.
The API and the simulator each run in a container; readings live in a volume.

In VS Code you can also use **Run and Debug** (▶ panel) for the API, simulator, training and tests,
and **Terminal → Run Task** for the same steps.

If you see a scikit-learn version warning when loading the model, just re-run `python -m src.train`.

## Where things are

| Folder | What | Brief |
|---|---|---|
| `simulator/` | IoT-style feed with dropouts, glitches, stuck sensors, late and resent readings; the edge node | R2, R9, R11 |
| `src/` | rules (labels, risk groups), cleaning pipeline, models, training | R1, R3, R9 |
| `app/` | the API: validation, de-duplication, classification, alerts, thresholds, login, storage | R4, R5, R6, R10 |
| `dashboard/` | clinician pages and trend charts | R5, R8, R10 |
| `tests/` | one test or more for every requirement | Output 4 |
| `notebooks/` | three notebooks that explain and demonstrate the work | Output 1, 4 |
| `docs/` | API contract, architecture, assumptions, checklists, ADRs, report outline | Outputs 1, 3, 5, 6 |

Start with **`START_HERE.md`**: it lists what is done and, importantly, what only you can do.

## The dashboard

| Page | What the clinician sees |
|---|---|
| **My patients** (`/dashboard`) | KPI tiles (Critical now, Warning now, open and escalated alerts, signal lost); own patients only, most urgent first, with latest vitals; alert cards with the vitals that drove each alert and an Acknowledge button; model health and data drift |
| **Patient** (`/dashboard/patients/<id>`) | latest vitals coloured by the early-warning points each one scores; trend charts over 1, 3 or 6 hours with Critical readings and the clinician's limits marked; readings table (late readings tagged); alert history; per-patient thresholds |

## How it works in one paragraph

The simulator creates readings (and problems). The **edge** node blanks impossible values, can warn
offline, and buffers when the network is down. The **cloud** API validates each reading (422 if
broken), recognises resent copies (200, no second alert), cleans it with the same pipeline used in
training, classifies it with the saved model, applies the clinician's own limits, stores it, and,
if it is Critical, raises one alert per episode for the assigned clinician.

## Extra features (beyond the brief)

1. **Explain each alert**: the vitals that drove it are shown with their points.
2. **Edge early warning**: a tiny offline rule on the phone (`simulator/edge.py`).
3. **Alarm-fatigue control**: one alert per episode, repeat counter, and escalation when unacknowledged.
4. **Signal-lost indicator** on the dashboard (missing data is shown, not hidden).
5. **Drift monitoring**: the dashboard's *Model health* card compares the newest readings with the training
   data, vital by vital, using the Population Stability Index (`src/drift.py`), so a change in the incoming data
   is noticed before it causes wrong alerts. Also available as `GET /model/health`.

## Limits you must be honest about

- Labels come from a points rule, so the model largely re-learns that rule (see `docs/assumptions.md`).
- Data is simulated; real patients are messier. Metrics say nothing about clinical safety.
- The Flask development server and SQLite are fine for a prototype, not for a hospital.
- Docker files were written to the Week 8 pattern but were **not run** while this was built
  (no Docker in the build environment): run `docker compose up --build` yourself and fix anything it reports.
- Not a medical device. Not clinically validated.

## AI use declaration (REQUIRED, complete it yourself)

The brief and the module guide say AI use must be declared and that you must be able to explain
every line. Complete `docs/ai-use-declaration.md` truthfully before you submit.

## Sources

NEWS2: Royal College of Physicians (2017) *National Early Warning Score (NEWS) 2*. London: RCP.
Add every other source you use to `docs/report/references.md` in Harvard style.
