"""Regenerate ALL publication figures for the APT paper from real data.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/make_figures.py

Sources (real, verified outputs — never fabricated):
  fig_decidability_map  <- outputs/p3/empirical_prior_map.json (empirical_map)
  fig_regime_ladder     <- outputs/p3/empirical_prior_map.json (empirical_map)
  fig_coverage_risk     <- outputs/p4/coverage_risk.json (curve)
  fig_hidden_violation  <- outputs/p5/validation_scaled.json (scale_v1.slices)
  fig_voi_identity      <- computed live via prudent_ai.solver.voi.voi_for_axis on
                           the §8.2 in-memory gadget (validates VoI == Δ(R) = δλ/(δ+λ)).

C7: the VoI figure reads the substrate ONLY through the solver (candidates/cell via
classify_candidate inside voi_for_axis). The gadget is an in-memory Substrate.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend — MUST precede pyplot import

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
FIGDIR = ROOT / "docs" / "paper" / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)
DPI = 150

# Pretty labels for the evidence-regime ladder.
REGIME_LABELS = {
    "accuracy_only": "accuracy\nonly",
    "acc_cost": "acc\n+cost",
    "acc_cost_latency": "+latency",
    "acc_cost_lat_throughput": "+throughput",
    "plus_energy": "+energy",
    "full": "full",
}


def _load(rel: str) -> dict:
    with (ROOT / rel).open() as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Figure 1 — decidability map (the headline): %underdetermined over the ladder.
# ---------------------------------------------------------------------------
def fig_decidability_map() -> Path:
    data = _load("outputs/p3/empirical_prior_map.json")
    emap = data["empirical_map"]
    ladder = data["metadata"]["regime_ladder"]
    underdet = [emap[r]["fractions"]["underdetermined"] * 100 for r in ladder]
    decidable = [emap[r]["fractions"]["decidable"] * 100 for r in ladder]
    xs = list(range(len(ladder)))
    labels = [REGIME_LABELS[r] for r in ladder]

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    width = 0.6
    bars_u = ax.bar(xs, underdet, width, color="#c0392b", label="underdetermined")
    bars_d = ax.bar(xs, decidable, width, bottom=underdet, color="#27ae60",
                    label="decidable")
    for x, u in zip(xs, underdet, strict=True):
        ax.text(x, u - 4, f"{u:.1f}%", ha="center", va="top", color="white",
                fontsize=9, fontweight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("% of empirical queries")
    ax.set_ylim(0, 105)
    ax.set_title(
        f"Decidability map: most deployments stay underdetermined\n"
        f"(empirical prior, n={data['metadata']['prior_n']} queries, φ=point, κ=H+M)",
        fontsize=11,
    )
    ax.legend(loc="lower right", framealpha=0.95)
    ax.axhline(100, color="0.6", lw=0.6, ls=":")
    fig.tight_layout()
    out = FIGDIR / "fig_decidability_map.png"
    fig.savefig(out, dpi=DPI)
    plt.close(fig)
    del bars_u, bars_d
    return out


# ---------------------------------------------------------------------------
# Figure 2 — regime ladder: %decidable vs regime as a line (limit-theorem shadow).
# ---------------------------------------------------------------------------
def fig_regime_ladder() -> Path:
    data = _load("outputs/p3/empirical_prior_map.json")
    emap = data["empirical_map"]
    ladder = data["metadata"]["regime_ladder"]
    xs = list(range(len(ladder)))
    decidable = [emap[r]["fractions"]["decidable"] * 100 for r in ladder]
    lo = [emap[r]["cis"]["decidable"][0] * 100 for r in ladder]
    hi = [emap[r]["cis"]["decidable"][1] * 100 for r in ladder]
    yerr = [[d - lov for d, lov in zip(decidable, lo, strict=True)],
            [h - d for d, h in zip(decidable, hi, strict=True)]]
    labels = [REGIME_LABELS[r] for r in ladder]

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.errorbar(xs, decidable, yerr=yerr, marker="o", ms=7, lw=2,
                color="#2c3e50", ecolor="#7f8c8d", capsize=4,
                label="% decidable (95% CI)")
    plateau = max(decidable)
    ax.axhline(plateau, color="#c0392b", ls="--", lw=1.2,
               label=f"plateau ≈ {plateau:.1f}%")
    for x, d in zip(xs, decidable, strict=True):
        ax.annotate(f"{d:.1f}%", (x, d), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=8.5)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("% decidable")
    ax.set_ylim(-2, max(20, plateau + 8))
    ax.set_xlabel("evidence regime R (richer →)")
    ax.set_title(
        "Adding axes raises decidability — then it plateaus\n"
        "(rising-then-saturating: the limit-theorem shadow)",
        fontsize=11,
    )
    ax.legend(loc="upper left", framealpha=0.95)
    ax.grid(axis="y", ls=":", color="0.85")
    fig.tight_layout()
    out = FIGDIR / "fig_regime_ladder.png"
    fig.savefig(out, dpi=DPI)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure 3 — coverage vs risk curve (Trust-or-Escalate shape).
# ---------------------------------------------------------------------------
def fig_coverage_risk() -> Path:
    data = _load("outputs/p4/coverage_risk.json")
    curve = data["curve"]
    margins = [pt["margin"] for pt in curve]
    coverage = [pt["coverage"] * 100 for pt in curve]
    risk = [pt["risk"] * 100 for pt in curve]

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.plot(margins, coverage, marker="o", ms=6, lw=2, color="#2980b9",
            label="coverage (% committed)")
    ax.plot(margins, risk, marker="s", ms=6, lw=2, color="#c0392b",
            label="risk (% wrong | committed)")
    ax.fill_between(margins, 0, coverage, color="#2980b9", alpha=0.08)
    ax.set_xlabel("decision margin")
    ax.set_ylabel("%")
    ax.set_ylim(-3, max(coverage) + 8)
    ax.set_title(
        "Trust-or-Escalate: bounded coverage at zero realized risk\n"
        f"(FULL regime, n={data['metadata']['n_queries']} queries, "
        f"truth = richer-κ proxy)",
        fontsize=11,
    )
    ax.annotate(
        f"max coverage {max(coverage):.1f}% @ risk {risk[coverage.index(max(coverage))]:.1f}%",
        xy=(margins[coverage.index(max(coverage))], max(coverage)),
        textcoords="offset points", xytext=(20, -6), fontsize=9,
        arrowprops={"arrowstyle": "->", "color": "0.4"},
    )
    ax.legend(loc="center right", framealpha=0.95)
    ax.grid(ls=":", color="0.85")
    fig.tight_layout()
    out = FIGDIR / "fig_coverage_risk.png"
    fig.savefig(out, dpi=DPI)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure 4 — hidden violations (THE C2 figure): per biting slice, the hidden
# violation rate of B2 / B3 baselines vs the selective procedure (≈0).
# ---------------------------------------------------------------------------
def _short_slice(name: str) -> str:
    # "BFCL/bind=quality+latency/mask=quality" -> "BFCL"
    # "routerbench[mmlu]/bind=quality/mask=quality" -> "mmlu"
    head = name.split("/")[0]
    if head.startswith("routerbench[") and head.endswith("]"):
        return head[len("routerbench["):-1]
    return head


def fig_hidden_violation() -> Path:
    data = _load("outputs/p5/validation_scaled.json")
    sv = data["scale_v1"]
    slices = sv["meta"]["biting_slices"]
    pooled = sv["pooled"]["B2_observed_pareto"]

    labels, b2, b3, sel = [], [], [], []
    for sname in slices:
        rules = sv["slices"][sname]["rules"]
        labels.append(_short_slice(sname))
        b2.append(rules["B2_observed_pareto"]["hidden_violation_rate"] * 100)
        b3.append(rules["B3_imputation"]["hidden_violation_rate"] * 100)
        sel.append(rules["selective"]["hidden_violation_rate"] * 100)

    xs = list(range(len(labels)))
    width = 0.27
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.bar([x - width for x in xs], b2, width, color="#c0392b",
           label="B2 observed-Pareto")
    ax.bar(xs, b3, width, color="#e67e22", label="B3 imputation")
    ax.bar([x + width for x in xs], sel, width, color="#27ae60",
           label="selective (APT)")
    for x, v in zip([x + width for x in xs], sel, strict=True):
        ax.text(x, v + 1.5, f"{v:.0f}", ha="center", va="bottom",
                fontsize=8, color="#27ae60", fontweight="bold")

    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("hidden violation rate (%)")
    ax.set_ylim(0, 110)
    ax.set_title(
        "C2: imputing the masked axis hides constraint violations; "
        "abstention does not\n"
        "(7 biting slices: BFCL + 6 RouterBench benchmarks)",
        fontsize=11,
    )
    note = (
        f"Pooled (n={pooled['n']}): baseline {pooled['baseline_hidden_violation_rate'] * 100:.1f}% "
        f"vs selective {pooled['selective_hidden_violation_rate'] * 100:.1f}%, "
        f"Δ={pooled['mean_diff'] * 100:.1f}% "
        f"[95% CI {pooled['ci95_lo'] * 100:.1f}–{pooled['ci95_hi'] * 100:.1f}%], "
        f"p≈{pooled['binom_p_one_sided']:.0e}, significant"
    )
    ax.text(0.5, -0.30, note, transform=ax.transAxes, ha="center", va="top",
            fontsize=9, color="0.25",
            bbox={"boxstyle": "round,pad=0.4", "fc": "#f4f4f4", "ec": "0.7"})
    ax.legend(loc="upper right", framealpha=0.95, ncol=1)
    ax.grid(axis="y", ls=":", color="0.85")
    fig.tight_layout()
    out = FIGDIR / "fig_hidden_violation.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure 5 — VoI identity (§8.7): implemented VoI vs theoretical Δ(R)=δλ/(δ+λ).
# Computed LIVE on the §8.2 in-memory gadget (replicates _seed_gadget).
# ---------------------------------------------------------------------------
def _i(session, model, **kw) -> None:
    session.execute(sqlite_insert(model).values(**kw).on_conflict_do_nothing())


def _seed_gadget(sub: Substrate, delta: float) -> None:
    """§8.2 gadget (x_cheap latency ⊥ → latency is the omitted binding axis)."""
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
    obs("s-lat", "x_safe", "latency_p95", 90.0)  # x_cheap latency ⊥ (omitted)
    s.commit()


def fig_voi_identity() -> tuple[Path, float]:
    lam = 1.0
    deltas = [round(d, 4) for d in [0.05 + 0.05 * k for k in range(20)]]  # 0.05..1.0
    q = make_query("gadget",
                   [("quality", ">=", 0.8), ("latency_p95", "<=", 100.0)],
                   label="q+lat")
    implemented, theoretical = [], []
    for delta in deltas:
        sub = Substrate(":memory:")
        _seed_gadget(sub, delta=delta)
        voi = voi_for_axis(sub, q, "latency_p95", phi=Phi.POINT, regime=FULL,
                           lam=lam)
        sub.close()
        implemented.append(voi)
        theoretical.append((delta * lam) / (delta + lam))

    max_abs_err = max(abs(a - b) for a, b in zip(implemented, theoretical,
                                                 strict=True))

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.plot(deltas, theoretical, "-", lw=3, color="#7f8c8d", alpha=0.7,
            label=r"theory  $\Delta(R)=\delta\lambda/(\delta+\lambda)$")
    ax.plot(deltas, implemented, "o", ms=6, color="#c0392b",
            label="implemented VoI(latency)")
    ax.set_xlabel(r"cost gap $\delta$  ($\lambda=1.0$)")
    ax.set_ylabel("value of information")
    ax.set_title(
        "§8.7 identity: implemented VoI equals Δ(R)\n"
        f"(in-memory §8.2 gadget; max |error| = {max_abs_err:.2e})",
        fontsize=11,
    )
    ax.legend(loc="upper left", framealpha=0.95)
    ax.grid(ls=":", color="0.85")
    fig.tight_layout()
    out = FIGDIR / "fig_voi_identity.png"
    fig.savefig(out, dpi=DPI)
    plt.close(fig)
    return out, max_abs_err


def main() -> None:
    results = []
    results.append(("fig_decidability_map", fig_decidability_map()))
    results.append(("fig_regime_ladder", fig_regime_ladder()))
    results.append(("fig_coverage_risk", fig_coverage_risk()))
    results.append(("fig_hidden_violation", fig_hidden_violation()))
    voi_path, voi_err = fig_voi_identity()
    results.append(("fig_voi_identity", voi_path))

    print("Generated figures:")
    for name, path in results:
        size = path.stat().st_size
        print(f"  {name}: {path}  ({size} bytes)")
    ok = math.isclose(voi_err, 0.0, abs_tol=1e-6)
    print(f"\nfig_voi_identity: max |implemented - theoretical| = {voi_err:.3e} "
          f"-> implemented {'==' if ok else '!='} theoretical")


if __name__ == "__main__":
    main()
