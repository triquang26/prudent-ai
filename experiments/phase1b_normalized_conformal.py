"""Phase 1b — locally-adaptive (MAD-normalized) conformal vs the global radius.

Phase 1 used a single global split-conformal radius tau. Heavy-tailed residuals (a few
near-unpredictable benchmarks) make that radius wide, so recovery is limited. The
principled upgrade is a locally-adaptive interval qhat +/- tau*shat, where shat estimates
the prediction-residual magnitude per cell (geometric mean of model- and benchmark-level
leave-one-out MAE) -- tight where the model predicts well, wide where it does not. Unlike
the sigma_B (label-spread) scale tried in Phase-0b, shat tracks the prediction error, so
it both tightens easy cells and preserves the coverage guarantee.

Reruns the masked-quality battery through the REAL verdict for both modes and reports
recovery (coverage) and realized HVR per α, alongside the held-out guarantee.

Run:  PYTHONNOUSERSITE=1 uv run python experiments/phase1b_normalized_conformal.py
Out:  outputs/phase1/normalized_conformal.json
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
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict

REPO = Path(__file__).parents[1]
DB = REPO / "data/apt_substrate.db"
PKL = REPO / "data/routerbench_0shot.pkl"
OUT = REPO / "outputs/phase1/normalized_conformal.json"
ALPHAS = (0.05, 0.10, 0.20)
PCTS = tuple(range(10, 91, 5))
BIND = ("quality", "cost")
MASK = "quality"


class TransferRule:
    sees_masked = False

    def __init__(self, overlays, name):
        self._overlays = overlays
        self.name = name

    def decide(self, sub, query, visible_regime, kappa, phi):  # noqa: ARG002
        overlaid = OverlayedSubstrate(sub, self._overlays)
        res = classify_query(overlaid, query, kappa=("H", "M"), phi=Phi.INTERVAL,
                             regime=FULL)
        return res.argmin_config if res.label is Decidability.DECIDABLE else None


def _battery(base, transfer, mode):
    """Pooled coverage/HVR over the masked-quality battery for each α in `mode`."""
    pools = {f"{a:g}": {"q": 0, "commit": 0, "viol": 0} for a in ALPHAS}
    overlays = {a: transfer.build_overlays(a, mode=mode) for a in ALPHAS}
    for bench in ValidationRunner(base).discover_routerbench_benchmarks():
        bsub = BenchmarkSubstrate(base, bench)
        mp = MaskAndPredict(bsub, kappa=("H",), phi=Phi.POINT)
        qs = mp.generate_queries("routerbench", BIND, pcts=PCTS)
        if not qs:
            continue
        for a in ALPHAS:
            m = mp.score_rule(TransferRule(overlays[a], f"tx@{a:g}"), qs, MASK)
            pools[f"{a:g}"]["q"] += m.n_queries
            pools[f"{a:g}"]["commit"] += m.n_commit
            pools[f"{a:g}"]["viol"] += m.n_hidden_violation
    return {a: {"coverage": round(p["commit"] / p["q"], 4) if p["q"] else 0.0,
                "hvr": round(p["viol"] / p["commit"], 4) if p["commit"] else 0.0,
                "n": p["q"]} for a, p in pools.items()}


def main() -> None:
    base = CachedSubstrate(Substrate(str(DB)))
    transfer = CalibratedTransfer.fit_from_pkl(PKL)

    result = {"metadata": {"experiment": "phase1b_normalized_conformal",
                           "pcts": list(PCTS), "alphas": list(ALPHAS)}}
    for mode in ("global", "normalized"):
        result[mode] = {
            "battery": _battery(base, transfer, mode),
            "held_out_guarantee": {f"{a:g}": transfer.test_guarantee(a, mode=mode)
                                   for a in ALPHAS},
        }
    base.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))

    print("masked-quality battery recovery (coverage) / HVR — real verdict:")
    for mode in ("global", "normalized"):
        print(f"  [{mode}]")
        for a in ALPHAS:
            b = result[mode]["battery"][f"{a:g}"]
            g = result[mode]["held_out_guarantee"][f"{a:g}"]
            print(f"    α={a:.2f}  recovery={100*b['coverage']:.1f}%  HVR={100*b['hvr']:.1f}%"
                  f"   | held-out cov={g['interval_coverage']:.3f} "
                  f"feas-err={g['feasibility_error']:.3f}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
