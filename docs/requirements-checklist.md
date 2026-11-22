# Requirements checklist (R1–R11 and Outputs 1–6)

Tick a row only when **you** have run the code, seen the test pass and taken your own screenshot.
"Code" and "Test" columns show where the evidence lives in this repository.

| ID | The system must… | Code | Test(s) | Screenshot taken? |
|---|---|---|---|---|
| R1 | Group patients into Low / Medium / High risk | `src/rules.py::risk_group`, `simulator/generator.py::make_patients` | `test_rules::test_risk_groups_follow_conditions_and_age` | ☐ |
| R2 | Ingest readings continuously via an IoT-style feed | `simulator/run_simulator.py`, `simulator/generator.py`, `POST /readings` | `test_api` (all), T7 | ☐ |
| R3 | Classify each reading Normal / Warning / Critical with a trained model | `src/model.py`, `src/train.py`, `app/classify.py` | `test_model` (4 tests) | ☐ |
| R4 | Alert the assigned clinician on Critical: patient ID, vitals, timestamp | `app/alerts.py::make_alert`, `app/main.py` | `test_alerts::test_critical_reading_raises_alert_with_id_vitals_timestamp` and 2 more | ☐ |
| R5 | Clinicians see only their own patients | `app/auth.py`, `app/main.py::own_patient`, `dashboard/views.py` | `test_security` (19 tests) | ☐ |
| R6 | History of readings and alerts per patient | `app/db.py` (SQLite + volume) | `test_api::test_duplicate_is_stored_once_history_r6`, late-order test | ☐ |
| R7 | UK GDPR, no real patient data | invented data only; `data/DATA_CARD.md`; hashed passwords; `.env` secrets | `test_security::test_no_real_patient_data_only_invented_ids`, `test_passwords_are_stored_hashed_not_plain` | ☐ |
| R8 | Show vital-sign trends over time | `dashboard/charts.py`, `dashboard/templates/patient.html` | `test_security::test_dashboard_chart_renders_a_png` | ☐ |
| Extra | Drift monitoring (guide's list of extra features) | `src/drift.py`, `GET /model/health`, overview *Model health* card | `test_drift` (7 tests) | ☐ |
| R9 | Handle missing / delayed / anomalous readings without false or missing alerts | `src/pipeline.py`, `simulator/edge.py`, `app/validation.py`, `app/alerts.py::is_late` | T7, T8, T9, T9b, T10 in `test_faults` | ☐ |
| R10 | Per-patient alert thresholds | `app/alerts.py::apply_thresholds`, `PUT /patients/{id}/thresholds` | `test_alerts` (5 threshold tests) | ☐ |
| R11 | Emerging-tech architecture (edge/cloud, API, containers), justified | `simulator/edge.py`, `app/`, `*/Dockerfile`, `docker-compose.yml`, `docs/architecture.png` | `test_edge`, `test_api`; **containers: run `docker compose up` yourself** | ☐ |

| Output | What | Where | Status |
|---|---|---|---|
| 1 | Critical comparison of ≥ 2 approaches | `docs/approaches.md`, notebook 01, `docs/results/model_comparison.md` | **You write the argument** |
| 2 | Working system | this repository | built; **you must run and understand it** |
| 3 | Ethics, security, privacy, sustainability, societal | `docs/ethics-security-checklist.md` | **You write the argument** |
| 4 | Test evidence: accuracy, precision, recall, F1, confusion matrix | `docs/results/`, `docs/test-plan.md`, tests | numbers generated; **you add screenshots** |
| 5 | Technical report, Harvard | `docs/report/report-outline.md` | **You write it** |
| 6 | 10-minute presentation and demo | `docs/report/demo-plan.md` | **You prepare and rehearse** |
