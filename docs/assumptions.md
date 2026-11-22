# Assumptions (the brief requires every assumption to be stated)

These describe what the code actually does. **Read each one, check it in the code, and decide whether you
agree.** Add your own, and reword them in your report. Each has an ID so you can cite it.

| ID | Assumption | Where in the code |
|---|---|---|
| A1 | Everything runs on a **simulated clock** starting 2026-01-01 08:00; timestamps are not wall-clock time. | `src/config.py::SIM_START` |
| A2 | Each patient sends **one reading a minute**. | `simulator/generator.py` |
| A3 | **Labels come from a points rule** inspired by NEWS2, not from clinicians. A model trained on them largely re-learns the rule, so high scores are expected and **do not prove clinical value**. | `src/rules.py` |
| A4 | Critical = 6+ points; Warning = 3–5 points or any single vital worth 3; else Normal. Diastolic and glucose bands are my own additions. | `src/rules.py::label` |
| A5 | **Glucose is monitored only for patients with diabetes**; for others it is empty (not zero). | `simulator/generator.py` |
| A6 | Risk group = points from conditions (arrhythmia 2, diabetes 1, hypertension 1) plus age (65+: 1, 75+: 2); 4+ High, 2–3 Medium, else Low. | `src/rules.py::risk_group` |
| A7 | One shared **device key** authenticates all simulated devices. A real system needs a key or certificate per device. | `app/auth.py` |
| A8 | All demo clinicians share one **demo password** from `.env`. Never do this for real. | `app/db.py::init_db` |
| A9 | A reading measured **more than 15 minutes before** the newest stored reading is *late*: stored, classified and shown, but **it does not page the clinician** (the moment has passed). Trade-off: a late Critical is not alerted. | `app/alerts.py::is_late` |
| A10 | **One alert per episode**: a repeat Critical within 10 minutes of an unacknowledged alert only raises its repeat counter. An alert unacknowledged for 15 minutes is shown as escalated. ("Now" is the newest reading from any patient, so an alert still escalates if that patient's sensor goes silent.) | `app/alerts.py` |
| A11 | A clinician's own limits can only **raise** a status by one level; they can never lower the model's status. | `app/alerts.py::apply_thresholds` |
| A12 | The optional **patient-facing view is not implemented**. | – |
| A13 | "Signal lost" is measured against the newest reading **in the whole system** (simulated clock), after 10 minutes. | `dashboard/views.py` |
| A14 | "Alert the clinician" = a stored alert on the dashboard + a server log line. There is **no SMS, email or push**. | `app/main.py` |
| A15 | Stuck-sensor detection (rolling std = 0 over 6 readings) is applied to heart rate, SpO2 and systolic only; temperature is excluded because a flat reading at 0.1 °C resolution is normal (measured: it caused many false "stuck" flags). | `src/config.py::STUCK_COLUMNS` |
| A16 | Gaps longer than 2 readings are filled with the **median from the training data** (imputer inside the model pipeline). | `src/model.py` |
| A17 | History for trend features is the patient's **last 12 stored readings** before the new one. | `src/config.py::HISTORY_WINDOW` |
| A18 | Models are trained and tested on **separate patients** (75 % / 25 %). | `src/model.py::split_by_patient` |
| A19 | SQLite on one node, the Flask development server and HTTP (no TLS) are enough for a **prototype**. | `app/main.py`, `docker-compose.yml` |
| A20 | The trust's clinicians each look after a fixed set of patients (C01–C04, five patients each). | `simulator/generator.py` |
| A21 | **Drift** is judged on the newest 1,000 stored readings of **all** patients, against the training patients' readings, with the Population Stability Index: below 0.10 stable, 0.10–0.25 watch, above 0.25 shift (an industry rule of thumb, not a clinical standard). Fewer than 200 values for a vital: not judged. Only aggregate numbers are shown, never another clinician's patient. | `src/drift.py`, `src/config.py::DRIFT_WINDOW` |
| A22 | The dashboard shows **status as a word and a colour** and lists the most urgent patients first; the overview refreshes every 15 seconds (no push notifications). | `dashboard/templates/` |

## Key risk and plan B (for design-plan question 9)
*Fill in your own.* Facts from the build you can use: Docker could not be run during the build, so container
problems are the most likely surprise; plan B is `python -m app.main` plus the simulator directly (works without Docker).
