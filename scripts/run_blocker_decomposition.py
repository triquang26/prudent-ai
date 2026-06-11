"""E6 — cost-vs-structural decomposition of the underdetermination headline.

Round-4 review, W3/Q1: "What fraction of the 91.1% is attributable SOLELY to cost
co-location/fragmentation (a cheaply-fixable data-integration issue, acq cost
0.05) versus to the genuinely never-measured axes (governance, reviewer_burden,
memory_hw, energy, throughput)? Give the verdict breakdown holding cost
DETERMINED, to isolate the structural component."

For each UNDERDETERMINED query (FULL regime, published classifier), classify its
blocking_axes:
  - cost_only          : B == {cost}                  (granting cost resolves it)
  - structural_only    : B subset of UNMEASURABLE, no cost, no other-measurable
  - cost_plus_structural (mixed): cost AND a never-measured axis both block
  - other              : a non-cost, non-blind-spot measurable axis blocks
and report the COST-DETERMINED RESIDUAL = fraction still underdetermined if cost
is granted = |{ B - {cost} != empty }| / n, split into structural vs other.

Run on TWO priors:
  - published   : the 91.1% headline taxonomy. Expectation: granting cost still
                  leaves ~72% blocked on never-measured axes -> headline is
                  STRUCTURAL, cost-co-location piece is small.
  - joint_drop  : the 75.1% skeptical floor (governance + reviewer_burden mappings
                  deleted). Expectation: granting cost drops it a lot -> the FLOOR
                  (not the headline) is what leans on cost. Shown honestly.

Frozen db read-only via the immutable interface; nothing imputed; no mutation.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_blocker_decomposition.py
"""

from __future__ import annotations

import json
from pathlib import Path

from prudent_ai.analysis.empirical_prior_map import (
    UNMEASURABLE_AXES,
    grounded_thresholds,
    load_prior,
)
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
PROVENANCE = "E6-blocker-decomposition"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT

AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]

# axes dropped for the joint-drop (skeptical floor) prior
_DROP_AXES = {"governance", "reviewer_burden"}


def _tags(row, field):
    return [t.strip() for t in (row.get(field) or "").split(",") if t.strip()]


def derive_joint_drop(row: dict) -> DerivedQuery:
    """Published taxonomy MINUS governance and reviewer_burden (tags + industry rule)."""
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
    # industry governance rule is dropped under joint_drop
    return DerivedQuery(tau=tau, binding_axes=frozenset(axes),
                        title=(row.get("title") or "")[:80],
                        industry=(row.get("industry") or "").strip())


def decompose(sub, prior: QueryPrior, th) -> dict:
    """One pass: classify every query, decompose the underdetermined blockers."""
    n = prior.n
    cats = dict.fromkeys(
        ("cost_only", "structural_only", "cost_plus_structural", "other"), 0)
    n_und = 0
    n_residual = 0           # underdetermined with a non-cost blocker (cost granted)
    n_residual_structural = 0  # ... where a non-cost blocker is never-measured
    n_residual_other = 0       # ... where the residual is only measurable non-cost
    blocker_tally: dict[str, int] = {}
    for dq in prior.derived:
        q = to_query(dq, th)
        res = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
        if res.label is not Decidability.UNDERDETERMINED:
            continue
        n_und += 1
        b = set(res.blocking_axes)
        for a in b:
            blocker_tally[a] = blocker_tally.get(a, 0) + 1
        has_cost = "cost" in b
        struct = b & UNMEASURABLE_AXES
        other_meas = b - {"cost"} - UNMEASURABLE_AXES
        # mutually-exclusive category
        if b == {"cost"}:
            cats["cost_only"] += 1
        elif has_cost and struct:
            cats["cost_plus_structural"] += 1
        elif struct and not has_cost and not other_meas:
            cats["structural_only"] += 1
        else:
            cats["other"] += 1
        # cost-determined residual: what survives granting cost
        residual = b - {"cost"}
        if residual:
            n_residual += 1
            if residual & UNMEASURABLE_AXES:
                n_residual_structural += 1
            else:
                n_residual_other += 1

    def fr(x):
        return round(x / n, 4) if n else 0.0

    def fru(x):
        return round(x / n_und, 4) if n_und else 0.0

    return {
        "n": n,
        "underdetermined": n_und,
        "frac_underdetermined": fr(n_und),
        "categories_of_underdetermined": cats,
        "cost_only_resolved_by_granting_cost": cats["cost_only"],
        "cost_determined_residual": {
            "n": n_residual,
            "frac_of_all": fr(n_residual),
            "frac_of_underdetermined": fru(n_residual),
            "structural_n": n_residual_structural,
            "structural_frac_of_all": fr(n_residual_structural),
            "other_measurable_n": n_residual_other,
            "other_measurable_frac_of_all": fr(n_residual_other),
        },
        "blockers": dict(sorted(blocker_tally.items(),
                                key=lambda kv: -kv[1])),
    }


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, base_prior = load_prior()
    taus = sorted({d.tau for d in base_prior.derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    published = decompose(sub, base_prior, th)
    joint = decompose(sub, QueryPrior(derived=[derive_joint_drop(r) for r in rows]), th)

    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH,
                     "phi": PHI.value, "kappa": list(KAPPA), "regime": "full",
                     "n_rows": len(rows),
                     "unmeasurable_axes": sorted(UNMEASURABLE_AXES),
                     "note": "cost is NOT in unmeasurable_axes; it is acquirable "
                             "(acq cost 0.05). cost-determined residual = fraction "
                             "still underdetermined if cost were granted as known."},
        "published_prior": published,
        "joint_drop_prior": joint,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "blocker_decomposition.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    def block(tag, d):
        cd = d["cost_determined_residual"]
        lines = [
            f"## {tag} prior",
            "",
            f"- underdetermined: {d['underdetermined']}/{d['n']} = "
            f"{100 * d['frac_underdetermined']:.1f}%",
            "- decomposition of the underdetermined set:",
            f"    - cost-only (granting cost resolves):        "
            f"{d['categories_of_underdetermined']['cost_only']}",
            f"    - structural-only (never-measured axis only): "
            f"{d['categories_of_underdetermined']['structural_only']}",
            f"    - cost + structural (mixed):                 "
            f"{d['categories_of_underdetermined']['cost_plus_structural']}",
            f"    - other measurable:                          "
            f"{d['categories_of_underdetermined']['other']}",
            "",
            f"- **cost-determined residual** (still underdetermined if cost granted): "
            f"**{100 * cd['frac_of_all']:.1f}% of all** "
            f"({100 * cd['frac_of_underdetermined']:.1f}% of underdetermined)",
            f"    - of which structural (never-measured axis): "
            f"**{100 * cd['structural_frac_of_all']:.1f}% of all**",
            f"    - of which other measurable:                 "
            f"{100 * cd['other_measurable_frac_of_all']:.1f}% of all",
            f"- cost-resolvable (cost-only) share: "
            f"{100 * (d['cost_only_resolved_by_granting_cost'] / d['n']):.1f}% of all",
            "",
        ]
        return lines

    md = ["# E6 — cost-vs-structural decomposition of the headline", "",
          "FULL regime, kappa=H+M, published classifier. blocking_axes is the "
          "complete blocker set. cost is acquirable (0.05) and NOT a structural "
          "blind-spot axis.", ""]
    md += block("Published (91.1% headline)", published)
    md += block("Joint-drop (75.1% skeptical floor)", joint)
    (OUT_DIR / "blocker_decomposition.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\nWrote {OUT_DIR / 'blocker_decomposition.json'} and .md")


if __name__ == "__main__":
    main()
