"""Settings shared by the simulator, the model and the API.

Settings come from environment variables (Week 8: "same image, different
places"), with safe defaults so everything also runs straight from VS Code.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path: Path = ROOT / ".env") -> None:
    """Read KEY=VALUE lines from .env into the environment (if the file exists).

    A real environment variable always wins, so Docker and VS Code settings are
    never overridden. Without this, `python -m app.main` in a terminal ignored
    .env while VS Code's Run and Debug used it, and the API and the simulator
    could end up with different device keys (every reading refused with 401).
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env_file()


def _path(env_name: str, default: str) -> Path:
    """Read a file path from the environment, or fall back to a repo path."""
    return Path(os.environ.get(env_name, ROOT / default))


MODEL_PATH = _path("MODEL_PATH", "models/smart_vitals_model.joblib")
PATIENTS_PATH = _path("PATIENTS_PATH", "data/patients.json")
DATA_PATH = _path("DATA_PATH", "data/simulated_readings.csv")
DB_PATH = _path("DB_PATH", "data/smart_vitals.db")
DRIFT_REFERENCE_PATH = _path("DRIFT_REFERENCE_PATH", "models/drift_reference.json")
RESULTS_DIR = ROOT / "docs" / "results"

RANDOM_STATE = 42

# The five vital signs in the brief (blood pressure is two numbers).
VITALS = ["heart_rate", "spo2", "systolic", "diastolic", "temperature", "glucose"]

# Physically possible values. Anything outside is a glitch (Week 4: range check).
RANGES = {
    "heart_rate": (30, 220),
    "spo2": (50, 100),
    "systolic": (50, 260),
    "diastolic": (30, 150),
    "temperature": (30.0, 43.0),
    "glucose": (20, 600),
}
UNITS = {
    "heart_rate": "bpm",
    "spo2": "%",
    "systolic": "mmHg",
    "diastolic": "mmHg",
    "temperature": "°C",
    "glucose": "mg/dL",
}

LABELS = ["Normal", "Warning", "Critical"]  # R3

# Pipeline settings (Weeks 4 and 5)
FILL_LIMIT = 2          # forward-fill gaps of at most 2 minutes
STUCK_WINDOW = 6        # std of 0 over 6 readings = stuck sensor
STUCK_COLUMNS = ["heart_rate", "spo2", "systolic"]  # not temperature: it is normally flat at 0.1 °C resolution
ROLL_WINDOW = 5         # 5-minute rolling features
HISTORY_WINDOW = 12     # readings the API loads from the database

# Alert behaviour
STALE_MINUTES = 15      # a reading older than this (vs newest stored) is "late"
ALERT_COOLDOWN_MINUTES = 10   # one alert per episode (alarm-fatigue control)
ESCALATE_AFTER_MINUTES = 15   # unacknowledged alert is escalated
SIGNAL_LOST_MINUTES = 10      # dashboard shows "signal lost" after this gap
DRIFT_WINDOW = 1000           # drift monitoring compares the newest N stored readings with training

# Simulated clock: the whole project runs in simulated time.
SIM_START = "2026-01-01T08:00:00"
