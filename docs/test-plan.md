# Test plan: a test for every requirement (Output 4)

Run all: `python tools/run_tests.py` (or `python -m pytest`). Run one file: `python -m pytest tests/test_alerts.py -v`.
Take a screenshot of each passing run for your report. The fault replays (T7–T10) take a few minutes.

| ID | Requirement | What is tested | File::test |
|---|---|---|---|
| T1 | R1 | risk group from conditions and age | test_rules::test_risk_groups_follow_conditions_and_age |
| T2 | R2 | a valid reading is stored (201) | test_api::test_normal_reading_is_created |
| T3 | R3 | model beats the always-Normal baseline on Critical, on unseen patients | test_model::* |
| T4 | R4 | Critical → alert with patient ID, vitals, timestamp, assigned clinician | test_alerts::test_critical_reading_raises_alert_with_id_vitals_timestamp |
| T5 | R5 | clinician gets 403 for another clinician's patient, alerts and thresholds | test_security::* |
| T6 | R6, R8 | history in time order; chart renders | test_api::*history*, test_security::test_dashboard_chart_renders_a_png |
| T7 | R9 | dropouts, resent copies and late readings never crash the API | test_faults::test_T7_… |
| T8 | R9 | every resent copy is 200 and never creates a second alert | test_faults::test_T8_… |
| T9 | R9 | glitched readings from healthy patients raise no false alert (edge on); refused with 422 when edge is off | test_faults::test_T9_…, test_T9b_… |
| T10 | R9 | real Critical episodes are not missed | test_faults::test_T10_… |
| T11 | R10 | thresholds can be set, raise a status one level, never lower it, reject nonsense | test_alerts::*threshold* |
| T12 | R7 | no names in the register; passwords hashed | test_security::* |
| T13 | R11 | edge range check, early warning, bounded buffer, backoff never retries a 422 | test_edge::* |
| T14 | extra | drift monitoring: same data is stable, shifted data is flagged, too little data is not judged; `/model/health` needs a login | test_drift::* |
| T15 | R5 | dashboard: only my patients, most urgent first; another clinician's patient is a 403 page; no redirect to other websites | test_security::test_overview_lists_only_my_patients_most_urgent_first, test_dashboard_errors_are_pages_and_api_errors_stay_json, test_acknowledge_cannot_redirect_to_another_website |
| T16 | R9 | odd timestamps (time zone, space, date only) never cause a 500; negative history limit is clamped | test_api::test_timestamp_*, test_history_limit_* |

## Not covered by automated tests (do these by hand and screenshot)
- `docker compose up --build`: both containers start, `/health` is 200, dashboard works.
- Stop the API container for 15 seconds mid-run and confirm the simulator recovers (Week 8 pattern).
- Log in as two clinicians in two private windows and confirm each sees only their five patients.
- Usability: can a clinician find a Critical patient in under 5 seconds?
