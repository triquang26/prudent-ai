"""Phase 1 — decidability/HVR with calibrated transfer ON, swept over α.

Re-runs the RouterBench masked-quality battery with the calibrated-transfer belief
injected for the masked (⊥) quality cell, through the EXISTING verdict + selective
procedure. For each α we measure, pooled over the per-benchmark slices:

  - transfer COVERAGE (= recovery: fraction of masked-quality decisions the calibrated
    interval makes decidable, so the procedure commits instead of abstaining);
  - transfer HVR (hidden-violation rate among its commits) — the guarantee predicts ≤ α;
  - the baselines for reference: B2 observed-Pareto, B3 median-imputation, B5 oracle,
    strict selective (abstains on every masked-quality query).

The transfer rule reads through the same MaskedSubstrate as every other rule, wraps it in
OverlayedSubstrate(α), and runs right_size with κ={H,M}, φ=interval (so the [lo,hi]
straddle logic applies and the synthetic confidence-M interval is visible). It commits
only when the verdict is DECIDABLE — never on a straddling interval.

Run:  PYTHONNOUSERSITE=1 uv run python experiments/phase1_decidability_with_transfer.py
Out:  outputs/phase1/decidability_with_transfer.json
"""

from __future__ import annotations

import json
from pathlib import Path

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.solver.beliefs import Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.decidability import Decidability, classify_query
from prudent_ai.solver.regimes import FULL
from prudent_ai.substrate.substrate import Substrate
from prudent_ai.transfer import CalibratedTransfer, OverlayedSubstrate
from prudent_ai.validation.baselines import ALL_RULES
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict

REPO = Path(__file__).parents[1]
DB = REPO / "data/apt_substrate.db"
PKL = REPO / "data/routerbench_0shot.pkl"
OUT = REPO / "outputs/phase1/decidability_with_transfer.json"
ALPHAS = (0.05, 0.10, 0.20)
PCTS = tuple(range(10, 91, 5))  # 17 queries / slice, matching the scaled battery
BIND = ("quality", "cost")
MASK = "quality"
# Strict selective abstains on every masked-quality query (quality ⊥ → straddle →
# underdetermined), so coverage 0 / HVR 0 by construction; we report it as a constant
# rather than recomputing its VoI-heavy abstention on every slice.
REF_RULES = ("B2_observed_pareto", "B3_imputation", "B5_oracle")


class TransferRule:
    """Selective rule that consults a calibrated transfer interval for the masked cell.

    Reads through the harness-provided (masked) substrate, overlays the calibrated
    quality interval, and runs the existing right_size with κ={H,M}, φ=interval. Commits
    only when DECIDABLE; abstains otherwise (never commits on a straddling interval).
    """

    sees_masked = False

    def __init__(self, overlays, name: str) -> None:
        self._overlays = overlays
        self.name = name

    def decide(self, sub, query, visible_regime, kappa, phi):  # noqa: ARG002
        overlaid = OverlayedSubstrate(sub, self._overlays)
        # classify_query directly (commit iff DECIDABLE) — no VoI ranking needed here.
        res = classify_query(overlaid, query, kappa=("H", "M"), phi=Phi.INTERVAL,
                             regime=FULL)
        return res.argmin_config if res.label is Decidability.DECIDABLE else None


def _pooled(counts: dict) -> dict:
    cov = counts["commit"] / counts["q"] if counts["q"] else 0.0
    hvr = counts["viol"] / counts["commit"] if counts["commit"] else 0.0
    return {
        "n_queries": counts["q"], "coverage": round(cov, 4),
        "hidden_violation_rate": round(hvr, 4),
        "n_commit": counts["commit"], "n_violation": counts["viol"],
    }


