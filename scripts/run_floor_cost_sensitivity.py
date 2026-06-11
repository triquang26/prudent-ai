"""E8 — cost-threshold sensitivity of the 75.1% skeptical floor.

Round-4 review, Q3: "How sensitive is the 75.1% skeptical floor to the
threshold-grounding for cost specifically, given cost becomes the modal blocker
there?" The joint-drop prior (governance + reviewer_burden deleted) is the floor;
its modal blocker is cost. Re-ground the COST threshold at percentiles
{p25, p40, p50, p60, p75} (every other axis stays at the published p50) and
recompute the underdetermined fraction.

Frozen db read-only via the immutable interface; no mutation; nothing imputed.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_floor_cost_sensitivity.py
"""

from __future__ import annotations

import json
from pathlib import Path

from prudent_ai.analysis.decidability_map import observed_thresholds
from prudent_ai.analysis.empirical_prior_map import load_prior
from prudent_ai.queries.query_prior import (
    ARCHETYPE_MAP,
    DEFAULT_TAU,
    TAG_TO_AXIS,
    UNIVERSAL_AXES,
    DerivedQuery,
    QueryPrior,
    to_query,
)
from prudent_ai.solver import Decidability, Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.decidability import classify_query
from prudent_ai.solver.regimes import FULL
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p3")
PROVENANCE = "E8-floor-cost-sensitivity"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
BASE_PCT = 50
COST_PCTS = (25, 40, 50, 60, 75)

AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]
_DROP_AXES = {"governance", "reviewer_burden"}


def _tags(row, field):
    return [t.strip() for t in (row.get(field) or "").split(",") if t.strip()]


def derive_joint_drop(row: dict) -> DerivedQuery:
    app = _tags(row, "application_tags")
    tech = _tags(row, "techniques_tags")
    all_tags = set(app) | set(tech)
    tau = DEFAULT_TAU
    for t in app:
        if t in ARCHETYPE_MAP:
            tau = ARCHETYPE_MAP[t]
            break
    axes = set(UNIVERSAL_AXES)
    for t in all_tags:
        if t in TAG_TO_AXIS and TAG_TO_AXIS[t] not in _DROP_AXES:
            axes.add(TAG_TO_AXIS[t])
    return DerivedQuery(tau=tau, binding_axes=frozenset(axes),
                        title=(row.get("title") or "")[:80],
                        industry=(row.get("industry") or "").strip())


def thresholds_with_cost_pct(sub, taus, cost_pct: int) -> dict[tuple[str, str], float]:
    """Ground every axis at p50 EXCEPT cost, grounded at *cost_pct*."""
    th: dict[tuple[str, str], float] = {}
    for tau in taus:
        for axis in AXES:
            pct = cost_pct if axis == "cost" else BASE_PCT
            pcts = observed_thresholds(sub, tau, axis, (pct,), KAPPA)
            if pct in pcts:
                th[(tau, axis)] = pcts[pct]
    return th


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, base_prior = load_prior()
    taus = sorted({d.tau for d in base_prior.derived})
    joint = QueryPrior(derived=[derive_joint_drop(r) for r in rows])

    sweep = {}
    for cp in COST_PCTS:
        th = thresholds_with_cost_pct(sub, taus, cp)
        n_und = 0
        for dq in joint.derived:
            q = to_query(dq, th)
            res = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
            if res.label is Decidability.UNDERDETERMINED:
                n_und += 1
        frac = n_und / joint.n
        sweep[f"cost_p{cp}"] = {"underdetermined": n_und, "n": joint.n,
                                "frac": round(frac, 4)}
        print(f"cost p{cp:>2}: {n_und}/{joint.n} = {100 * frac:.1f}% underdetermined")

    fracs = [v["frac"] for v in sweep.values()]
    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH,
                     "phi": PHI.value, "kappa": list(KAPPA), "regime": "full",
                     "prior": "joint_drop (governance+reviewer_burden deleted)",
                     "base_pct_other_axes": BASE_PCT, "cost_pcts": list(COST_PCTS)},
        "sweep": sweep,
        "floor_range": {"min": round(min(fracs), 4), "max": round(max(fracs), 4)},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "floor_cost_sensitivity.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# E8 — cost-threshold sensitivity of the joint-drop floor", "",
             "Joint-drop prior (governance+reviewer_burden deleted); cost grounded "
             "at each percentile, other axes at p50; FULL regime.", "",
             "| cost percentile | underdetermined |", "|---|---|"]
    for cp in COST_PCTS:
        v = sweep[f"cost_p{cp}"]
        lines.append(f"| p{cp} | {v['underdetermined']}/{v['n']} = "
                     f"{100 * v['frac']:.1f}% |")
    lines.append("")
    lines.append(f"- floor range across cost percentiles p25–p75: "
                 f"**{100 * min(fracs):.1f}% – {100 * max(fracs):.1f}%**")
    (OUT_DIR / "floor_cost_sensitivity.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n" + "\n".join(lines[-2:]))
    print(f"\nWrote {OUT_DIR / 'floor_cost_sensitivity.json'} and .md")


if __name__ == "__main__":
    main()
