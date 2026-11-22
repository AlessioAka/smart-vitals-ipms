"""The EDGE part of the edge/cloud split (R11, Weeks 4 and 6).

The edge is the phone / wearable gateway. It has little battery and a flaky
network, so it only does what is cheap and urgent:

  1. range check  - impossible values are blanked before they travel (saves a 422),
  2. early warning - a tiny rule that still warns the wearer when the cloud is
                     unreachable (extra feature, "edge early warning"),
  3. buffering    - readings wait in a queue while the network is down.

The cloud does what needs history, memory and the trained model: classifying,
storing history, alerting the clinician. Pure Python on purpose.
"""
from collections import deque

from src import config

# Very simple "call for help" limits for the wearer's phone. NOT the clinical model.
EARLY_WARNING = {"spo2_below": 88, "heart_rate_above": 150, "heart_rate_below": 38,
                 "temperature_above": 40.0}


def range_check(reading: dict) -> tuple:
    """Return (cleaned_reading, list_of_blanked_vitals)."""
    clean, blanked = dict(reading), []
    for vital, (low, high) in config.RANGES.items():
        value = clean.get(vital)
        if value is not None and not low <= value <= high:
            clean[vital] = None
            blanked.append(vital)
    return clean, blanked


def early_warning(reading: dict) -> list:
    """Local warnings that need no network and no model."""
    out = []
    if reading.get("spo2") is not None and reading["spo2"] < EARLY_WARNING["spo2_below"]:
        out.append(f"SpO2 {reading['spo2']}% is very low")
    hr = reading.get("heart_rate")
    if hr is not None and hr > EARLY_WARNING["heart_rate_above"]:
        out.append(f"heart rate {hr} is very high")
    if hr is not None and hr < EARLY_WARNING["heart_rate_below"]:
        out.append(f"heart rate {hr} is very low")
    if reading.get("temperature") is not None and reading["temperature"] > EARLY_WARNING["temperature_above"]:
        out.append(f"temperature {reading['temperature']} is very high")
    return out


class EdgeBuffer:
    """A bounded queue: oldest readings are dropped first if the phone runs out of room."""

    def __init__(self, max_items: int = 500):
        self.queue = deque(maxlen=max_items)

    def add(self, reading: dict) -> None:
        self.queue.append(reading)

    def __len__(self) -> int:
        return len(self.queue)

    def pop_oldest(self):
        return self.queue.popleft() if self.queue else None
