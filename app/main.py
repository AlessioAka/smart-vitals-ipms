"""The Smart Vitals API (Week 8). Run:  python -m app.main

Contract (see docs/api.md):
  POST /readings                    device key   201 new | 200 copy | 404 | 422
  POST /login                       -            200 token | 401
  GET  /patients                    clinician    only MY patients
  GET  /patients/<id>/readings      clinician    200 | 403 | 404
  GET  /patients/<id>/alerts        clinician    200 | 403 | 404
  GET  /patients/<id>/thresholds    clinician    200 | 403 | 404
  PUT  /patients/<id>/thresholds    clinician    200 | 403 | 404 | 422
  GET  /alerts                      clinician    my alerts (?clinician=ME only)
  POST /alerts/<id>/acknowledge     clinician    200 | 403 | 404
  GET  /model/health                clinician    model name, test metrics, drift per vital
  GET  /health                      -            200 | 503
Plus the dashboard pages (dashboard/views.py).
"""
import json
import logging
import os
import sqlite3

from flask import Flask, g, jsonify, request

from app import alerts as A, auth, db, validation
from app.db import get_conn
from app.classify import classify
from src import config, drift, model as M, rules

log = logging.getLogger("smart_vitals")


def default_config() -> dict:
    """Settings come from the environment (.env locally, env_file in Docker), never from the code."""
    return {
        "DB_PATH": str(config.DB_PATH),
        "MODEL_PATH": str(config.MODEL_PATH),
        "PATIENTS_PATH": str(config.PATIENTS_PATH),
        "DRIFT_REFERENCE_PATH": str(config.DRIFT_REFERENCE_PATH),
        "DEVICE_KEY": os.environ.get("DEVICE_KEY", "dev-device-key"),
        "SECRET_KEY": os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        "DEMO_PASSWORD": os.environ.get("DEMO_PASSWORD", "demo-only-change-me"),
    }