def main() -> None:
    base = CachedSubstrate(Substrate(str(DB)))
    transfer = CalibratedTransfer.fit_from_pkl(PKL)
    ref_rules = {r.name: r for r in ALL_RULES if r.name in REF_RULES}

    runner = ValidationRunner(base)
    benches = runner.discover_routerbench_benchmarks()

    # reference baselines (α-independent), pooled across slices
    ref_pool = {n: {"q": 0, "commit": 0, "viol": 0} for n in REF_RULES}
    # transfer pooled per α
    tx_pool = {f"{a:g}": {"q": 0, "commit": 0, "viol": 0} for a in ALPHAS}
    overlays_by_alpha = {a: transfer.build_overlays(a) for a in ALPHAS}

    per_slice = []
    for bench in benches:
        bsub = BenchmarkSubstrate(base, bench)
        mp = MaskAndPredict(bsub, kappa=("H",), phi=Phi.POINT)
        qs = mp.generate_queries("routerbench", BIND, pcts=PCTS)
        if not qs:
            continue
        row = {"benchmark": bench, "n_queries": len(qs)}
        # baselines
        for n, rule in ref_rules.items():
            m = mp.score_rule(rule, qs, MASK)
            ref_pool[n]["q"] += m.n_queries
            ref_pool[n]["commit"] += m.n_commit
            ref_pool[n]["viol"] += m.n_hidden_violation
            row[n] = {"cov": round(m.coverage, 3), "hvr": round(m.hidden_violation_rate, 3)}
        # transfer per α
        for a in ALPHAS:
            tr = TransferRule(overlays_by_alpha[a], name=f"transfer@{a:g}")
            m = mp.score_rule(tr, qs, MASK)
            tx_pool[f"{a:g}"]["q"] += m.n_queries
            tx_pool[f"{a:g}"]["commit"] += m.n_commit
            tx_pool[f"{a:g}"]["viol"] += m.n_hidden_violation
            row[f"transfer@{a:g}"] = {
                "cov": round(m.coverage, 3), "hvr": round(m.hidden_violation_rate, 3)}
        per_slice.append(row)

    pooled = {
        "baselines": {n: _pooled(ref_pool[n]) for n in REF_RULES},
        "selective_strict": {"coverage": 0.0, "hidden_violation_rate": 0.0,
                             "note": "abstains on every masked-quality query "
                                     "(quality ⊥ → straddle → underdetermined)"},
        "transfer": {a: _pooled(tx_pool[a]) for a in tx_pool},
    }
    # coverage–risk curve for transfer: (α, recovery=coverage, realized HVR)
    curve = [{
        "alpha": a,
        "recovery": pooled["transfer"][f"{a:g}"]["coverage"],
        "realized_hvr": pooled["transfer"][f"{a:g}"]["hidden_violation_rate"],
        "guarantee_holds": pooled["transfer"][f"{a:g}"]["hidden_violation_rate"] <= a + 0.02,
    } for a in ALPHAS]

    result = {
        "metadata": {
            "experiment": "phase1_decidability_with_transfer",
            "n_benchmark_slices": len(per_slice),
            "pcts": list(PCTS), "bind_axes": list(BIND), "masked_axis": MASK,
            "alphas": list(ALPHAS),
            "note": "Transfer commits only on DECIDABLE (non-straddling) calibrated "
                    "intervals; HVR ≤ α is the conformal guarantee. Recovery is the "
                    "fraction of masked-quality decisions made decidable.",
        },
        "pooled": pooled,
        "coverage_risk_curve": curve,
        "per_slice": per_slice,
    }
    base.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))

    print(f"slices={len(per_slice)}  pcts={PCTS[0]}..{PCTS[-1]} step5")
    print("\nbaselines (pooled):")
    for n in REF_RULES:
        p = pooled["baselines"][n]
        print(f"  {n:22} cov={p['coverage']:.3f}  HVR={p['hidden_violation_rate']:.3f}  "
              f"(n={p['n_queries']})")
    print("\ntransfer coverage–risk curve:")
    for c in curve:
        print(f"  α={c['alpha']:.2f}  recovery={100*c['recovery']:.1f}%  "
              f"realized_HVR={100*c['realized_hvr']:.1f}%  "
              f"guarantee_holds={c['guarantee_holds']}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
