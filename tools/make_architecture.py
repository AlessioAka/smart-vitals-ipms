"""Draws docs/architecture.png.  python tools/make_architecture.py"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
fig, ax = plt.subplots(figsize=(12, 6.4))
ax.set_xlim(0, 12); ax.set_ylim(0, 6.4); ax.axis("off")


def box(x, y, w, h, title, lines, fill, edge="#1f4e79"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fill, ec=edge, lw=1.4))
    ax.text(x + w / 2, y + h - 0.2, title, ha="center", va="top", fontsize=10.5, fontweight="bold", color="#14202b")
    ax.text(x + w / 2, y + h - 0.55, "\n".join(lines), ha="center", va="top", fontsize=8.3, color="#26323d", linespacing=1.35)


def arrow(x1, y1, x2, y2, label, dy=0.18):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", lw=1.6, color="#444"))
    ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, label, ha="center", fontsize=8, color="#444")


# zones
ax.add_patch(FancyBboxPatch((0.15, 0.55), 3.3, 5.3, boxstyle="round,pad=0.02,rounding_size=0.1", fc="#eef5fb", ec="#9db9d3", lw=1, ls="--"))
ax.text(1.8, 5.7, "EDGE  (wearable + phone)", ha="center", fontsize=9, color="#3b5f82", fontweight="bold")
ax.add_patch(FancyBboxPatch((4.15, 0.55), 5.0, 5.3, boxstyle="round,pad=0.02,rounding_size=0.1", fc="#f4f8f2", ec="#a5c49a", lw=1, ls="--"))
ax.text(6.65, 5.7, "CLOUD  (Docker Compose: two containers + a volume)", ha="center", fontsize=9, color="#3f6b35", fontweight="bold")

box(0.4, 3.55, 2.8, 1.75, "Simulator (container)", ["20 patients, 1 reading/min", "dropouts, glitches, stuck,", "late readings, resent copies"], "#ffffff")
box(0.4, 1.0, 2.8, 2.25, "Edge node (cheap + urgent)", ["1. range check (blank impossible)", "2. early warning, works offline", "3. buffer + retry with backoff", "No model, no history"], "#ffffff")

box(4.4, 3.0, 4.55, 2.3, "API container (Flask)", ["", "", "", "", ""], "#ffffff", "#3f6b35")
ax.text(5.6, 4.85, "validate  -> 422\nrecognise copies -> 200\nclassify, model loaded once\nalert + per-patient limits\nlogin + access control\nserves the dashboard", ha="center", va="top", fontsize=8.3, color="#26323d", linespacing=1.35)
box(7.0, 3.15, 1.8, 1.55, "Model", ["random forest,", "trained on invented", "data"], "#f4f8f2", "#3f6b35")
box(4.4, 1.0, 4.55, 1.7, "SQLite database in a Docker volume", ["readings and alerts per patient (R6)", "clinician -> patient assignment (R5)", "per-patient thresholds (R10)  |  hashed passwords"], "#ffffff", "#3f6b35")

box(9.7, 3.0, 2.1, 2.3, "Clinician dashboard", ["only MY patients (R5)", "trend charts (R8)", "alerts + acknowledge", "set thresholds (R10)"], "#fff8ec", "#a86b00")
ax.text(10.75, 2.55, "browser, logged in", ha="center", fontsize=8, color="#7a5000")
ax.text(10.75, 1.8, "A Critical reading\nreaches the clinician as\nan alert: patient ID,\nvitals, timestamp", ha="center", fontsize=8.2, color="#7a5000")

arrow(1.8, 3.55, 1.8, 3.25, "raw reading", dy=0.0)
ax.annotate("", xy=(4.4, 3.6), xytext=(3.2, 2.1), arrowprops=dict(arrowstyle="->", lw=1.6, color="#444"))
ax.text(3.85, 2.55, "POST /readings\n(JSON + key)", ha="center", fontsize=8, color="#444", bbox=dict(fc="white", ec="none", pad=1))
arrow(5.5, 3.0, 5.5, 2.7, "", dy=0)
arrow(9.7, 4.15, 8.95, 4.15, "", dy=0)
ax.text(9.33, 4.3, "HTTP", ha="center", fontsize=7.5, color="#444")
ax.text(6.0, 0.28, "Same code in src/ cleans data for training AND for live readings: no train/serve skew.", ha="center", fontsize=8.5, style="italic", color="#444")
fig.savefig(ROOT / "docs" / "architecture.png", dpi=150, bbox_inches="tight")
print("wrote docs/architecture.png")
