"""Phase 1c — the recovery–risk frontier (fine α sweep + convex Pareto envelope).

Sweeps the conformal miscoverage α finely and traces the trade-off between recovery
(decisions the calibrated interval resolves) and realized risk (feasibility error), for
both the global and the locally-adaptive (normalized) split-conformal. Produces:

  - the held-out cell-level frontier: decisive-rate vs realized feasibility error, both
    modes, plus the convex upper envelope (the optimal achievable recovery at each risk);
  - the decision-level battery recovery at a few α (the real-verdict ceiling ~25%);
  - a figure outputs/phase1/risk_frontier.png.

Run:  PYTHONNOUSERSITE=1 uv run python experiments/phase1c_risk_frontier.py
Out:  outputs/phase1/risk_frontier.json, outputs/phase1/risk_frontier.png
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from prudent_ai.analysis.validation_run import ValidationRunner  # noqa: E402
from prudent_ai.solver.beliefs import Phi  # noqa: E402
from prudent_ai.solver.cache import CachedSubstrate  # noqa: E402
from prudent_ai.solver.decidability import Decidability, classify_query  # noqa: E402
from prudent_ai.solver.regimes import FULL  # noqa: E402
from prudent_ai.substrate.substrate import Substrate  # noqa: E402
from prudent_ai.transfer import CalibratedTransfer, OverlayedSubstrate  # noqa: E402
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict  # noqa: E402

REPO = Path(__file__).parents[1]
DB = REPO / "data/apt_substrate.db"
PKL = REPO / "data/routerbench_0shot.pkl"
OUT_JSON = REPO / "outputs/phase1/risk_frontier.json"
OUT_PNG = REPO / "outputs/phase1/risk_frontier.png"
ALPHA_GRID = [round(a, 3) for a in np.linspace(0.01, 0.45, 23)]
BATTERY_ALPHAS = (0.02, 0.05, 0.10, 0.20, 0.35)
PCTS = tuple(range(10, 91, 5))


class TransferRule:
    sees_masked = False

    def __init__(self, overlays):
        self._overlays = overlays
        self.name = "transfer"

    def decide(self, sub, query, visible_regime, kappa, phi):  # noqa: ARG002
        ov = OverlayedSubstrate(sub, self._overlays)
        res = classify_query(ov, query, kappa=("H", "M"), phi=Phi.INTERVAL, regime=FULL)
        return res.argmin_config if res.label is Decidability.DECIDABLE else None


def cell_frontier(transfer: CalibratedTransfer, mode: str) -> list[dict]:
    """Held-out cell-level: decisive-rate vs realized feasibility error per α."""
    rows = []
    n_grid = 9  # thresholds 0.1..0.9 inside test_guarantee
    for a in ALPHA_GRID:
        g = transfer.test_guarantee(a, mode=mode)
        denom = g["n_test"] * n_grid
        rows.append({
            "alpha": a,
            "recovery": round(g["n_decisive_commit"] / denom, 4) if denom else 0.0,
            "risk": g["feasibility_error"],
            "coverage": g["interval_coverage"],
            "width": g["mean_interval_width"],
        })
    return rows


def battery_recovery(base, transfer, mode) -> list[dict]:
    """Decision-level recovery (real verdict) + realized HVR at a few α."""
    benches = ValidationRunner(base).discover_routerbench_benchmarks()
    out = []
    for a in BATTERY_ALPHAS:
        ov = transfer.build_overlays(a, mode=mode)
        q = c = v = 0
        for bench in benches:
            bsub = BenchmarkSubstrate(base, bench)
            mp = MaskAndPredict(bsub, kappa=("H",), phi=Phi.POINT)
            qs = mp.generate_queries("routerbench", ("quality", "cost"), pcts=PCTS)
            if not qs:
                continue
            m = mp.score_rule(TransferRule(ov), qs, "quality")
            q += m.n_queries
            c += m.n_commit
            v += m.n_hidden_violation
        out.append({"alpha": a, "recovery": round(c / q, 4) if q else 0.0,
                    "realized_hvr": round(v / c, 4) if c else 0.0, "n": q})
    return out


def pareto_envelope(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Upper envelope: max recovery achievable at risk ≤ x. Sort by risk, cum-max recovery."""
    pts = sorted(points, key=lambda p: (p[0], -p[1]))
    env, best = [], -1.0
    for risk, rec in pts:
        if rec > best:
            best = rec
            env.append((risk, rec))
    return env


def main() -> None:
    base = CachedSubstrate(Substrate(str(DB)))
    transfer = CalibratedTransfer.fit_from_pkl(PKL)

    frontier = {m: cell_frontier(transfer, m) for m in ("global", "normalized")}
    battery = {m: battery_recovery(base, transfer, m) for m in ("global", "normalized")}
    base.close()

    # convex upper envelope over BOTH modes (the optimal achievable recovery vs risk)
    allpts = [(r["risk"], r["recovery"]) for m in frontier for r in frontier[m]]
    env = pareto_envelope(allpts)

    result = {
        "metadata": {"experiment": "phase1c_risk_frontier",
                     "alpha_grid": ALPHA_GRID, "battery_alphas": list(BATTERY_ALPHAS)},
        "cell_frontier": frontier,
        "battery_recovery": battery,
        "pareto_envelope": [{"risk": r, "recovery": v} for r, v in env],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2))

    # ---- figure ----
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    for m, color in (("global", "#1f77b4"), ("normalized", "#d62728")):
        xs = [r["risk"] for r in frontier[m]]
        ys = [100 * r["recovery"] for r in frontier[m]]
        ax.plot(xs, ys, "-o", ms=3, color=color, alpha=0.7,
                label=f"cell-level, {m}")
    ex = [r for r, _ in env]
    ey = [100 * v for _, v in env]
    ax.plot(ex, ey, "k--", lw=1.8, label="convex envelope (optimal)")
    # decision-level battery recovery (the real ceiling), normalized mode
    bx = [r["realized_hvr"] for r in battery["normalized"]]
    by = [100 * r["recovery"] for r in battery["normalized"]]
    ax.plot(bx, by, "s", ms=8, color="#2ca02c",
            label="decision-level (real verdict)")
    ax.axhline(24.9, ls=":", color="#2ca02c", alpha=0.6)
    ax.text(0.30, 26, "decision ceiling ≈25%", color="#2ca02c", fontsize=8)
    ax.set_xlabel("realized risk  (feasibility error)")
    ax.set_ylabel("recovery  (%)")
    ax.set_title("Recovery–risk frontier: calibrated transfer")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=140)

    print("cell-level frontier (held-out), normalized mode:")
    for r in frontier["normalized"]:
        print(f"  α={r['alpha']:.3f}  risk={r['risk']:.3f}  recovery={100*r['recovery']:.1f}%"
              f"  width={r['width']:.3f}")
    print("\ndecision-level battery recovery (real verdict):")
    for m in ("global", "normalized"):
        for r in battery[m]:
            print(f"  [{m}] α={r['alpha']:.2f}  recovery={100*r['recovery']:.1f}%  "
                  f"HVR={100*r['realized_hvr']:.1f}%")
    print(f"\nWrote {OUT_JSON} and {OUT_PNG}")


if __name__ == "__main__":
    main()
