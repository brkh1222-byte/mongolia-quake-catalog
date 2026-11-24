"""Figure: pipeline diagram (paper Fig. 3). python src/fig_pipeline.py"""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

REPO = Path(__file__).resolve().parents[1]
steps = [
    ("EarthScope FDSN\nXL, HH 100 Hz\n75,267 station-days", "data"),
    ("Pass 1 (GPU, streaming)\nPhaseNet + EQTransformer\n× stead / instance / original", "gpu"),
    ("Ensemble picks\n≥2 of 6 pairs, mean p ≥ 0.3", "cpu"),
    ("PyOcto association\n1-D layered model", "cpu"),
    ("Least-squares location\nquality classes A–D", "cpu"),
    ("Event snippets (100 Hz)\nML (Wood–Anderson)", "cpu"),
    ("Cross-correlation (GPU)\nGrowClust relocation", "gpu"),
    ("Template matching\nEQcorrscan + FMF (GPU), 20 Hz", "gpu"),
    ("Catalogue: Mc, b, D90,\nblast flags, faults", "out"),
]
col = {"data": "#d6eaf8", "gpu": "#fdebd0", "cpu": "#e8f8f5", "out": "#f5eef8"}
fig, ax = plt.subplots(figsize=(4.2, 9))
ax.set_xlim(0, 1); ax.set_ylim(0, len(steps)); ax.axis("off")
for i, (txt, kind) in enumerate(steps):
    y = len(steps) - i - 0.5
    ax.add_patch(FancyBboxPatch((0.08, y - 0.36), 0.84, 0.72, boxstyle="round,pad=0.02", fc=col[kind], ec="0.3", lw=0.8))
    ax.text(0.5, y, txt, ha="center", va="center", fontsize=7.5)
    if i < len(steps) - 1:
        ax.annotate("", xy=(0.5, y - 0.62), xytext=(0.5, y - 0.38), arrowprops=dict(arrowstyle="-|>", lw=0.8, color="0.3"))
ax.text(0.5, -0.05, "orange: GPU; green: CPU", ha="center", fontsize=6.5, color="0.4")
fig.savefig(REPO / "results" / "fig_pipeline.png", dpi=220, bbox_inches="tight")
print("wrote results/fig_pipeline.png")
