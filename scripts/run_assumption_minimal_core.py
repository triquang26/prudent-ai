"""Assumption-minimal core: bounded completion AND no declared governance binding.

The 2x2 of two orthogonal modelling knobs:
  (A) completion of a ⊥ MEASURABLE cell: full-domain (adversarial) vs bounded (observed range)
  (B) declared-implies-binding for governance/reviewer-burden: granted (p=1) vs deleted (p=0)

Three corners are already reported: full+granted=91.1%, full+deleted=75.1%,
bounded+granted=56.9%. This computes the FOURTH, missing corner — bounded completion AND
governance/reviewer-burden bindings deleted — the share robust to BOTH knobs (expected
to corroborate the 12.4% negative-control). No new modelling: same frozen substrate, same
queries/thresholds, the bounded-completion semantics of run_bounded_completion.py applied
to the joint-drop (p=0) prior.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_assumption_minimal_core.py
Out:  outputs/p3/assumption_minimal_core.json
"""

from __future__ import annotations

import dataclasses
import json
from collections import namedtuple
from pathlib import Path

from prudent_ai.analysis.empirical_prior_map import (
    UNMEASURABLE_AXES,
    grounded_thresholds,
    load_prior,
)
from prudent_ai.queries.query_prior import to_query
from prudent_ai.solver import Decidability, Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.decidability import classify_query
from prudent_ai.solver.regimes import FULL
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT = Path("outputs/p3/assumption_minimal_core.json")
KAPPA = ("H", "M")
PHI = Phi.INTERVAL
AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]
BOUNDED_AXES = ("quality", "cost", "latency_p95")
DROP = {"governance", "reviewer_burden"}  # the joint-drop (p=0) axes
WIDTHS = [("point_p50", 50, 50), ("p25_p75", 25, 75), ("p10_p90", 10, 90),
          ("full_domain", None, None)]

_Obs = namedtuple("_Obs", ["confidence", "value_num"])


def _pct(vals: list[float], p: int) -> float:
    if not vals:
        return 0.0
    k = (len(vals) - 1) * (p / 100.0)
    lo_i, hi_i = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo_i] * (1 - (k - lo_i)) + vals[hi_i] * (k - lo_i)


class BoundedCompletionSubstrate:
    def __init__(self, sub, bounds):
        self._sub = sub
        self._bounds = bounds

    def candidates(self, tau):
        return self._sub.candidates(tau)

    def cell(self, x, a):
        real = self._sub.cell(x, a)
        if real:
            return real
        b = self._bounds.get(a)
        return [_Obs("M", b[0]), _Obs("M", b[1])] if b else []

    def required_fields(self, bundle):
        return self._sub.required_fields(bundle)

    def __getattr__(self, name):
        return getattr(self._sub, name)


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, prior = load_prior()
    taus = sorted({d.tau for d in prior.derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    # joint-drop: remove declared governance / reviewer-burden bindings (p=0)
    dropped = [dataclasses.replace(d, binding_axes=frozenset(d.binding_axes) - DROP)
               for d in prior.derived]

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

    n = prior.n
    sweep = {}
    for label, plo, phip in WIDTHS:
        bounds = ({} if plo is None
                  else {a: (_pct(vals[a], plo), _pct(vals[a], phip))
                        for a in BOUNDED_AXES if vals[a]})
        wsub = BoundedCompletionSubstrate(sub, bounds)
        n_und = n_struct = 0
        for dq in dropped:
            res = classify_query(wsub, to_query(dq, th), kappa=KAPPA, phi=PHI, regime=FULL)
            if res.label is Decidability.UNDERDETERMINED:
                n_und += 1
                if set(res.blocking_axes) & UNMEASURABLE_AXES:
                    n_struct += 1
        sweep[label] = {"underdetermined": n_und, "n": n,
                        "frac": round(n_und / n, 4),
                        "frac_structural": round(n_struct / n, 4)}
        print(f"  [{label:>11}] bounded+joint-drop: {n_und}/{n} = {100*n_und/n:.1f}% "
              f"(structural {100*n_struct/n:.1f}%)")

    core = sweep["p25_p75"]["frac"]
    result = {
        "metadata": {"provenance": "assumption-minimal-core",
                     "knobs": "bounded completion (measurable) AND governance/RB "
                              "bindings deleted (p=0)", "kappa": list(KAPPA)},
        "two_by_two": {
            "full_domain__granted": 0.911, "full_domain__deleted": 0.751,
            "bounded__granted": 0.569,
            "bounded__deleted": sweep["p25_p75"]["frac"],
        },
        "bounded_deleted_sweep": sweep,
        "negative_control_reference": 0.124,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    print(f"\n>>> assumption-minimal core (bounded + p=0) = {100*core:.1f}% "
          f"(neg-control reference 12.4%)")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
