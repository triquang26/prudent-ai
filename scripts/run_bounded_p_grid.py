"""Bounded-completion x binding-probability grid: the anchored belief-robust estimate.

The completion-semantics sweep (run_bounded_completion.py) runs only on the full-domain
p=1 prior; the p-sweep (run_prob_binding.py) runs only under full-domain completion. This
fills the interior: for each binding probability p (declared governance/reviewer-burden
constraints kept with probability p, seeded) we classify under BOUNDED completion of the
measurable axes. The value at the OMB anchor (p=0.345) is the data-anchored belief-robust
estimate, between the 41.0% assumption-minimal floor (p=0) and the 56.9% belief-robust
rate (p=1).

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_bounded_p_grid.py
Out:  outputs/p3/bounded_p_grid.json
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from prudent_ai.analysis.empirical_prior_map import (
    UNMEASURABLE_AXES,
    grounded_thresholds,
    load_prior,
)
from prudent_ai.queries.query_prior import QueryPrior, to_query
from prudent_ai.solver import Decidability, Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.decidability import classify_query
from prudent_ai.solver.regimes import FULL
from prudent_ai.substrate import Substrate

sys.path.insert(0, str(Path(__file__).parent))
from run_assumption_minimal_core import (  # noqa: E402
    BOUNDED_AXES,
    BoundedCompletionSubstrate,
    _pct,
)
from run_prob_binding import derive_prob_binding  # noqa: E402

DB = "data/apt_substrate.db"
OUT = Path("outputs/p3/bounded_p_grid.json")
KAPPA = ("H", "M")
AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]
P_GRID = (0.0, 0.25, 0.345, 0.5, 0.75, 1.0)  # 0.345 = OMB binding-indicator anchor
SEED = 20240613


def main() -> None:
    sub = CachedSubstrate(Substrate(DB))
    rows, base_prior = load_prior()
    taus = sorted({d.tau for d in base_prior.derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    # corpus-wide observed values per bounded axis (for the p25_p75 bounded reading)
    seen, vals = set(), {a: [] for a in BOUNDED_AXES}
    for tau in taus:
        for c in sub.candidates(tau):
            if c.id in seen:
                continue
            seen.add(c.id)
            for a in BOUNDED_AXES:
                for o in sub.cell(c.id, a):
                    if o.confidence in KAPPA and o.value_num is not None:
                        vals[a].append(o.value_num)
    for a in BOUNDED_AXES:
        vals[a].sort()
    bounds = {a: (_pct(vals[a], 25), _pct(vals[a], 75)) for a in BOUNDED_AXES if vals[a]}
    wsub = BoundedCompletionSubstrate(sub, bounds)  # bounded completion, fixed

    n = base_prior.n
    grid = {}
    for i, p in enumerate(P_GRID):
        rng = random.Random(SEED + i)
        prior_p = QueryPrior(derived=[derive_prob_binding(r, p, rng) for r in rows])
        n_und = n_struct = 0
        for dq in prior_p.derived:
            res = classify_query(wsub, to_query(dq, th), kappa=KAPPA,
                                 phi=Phi.INTERVAL, regime=FULL)
            if res.label is Decidability.UNDERDETERMINED:
                n_und += 1
                if set(res.blocking_axes) & UNMEASURABLE_AXES:
                    n_struct += 1
        grid[f"{p:g}"] = {"p": p, "underdetermined": n_und, "n": n,
                          "frac": round(n_und / n, 4),
                          "frac_structural": round(n_struct / n, 4)}
        print(f"  bounded, p={p:<5}: {n_und}/{n} = {100*n_und/n:.1f}% "
              f"(structural {100*n_struct/n:.1f}%)")

    anchored = grid["0.345"]["frac"]
    result = {
        "metadata": {"provenance": "bounded-p-grid", "completion": "bounded p25_p75",
                     "kappa": list(KAPPA), "seed": SEED, "omb_anchor_p": 0.345},
        "grid": grid,
        "anchored_belief_robust_estimate": anchored,
        "floor_p0": grid["0"]["frac"], "belief_robust_p1": grid["1"]["frac"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    print(f"\n>>> anchored belief-robust estimate (bounded, p=0.345 OMB) = "
          f"{100*anchored:.1f}%  (floor {100*grid['0']['frac']:.1f}%, "
          f"belief-robust {100*grid['1']['frac']:.1f}%)")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
