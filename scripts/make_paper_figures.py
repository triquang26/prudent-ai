"""Regenerate the ICLR-paper figures (vector PDF, no in-figure titles) from real data.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/make_paper_figures.py

Differences from scripts/make_figures.py (the docs/project-page variants):
  * output is vector PDF into paper/figures/ (crisp at print size);
  * NO in-figure titles and NO internal jargon -- the LaTeX caption carries the story;
  * fonts sized for a \\linewidth or full-width figure in the ICLR two-column-free layout.

Sources (real, verified outputs -- never fabricated):
  fig_teaser            <- outputs/p3/empirical_prior_map.json (axis_binding_frequency)
                           + the per-axis miss-rates of the map snapshot (documented in
                           docs/P3_decidability_map.md, descriptive direct-DB read)
                           + outputs/p5/validation_scaled.json (pooled_h_only)
  fig_decidability_map  <- outputs/p3/empirical_prior_map.json (empirical_map)
  fig_hidden_violation  <- outputs/p5/validation_scaled.json (scale_v1.slices)
  fig_voi_identity      <- computed live on the in-memory two-world gadget
  fig_coverage_risk_gt  <- outputs/p4/coverage_risk_gt.json (curve)
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # noqa: E402

from prudent_ai.solver import Phi, make_query  # noqa: E402
from prudent_ai.solver.regimes import FULL  # noqa: E402
from prudent_ai.solver.voi import voi_for_axis  # noqa: E402
from prudent_ai.substrate import Substrate  # noqa: E402
from prudent_ai.substrate.orm import (  # noqa: E402
    Component,
    Config,
    ConfigComponent,
    Source,
)
from prudent_ai.substrate.orm import Observation as ObsORM  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIGDIR = ROOT / "paper" / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 11,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "pdf.fonttype": 42,  # embed TrueType -- ICLR-safe
})

REGIME_LABELS = {
    "accuracy_only": "accuracy\nonly",
    "acc_cost": "+cost",
    "acc_cost_latency": "+latency",
    "acc_cost_lat_throughput": "+throughput",
    "plus_energy": "+energy",
    "full": "full",
}

# Per-axis miss-rate of the decidability-map substrate snapshot (fraction of configs
# with zero H+M observation on the axis). Descriptive direct-DB read documented in
# docs/P3_decidability_map.md / docs/paper/05_findings.md S5.3 -- NOT invented here.
MISS_RATE = {
    "quality": 0.231,
    "latency_p95": 0.170,
    "throughput": 0.769,
    "cost": 0.401,
    "energy": 0.813,
    "memory_hw": 1.000,
    "governance": 1.000,
    "reviewer_burden": 1.000,
}

AXIS_LABEL = {
    "quality": "quality",
    "latency_p95": "latency",
    "throughput": "throughput",
    "cost": "cost",
    "energy": "energy",
    "memory_hw": "memory/hw",
    "governance": "governance",
    "reviewer_burden": "reviewer\nburden",
}


def _load(rel: str) -> dict:
    with (ROOT / rel).open() as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Figure 1 (teaser) -- (a) what real deployments constrain vs what the evidence
# reports; (b) what answering anyway costs (pooled hidden-violation).
# ---------------------------------------------------------------------------
def fig_teaser() -> Path:
    prior = _load("outputs/p3/empirical_prior_map.json")
    n = prior["metadata"]["prior_n"]
    bind_freq = prior["axis_binding_frequency"]

    axes_order = ["quality", "latency_p95", "cost", "governance",
                  "reviewer_burden", "memory_hw", "throughput", "energy"]
    bind = [100.0 * bind_freq.get(a, 0) / n for a in axes_order]
    miss = [100.0 * MISS_RATE[a] for a in axes_order]
    labels = [AXIS_LABEL[a] for a in axes_order]

    val = _load("outputs/p5/validation_scaled.json")
    ph = val["scale_v1"]["pooled_h_only"]["B2_observed_pareto"]
    hv_baseline = 100.0 * ph["baseline_hidden_violation_rate"]
    hv_selective = 100.0 * ph["selective_hidden_violation_rate"]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(10.6, 2.8), gridspec_kw={"width_ratios": [1.85, 1.0]})

    xs = list(range(len(axes_order)))
    w = 0.38
    ax1.bar([x - w / 2 for x in xs], bind, w, color="#2980b9",
            label="constrained by real deployments (%)")
    ax1.bar([x + w / 2 for x in xs], miss, w, color="#c0392b",
            label="missing from the evidence (%)")
    # one bracket over the needed-but-invisible pair (governance, reviewer burden)
    hi = [i for i, a in enumerate(axes_order)
          if MISS_RATE[a] == 1.0 and bind_freq.get(a, 0) / n > 0.05]
    if hi:
        lo_x, hi_x = min(hi) - 0.25, max(hi) + 0.25
        ax1.plot([lo_x, lo_x, hi_x, hi_x], [104, 107, 107, 104],
                 lw=1.2, color="#7b241c")
        # label directly above the bracket (legend now sits outside the axes)
        ax1.text((lo_x + hi_x) / 2, 110, "needed, never measured",
                 ha="center", va="bottom", fontsize=9,
                 color="#7b241c", fontweight="bold")
    ax1.set_xticks(xs)
    ax1.set_xticklabels(labels, fontsize=8.5, rotation=12)
    ax1.set_ylabel("% ")
    ax1.set_ylim(0, 124)
    # legend ABOVE the axes so nothing inside the plot can collide with it
    ax1.legend(loc="lower left", bbox_to_anchor=(0.0, 1.02), ncol=2,
               framealpha=0.95, fontsize=8.2, borderaxespad=0.0)
    ax1.grid(axis="y", ls=":", color="0.88")
    ax1.set_axisbelow(True)

    rules = ["leaderboard\n(observed-Pareto)", "impute the\nmissing axis", "selective\n(ours)"]
    hv = [hv_baseline, hv_baseline, hv_selective]
    colors = ["#c0392b", "#e67e22", "#27ae60"]
    bars = ax2.bar(rules, hv, 0.62, color=colors)
    for b, v in zip(bars, hv, strict=True):
        ax2.text(b.get_x() + b.get_width() / 2, v + 1.6, f"{v:.1f}%",
                 ha="center", fontsize=10.5, fontweight="bold",
                 color=b.get_facecolor())
    ax2.set_ylabel("hidden violations (%)")
    ax2.set_ylim(0, 75)
    ax2.tick_params(axis="x", labelsize=9)
    ax2.grid(axis="y", ls=":", color="0.88")
    ax2.set_axisbelow(True)

    fig.tight_layout(w_pad=2.2)
    out = FIGDIR / "fig_teaser.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure 2 -- decidability over the evidence-regime ladder (stacked bars).
# ---------------------------------------------------------------------------
def fig_decidability_map() -> Path:
    data = _load("outputs/p3/empirical_prior_map.json")
    emap = data["empirical_map"]
    ladder = data["metadata"]["regime_ladder"]
    underdet = [emap[r]["fractions"]["underdetermined"] * 100 for r in ladder]
    decidable = [emap[r]["fractions"]["decidable"] * 100 for r in ladder]
    xs = list(range(len(ladder)))
    labels = [REGIME_LABELS[r] for r in ladder]

    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    ax.bar(xs, underdet, 0.6, color="#c0392b", label="underdetermined")
    ax.bar(xs, decidable, 0.6, bottom=underdet, color="#27ae60", label="decidable")
    for x, u in zip(xs, underdet, strict=True):
        ax.text(x, u - 4, f"{u:.1f}%", ha="center", va="top", color="white",
                fontsize=9.5, fontweight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_xlabel("evidence regime (axes the rule may see; richer $\\rightarrow$)")
    ax.set_ylabel("% of 1716 real queries")
    ax.set_ylim(0, 104)
    ax.legend(loc="lower right", framealpha=0.95)
    fig.tight_layout()
    out = FIGDIR / "fig_decidability_map.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure 3 -- per-slice hidden violation (subset; pooled stats in the caption).
# ---------------------------------------------------------------------------
_DISPLAY_SLICES = [
    "routerbench[mmlu]/bind=quality/mask=quality",
    "routerbench[hellaswag]/bind=quality/mask=quality",
    "routerbench[arc-challenge]/bind=quality/mask=quality",
    "routerbench[winogrande]/bind=quality/mask=quality",
    "routerbench[mbpp]/bind=quality/mask=quality",
    "routerbench[grade-school-math]/bind=quality/mask=quality",
    "BFCL/bind=quality+latency/mask=quality",
]


def _short_slice(name: str) -> str:
    head = name.split("/")[0]
    if head.startswith("routerbench[") and head.endswith("]"):
        return head[len("routerbench["):-1]
    return head


def fig_hidden_violation() -> Path:
    data = _load("outputs/p5/validation_scaled.json")
    sv = data["scale_v1"]
    h_set = set(sv["meta"]["biting_slices_h"])

    display = [s for s in _DISPLAY_SLICES if s in sv["slices"]]
    labels, b2, b3, sel, is_h = [], [], [], [], []
    for sname in display:
        rules = sv["slices"][sname]["rules"]
        labels.append(_short_slice(sname))
        b2.append(rules["B2_observed_pareto"]["hidden_violation_rate"] * 100)
        b3.append(rules["B3_imputation"]["hidden_violation_rate"] * 100)
        sel.append(rules["selective"]["hidden_violation_rate"] * 100)
        is_h.append(sname in h_set)

    xs = list(range(len(labels)))
    w = 0.27
    fig, ax = plt.subplots(figsize=(7.4, 2.85))
    ax.bar([x - w for x in xs], b2, w, color="#c0392b", label="observed-Pareto")
    ax.bar(xs, b3, w, color="#e67e22", label="imputation")
    ax.bar([x + w for x in xs], sel, w, color="#27ae60", label="selective (ours)")
    for x, v in zip([x + w for x in xs], sel, strict=True):
        ax.text(x, v + 2, f"{v:.0f}", ha="center", va="bottom",
                fontsize=9, color="#1e8449", fontweight="bold")
    for x, h in zip(xs, is_h, strict=True):
        if not h:
            ax.text(x, 101, "med.-conf.", ha="center", va="bottom",
                    fontsize=8, color="0.45", style="italic")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=18, ha="right", fontsize=9)
    ax.set_ylabel("hidden violation rate (%)")
    ax.set_ylim(0, 112)
    # legend above the axes so it never overlaps the tall bars
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=3,
              framealpha=0.95, fontsize=8.6, columnspacing=1.0,
              handlelength=1.4, borderaxespad=0.0)
    ax.grid(axis="y", ls=":", color="0.88")
    ax.set_axisbelow(True)
    fig.tight_layout()
    out = FIGDIR / "fig_hidden_violation.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure 4 -- VoI identity, computed live on the two-world gadget.
# ---------------------------------------------------------------------------
def _i(session, model, **kw) -> None:
    session.execute(sqlite_insert(model).values(**kw).on_conflict_do_nothing())


def _seed_gadget(sub: Substrate, delta: float) -> None:
    s = sub._session
    _i(s, Source, evidence_id="g", source_type="benchmark", citation="g",
       snapshot_version="1")
    for cid in ("x_cheap", "x_safe"):
        _i(s, Component, id=f"m-{cid}", kind="model", name=cid)
        _i(s, Config, id=cid, tau="gadget")
        _i(s, ConfigComponent, config_id=cid, component_id=f"m-{cid}")

    def obs(oid, cid, axis, val):
        _i(s, ObsORM, obs_id=oid, config_id=cid, axis=axis, value_num=val,
           value_cat=None, confidence="H", evidence_id="g", hardware_tier="hw",
           dataset="d", split="test", decoding_cfg="greedy", obs_date="2026")

    obs("c-cost", "x_cheap", "cost", 1.0)
    obs("s-cost", "x_safe", "cost", 1.0 + delta)
    obs("c-q", "x_cheap", "quality", 0.9)
    obs("s-q", "x_safe", "quality", 0.9)
    obs("s-lat", "x_safe", "latency_p95", 90.0)
    s.commit()


def fig_voi_identity() -> tuple[Path, float]:
    lam = 1.0
    deltas = [round(0.05 + 0.05 * k, 4) for k in range(20)]
    q = make_query("gadget",
                   [("quality", ">=", 0.8), ("latency_p95", "<=", 100.0)],
                   label="q+lat")
    implemented, theoretical = [], []
    for delta in deltas:
        sub = Substrate(":memory:")
        _seed_gadget(sub, delta=delta)
        implemented.append(
            voi_for_axis(sub, q, "latency_p95", phi=Phi.POINT, regime=FULL,
                         lam=lam))
        sub.close()
        theoretical.append((delta * lam) / (delta + lam))
    max_abs_err = max(abs(a - b)
                      for a, b in zip(implemented, theoretical, strict=True))

    fig, ax = plt.subplots(figsize=(4.6, 2.7))
    ax.plot(deltas, theoretical, "-", lw=3, color="#7f8c8d", alpha=0.75,
            label=r"theory $\Delta(R)=\delta\lambda/(\delta+\lambda)$")
    ax.plot(deltas, implemented, "o", ms=5.5, color="#c0392b",
            label="implemented VoI")
    ax.set_xlabel(r"cost gap $\delta$  ($\lambda=1$)")
    ax.set_ylabel("value of information")
    ax.legend(loc="lower right", framealpha=0.95, fontsize=9)
    ax.grid(ls=":", color="0.88")
    ax.set_axisbelow(True)
    fig.tight_layout()
    out = FIGDIR / "fig_voi_identity.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out, max_abs_err


# ---------------------------------------------------------------------------
# Figure 5 -- real-GT coverage vs feasibility risk.
# ---------------------------------------------------------------------------
def fig_coverage_risk_gt() -> Path:
    data = _load("outputs/p4/coverage_risk_gt.json")
    curve = data["curve"]
    margins = [pt["margin"] for pt in curve]
    coverage = [pt["coverage"] * 100 for pt in curve]
    risk = [pt["risk"] * 100 for pt in curve]

    fig, ax = plt.subplots(figsize=(4.6, 2.7))
    ax.plot(margins, coverage, marker="o", ms=5, lw=2, color="#2980b9",
            label="coverage (% committed)")
    ax.plot(margins, risk, marker="s", ms=5, lw=2, color="#c0392b",
            label="feasibility risk (%)")
    ax.fill_between(margins, 0, coverage, color="#2980b9", alpha=0.07)
    for cal in data["calibrations"]:
        ax.axvline(cal["margin"], color="#27ae60", ls="--", lw=1.0, alpha=0.6)
    ax.set_xlabel("decision margin $m$")
    ax.set_ylabel("%")
    ax.set_ylim(-3, 108)
    ax.legend(loc="center right", framealpha=0.95, fontsize=9)
    ax.grid(ls=":", color="0.88")
    ax.set_axisbelow(True)
    fig.tight_layout()
    out = FIGDIR / "fig_coverage_risk_gt.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure (appendix) -- cost-versus-structural decomposition: what survives
# granting cost as determined, on the published headline vs the skeptical floor.
# Source: outputs/p3/blocker_decomposition.json (E6).
# ---------------------------------------------------------------------------
def fig_cost_decomposition() -> Path:
    data = _load("outputs/p3/blocker_decomposition.json")

    def segs(block: dict) -> tuple[float, float, float]:
        n = block["n"]
        cost_res = 100.0 * block["cost_only_resolved_by_granting_cost"] / n
        struct = 100.0 * block["cost_determined_residual"]["structural_frac_of_all"]
        other = 100.0 * block["cost_determined_residual"]["other_measurable_frac_of_all"]
        return cost_res, struct, other

    rows = [
        ("Published\nheadline", segs(data["published_prior"])),
        ("Skeptical\nfloor", segs(data["joint_drop_prior"])),
    ]
    # left-to-right: resolved by granting cost | structural residual | other residual
    c_cost, c_struct, c_other = "#95a5a6", "#c0392b", "#e67e22"
    labels = ["resolved by granting cost",
              "residual: never-measured axis",
              "residual: other measurable axis"]

    fig, ax = plt.subplots(figsize=(7.0, 1.95))
    ys = [1, 0]
    for y, (_, (cr, st, ot)) in zip(ys, rows, strict=True):
        left = 0.0
        for val, col in ((cr, c_cost), (st, c_struct), (ot, c_other)):
            ax.barh(y, val, left=left, height=0.55, color=col,
                    edgecolor="white", linewidth=0.7)
            if val >= 4.0:
                ax.text(left + val / 2, y, f"{val:.1f}", ha="center", va="center",
                        color="white", fontsize=9.5, fontweight="bold")
            left += val
        ax.text(left + 1.5, y, f"{left:.1f}% underdet.", ha="left", va="center",
                fontsize=9.5)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=10)
    ax.set_xlim(0, 104)
    ax.set_xlabel("% of 1716 real queries")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (c_cost, c_struct, c_other)]
    ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.32),
              ncol=3, fontsize=8.6, framealpha=0.95, handlelength=1.2,
              columnspacing=1.0)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out = FIGDIR / "fig_cost_decomposition.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    outs = [fig_teaser(), fig_decidability_map(), fig_hidden_violation()]
    voi_path, voi_err = fig_voi_identity()
    outs += [voi_path, fig_coverage_risk_gt(), fig_cost_decomposition()]
    print("Generated:")
    for p in outs:
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size} bytes)")
    print(f"VoI identity max |err| = {voi_err:.2e}")


if __name__ == "__main__":
    main()
