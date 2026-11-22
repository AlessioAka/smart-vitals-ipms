"""Vital-sign trend charts for the clinician dashboard (R8).

Week 5 chart rules applied: units on every axis, a shared time axis, the
clinician's own limits drawn as dashed lines, Critical readings marked in red
AND labelled (never colour alone), light grid, and the y-axis uses a sensible range
(fixed display ranges, stretched if a reading falls outside).
"""
import io
from datetime import datetime

import matplotlib.dates as mdates
from matplotlib.figure import Figure

# Figure is used directly, NOT matplotlib.pyplot: pyplot keeps one shared "current figure",
# which is not safe when the web server draws two charts at once (one thread per request).

LINE = "#1f4e79"      # one hue for the data
LINE_2 = "#7aa6d1"    # lighter step of the same hue (diastolic)
LIMIT = "#8a6d00"     # dashed: clinician-set limit
CRITICAL = "#c0392b"  # reserved for Critical

# Fixed display ranges so a 1-point wobble does not look like a crisis (Week 5: honest charts).
# They stretch automatically if a reading falls outside.
DISPLAY_RANGE = {
    "heart_rate": (40, 140), "spo2": (85, 100), "bp": (40, 200),
    "temperature": (35.0, 40.0), "glucose": (40, 300),
}

PANELS = [
    ("heart_rate", "Heart rate (bpm)", ["heart_rate"]),
    ("spo2", "SpO2 (%)", ["spo2"]),
    ("bp", "Blood pressure (mmHg)", ["systolic", "diastolic"]),
    ("temperature", "Temperature (°C)", ["temperature"]),
    ("glucose", "Glucose (mg/dL)", ["glucose"]),
]


def patient_chart(readings: list, thresholds: dict, has_diabetes: bool) -> bytes:
    """PNG bytes: one small panel per vital sign."""
    panels = [p for p in PANELS if p[0] != "glucose" or has_diabetes]
    fig = Figure(figsize=(9, 2.0 * len(panels)))
    axes = fig.subplots(len(panels), 1, sharex=True, squeeze=False)[:, 0]
    times = [datetime.fromisoformat(r["ts"]) for r in readings]
    crit = [datetime.fromisoformat(r["ts"]) for r in readings if r["status"] == "Critical"]

    for ax, (key, title, cols) in zip(axes, panels):
        for i, col in enumerate(cols):
            pts = [(t, r[col]) for t, r in zip(times, readings) if r[col] is not None]
            if pts:
                ax.plot(*zip(*pts), color=LINE if i == 0 else LINE_2, linewidth=1.6,
                        label=col if len(cols) > 1 else None)
        for name, limit in thresholds.items():
            vital, side = name.rsplit("_", 1)
            if vital in cols:
                ax.axhline(limit, color=LIMIT, linestyle="--", linewidth=1)
                ax.text(0.995, limit, f"{side} limit {limit}", transform=ax.get_yaxis_transform(),
                        ha="right", va="bottom", fontsize=7, color=LIMIT)
        for t in crit:
            ax.axvline(t, color=CRITICAL, alpha=0.18, linewidth=3)
        values = [r[c] for r in readings for c in cols if r[c] is not None]
        lo, hi = DISPLAY_RANGE[key]
        if values:
            lo, hi = min(lo, min(values) - 2), max(hi, max(values) + 2)
        ax.set_ylim(lo, hi)
        ax.set_ylabel(title, fontsize=8)
        ax.tick_params(labelsize=8)
        ax.grid(axis="y", color="#e3e3e3", linewidth=0.6)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        if len(cols) > 1:
            ax.legend(fontsize=7, frameon=False, loc="upper right", ncol=2)
    if crit:
        axes[0].text(0.01, 1.02, "red bands = Critical readings", transform=axes[0].transAxes,
                     fontsize=8, color=CRITICAL)
    if readings:
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    else:
        axes[0].text(0.5, 0.5, "No readings yet", transform=axes[0].transAxes,
                     ha="center", va="center", fontsize=10, color="#5b6670")
    axes[-1].set_xlabel("Time (simulated clock)", fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    return buf.getvalue()
