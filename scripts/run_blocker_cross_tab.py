"""Cross-tab decomposition of the 1,563 underdetermined queries.

For the paper: reconcile the two numbers reported in the existing text:
  - 82.5% co-location failures (type-b: measurable axis missing for specific config)
  - 72.4% structural (type-a: never-measured axis blocks, i.e. UNMEASURABLE_AXES)

These are NOT mutually exclusive; most queries have BOTH.  This script produces the
cross-tab that shows how many queries are:

  purely_measurable : blocking_axes ⊆ measurable set  (no UNMEASURABLE_AXES in blocker)
  structural_only   : blocking_axes ⊆ UNMEASURABLE_AXES  (= old "a_only" = 274)
  mixed             : both measurable AND unmeasurable axes in blocking set

Two tie-break variants:
  measurement_dominant : purely_measurable + mixed   (= "b_present" = 82.5%)
  structural_dominant  : mixed + structural_only     (conservative: any structural blocker)

Also: skeptic-floor decomposition — drop governance + reviewer_burden from binding_axes
before to_query(), re-classify, then break down remaining blockers by axis.

Run: PYTHONNOUSERSITE=1 uv run python scripts/run_blocker_cross_tab.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from prudent_ai.analysis.empirical_prior_map import (
    UNMEASURABLE_AXES,
    grounded_thresholds,
    load_prior,
)
from prudent_ai.queries.query_prior import (
    UNIVERSAL_AXES,
    DerivedQuery,
    to_query,
)
from prudent_ai.solver import Decidability, Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.decidability import classify_query
from prudent_ai.solver.regimes import FULL
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p3")
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT

AXES = [
    "quality", "latency_p95", "throughput", "cost",
    "energy", "memory_hw", "governance", "reviewer_burden",
]

# Axes that CAN be measured in principle (present in the substrate for some configs).
MEASURABLE_AXES: frozenset[str] = frozenset({"quality", "latency_p95", "cost", "throughput"})

# Axes dropped for the skeptic-floor scenario.
SKEPTIC_DROP: frozenset[str] = frozenset({"governance", "reviewer_burden"})


def run_cross_tab(sub: CachedSubstrate, prior, th: dict) -> dict:
    """Cross-tab decomposition of underdetermined queries by blocker type."""
    n_total = prior.n
    n_und = 0

    n_purely_measurable = 0   # blocking_axes ⊆ MEASURABLE_AXES
    n_structural_only = 0     # blocking_axes ⊆ UNMEASURABLE_AXES  (= a_only)
    n_mixed = 0               # both measurable AND unmeasurable in blocking set

    for dq in prior.derived:
        q = to_query(dq, th)
        res = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
        if res.label is not Decidability.UNDERDETERMINED:
            continue
        n_und += 1

        blocking = set(res.blocking_axes)
        meas_in_blocking = blocking - UNMEASURABLE_AXES
        struct_in_blocking = blocking & UNMEASURABLE_AXES

        if struct_in_blocking and not meas_in_blocking:
            n_structural_only += 1
        elif meas_in_blocking and not struct_in_blocking:
            n_purely_measurable += 1
        else:
            # both non-empty
            n_mixed += 1

    def frac_und(x: int) -> float:
        return round(x / n_und, 4) if n_und else 0.0

    measurement_dominant = n_purely_measurable + n_mixed
    structural_dominant = n_mixed + n_structural_only

    return {
        "n_total": n_total,
        "n_underdetermined": n_und,
        "frac_underdetermined": round(n_und / n_total, 4) if n_total else 0.0,
        "cross_tab": {
            "purely_measurable_n": n_purely_measurable,
            "purely_measurable_frac_of_underdetermined": frac_und(n_purely_measurable),
            "mixed_n": n_mixed,
            "mixed_frac_of_underdetermined": frac_und(n_mixed),
            "structural_only_n": n_structural_only,
            "structural_only_frac_of_underdetermined": frac_und(n_structural_only),
        },
        "tie_break_variants": {
            "measurement_dominant_n": measurement_dominant,
            "measurement_dominant_frac": frac_und(measurement_dominant),
            "structural_dominant_n": structural_dominant,
            "structural_dominant_frac": frac_und(structural_dominant),
            "purely_measurable_n": n_purely_measurable,
            "purely_measurable_frac": frac_und(n_purely_measurable),
        },
    }


def run_skeptic_floor(sub: CachedSubstrate, prior, th: dict) -> dict:
    """Skeptic-floor: drop governance+reviewer_burden from binding axes, re-classify.

    Returns the blocking axis distribution among the remaining underdetermined queries.
    """
    n_total = prior.n
    n_und_floor = 0
    blocking_axis_counts: Counter[str] = Counter()

    # Axis combos for fine-grained breakdown.
    cost_only = 0
    cost_plus_latency = 0
    cost_plus_quality = 0

    for dq in prior.derived:
        # Drop governance + reviewer_burden from binding axes.
        new_binding = dq.binding_axes - SKEPTIC_DROP
        # Rebuild DerivedQuery with reduced binding axes.
        dq_floor = DerivedQuery(
            tau=dq.tau,
            binding_axes=frozenset(new_binding),
            title=dq.title,
            industry=dq.industry,
        )
        q = to_query(dq_floor, th)
        res = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
        if res.label is not Decidability.UNDERDETERMINED:
            continue
        n_und_floor += 1

        blocking = set(res.blocking_axes)
        for ax in blocking:
            blocking_axis_counts[ax] += 1

        # Fine-grained combos (all measurable under floor since governance/reviewer_burden removed).
        has_cost = "cost" in blocking
        has_latency = "latency_p95" in blocking
        has_quality = "quality" in blocking

        if has_cost and not has_latency and not has_quality:
            cost_only += 1
        if has_cost and has_latency:
            cost_plus_latency += 1
        if has_cost and has_quality:
            cost_plus_quality += 1

    def frac_floor(x: int) -> float:
        return round(x / n_und_floor, 4) if n_und_floor else 0.0

    def frac_total(x: int) -> float:
        return round(x / n_total, 4) if n_total else 0.0

    return {
        "n_underdetermined": n_und_floor,
        "frac_underdetermined": frac_total(n_und_floor),
        "blocking_axis_counts": dict(
            sorted(blocking_axis_counts.items(), key=lambda kv: -kv[1])
        ),
        "cost_only_n": cost_only,
        "cost_only_frac_of_floor_underdetermined": frac_floor(cost_only),
        "cost_plus_latency_n": cost_plus_latency,
        "cost_plus_latency_frac_of_floor_underdetermined": frac_floor(cost_plus_latency),
        "cost_plus_quality_n": cost_plus_quality,
        "cost_plus_quality_frac_of_floor_underdetermined": frac_floor(cost_plus_quality),
    }


def main() -> None:
    print("Loading substrate and prior…")
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, base_prior = load_prior()
    taus = sorted({d.tau for d in base_prior.derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    print(f"Prior: {base_prior.n} queries over taus={taus}")
    print("Running cross-tab decomposition…")
    ct = run_cross_tab(sub, base_prior, th)

    print("Running skeptic-floor decomposition…")
    sf = run_skeptic_floor(sub, base_prior, th)

    output = {
        "metadata": {
            "provenance": "blocker-cross-tab",
            "db_path": DB_PATH,
            "phi": PHI.value,
            "kappa": list(KAPPA),
            "regime": "full",
            "unmeasurable_axes": sorted(UNMEASURABLE_AXES),
            "measurable_axes": sorted(MEASURABLE_AXES),
            "skeptic_drop_axes": sorted(SKEPTIC_DROP),
            "cross_tab_definitions": {
                "purely_measurable": (
                    "blocking_axes ⊆ MEASURABLE_AXES — no UNMEASURABLE_AXES in blocking set; "
                    "resolvable purely by measuring cost/latency/quality"
                ),
                "structural_only": (
                    "blocking_axes ⊆ UNMEASURABLE_AXES — only structural (never-measured) axes "
                    "block; equals the old 'a_only' count"
                ),
                "mixed": (
                    "both measurable AND unmeasurable axes appear in the blocking set — "
                    "cannot be resolved by measurement alone"
                ),
            },
            "tie_break_definitions": {
                "measurement_dominant": (
                    "purely_measurable + mixed = queries where at least one measurable axis "
                    "blocks (= current 82.5% 'b_present' framing)"
                ),
                "structural_dominant": (
                    "mixed + structural_only = queries with ANY structural (unmeasurable) "
                    "blocker (conservative framing)"
                ),
            },
        },
        "cross_tab": ct["cross_tab"],
        "tie_break_variants": ct["tie_break_variants"],
        "skeptic_floor": sf,
    }

    # ---- Print key numbers ----
    n_und = ct["n_underdetermined"]
    n_total = ct["n_total"]
    c = ct["cross_tab"]
    tb = ct["tie_break_variants"]

    print("\n" + "=" * 65)
    print(f"CROSS-TAB DECOMPOSITION  (n_total={n_total}, n_und={n_und})")
    print("=" * 65)
    print(f"  purely_measurable :  {c['purely_measurable_n']:5d}  "
          f"({100*c['purely_measurable_frac_of_underdetermined']:.1f}% of underdetermined)")
    print(f"  mixed             :  {c['mixed_n']:5d}  "
          f"({100*c['mixed_frac_of_underdetermined']:.1f}% of underdetermined)")
    print(f"  structural_only   :  {c['structural_only_n']:5d}  "
          f"({100*c['structural_only_frac_of_underdetermined']:.1f}% of underdetermined)")
    print()
    print("TIE-BREAK VARIANTS:")
    print(f"  measurement_dominant (purely_meas + mixed)  : "
          f"{tb['measurement_dominant_n']:5d}  ({100*tb['measurement_dominant_frac']:.1f}%)")
    print(f"  structural_dominant  (mixed + struct_only)  : "
          f"{tb['structural_dominant_n']:5d}  ({100*tb['structural_dominant_frac']:.1f}%)")
    print(f"  purely_measurable    (no structural at all) : "
          f"{tb['purely_measurable_n']:5d}  ({100*tb['purely_measurable_frac']:.1f}%)")

    print()
    print("=" * 65)
    print(f"SKEPTIC FLOOR  (drop governance+reviewer_burden from binding)")
    print("=" * 65)
    n_sf = sf["n_underdetermined"]
    frac_sf = sf["frac_underdetermined"]
    print(f"  n_underdetermined  : {n_sf}  ({100*frac_sf:.1f}% of all {n_total})")
    print(f"  blocking axis counts:")
    for ax, cnt in sf["blocking_axis_counts"].items():
        print(f"    {ax:20s}: {cnt}")
    print(f"  cost_only          : {sf['cost_only_n']}  "
          f"({100*sf['cost_only_frac_of_floor_underdetermined']:.1f}% of floor underdetermined)")
    print(f"  cost + latency     : {sf['cost_plus_latency_n']}  "
          f"({100*sf['cost_plus_latency_frac_of_floor_underdetermined']:.1f}%)")
    print(f"  cost + quality     : {sf['cost_plus_quality_n']}  "
          f"({100*sf['cost_plus_quality_frac_of_floor_underdetermined']:.1f}%)")
    print("=" * 65)

    # Save output.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "blocker_cross_tab.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
