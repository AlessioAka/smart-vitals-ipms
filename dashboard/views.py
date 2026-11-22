"""The clinician dashboard (R5, R8, R10): server-rendered pages.

A clinician sees ONLY their own patients. Every patient page checks this again
on the server (the "object-level" check, OWASP API1) - hiding a link is not security.

Pages
  /dashboard/login                    log in (CSRF-protected form)
  /dashboard                          my patients, KPI tiles, latest alerts, model health
  /dashboard/patients/<id>            one patient: latest vitals, trend chart, thresholds, alerts, readings
  /dashboard/patients/<id>/chart.png  the trend chart itself (R8)
"""
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from flask import (Blueprint, Response, abort, current_app, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)

from jinja2 import Undefined

from app import alerts as A, auth, db, validation
from app.db import get_conn
from dashboard.charts import patient_chart
from src import config, drift, rules

bp = Blueprint("dashboard", __name__)

CHART_WINDOWS = {60: "1 hour", 180: "3 hours", 360: "6 hours"}  # minutes
STATUS_ORDER = {"Critical": 0, "Warning": 1, "Normal": 2, "No data": 3}


def in_window(readings: list, minutes: int) -> list:
    """Keep only readings from the last `minutes` before the newest one (oldest first in, oldest first out).

    The database query fetches at most one reading per minute of the window; this cut makes
    "3 hours" mean three hours of time even when the sensor (or the computer) was off for a while.
    """
    if not readings:
        return []
    start = (datetime.fromisoformat(readings[-1]["ts"]) - timedelta(minutes=minutes)).isoformat()
    return [r for r in readings if r["ts"] >= start]


