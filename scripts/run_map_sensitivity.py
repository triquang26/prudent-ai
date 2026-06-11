"""E2 — sensitivity of the decidability verdict (reviewer-hardening node 6rb8dp).

Two knobs the external review flags as under-specified:
  1. THRESHOLD GROUNDING — the published map grounds each (tau, axis) threshold at
     the median (p50) observed value. Sweep the grounding percentile.
  2. COST TIES / NEAR-TIES — Definition 1 requires argmin invariance; the published
     classifier treats ANY strict undercut as a flip. Sweep a relative epsilon
     below which a potential undercut is ignored (two candidates within eps are
     treated as interchangeable). eps=0 reproduces the published verdict.

Both sweeps run the FULL-regime classification of all 1,716 derived queries over
the frozen prior snapshot, through the immutable interface, phi=POINT, kappa=H+M.

The epsilon variant is a SCRIPT-LOCAL copy of solver.decidability.classify_query
with the two cost-comparison lines parameterized; the published classifier is not
modified (eps=0 cross-checked against it for byte-identical labels).

Outputs: outputs/p3/map_sensitivity.{json,md}

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_map_sensitivity.py
"""

from __future__ import annotations

import json
from pathlib import Path

from prudent_ai.analysis.decidability_map import observed_thresholds
from prudent_ai.analysis.empirical_prior_map import load_prior
from prudent_ai.queries.query_prior import to_query
from prudent_ai.solver import Decidability, Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.decidability import classify_query
from prudent_ai.solver.feasibility import FeasState, classify_candidate
from prudent_ai.solver.regimes import FULL
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p3")
PROVENANCE = "E2-map-sensitivity"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT

AXES = [
    "quality", "latency_p95", "throughput", "cost",
    "energy", "memory_hw", "governance", "reviewer_burden",
]
PCT_SWEEP = (25, 40, 50, 60, 75)
EPS_SWEEP = (0.0, 0.01, 0.05, 0.10, 0.20)


def thresholds_at(sub, taus, pct: int) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for tau in taus:
        for axis in AXES:
            pcts = observed_thresholds(sub, tau, axis, (pct,), KAPPA)
            if pct in pcts:
                out[(tau, axis)] = pcts[pct]
    return out


def classify_query_eps(sub, query, kappa, phi, regime, eps: float):
    """classify_query with a relative epsilon on the argmin-flip comparison.

    Derived verbatim from solver.decidability.classify_query; the only change is
    that a rival flips the argmin only when it could undercut the best sure
    option by MORE than a relative eps:  cost < best_sure_cost * (1 - eps).
    eps=0.0 reproduces the published strict comparison.
    """
    verdicts = [
        classify_candidate(sub, cand.id, query.bundle, kappa, phi, regime)
        for cand in sub.candidates(query.tau)
    ]
    maybe = [v for v in verdicts if v.state is not FeasState.PROVABLY_INFEASIBLE]
    if not maybe:
        return Decidability.INFEASIBLE
    pf_costed = [
        v for v in maybe
        if v.state is FeasState.PROVABLY_FEASIBLE and v.cost_belief.is_present
    ]
    if not pf_costed:
        return Decidability.UNDERDETERMINED
    best_sure = min(pf_costed, key=lambda v: v.cost_belief.hi)
    bar = best_sure.cost_belief.hi * (1.0 - eps)
    for v in maybe:
        if v.state is FeasState.PROVABLY_FEASIBLE and v.cost_belief.is_present:
            if v is best_sure:
                continue
            if v.cost_belief.lo < bar:
                return Decidability.UNDERDETERMINED
            continue
        optimistic = v.cost_belief.lo if v.cost_belief.is_present else 0.0
        if optimistic < bar:
            return Decidability.UNDERDETERMINED
    return Decidability.DECIDABLE


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    _rows, prior = load_prior()
    taus = sorted({dq.tau for dq in prior.derived})
    n = prior.n

    # ---- 1. threshold-percentile sweep (published classifier, eps=0) ----
    pct_rows = []
    for pct in PCT_SWEEP:
        th = thresholds_at(sub, taus, pct)
        und = 0
        for dq in prior.derived:
            q = to_query(dq, th)
            res = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
            und += int(res.label is Decidability.UNDERDETERMINED)
        pct_rows.append({"pct": pct, "n": n, "underdetermined": und,
                         "frac": round(und / n, 4)})
        print(f"pct={pct}: underdetermined {und}/{n} = {und/n:.3f}")

    # ---- 2. epsilon-tie sweep (median thresholds) ----
    th50 = thresholds_at(sub, taus, 50)
    eps_rows = []
    mismatch_check = None
    for eps in EPS_SWEEP:
        und = 0
        agree = 0
        for dq in prior.derived:
            q = to_query(dq, th50)
            lab = classify_query_eps(sub, q, KAPPA, PHI, FULL, eps)
            und += int(lab is Decidability.UNDERDETERMINED)
            if eps == 0.0:
                ref = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
                agree += int(ref.label is lab)
        if eps == 0.0:
            mismatch_check = {"n": n, "agree": agree, "identical": agree == n}
        eps_rows.append({"eps": eps, "n": n, "underdetermined": und,
                         "frac": round(und / n, 4)})
        print(f"eps={eps}: underdetermined {und}/{n} = {und/n:.3f}")

    res = {
        "metadata": {
            "provenance": PROVENANCE, "db_path": DB_PATH,
            "phi": PHI.value, "kappa": list(KAPPA), "regime": "full",
            "prior_n": n,
            "eps0_crosscheck_vs_published": mismatch_check,
        },
        "threshold_percentile_sweep": pct_rows,
        "epsilon_tie_sweep": eps_rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "map_sensitivity.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# E2 — decidability-verdict sensitivity (FULL regime, n=1716)", ""]
    lines.append("## Threshold-grounding percentile sweep (published eps=0)")
    lines.append("")
    lines.append("| grounding pct | underdetermined | fraction |")
    lines.append("|---|---|---|")
    for r in pct_rows:
        lines.append(f"| p{r['pct']} | {r['underdetermined']}/{r['n']} | "
                     f"{100*r['frac']:.1f}% |")
    lines.append("")
    lines.append("## Relative epsilon-tie sweep (median thresholds)")
    lines.append("")
    lines.append("| eps | underdetermined | fraction |")
    lines.append("|---|---|---|")
    for r in eps_rows:
        lines.append(f"| {r['eps']:.2f} | {r['underdetermined']}/{r['n']} | "
                     f"{100*r['frac']:.1f}% |")
    lines.append("")
    lines.append(f"eps=0 cross-check vs published classifier: {mismatch_check}")
    (OUT_DIR / "map_sensitivity.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {OUT_DIR/'map_sensitivity.json'} and .md")


if __name__ == "__main__":
    main()
