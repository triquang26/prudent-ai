"""E10 — completion-semantics sensitivity (bounded-prior headline).

Round-6 review, W1/Q1: the decidability criterion quantifies over ALL completions
with a missing (⊥) cell ranging over its ENTIRE admissible domain --- an adversarial
reading under which almost any hidden binding axis forces underdetermination. The
reviewer asks: separate "underdetermined because adversarial completions exist" from
"underdetermined under any reasonable belief" by varying the completion semantics.

We do exactly that. The QUERIES and thresholds are held fixed; only the COMPLETION of
each ⊥ cell changes. For a ⊥ cell on a MEASURABLE axis (quality, cost, latency --- the
axes with real coverage) we restrict the completion to a bounded interval drawn from
the corpus-wide observed distribution of that axis, and sweep the bound width:
  point(p50)  ->  [p40,p60]  ->  [p25,p75]  ->  [p10,p90]  ->  full domain (adversarial).
The never-measured axes (governance, reviewer_burden, memory_hw, energy, throughput ---
UNMEASURABLE_AXES, zero observed values anywhere) have NO plausible range to restrict,
so they stay ⊥ at every width. A query is then underdetermined under Phi.INTERVAL only
if some cell's bounded interval genuinely straddles its threshold.

Expectation: the headline falls from the full-domain (adversarial) reference as the
bound tightens, but PLATEAUS at the structural floor (the governance/reviewer-driven
core that cannot be bounded). This isolates the any-reasonable-belief core --- a
natural generalization of E6 (granting cost = the point-bound extreme on one axis).

Frozen db read-only via the immutable interface; the bounded belief is a labelled
SENSITIVITY, never an ingested row; nothing is mutated; OUR procedure still never
imputes (this is a criterion-sensitivity, reported alongside 91.1%, not a new headline).

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_bounded_completion.py
"""

from __future__ import annotations

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
OUT_DIR = Path("outputs/p3")
PROVENANCE = "E10-bounded-completion"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.INTERVAL  # completion semantics live in the interval reading

AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]
# axes with real coverage that a bounded-prior reading can restrict; the
# never-measured UNMEASURABLE_AXES have no observed range and stay ⊥.
BOUNDED_AXES = ("quality", "cost", "latency_p95")

# (label, lo_pct, hi_pct); None,None = full domain (no bounding -> adversarial ⊥)
WIDTHS = [
    ("point_p50", 50, 50),
    ("p40_p60", 40, 60),
    ("p25_p75", 25, 75),
    ("p10_p90", 10, 90),
    ("full_domain", None, None),
]

_Obs = namedtuple("_Obs", ["confidence", "value_num"])


def _pct(sorted_vals: list[float], p: int) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo_i, hi_i = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    frac = k - lo_i
    return sorted_vals[lo_i] * (1 - frac) + sorted_vals[hi_i] * frac


class BoundedCompletionSubstrate:
    """⊥ cells on bounded axes complete over [lo,hi]; else pass through (stay ⊥)."""

    def __init__(self, sub, bounds: dict[str, tuple[float, float]]) -> None:
        self._sub = sub
        self._bounds = bounds  # axis -> (lo, hi); absent axis = not bounded

    def candidates(self, tau):
        return self._sub.candidates(tau)

    def cell(self, x, a):
        real = self._sub.cell(x, a)
        if real:
            return real
        b = self._bounds.get(a)
        if b is None:
            return []  # ⊥ stays ⊥ (never-measured axis, or full-domain reference)
        lo, hi = b
        return [_Obs("M", lo), _Obs("M", hi)]

    def required_fields(self, bundle):
        return self._sub.required_fields(bundle)

    def __getattr__(self, name):
        return getattr(self._sub, name)


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, prior = load_prior()
    taus = sorted({d.tau for d in prior.derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    # corpus-wide observed values per bounded axis (dedup configs across taus)
    seen: set[str] = set()
    vals: dict[str, list[float]] = {a: [] for a in BOUNDED_AXES}
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

    sweep = {}
    for label, plo, phi_pct in WIDTHS:
        if plo is None:
            bounds: dict[str, tuple[float, float]] = {}  # full domain: no bounding
        else:
            bounds = {a: (_pct(vals[a], plo), _pct(vals[a], phi_pct))
                      for a in BOUNDED_AXES if vals[a]}
        wsub = BoundedCompletionSubstrate(sub, bounds)
        n_und = n_struct = 0
        for dq in prior.derived:
            q = to_query(dq, th)
            res = classify_query(wsub, q, kappa=KAPPA, phi=PHI, regime=FULL)
            if res.label is Decidability.UNDERDETERMINED:
                n_und += 1
                if set(res.blocking_axes) & UNMEASURABLE_AXES:
                    n_struct += 1
        n = prior.n
        sweep[label] = {
            "underdetermined": n_und, "n": n,
            "frac_underdetermined": round(n_und / n, 4),
            "frac_structural_attributable": round(n_struct / n, 4),
        }
        print(f"{label:>12}: underdetermined {n_und}/{n} = "
              f"{100 * n_und / n:.1f}%  (blind-spot-attributable "
              f"{100 * n_struct / n:.1f}%)")

    adversarial = sweep["full_domain"]["frac_underdetermined"]
    floor = sweep["point_p50"]["frac_underdetermined"]
    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH,
                     "phi": PHI.value, "kappa": list(KAPPA), "regime": "full",
                     "bounded_axes": list(BOUNDED_AXES),
                     "unmeasurable_axes": sorted(UNMEASURABLE_AXES),
                     "note": "queries/thresholds fixed; only the completion of each ⊥ "
                             "cell varies. never-measured axes have no observed range "
                             "and stay ⊥ at every width (the structural floor)."},
        "axis_bounds_pctized": {a: {p: round(_pct(vals[a], p), 4)
                                    for p in (10, 25, 40, 50, 60, 75, 90)}
                                for a in BOUNDED_AXES if vals[a]},
        "sweep": sweep,
        "adversarial_full_domain": adversarial,
        "bounded_floor_point": floor,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "bounded_completion.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# E10 — completion-semantics sensitivity (bounded-prior headline)", "",
             "Queries and thresholds fixed; only the completion of each ⊥ cell varies "
             "(Phi.INTERVAL). Never-measured axes stay ⊥ at every width.", "",
             "| completion of ⊥ measurable cells | underdetermined | "
             "blind-spot-attributable |", "|---|---|---|"]
    for label, _, _ in WIDTHS:
        s = sweep[label]
        lines.append(f"| {label} | {s['underdetermined']}/{s['n']} = "
                     f"{100 * s['frac_underdetermined']:.1f}% | "
                     f"{100 * s['frac_structural_attributable']:.1f}% |")
    lines += ["",
              f"- adversarial (full-domain) reference: {100 * adversarial:.1f}%",
              f"- bounded floor (point completion on measurable axes): "
              f"{100 * floor:.1f}% --- the structural core that no bounding removes, "
              "because never-measured axes have no plausible range."]
    (OUT_DIR / "bounded_completion.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n" + "\n".join(lines[-3:]))
    print(f"\nWrote {OUT_DIR / 'bounded_completion.json'} and .md")


if __name__ == "__main__":
    main()
