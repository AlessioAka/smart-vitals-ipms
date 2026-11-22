"""SQLite storage: patients, readings, alerts, thresholds (R5, R6).

SQLite is in Python's standard library, so there is nothing extra to install,
and the file lives in a Docker volume so history survives a restart (Week 8).
The API keeps NO readings in memory (stateless, Week 7), so every copy of the
API sees the same history.
"""
import json
import sqlite3

from flask import current_app, g

from werkzeug.security import check_password_hash, generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS clinicians (
    clinician_id TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    clinician_id TEXT NOT NULL REFERENCES clinicians(clinician_id),
    age INTEGER, conditions TEXT, risk_group TEXT, has_diabetes INTEGER
);
CREATE TABLE IF NOT EXISTS thresholds (
    patient_id TEXT PRIMARY KEY REFERENCES patients(patient_id),
    values_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS readings (
    reading_id TEXT PRIMARY KEY,           -- UNIQUE: the safety net for resent copies
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    ts TEXT NOT NULL,
    heart_rate REAL, spo2 REAL, systolic REAL, diastolic REAL, temperature REAL, glucose REAL,
    status TEXT NOT NULL,
    reasons TEXT,
    late INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_readings_patient_ts ON readings(patient_id, ts);
CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    clinician_id TEXT NOT NULL,
    reading_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    last_ts TEXT NOT NULL,
    status TEXT NOT NULL,
    vitals TEXT NOT NULL,
    reasons TEXT,
    repeat_count INTEGER NOT NULL DEFAULT 1,
    acknowledged INTEGER NOT NULL DEFAULT 0
);
"""

VITAL_COLUMNS = ["heart_rate", "spo2", "systolic", "diastolic", "temperature", "glucose"]


def connect(path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_conn() -> sqlite3.Connection:
    """One database connection per request (closed in app.main's teardown)."""
    if "conn" not in g:
        g.conn = connect(current_app.config["DB_PATH"])
    return g.conn


def init_db(conn: sqlite3.Connection, patients: list, demo_password: str) -> None:
    # Every query in this file uses "?" placeholders, never string formatting: values are sent
    # separately from the SQL, which makes SQL injection impossible.
    """Create tables and load the patient register. Passwords are stored HASHED."""
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM clinicians").fetchone()[0] == 0:
        pw_hash = generate_password_hash(demo_password, method="pbkdf2:sha256")
        for cid in sorted({p["clinician_id"] for p in patients}):
            conn.execute("INSERT INTO clinicians VALUES (?, ?)", (cid, pw_hash))
        for p in patients:
            conn.execute(
                "INSERT INTO patients VALUES (?,?,?,?,?,?)",
                (p["patient_id"], p["clinician_id"], p["age"], json.dumps(p["conditions"]),
                 p["risk_group"], int(p["has_diabetes"])),
            )
        conn.commit()
    else:
        # The database already exists. If DEMO_PASSWORD was changed since it was made,
        # store the new hash - otherwise the old password would silently keep working
        # and the one in .env would not.
        row = conn.execute("SELECT password_hash FROM clinicians LIMIT 1").fetchone()
        if not check_password_hash(row["password_hash"], demo_password):
            conn.execute("UPDATE clinicians SET password_hash = ?",
                         (generate_password_hash(demo_password, method="pbkdf2:sha256"),))
            conn.commit()


# ---------------------------------------------------------------- patients
def get_patient(conn, patient_id):
    return conn.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()


def patients_of(conn, clinician_id):
    return conn.execute("SELECT * FROM patients WHERE clinician_id = ? ORDER BY patient_id",
                        (clinician_id,)).fetchall()


def get_thresholds(conn, patient_id) -> dict:
    row = conn.execute("SELECT values_json FROM thresholds WHERE patient_id = ?", (patient_id,)).fetchone()
    return json.loads(row["values_json"]) if row else {}


def set_thresholds(conn, patient_id, values: dict) -> dict:
    merged = {**get_thresholds(conn, patient_id), **values}
    merged = {k: v for k, v in merged.items() if v is not None}
    conn.execute("INSERT OR REPLACE INTO thresholds VALUES (?, ?)", (patient_id, json.dumps(merged)))
    conn.commit()
    return merged


# ---------------------------------------------------------------- readings
def already_stored(conn, reading_id: str) -> bool:
    """Idempotency (Week 8): have we seen this reading_id before?"""
    return conn.execute("SELECT 1 FROM readings WHERE reading_id = ?", (reading_id,)).fetchone() is not None


def latest_ts(conn, patient_id):
    row = conn.execute("SELECT MAX(ts) AS t FROM readings WHERE patient_id = ?", (patient_id,)).fetchone()
    return row["t"]


def last_reading(conn, patient_id: str):
    """The patient's newest reading (by measurement time), or None."""
    row = conn.execute("SELECT * FROM readings WHERE patient_id = ? ORDER BY ts DESC LIMIT 1",
                       (patient_id,)).fetchone()
    return dict(row) if row else None


def recent_all(conn, n: int) -> list:
    """The newest n readings from ALL patients (vitals only): input for drift monitoring."""
    rows = conn.execute("SELECT heart_rate, spo2, systolic, diastolic, temperature, glucose "
                        "FROM readings ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
    return [dict(r) for r in rows]


def newest_ts(conn):
    """The newest reading from ANY patient: the system's "now" on the simulated clock."""
    return conn.execute("SELECT MAX(ts) AS t FROM readings").fetchone()["t"]


def recent_readings(conn, patient_id: str, before_ts: str, n: int) -> list:
    """The last n readings measured before `before_ts`, oldest first."""
    rows = conn.execute(
        "SELECT * FROM readings WHERE patient_id = ? AND ts < ? ORDER BY ts DESC LIMIT ?",
        (patient_id, before_ts, n)).fetchall()
    return [dict(r) for r in reversed(rows)]


def store_reading(conn, reading: dict, status: str, reasons: list, late: bool) -> None:
    conn.execute(
        "INSERT INTO readings (reading_id, patient_id, ts, heart_rate, spo2, systolic, diastolic, "
        "temperature, glucose, status, reasons, late) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (reading["reading_id"], reading["patient_id"], reading["timestamp"],
         *[reading.get(v) for v in VITAL_COLUMNS], status, json.dumps(reasons), int(late)))


def history(conn, patient_id: str, limit: int = 120) -> list:
    rows = conn.execute(
        "SELECT * FROM (SELECT * FROM readings WHERE patient_id = ? ORDER BY ts DESC LIMIT ?) ORDER BY ts",
        (patient_id, limit)).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ alerts
def open_alert(conn, patient_id: str):
    """The patient's newest alert that nobody has acknowledged yet."""
    return conn.execute(
        "SELECT * FROM alerts WHERE patient_id = ? AND acknowledged = 0 ORDER BY ts DESC LIMIT 1",
        (patient_id,)).fetchone()


def add_alert(conn, alert: dict) -> int:
    cur = conn.execute(
        "INSERT INTO alerts (patient_id, clinician_id, reading_id, ts, last_ts, status, vitals, reasons) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (alert["patient_id"], alert["clinician_id"], alert["reading_id"], alert["timestamp"],
         alert["timestamp"], alert["status"], json.dumps(alert["vitals"]), json.dumps(alert["reasons"])))
    return cur.lastrowid


def bump_alert(conn, alert_id: int, ts: str) -> None:
    conn.execute("UPDATE alerts SET repeat_count = repeat_count + 1, last_ts = MAX(last_ts, ?) "
                 "WHERE alert_id = ?", (ts, alert_id))


def alerts_for_patient(conn, patient_id: str) -> list:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM alerts WHERE patient_id = ? ORDER BY ts DESC", (patient_id,)).fetchall()]


def alerts_for_clinician(conn, clinician_id: str) -> list:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM alerts WHERE clinician_id = ? ORDER BY ts DESC", (clinician_id,)).fetchall()]


def get_alert(conn, alert_id: int):
    return conn.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()


def acknowledge(conn, alert_id: int) -> None:
    conn.execute("UPDATE alerts SET acknowledged = 1 WHERE alert_id = ?", (alert_id,))
    conn.commit()