def create_app(overrides: dict | None = None) -> Flask:
    """App factory: tests build an app with a temporary database and their own model."""
    app = Flask(__name__, template_folder=str(config.ROOT / "dashboard" / "templates"),
                static_folder=None)
    app.config.update(default_config())
    app.config.update(overrides or {})
    # Session cookie: not readable by page scripts (HttpOnly), not sent by other sites' forms (SameSite).
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

    # Load the model ONCE at start-up, not on every request (Week 8 design C vs D:
    # notebook 03 measures loading per request as about 3x slower).
    app.config["MODEL"] = app.config.get("MODEL")
    if app.config["MODEL"] is None:
        try:
            app.config["MODEL"] = M.load_model(app.config["MODEL_PATH"])
        except FileNotFoundError:
            log.error("model file not found: %s", app.config["MODEL_PATH"])  # /health then says 503
    # What the training data looked like, for drift monitoring (extra feature; src/drift.py).
    if "DRIFT_REFERENCE" not in app.config:
        from pathlib import Path
        app.config["DRIFT_REFERENCE"] = drift.load_reference(Path(app.config["DRIFT_REFERENCE_PATH"]))

    # Create the tables and load the patient register on first start (R1, R5).
    with open(app.config["PATIENTS_PATH"], encoding="utf-8") as f:
        patients = json.load(f)
    conn = db.connect(app.config["DB_PATH"])
    db.init_db(conn, patients, app.config["DEMO_PASSWORD"])
    conn.close()

    @app.teardown_appcontext
    def close_conn(_exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    # ------------------------------------------------------------- helpers
    def own_patient(patient_id):
        """(patient, error_response). 404 if it does not exist, 403 if it is not mine (R5).

        This is the object-level check (OWASP API1: broken object-level authorisation):
        being logged in is not enough, the patient must be assigned to THIS clinician.
        """
        patient = db.get_patient(get_conn(), patient_id)
        if patient is None:
            return None, (jsonify({"outcome": "unknown patient"}), 404)
        if patient["clinician_id"] != g.clinician_id:
            return None, (jsonify({"outcome": "forbidden", "message": "not your patient"}), 403)
        return patient, None

    # ------------------------------------------------------------- health
    @app.get("/health")
    def health():
        """Docker's health check: 200 only when the model is loaded (docker-compose waits for it)."""
        if app.config["MODEL"] is None:
            return jsonify({"status": "no model loaded"}), 503
        return jsonify({"status": "ok"}), 200

    # ----------------------------------------------------------- ingest
    @app.post("/readings")
    @auth.device_key_required
    def post_reading():
        """One reading from a device. The heart of the system (R2, R3, R4, R6, R9, R10)."""
        # 1. VALIDATE the shape. Anything broken is the caller's fault: 422 with every problem listed.
        payload = request.get_json(silent=True)
        problems = validation.problems_in(payload)
        if problems:
            return jsonify({"outcome": "invalid", "problems": problems}), validation.status_code("invalid")

        # From here on the timestamp is always in one standard form (see validation.clean_timestamp).
        payload = {**payload, "timestamp": validation.clean_timestamp(payload["timestamp"])}

        # 2. KNOWN PATIENT? 404 if not.
        conn = get_conn()
        patient = db.get_patient(conn, payload["patient_id"])
        if patient is None:
            return jsonify({"outcome": "unknown patient"}), validation.status_code("unknown patient")
        # 3. RESENT COPY? (idempotency, Week 7/8) The same reading_id again is a success (200),
        #    but nothing new is stored and no second alert is raised (R9).
        if db.already_stored(conn, payload["reading_id"]):
            return jsonify({"outcome": "duplicate", "reading_id": payload["reading_id"]}), \
                validation.status_code("duplicate")
        if app.config["MODEL"] is None:
            return jsonify({"outcome": "no model loaded"}), 503

        # 4. LATE? Measured long before the newest reading we hold: store it, but do not page anyone (A9).
        ts = payload["timestamp"]
        late = A.is_late(ts, db.latest_ts(conn, patient["patient_id"]))

        # 5. CLASSIFY with the trained model, using the patient's recent history for trend features (R3).
        history_rows = db.recent_readings(conn, patient["patient_id"], ts, config.HISTORY_WINDOW)
        status, vitals = classify(app.config["MODEL"], patient, history_rows, payload)

        # 6. THRESHOLDS: the clinician's own limits for this patient (R10; can only raise the status).
        status, breaches = A.apply_thresholds(status, vitals, db.get_thresholds(conn, patient["patient_id"]))
        reasons = rules.explain(vitals) + breaches   # "why": which vitals drove the status (extra feature)

        # 7. STORE the reading as it arrived (validated), never the cleaned copy (raw data is kept) (R6).
        try:
            db.store_reading(conn, payload, status, reasons, late)
        except sqlite3.IntegrityError:
            # Two copies arrived at the same moment and the other one was stored first.
            # The UNIQUE reading_id is the safety net: answer "duplicate", not a 500.
            conn.rollback()
            return jsonify({"outcome": "duplicate", "reading_id": payload["reading_id"]}), \
                validation.status_code("duplicate")

        # 8. ALERT the assigned clinician on Critical (R4), at most once per episode (alarm-fatigue control):
        #    a repeat Critical soon after an unacknowledged alert only raises that alert's repeat counter.
        alert_id, new_alert, suppressed = None, False, False
        if status == "Critical" and not late:
            open_alert = db.open_alert(conn, patient["patient_id"])
            if open_alert is not None and A.within_cooldown(ts, open_alert["last_ts"]):
                db.bump_alert(conn, open_alert["alert_id"], ts)
                alert_id, suppressed = open_alert["alert_id"], True
            else:
                alert = A.make_alert(patient, payload["reading_id"], ts, status, vitals, reasons)
                alert_id = db.add_alert(conn, alert)
                new_alert = True
                log.warning("ALERT to %s: patient %s %s at %s %s", alert["clinician_id"],
                            alert["patient_id"], alert["status"], ts, alert["vitals"])
        conn.commit()  # reading and alert are saved together, or not at all
        return jsonify({"outcome": "created", "status": status, "alert": new_alert,
                        "alert_id": alert_id, "suppressed": suppressed, "late": late,
                        "reasons": reasons}), validation.status_code("created")

    # -------------------------------------------------------------- login
    @app.post("/login")
    def login():
        """Clinician ID + password in, a signed token (valid one shift) out (R5)."""
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            body = {}
        cid, password = str(body.get("clinician_id", "")), str(body.get("password", ""))
        if not auth.check_login(get_conn(), cid, password):
            return jsonify({"outcome": "unauthorised", "message": "wrong ID or password"}), 401
        return jsonify({"outcome": "ok", "token": auth.issue_token(cid)}), 200

    # ----------------------------------------------------------- patients
    @app.get("/patients")
    @auth.clinician_required
    def my_patients():
        rows = db.patients_of(get_conn(), g.clinician_id)   # the SQL filters by the logged-in clinician
        return jsonify([{k: r[k] for k in ("patient_id", "age", "risk_group", "has_diabetes")}
                        | {"conditions": json.loads(r["conditions"])} for r in rows]), 200

    @app.get("/patients/<patient_id>/readings")
    @auth.clinician_required
    def patient_readings(patient_id):
        patient, error = own_patient(patient_id)
        if error:
            return error
        # Between 1 and 1000. (A negative LIMIT means "no limit" in SQLite, so it must be clamped.)
        limit = max(1, min(request.args.get("limit", default=120, type=int), 1000))
        return jsonify(db.history(get_conn(), patient["patient_id"], limit)), 200

    @app.get("/patients/<patient_id>/alerts")
    @auth.clinician_required
    def patient_alerts(patient_id):
        patient, error = own_patient(patient_id)
        if error:
            return error
        return jsonify(db.alerts_for_patient(get_conn(), patient["patient_id"])), 200

    @app.get("/patients/<patient_id>/thresholds")
    @auth.clinician_required
    def get_thresholds(patient_id):
        patient, error = own_patient(patient_id)
        if error:
            return error
        return jsonify(db.get_thresholds(get_conn(), patient["patient_id"])), 200

    @app.put("/patients/<patient_id>/thresholds")
    @auth.clinician_required
    def put_thresholds(patient_id):
        patient, error = own_patient(patient_id)
        if error:
            return error
        body = request.get_json(silent=True)
        problems = validation.threshold_problems(body)
        if problems:
            return jsonify({"outcome": "invalid", "problems": problems}), 422
        return jsonify(db.set_thresholds(get_conn(), patient["patient_id"], body)), 200

    # ------------------------------------------------------------- alerts
    @app.get("/alerts")
    @auth.clinician_required
    def my_alerts():
        asked = request.args.get("clinician")
        if asked and asked != g.clinician_id:
            return jsonify({"outcome": "forbidden", "message": "not your alerts"}), 403
        conn = get_conn()
        rows = db.alerts_for_clinician(conn, g.clinician_id)
        now = db.newest_ts(conn)
        for r in rows:
            r["escalated"] = A.is_escalated(r, now)
        return jsonify(rows), 200

    @app.post("/alerts/<int:alert_id>/acknowledge")
    @auth.clinician_required
    def acknowledge(alert_id):
        row = db.get_alert(get_conn(), alert_id)
        if row is None:
            return jsonify({"outcome": "unknown alert"}), 404
        if row["clinician_id"] != g.clinician_id:
            return jsonify({"outcome": "forbidden", "message": "not your alert"}), 403
        db.acknowledge(get_conn(), alert_id)
        return jsonify({"outcome": "acknowledged", "alert_id": alert_id}), 200

    # ------------------------------------------------------- model health
    @app.get("/model/health")
    @auth.clinician_required
    def model_health():
        """Which model is serving, how it scored on unseen patients, and whether live data drifts."""
        from dashboard.views import model_health as health_report
        report = health_report(get_conn())
        report.pop("units", None)
        return jsonify(report), 200

    # ---------------------------------------------------------- dashboard
    from dashboard.views import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Only this computer can reach the API unless HOST says otherwise (the Dockerfile sets
    # HOST=0.0.0.0, which a container needs so that its published port works).
    # load_dotenv=False: src/config.py has already read .env, so Flask need not look for python-dotenv.
    create_app().run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 8000)),
                     load_dotenv=False)