# ------------------------------------------------------------------ CSRF
@bp.app_context_processor
def csrf_token():
    """Give every form a secret token (stops other websites posting forms for the clinician)."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return {"csrf": session["csrf"]}


@bp.before_request
def check_csrf():
    """Every dashboard POST must carry the token from this session, or it is refused (400)."""
    if request.method == "POST":
        sent = request.form.get("csrf", "")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400)


@bp.app_template_filter("vital")
def format_vital(value, vital: str) -> str:
    """Show a vital the way a clinician reads it: whole numbers for pulse, pressure and glucose,
    one decimal for SpO2 and temperature, and a dash (not 0) when the value is missing."""
    if value is None or isinstance(value, Undefined):
        return "–"
    if vital in ("heart_rate", "systolic", "diastolic", "glucose"):
        return str(int(round(value)))
    return f"{value:.1f}"


# ---------------------------------------------------------------- errors
@bp.app_errorhandler(400)
@bp.app_errorhandler(403)
@bp.app_errorhandler(404)
def error_page(err):
    """Dashboard users get a readable page; API callers keep getting JSON."""
    if not request.path.startswith("/dashboard"):
        return jsonify({"outcome": err.name.lower()}), err.code
    messages = {
        400: "The form had expired or was not sent from this site. Go back, reload the page and try again.",
        403: "This patient is not assigned to you. Clinicians can only open their own patients.",
        404: "There is no such page or patient.",
    }
    return render_template("error.html", code=err.code, title=err.name,
                           message=messages.get(err.code, err.description)), err.code


# --------------------------------------------------------------- helpers
def _minutes_between(later: str, earlier: str) -> int:
    return int((datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).total_seconds() // 60)


def _my_patient_or_abort(patient_id):
    """404 if the patient does not exist, 403 if it belongs to another clinician (R5)."""
    patient = db.get_patient(get_conn(), patient_id)
    if patient is None:
        abort(404)
    if patient["clinician_id"] != g.clinician_id:
        abort(403)
    return patient


def _signal(last_ts, now):
    """(minutes since the patient's last reading, signal lost?) on the simulated clock (A13)."""
    if not last_ts or not now:
        return None, False
    gap = _minutes_between(now, last_ts)
    return gap, gap > config.SIGNAL_LOST_MINUTES


def _prepare_alerts(alerts: list, now) -> list:
    """Decode the JSON columns and work out which open alerts are escalated (A10)."""
    for a in alerts:
        a["vitals"] = json.loads(a["vitals"]) if isinstance(a["vitals"], str) else a["vitals"]
        a["reasons"] = json.loads(a["reasons"] or "[]")
        a["escalated"] = A.is_escalated(a, now)
    return alerts


def model_health(conn) -> dict:
    """What the clinician should know about the model: which one, how good, and is the data drifting?"""
    meta_path = Path(current_app.config["MODEL_PATH"]).with_suffix(".json")  # written by src/model.py
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    reference = current_app.config.get("DRIFT_REFERENCE") or {}
    report = drift.drift_report(reference, db.recent_all(conn, config.DRIFT_WINDOW)) if reference else {}
    worst = max((r["psi"] for r in report.values() if r["psi"] is not None), default=None)
    return {
        "name": meta.get("name", "unknown"),
        "recall_critical": meta.get("test_metrics", {}).get("recall_critical"),
        "accuracy": meta.get("test_metrics", {}).get("accuracy"),
        "drift": report,
        "drift_verdict": drift.verdict(worst) if report else "no reference",
        "units": config.UNITS,
    }


def _safe_next(default: str) -> str:
    """Only redirect back to our own dashboard pages (never to another website: open-redirect risk)."""
    target = request.form.get("next", "")
    return target if target.startswith("/dashboard") and not target.startswith("//") else default


# ------------------------------------------------------------------ pages
@bp.get("/")
def index():
    return redirect(url_for("dashboard.overview" if session.get("clinician_id") else "dashboard.login"))


@bp.route("/dashboard/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        cid = request.form.get("clinician_id", "").strip()
        if auth.check_login(get_conn(), cid, request.form.get("password", "")):
            keep = session.get("csrf")
            session.clear()          # a fresh session on log-in (stops session fixation)
            session["csrf"] = keep
            session["clinician_id"] = cid
            return redirect(url_for("dashboard.overview"))
        flash("Wrong clinician ID or password.", "error")  # same message either way (no ID guessing)
    return render_template("login.html")


@bp.post("/dashboard/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "ok")
    return redirect(url_for("dashboard.login"))


@bp.get("/dashboard")
@auth.clinician_page
def overview():
    conn = get_conn()
    now = db.newest_ts(conn)  # the simulated "now": newest reading in the whole system
    rows = []
    for p in db.patients_of(conn, g.clinician_id):
        last = db.last_reading(conn, p["patient_id"])
        gap, lost = _signal(last["ts"] if last else None, now)
        rows.append({
            "patient_id": p["patient_id"], "risk_group": p["risk_group"], "age": p["age"],
            "conditions": ", ".join(json.loads(p["conditions"])) or "none",
            "has_diabetes": bool(p["has_diabetes"]),
            "status": last["status"] if last else "No data",
            "last": last, "last_seen": last["ts"][11:16] if last else "-",
            "signal_lost": lost, "gap": gap,
            "open_alert": db.open_alert(conn, p["patient_id"]) is not None,
        })
    # Most urgent first: Critical, then Warning, then Normal (a clinician finds a Critical patient at once).
    rows.sort(key=lambda r: (STATUS_ORDER[r["status"]], r["patient_id"]))
    alerts = _prepare_alerts(db.alerts_for_clinician(conn, g.clinician_id), now)
    open_alerts = [a for a in alerts if not a["acknowledged"]]
    kpis = {
        "patients": len(rows),
        "critical": sum(r["status"] == "Critical" for r in rows),
        "warning": sum(r["status"] == "Warning" for r in rows),
        "open_alerts": len(open_alerts),
        "escalated": sum(a["escalated"] for a in open_alerts),
        "signal_lost": sum(r["signal_lost"] for r in rows),
    }
    return render_template("overview.html", rows=rows, alerts=alerts[:15], kpis=kpis,
                           clinician=g.clinician_id, now=now, health=model_health(conn))


@bp.get("/dashboard/patients/<patient_id>")
@auth.clinician_page
def patient_page(patient_id):
    patient = _my_patient_or_abort(patient_id)
    conn = get_conn()
    now = db.newest_ts(conn)
    readings = db.history(conn, patient_id, 40)[::-1]  # newest first for the table
    for r in readings:
        r["reasons"] = json.loads(r["reasons"] or "[]")
    latest = readings[0] if readings else None
    gap, lost = _signal(latest["ts"] if latest else None, now)
    window = request.args.get("window", 180, type=int)
    window = window if window in CHART_WINDOWS else 180
    return render_template(
        "patient.html", patient=patient, conditions=json.loads(patient["conditions"]),
        readings=readings, latest=latest,
        # Points per vital for the newest reading: which vitals are pushing the score up ("explain").
        points=rules.points_for(latest) if latest else {},
        gap=gap, signal_lost=lost, now=now,
        alerts=_prepare_alerts(db.alerts_for_patient(conn, patient_id), now),
        thresholds=db.get_thresholds(conn, patient_id),
        fields=list(validation.THRESHOLD_FIELDS), units=config.UNITS,
        window=window, windows=CHART_WINDOWS)


@bp.get("/dashboard/patients/<patient_id>/chart.png")
@auth.clinician_page
def chart(patient_id):
    patient = _my_patient_or_abort(patient_id)
    conn = get_conn()
    window = request.args.get("window", 180, type=int)
    window = window if window in CHART_WINDOWS else 180
    png = patient_chart(in_window(db.history(conn, patient_id, window), window),
                        db.get_thresholds(conn, patient_id), bool(patient["has_diabetes"]))
    return Response(png, mimetype="image/png", headers={"Cache-Control": "no-store"})


@bp.post("/dashboard/patients/<patient_id>/thresholds")
@auth.clinician_page
def save_thresholds(patient_id):
    """R10: the form sends every threshold field; blank means "no limit"."""
    _my_patient_or_abort(patient_id)
    body = {}
    for field in validation.THRESHOLD_FIELDS:
        raw = request.form.get(field, "").strip()
        if raw == "":
            body[field] = None  # blank clears the limit
        else:
            try:
                body[field] = float(raw)
            except ValueError:
                body[field] = raw  # validation will say "must be a number"
    problems = validation.threshold_problems(body)
    if problems:
        for p in problems:
            flash(p.replace("_", " "), "error")
    else:
        db.set_thresholds(get_conn(), patient_id, body)
        flash("Thresholds saved. They apply to the next reading.", "ok")
    return redirect(url_for("dashboard.patient_page", patient_id=patient_id) + "#thresholds")


@bp.post("/dashboard/alerts/<int:alert_id>/acknowledge")
@auth.clinician_page
def ack(alert_id):
    row = db.get_alert(get_conn(), alert_id)
    if row is None:
        abort(404)
    if row["clinician_id"] != g.clinician_id:
        abort(403)
    db.acknowledge(get_conn(), alert_id)
    flash(f"Alert for {row['patient_id']} acknowledged.", "ok")
    return redirect(_safe_next(url_for("dashboard.overview")))
