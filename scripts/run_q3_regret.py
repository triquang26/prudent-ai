"""Q3 — realized mis-sizing regret vs Δ(R), instantiated with real RouterBench geometry.

For each biting slice (benchmark × q* percentile where the cheapest config is infeasible),
read δ = price of caution = cost(true-min-cost-feasible) − cost(global-cheapest) from
full-sample truth, set λ = DEFAULT_LAMBDA (declared violation penalty), and compute the
limit-theorem floor Δ(R)=δλ/(δ+λ). Report that both naive rules (leaderboard cost-min,
cautious over-provisioner) realize regret ≥ Δ(R), while the selective procedure abstains
(0) and would pay only Δ(R) as acquirable VoI. Also report the real cost stakes
(`overshoot_rel` = relative price of caution).

Writes:
  - outputs/p4/q3_regret.json — per-slice δ/λ/Δ(R)/regrets + aggregate + provenance.
  - outputs/p4/q3_regret.md   — per-slice table + the Δ(R) ≤ realized-regret summary.

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_q3_regret.py
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from prudent_ai.analysis.regret_delta import gadget_minimax, slice_regret
from prudent_ai.solver.voi import DEFAULT_LAMBDA
from prudent_ai.validation.gt_guarantee import MODELS, GTCoverageGuarantee

OUT_DIR = Path("outputs/p4")
PROVENANCE = "P4-Q3-regret"
PERCENTILES = (0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)


def _render_md(slices, agg) -> str:
    L: list[str] = []
    L.append("# Q3 — Realized mis-sizing regret vs the limit theorem Δ(R) (real geometry)\n")
    L.append(
        "The §8 limit theorem floors any regime-restricted rule's regret at "
        "**Δ(R)=δλ/(δ+λ)**. We instantiate it with **real** RouterBench truth: on each "
        "biting slice (cheapest config infeasible at q*), **δ = the price of caution** = "
        "cost(true min-cost-feasible) − cost(global cheapest) (measured), and **λ = the "
        "declared violation penalty** (`DEFAULT_LAMBDA`). Δ(R) is the irreducible regret; "
        "the leaderboard cost-minimizer realizes worst-world regret **λ** and the cautious "
        "over-provisioner **δ**, both ≥ Δ(R). The selective procedure abstains (0) and "
        "would pay only Δ(R) as *acquirable* VoI.\n"
    )
    L.append(f"- λ (declared violation penalty): **{DEFAULT_LAMBDA:g}**")
    L.append(f"- biting slices: **{agg['n_biting']}** of {agg['n_total']} "
             f"(benchmark × q* percentile)")
    L.append(f"- Δ(R) ≤ min(δ,λ) on **{agg['n_floor_below_naive']}/{agg['n_biting']}** "
             f"biting slices (the floor is strictly below both naive rules' regret)")
    L.append(f"- mean price of caution (overshoot_rel): **{agg['mean_overshoot_rel']:.3f}** "
             f"(over-provisioning to guarantee feasibility costs that fraction more than "
             f"the cheapest, infeasible config)")
    L.append(f"- mean δ (absolute cost gap): **{agg['mean_delta']:.4g}**; "
             f"mean Δ(R): **{agg['mean_delta_R']:.4g}**")
    L.append("")
    L.append("## Per-slice (biting only)\n")
    L.append("| benchmark | q* | δ (price of caution) | Δ(R) | cost-min regret (=λ) | "
             "over-prov regret (=δ) | Δ(R)≤both? | overshoot_rel |")
    L.append("|---|---|---|---|---|---|---|---|")
    for s in slices:
        floor_ok = "✅" if s.delta_R <= s.regret_costmin and s.delta_R <= s.regret_overprov else "⚠"
        L.append(
            f"| {s.benchmark} | {s.q_star:.3f} | {s.delta:.4g} | {s.delta_R:.4g} | "
            f"{s.regret_costmin:g} | {s.regret_overprov:.4g} | {floor_ok} | "
            f"{s.overshoot_rel:.3f} |"
        )
    L.append("")
    L.append(
        "**Reading.** Δ(R) is strictly below both naive rules' realized regret on every "
        "biting slice — real mis-sizing *exceeds* the theorem's irreducible floor, as Q3 "
        "asks. The selective procedure is the only rule that pays 0 by abstaining; the gap "
        "it would otherwise pay (Δ(R)) is exactly the cost-aware VoI it reports, so it can "
        "*acquire* the binding axis rather than gamble. `overshoot_rel` is the concrete "
        "real cost the binding axis controls — the money leaderboard right-sizing leaves on "
        "the table when it commits blind."
    )
    return "\n".join(L)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    g = GTCoverageGuarantee()
    g._load()  # noqa: SLF001 — load truths for direct scoring

    slices = []
    n_total = 0
    for bench in g.benchmarks:
        t = g.truth(bench)
        quality = t.quality
        cost = t.cost
        for pct in PERCENTILES:
            n_total += 1
            q_star = g.q_star_for(bench, pct)
            sr = slice_regret(bench, quality, cost, q_star)
            if sr is not None:
                slices.append(sr)

    n_biting = len(slices)
    n_floor = sum(
        1 for s in slices
        if s.delta_R <= s.regret_costmin + 1e-12 and s.delta_R <= s.regret_overprov + 1e-12
    )
    # consistency: closed-form Δ(R) matches the proven gadget minimax on every slice
    max_gap = max(
        (abs(s.delta_R - gadget_minimax(s.delta, s.lam)) for s in slices), default=0.0
    )
    agg = {
        "n_total": n_total,
        "n_biting": n_biting,
        "n_floor_below_naive": n_floor,
        "mean_delta": (sum(s.delta for s in slices) / n_biting if n_biting else 0.0),
        "mean_delta_R": (sum(s.delta_R for s in slices) / n_biting if n_biting else 0.0),
        "mean_overshoot_rel": (
            sum(s.overshoot_rel for s in slices) / n_biting if n_biting else 0.0
        ),
        "closedform_vs_gadget_max_abs_gap": max_gap,
    }

    payload = {
        "metadata": {"provenance": PROVENANCE, "pkl": g.pkl_path,
                     "lambda": DEFAULT_LAMBDA, "percentiles": list(PERCENTILES),
                     "models": len(MODELS)},
        "aggregate": agg,
        "slices": [asdict(s) for s in slices],
    }
    (OUT_DIR / "q3_regret.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (OUT_DIR / "q3_regret.md").write_text(_render_md(slices, agg), encoding="utf-8")

    print("=" * 76)
    print("Q3 — REALIZED REGRET vs Δ(R) (real RouterBench geometry)")
    print("=" * 76)
    print(f"  biting slices: {n_biting}/{n_total}")
    print(f"  Δ(R) ≤ min(δ,λ) on {n_floor}/{n_biting} slices (floor below naive regret)")
    print(f"  mean price of caution (overshoot_rel): {agg['mean_overshoot_rel']:.3f}")
    print(f"  mean δ={agg['mean_delta']:.4g}  mean Δ(R)={agg['mean_delta_R']:.4g}")
    print(f"  closed-form Δ(R) vs proven gadget minimax: max abs gap "
          f"{max_gap:.2e} (consistency)")
    print("=" * 76)
    print(f"Wrote {OUT_DIR / 'q3_regret.json'}")
    print(f"Wrote {OUT_DIR / 'q3_regret.md'}")


if __name__ == "__main__":
    main()
