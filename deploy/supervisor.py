"""Always-on service for the Smart Vitals demo (macOS).

macOS (launchd, see install_macos.sh) starts THIS script when you log in and starts it
again if it ever stops. It runs from its own clone of the GitHub repository, outside the
iCloud-synced Desktop, so it does not depend on VS Code being open. It:

  1. starts the API + dashboard   (python -m app.main)
  2. starts the live sensor feed  (python -m simulator.run_simulator, LIVE=on)
  3. restarts either one if it stops, or if the API stops answering /health
  4. every UPDATE_EVERY seconds asks GitHub for new commits; if there are any it pulls
     them and restarts, so the website always runs the latest pushed code
  5. once a day deletes readings and alerts older than KEEP_DAYS and rotates big logs,
     so a feed that never stops cannot fill the disk

Nothing here is needed for the coursework itself: it only keeps the demo running.
"""
import os
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]           # the service's clone of the repository
HOME = REPO.parent                                    # ~/smart-vitals-service
LOGS = HOME / "logs"
PY = sys.executable                                   # the service's own virtual environment
PORT = int(os.environ.get("PORT", 8000))
UPDATE_EVERY = 300        # seconds between "anything new on GitHub?" checks
HEALTH_EVERY = 60         # seconds between /health checks
HEALTH_FAILS = 3          # restart the API after this many failed checks in a row
KEEP_DAYS = 7             # readings/alerts older than this are deleted
MAX_LOG = 20 * 1024 ** 2  # rotate a log bigger than 20 MB

children = {}             # name -> (Popen, open log file)


def log(msg: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}", flush=True)


def git(*args: str) -> str:
    out = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=120)
    if out.returncode:
        raise RuntimeError(out.stderr.strip() or f"git {args[0]} failed")
    return out.stdout.strip()


# ----------------------------------------------------------- child processes
def start(name: str) -> None:
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PORT": str(PORT)}
    if name == "simulator":
        env.update(LIVE="on", API_URL=f"http://127.0.0.1:{PORT}")
        cmd = [PY, "-m", "simulator.run_simulator"]
    else:
        cmd = [PY, "-m", "app.main"]
    out = open(LOGS / f"{name}.log", "a")
    children[name] = (subprocess.Popen(cmd, cwd=REPO, env=env, stdout=out, stderr=subprocess.STDOUT), out)
    log(f"started {name} (pid {children[name][0].pid})")


def stop(name: str) -> None:
    proc, out = children.pop(name, (None, None))
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    out.close()
    log(f"stopped {name}")


def stop_all() -> None:
    for name in ("simulator", "api"):  # the feed first, so nothing is sent to a closing API
        stop(name)


def api_healthy() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def start_all() -> None:
    start("api")
    for _ in range(60):  # loading the model takes a few seconds
        if api_healthy():
            break
        time.sleep(1)
    start("simulator")   # if the API is still not up, the simulator's edge buffer waits for it


# ------------------------------------------------------------------ updates
def check_for_update() -> None:
    """Pull new commits from GitHub. Returns normally; exits if the supervisor itself changed."""
    try:
        git("fetch", "--quiet", "origin", "main")
        old, new = git("rev-parse", "HEAD"), git("rev-parse", "origin/main")
        if old == new:
            return
        changed = git("diff", "--name-only", old, new).splitlines()
        git("merge", "--ff-only", "--quiet", "origin/main")
    except Exception as err:  # offline, or GitHub unreachable: try again next time
        log(f"update check skipped: {err}")
        return
    log(f"updated {old[:7]} -> {new[:7]} ({len(changed)} files changed)")
    stop_all()
    if any(Path(f).name == "requirements.txt" for f in changed):
        log("requirements changed: installing")
        subprocess.run([PY, "-m", "pip", "install", "--quiet", "-r", str(REPO / "requirements.txt")],
                       cwd=REPO, stdout=sys.stdout, stderr=subprocess.STDOUT)
    if any(f.startswith("deploy/") for f in changed):
        log("the service itself changed: exiting so macOS restarts the new version")
        sys.exit(0)
    start_all()


# -------------------------------------------------------------- maintenance
def maintenance() -> None:
    """Delete data older than KEEP_DAYS and rotate large logs (the feed adds ~29,000 readings a day)."""
    sys.path.insert(0, str(REPO))
    from src import config  # reads the service's .env, so DB_PATH is the one the API uses
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).replace(tzinfo=None)
    cutoff = cutoff.isoformat(timespec="seconds")
    if Path(config.DB_PATH).exists():
        conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
        with conn:
            r = conn.execute("DELETE FROM readings WHERE ts < ?", (cutoff,)).rowcount
            a = conn.execute("DELETE FROM alerts WHERE last_ts < ?", (cutoff,)).rowcount
        conn.close()
        log(f"maintenance: removed {r} readings and {a} alerts older than {KEEP_DAYS} days")
    big = [n for n in ("api", "simulator") if (LOGS / f"{n}.log").exists()
           and (LOGS / f"{n}.log").stat().st_size > MAX_LOG]
    if big:
        stop_all()
        for n in big:
            (LOGS / f"{n}.log").replace(LOGS / f"{n}.log.1")  # keep one old copy
        start_all()
        log(f"rotated logs: {', '.join(big)}")


# --------------------------------------------------------------------- main
def main() -> None:
    LOGS.mkdir(exist_ok=True)
    signal.signal(signal.SIGTERM, lambda *_: (stop_all(), sys.exit(0)))  # launchctl stop / log out
    log(f"Smart Vitals service starting from {REPO} on http://127.0.0.1:{PORT}")
    start_all()
    last_update = last_health = time.monotonic()
    last_maintenance, fails = 0.0, 0
    while True:
        time.sleep(5)
        now = time.monotonic()
        for name in ("api", "simulator"):
            proc = children.get(name, (None,))[0]
            if proc is not None and proc.poll() is not None:
                log(f"{name} stopped (exit {proc.returncode}): restarting")
                stop(name)
                time.sleep(2)
                start(name)
        if now - last_health >= HEALTH_EVERY:
            last_health = now
            fails = 0 if api_healthy() else fails + 1
            if fails >= HEALTH_FAILS:
                log("API not answering /health: restarting it")
                stop("api")
                start("api")
                fails = 0
        if now - last_update >= UPDATE_EVERY:
            last_update = now
            check_for_update()
        if now - last_maintenance >= 24 * 3600 or last_maintenance == 0:
            last_maintenance = now
            try:
                maintenance()
            except Exception as err:
                log(f"maintenance failed: {err}")


if __name__ == "__main__":
    main()
