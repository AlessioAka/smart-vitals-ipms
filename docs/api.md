# API contract (Week 8: the API is a contract)

Base URL `http://localhost:8000`. All bodies are JSON. Change this file whenever the API changes.

| Method and path | Who | Does | Success | Errors | Brief |
|---|---|---|---|---|---|
| `POST /readings` | device (`X-Device-Key`) | validate, recognise copies, classify, store, alert | **201** new · **200** copy | 401 · 404 · 422 · 503 | R2 R4 R6 R9 |
| `POST /login` | anyone | exchange ID + password for a token (8 h) | 200 | 401 | R5 |
| `GET /patients` | clinician | only **my** patients | 200 | 401 | R5 |
| `GET /patients/{id}/readings?limit=` | clinician | history in time order (late readings included); `limit` 1–1000, default 120 | 200 | 401 · 403 · 404 | R6 R5 |
| `GET /patients/{id}/alerts` | clinician | alert history for a patient | 200 | 401 · 403 · 404 | R6 |
| `GET /patients/{id}/thresholds` | clinician | my limits for this patient | 200 | 401 · 403 · 404 | R10 |
| `PUT /patients/{id}/thresholds` | clinician | set / clear limits (`null` clears) | 200 | 401 · 403 · 404 · 422 | R10 |
| `GET /alerts[?clinician=ME]` | clinician | my alerts, with `escalated` flag | 200 | 401 · 403 | R4 |
| `POST /alerts/{id}/acknowledge` | clinician | acknowledge an alert | 200 | 401 · 403 · 404 | R4 |
| `GET /model/health` | clinician | serving model, its test recall for Critical, data drift per vital (PSI) | 200 | 401 | extra |
| `GET /health` | Docker | alive and model loaded? | 200 | 503 | R11 |

Dashboard pages (browser, cookie session + CSRF token): `/dashboard/login`, `/dashboard`,
`/dashboard/patients/{id}`, `/dashboard/patients/{id}/chart.png`.

## POST /readings

```json
{"reading_id": "P001-0042", "patient_id": "P001", "timestamp": "2026-01-01T08:42:00",
 "heart_rate": 72, "spo2": 97.5, "systolic": 121, "diastolic": 77, "temperature": 36.7, "glucose": 130}
```
`glucose` only for patients with diabetes. Any vital may be `null`/missing, but at least one must be present.
Allowed ranges: heart_rate 30–220, spo2 50–100, systolic 50–260, diastolic 30–150, temperature 30–43, glucose 20–600.
`timestamp` must be a string with a date **and** a time (ISO 8601). It is stored in one standard form,
`2026-01-01T08:42:00`: a time zone (`+01:00`, `Z`) is converted to UTC; a date on its own is a 422.

| Reply | When | Body |
|---|---|---|
| 201 | new reading stored | `{"outcome":"created","status":"Normal","alert":false,"alert_id":null,"suppressed":false,"late":false,"reasons":[]}` |
| 200 | same `reading_id` seen before | `{"outcome":"duplicate","reading_id":"P001-0042"}` |
| 422 | a rule is broken | `{"outcome":"invalid","problems":["heart_rate = 250 is outside 30 to 220"]}` |
| 404 | no such patient | `{"outcome":"unknown patient"}` |
| 401 | wrong / missing device key | `{"outcome":"unauthorised",...}` |
| 503 | no model loaded | `{"outcome":"no model loaded"}` |

Order of checks: shape (422) → patient exists (404) → already stored (200) → classify and store (201).

**Why a copy is 200, not 201:** nothing new was created; a retry must be safe (idempotency key = `reading_id`).
**Why a missing SpO2 is still 201:** refusing it would lose the other vitals (R9). The pipeline fills short gaps.
**Late readings** (measured more than 15 min before the newest stored reading) are stored and classified,
marked `late: true`, but do not page the clinician (the moment has passed). See `docs/assumptions.md` A9.

## Security notes
- 403 (not 404) for another clinician's patient follows the Week 8 contract; it reveals that the ID exists.
  Discuss that trade-off in your threat model.
- No password or key is in the code: `DEVICE_KEY`, `SECRET_KEY`, `DEMO_PASSWORD` come from `.env`
  (read by `src/config.py`; a real environment variable wins). Changing `DEMO_PASSWORD` takes effect at the next start.
- Run directly, the API listens on `127.0.0.1` only. The Docker image sets `HOST=0.0.0.0`.
