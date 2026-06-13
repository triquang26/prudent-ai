"""Render the recovery–risk frontier figure from the precomputed JSON.

Standalone plotter: reads outputs/phase1/risk_frontier.json (produced by
phase1c_risk_frontier.py) and emits a crisp, black-&-white-legible figure.
Does NOT recompute or alter any numbers — it only reads + draws.

Run:  PYTHONNOUSERSITE=1 uv run python experiments/plot_frontier.py
Out:  paper/figures/fig_risk_frontier.pdf  (vector)
      paper/figures/fig_risk_frontier.png  (dpi=200)
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).parents[1]
IN_JSON = REPO / "outputs/phase1/risk_frontier.json"
OUT_PDF = REPO / "paper/figures/fig_risk_frontier.pdf"
OUT_PNG = REPO / "paper/figures/fig_risk_frontier.png"

# Global B&W-legible style: large fonts, series distinguished by marker+linestyle.
plt.rcParams.update({
    "font.size": 14,
    "axes.titlesize": 15,
    "axes.labelsize": 14,
    "xtick.labelsize": 13,
    "ytick.labelsize": 13,
    "legend.fontsize": 12,
    "pdf.fonttype": 42,  # embed TrueType so text stays selectable / portable
    "ps.fonttype": 42,
})


def main() -> None:
    data = json.loads(IN_JSON.read_text())
    frontier = data["cell_frontier"]
    battery = data["battery_recovery"]
    env = data["pareto_envelope"]

    fig, ax = plt.subplots(figsize=(6.4, 4.4))

    # Two cell-level curves. Distinguished by COLOR + MARKER + LINESTYLE so they
    # remain separable in grayscale print.
    styles = {
        "global": dict(color="#1f77b4", marker="o", linestyle="-",
                       label="cell-level, global"),
        "normalized": dict(color="#d62728", marker="s", linestyle="--",
                           label="cell-level, normalized"),
    }
    for mode, st in styles.items():
        xs = [r["risk"] for r in frontier[mode]]
        ys = [100 * r["recovery"] for r in frontier[mode]]
        ax.plot(xs, ys, marker=st["marker"], linestyle=st["linestyle"],
                color=st["color"], ms=6, lw=2.0, markeredgecolor="black",
                markeredgewidth=0.5, alpha=0.9, label=st["label"])

    # Convex upper envelope — thick black dotted line.
    ex = [p["risk"] for p in env]
    ey = [100 * p["recovery"] for p in env]
    ax.plot(ex, ey, color="black", linestyle=":", lw=3.0,
            label="convex envelope (optimal)")

    # Decision-level battery recovery (real verdict), normalized mode: green diamonds.
    bx = [r["realized_hvr"] for r in battery["normalized"]]
    by = [100 * r["recovery"] for r in battery["normalized"]]
    ax.plot(bx, by, marker="D", linestyle="none", ms=12, color="#2ca02c",
            markeredgecolor="black", markeredgewidth=0.8,
            label="decision-level (real verdict)")

    # Decision ceiling reference line at ~24.9%.
    ax.axhline(24.9, ls=(0, (1, 1)), color="#2ca02c", lw=1.5, alpha=0.8)
    ax.text(0.30, 25.8, "decision ceiling ≈25%", color="#2ca02c",
            fontsize=12, fontweight="bold")

    ax.set_xlabel("realized risk  (feasibility error)")
    ax.set_ylabel("recovery  (%)")
    ax.set_title("Recovery–risk frontier of calibrated transfer")
    ax.legend(loc="lower right", framealpha=0.9)
    ax.grid(alpha=0.25)

    fig.tight_layout()
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF)          # vector
    fig.savefig(OUT_PNG, dpi=200)  # raster
    print(f"Wrote {OUT_PDF}")
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
