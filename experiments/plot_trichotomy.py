"""The resolution trichotomy — schematic figure.

A clean three-box schematic: an underdetermined co-location decision is resolved
exactly one of three ways. B&W-legible (grayscale fills + distinct hatching,
black text >=14pt).

Run:  PYTHONNOUSERSITE=1 uv run python experiments/plot_trichotomy.py
Out:  paper/figures/fig_trichotomy.pdf  (vector)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

REPO = Path(__file__).parents[1]
OUT_PDF = REPO / "paper/figures/fig_trichotomy.pdf"
OUT_PNG = REPO / "paper/figures/fig_trichotomy.png"

plt.rcParams.update({
    "font.size": 14,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})


def main() -> None:
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # Root / title box (top, full width).
    root_y, root_h = 86, 12
    root = FancyBboxPatch(
        (12, root_y), 76, root_h,
        boxstyle="round,pad=0.6,rounding_size=2",
        linewidth=1.8, edgecolor="black", facecolor="white",
        mutation_aspect=1,
    )
    ax.add_patch(root)
    ax.text(50, root_y + root_h / 2, "Underdetermined co-location decision",
            ha="center", va="center", fontsize=15, fontweight="bold")

    # Three resolution boxes.
    box_w, box_h = 30.0, 64
    box_y = 4
    gap = (100 - 3 * box_w) / 4.0
    xs = [gap + i * (box_w + gap) for i in range(3)]  # evenly spaced left edges
    centers = [x + box_w / 2 for x in xs]

    boxes = [
        {
            "tag": "(i) Curable by transfer",
            "fill": "#e6e6e6",
            "hatch": "",
            "body": ("calibrated interval;\n"
                     "guaranteed\n"
                     "P(infeasible | commit) ≤ α.\n"
                     "Recovers 24.9% at\n"
                     "0 violations, no new\n"
                     "measurement."),
        },
        {
            "tag": "(ii) Resolvable by\nmeasurement",
            "fill": "#ffffff",
            "hatch": "////",
            "body": ("live acquisition loop:\n"
                     "measure the VoI-ranked\n"
                     "axis (1–2 real probes).\n"
                     "100% coverage,\n"
                     "0 violations,\n"
                     "minimum-sufficient."),
        },
        {
            "tag": "(iii) Structurally\nunmeasured",
            "fill": "#bfbfbf",
            "hatch": "..",
            "body": ("no measurement path\n"
                     "(e.g. governance);\n"
                     "the loop refuses\n"
                     "rather than fabricate."),
        },
    ]

    for x, c, spec in zip(xs, centers, boxes, strict=True):
        b = FancyBboxPatch(
            (x, box_y), box_w, box_h,
            boxstyle="round,pad=0.6,rounding_size=2",
            linewidth=1.8, edgecolor="black",
            facecolor=spec["fill"], hatch=spec["hatch"],
        )
        ax.add_patch(b)
        # Tag (bold header) near the top of the box, on a white strip so it stays
        # readable over the hatching.
        n_tag_lines = spec["tag"].count("\n") + 1
        head_y = box_y + box_h
        ax.text(c, head_y - 4, spec["tag"],
                ha="center", va="top", fontsize=14, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.25", fc="white",
                          ec="none", alpha=0.95))
        # Body text below the header.
        body_top = head_y - 4 - n_tag_lines * 8 - 3
        ax.text(c, body_top, spec["body"],
                ha="center", va="top", fontsize=12, linespacing=1.35,
                bbox=dict(boxstyle="round,pad=0.2", fc="white",
                          ec="none", alpha=0.85))

        # Arrow from root box down to each resolution box.
        arr = FancyArrowPatch(
            (50, root_y), (c, box_y + box_h),
            arrowstyle="-|>", mutation_scale=18,
            linewidth=1.6, color="black",
            shrinkA=2, shrinkB=2,
        )
        ax.add_patch(arr)

    fig.tight_layout(pad=0.4)
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF)
    fig.savefig(OUT_PNG, dpi=200)
    print(f"Wrote {OUT_PDF}")
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
