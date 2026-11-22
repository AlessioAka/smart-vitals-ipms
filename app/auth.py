"""Who is calling? (R5)

Two kinds of caller:
  * a DEVICE (the simulator / phone) sends a shared key in the X-Device-Key header,
  * a CLINICIAN logs in with an ID and password and gets a signed, expiring token
    (Authorization: Bearer ...) or a signed session cookie for the dashboard.

Passwords are stored hashed (db.py). The key and secret come from the environment
(.env), never from the code.
"""
import hmac
from functools import wraps

from flask import current_app, g, jsonify, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash

from app import db

TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60  # one shift


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="clinician-token")


def issue_token(clinician_id: str) -> str:
    """A token signed with SECRET_KEY: anyone can read it, nobody can forge or change it,
    and it stops working after TOKEN_MAX_AGE_SECONDS."""
    return _serializer().dumps({"clinician_id": clinician_id})


def check_login(conn, clinician_id: str, password: str) -> bool:
    row = conn.execute("SELECT password_hash FROM clinicians WHERE clinician_id = ?",
                       (clinician_id,)).fetchone()
    # Same answer whether the ID or the password was wrong, so an attacker cannot learn which IDs exist.
    # check_password_hash re-hashes the attempt (PBKDF2) and compares: the password itself is never stored.
    return bool(row) and check_password_hash(row["password_hash"], password)


def _clinician_from_request():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        try:
            return _serializer().loads(header[7:], max_age=TOKEN_MAX_AGE_SECONDS)["clinician_id"]
        except (BadSignature, SignatureExpired):
            return None
    return session.get("clinician_id")


def clinician_required(view):
    """API routes: 401 JSON if not logged in."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        cid = _clinician_from_request()
        if not cid:
            return jsonify({"outcome": "unauthorised", "message": "log in first"}), 401
        g.clinician_id = cid
        return view(*args, **kwargs)
    return wrapper


def clinician_page(view):
    """Dashboard pages: redirect to the login page if not logged in."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        cid = session.get("clinician_id")
        if not cid:
            return redirect(url_for("dashboard.login"))
        g.clinician_id = cid
        return view(*args, **kwargs)
    return wrapper


def device_key_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        sent = request.headers.get("X-Device-Key", "")
        # compare_digest takes the same time whether the first or the last character differs,
        # so the key cannot be guessed one character at a time by timing the answers.
        if not hmac.compare_digest(sent.encode(), current_app.config["DEVICE_KEY"].encode()):
            return jsonify({"outcome": "unauthorised", "message": "bad or missing device key"}), 401
        return view(*args, **kwargs)
    return wrapper
