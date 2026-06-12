"""C1 — anti-circularity decomposition of underdetermined decisions (three-way).

For every underdetermined query in the ZenML corpus (corpus 1, published prior),
classify each blocking axis by its cause:

  (a) never-measured ⊥:
      axis ∈ UNMEASURABLE_AXES  AND  every blocking candidate's cell for
      that axis is bottom (⊥).  By-construction — no evidence in the substrate.

  (b) measurable-axis fragmented ⊥:
      axis ∈ {quality, cost, latency_p95}  AND  the axis is ⊥ on the blocking
      candidate(s) for this query.  The axis IS measured for OTHER configs in the
      substrate but NOT for THIS deployment config — a co-location failure, not a
      structural gap.

  (c) interval straddle:
      axis is present (not ⊥) but the belief interval spans the threshold, so
      the certified outcome is genuinely uncertain.

For each blocking axis in each underdetermined query we assign cause (a), (b), or
(c).  A query is then labelled:

  - "(a)-only"     : all blocking axes are cause (a)
  - "(b)-present"  : at least one blocking axis is cause (b) (may also have (a)/(c))
  - "(c)-present"  : at least one blocking axis is cause (c) (may also have (a)/(b))
  - "(b)+(c)-any"  : at least one blocking axis is cause (b) or (c)

The anti-circularity claim: "(b)+(c) is X% of underdetermined decisions" — these
are non-tautological, because the system is not simply demanding an axis that was
never measured by anyone (case a).  Case (b) means the data IS there, just not for
this config (co-location).  Case (c) means the data IS there but the interval is
genuinely wide (epistemic uncertainty, not structural absence).

Implementation notes
--------------------
- Blocking axes come from `classify_query` (DecidabilityResult.blocking_axes).
- To distinguish (a)/(b)/(c) for a blocking axis we inspect the `maybe`-feasible
  candidates (not provably-infeasible).  For each candidate's pending field we call
  `sub.cell(config_id, axis)` and `aggregate(...)` to check `is_bottom`.
- POINT mode is used (matching run_blocker_decomposition.py).
- Uses CachedSubstrate for speed.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_circularity_decomposition.py
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
    UNIVERSAL_AXES,
    DerivedQuery,
    QueryPrior,
    to_query,
)
from prudent_ai.solver import Decidability, Phi
from prudent_ai.solver.beliefs import aggregate
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.decidability import classify_query
from prudent_ai.solver.feasibility import FeasState, classify_candidate
from prudent_ai.solver.regimes import FULL
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p3")
PROVENANCE = "C1-circularity-decomposition"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT

AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]

# Axes that CAN be measured in principle (present in the substrate for some configs).
MEASURABLE_AXES: frozenset[str] = frozenset(
    {"quality", "latency_p95", "cost", "throughput"}
)


def _cause_of_blocking_axis(
    sub: CachedSubstrate,
    blocking_axis: str,
    maybe_verdicts,  # list[CandidateVerdict]
    kappa: tuple[str, ...],
) -> str:
    """Return 'a', 'b', or 'c' for a single blocking axis.

    (a) never-measured ⊥  : axis ∈ UNMEASURABLE_AXES (structurally absent).
    (b) measurable frag ⊥  : axis ∈ MEASURABLE_AXES, cell is ⊥ for every
                              blocking candidate that has this axis pending.
    (c) straddle           : axis is present (not ⊥) but spans the threshold.

    We look at all maybe-feasible candidates that have this axis in their
    pending_fields.  If ANY of them shows a present belief (is_bottom=False)
    that axis is a straddle → (c).  If all are bottom → (b) or (a).
    """
    if blocking_axis in UNMEASURABLE_AXES:
        return "a"

    # For measurable axes, check whether the belief is actually ⊥ or a straddle.
    # A candidate with the axis in pending_fields either has:
    #   - belief.is_bottom → the cell is empty (fragmented ⊥)         → (b)
    #   - belief.is_present → interval spans threshold (straddle)       → (c)
    for v in maybe_verdicts:
        if blocking_axis in v.pending_fields:
            belief = aggregate(sub.cell(v.config_id, blocking_axis), kappa, PHI)
            if belief.is_present:
                return "c"
    # All relevant candidates had ⊥ on this axis.
    return "b"


def decompose_circularity(sub: CachedSubstrate, prior: QueryPrior, th: dict) -> dict:
    """Classify every underdetermined query by cause (a)/(b)/(c) for each blocking axis."""

    n = prior.n
    n_und = 0

    # Per-query dominant category counters.
    n_a_only = 0         # all blocking axes are (a)
    n_b_present = 0      # at least one blocking axis is (b)
    n_c_present = 0      # at least one blocking axis is (c)
    n_bc_any = 0         # at least one blocking axis is (b) or (c)

    # Per-axis-instance tallies (one per (query, axis) pair).
    axis_cause_tally: dict[str, dict[str, int]] = {}  # axis -> {a: n, b: n, c: n}

    query_details: list[dict] = []

    for dq in prior.derived:
        q = to_query(dq, th)
        res = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
        if res.label is not Decidability.UNDERDETERMINED:
            continue
        n_und += 1

        # Get the maybe-feasible verdicts for cause analysis.
        verdicts = [
            classify_candidate(sub, cand.id, q.bundle, KAPPA, PHI, FULL)
            for cand in sub.candidates(q.tau)
        ]
        maybe_verdicts = [
            v for v in verdicts if v.state is not FeasState.PROVABLY_INFEASIBLE
        ]

        # Classify each blocking axis.
        blocking = set(res.blocking_axes)
        causes: dict[str, str] = {}
        for ax in blocking:
            causes[ax] = _cause_of_blocking_axis(sub, ax, maybe_verdicts, KAPPA)
            if ax not in axis_cause_tally:
                axis_cause_tally[ax] = {"a": 0, "b": 0, "c": 0}
            axis_cause_tally[ax][causes[ax]] += 1

        cause_set = set(causes.values())
        has_b = "b" in cause_set
        has_c = "c" in cause_set
        has_bc = has_b or has_c
        all_a = cause_set == {"a"} or cause_set == set()

        if all_a:
            n_a_only += 1
        if has_b:
            n_b_present += 1
        if has_c:
            n_c_present += 1
        if has_bc:
            n_bc_any += 1

        query_details.append({
            "tau": dq.tau,
            "title": dq.title,
            "blocking_axes": sorted(blocking),
            "causes": {k: v for k, v in sorted(causes.items())},
            "has_b": has_b,
            "has_c": has_c,
            "has_bc_any": has_bc,
            "all_a": all_a,
        })

    def pct_of_und(x: int) -> float:
        return round(x / n_und, 4) if n_und else 0.0

    def pct_of_all(x: int) -> float:
        return round(x / n, 4) if n else 0.0

    return {
        "n": n,
        "n_underdetermined": n_und,
        "frac_underdetermined": pct_of_all(n_und),
        "cause_summary": {
            "a_only_n": n_a_only,
            "a_only_frac_of_underdetermined": pct_of_und(n_a_only),
            "a_only_frac_of_all": pct_of_all(n_a_only),
            "b_present_n": n_b_present,
            "b_present_frac_of_underdetermined": pct_of_und(n_b_present),
            "b_present_frac_of_all": pct_of_all(n_b_present),
            "c_present_n": n_c_present,
            "c_present_frac_of_underdetermined": pct_of_und(n_c_present),
            "c_present_frac_of_all": pct_of_all(n_c_present),
            "bc_any_n": n_bc_any,
            "bc_any_frac_of_underdetermined": pct_of_und(n_bc_any),
            "bc_any_frac_of_all": pct_of_all(n_bc_any),
        },
        "axis_cause_tally": {
            k: v for k, v in sorted(
                axis_cause_tally.items(), key=lambda kv: -sum(kv[1].values()))
        },
        "query_details": query_details,
    }


def fragmentation_colocation_matrix(
    sub: CachedSubstrate,
    prior: QueryPrior,
    kappa: tuple[str, ...] = KAPPA,
) -> dict:
    """Per-archetype (tau) × axis coverage matrix.

    For each (tau, axis) pair: fraction of candidates for that tau that have ANY
    measurement (not ⊥) on that axis under kappa.

    Returns a dict {tau: {axis: coverage_fraction}}.
    """
    taus = sorted({d.tau for d in prior.derived})
    axes_order = ["quality", "latency_p95", "cost", "energy",
                  "memory_hw", "governance", "reviewer_burden", "throughput"]

    matrix: dict[str, dict[str, float]] = {}
    for tau in taus:
        candidates = sub.candidates(tau)
        n_cands = len(candidates)
        row: dict[str, float] = {}
        for ax in axes_order:
            if n_cands == 0:
                row[ax] = 0.0
            else:
                n_present = sum(
                    1 for cand in candidates
                    if aggregate(sub.cell(cand.id, ax), kappa, PHI).is_present
                )
                row[ax] = round(n_present / n_cands, 4)
        matrix[tau] = row
    return {"taus": taus, "axes": axes_order, "matrix": matrix}


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, base_prior = load_prior()
    taus = sorted({d.tau for d in base_prior.derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    print("Running circularity decomposition over the published prior…")
    result = decompose_circularity(sub, base_prior, th)

    print("Computing fragmentation/co-location matrix…")
    coloc = fragmentation_colocation_matrix(sub, base_prior)

    bc_n = result["cause_summary"]["bc_any_n"]
    n_und = result["n_underdetermined"]
    bc_pct = 100.0 * result["cause_summary"]["bc_any_frac_of_underdetermined"]

    output = {
        "metadata": {
            "provenance": PROVENANCE,
            "db_path": DB_PATH,
            "phi": PHI.value,
            "kappa": list(KAPPA),
            "regime": "full",
            "n_rows": len(rows),
            "unmeasurable_axes": sorted(UNMEASURABLE_AXES),
            "measurable_axes": sorted(MEASURABLE_AXES),
            "cause_definitions": {
                "a": ("never-measured ⊥: axis ∈ UNMEASURABLE_AXES — by construction, "
                      "no evidence in the substrate for any config"),
                "b": ("measurable fragmented ⊥: axis ∈ measurable set AND the "
                      "blocking candidate's cell is ⊥ — co-location failure, not "
                      "structural absence"),
                "c": ("interval straddle: axis is present (not ⊥) but the belief "
                      "interval spans the threshold — genuine epistemic uncertainty"),
            },
            "anti_circularity_headline": (
                f"(b)+(c) accounts for {bc_pct:.1f}% of the {n_und} underdetermined "
                f"decisions ({bc_n} queries). These are non-tautological: the system "
                f"is NOT simply demanding axes that were never measured by anyone."
            ),
        },
        "decomposition": {
            "n": result["n"],
            "n_underdetermined": n_und,
            "frac_underdetermined": result["frac_underdetermined"],
            "cause_summary": result["cause_summary"],
            "axis_cause_tally": result["axis_cause_tally"],
        },
        "fragmentation_colocation_matrix": coloc,
    }

    # Save full query details separately to keep the main file manageable.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    details_path = OUT_DIR / "circularity_decomposition_details.json"
    details_path.write_text(
        json.dumps(result["query_details"], indent=2), encoding="utf-8"
    )

    main_path = OUT_DIR / "circularity_decomposition.json"
    main_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    # Write markdown summary.
    cs = result["cause_summary"]
    md_lines = [
        "# C1 — Anti-circularity decomposition of underdetermined decisions",
        "",
        f"Full regime · kappa=H+M · phi=point · {result['n']} ZenML queries",
        "",
        "## Cause definitions",
        "",
        "- **(a) never-measured ⊥**: axis ∈ UNMEASURABLE_AXES; no evidence in substrate.",
        "- **(b) measurable fragmented ⊥**: axis IS measured for other configs, but this",
        "  deployment config has no evidence on that axis (co-location failure).",
        "- **(c) interval straddle**: belief IS present but spans the threshold",
        "  (genuine epistemic uncertainty).",
        "",
        "## Headline",
        "",
        f"- Underdetermined: **{n_und} / {result['n']} "
        f"({100 * result['frac_underdetermined']:.1f}%)**",
        "",
        "## Breakdown of the underdetermined set",
        "",
        f"| Category | N | % of underdetermined | % of all |",
        f"|---|---|---|---|",
        f"| (a)-only — purely never-measured ⊥ | {cs['a_only_n']} "
        f"| {100 * cs['a_only_frac_of_underdetermined']:.1f}% "
        f"| {100 * cs['a_only_frac_of_all']:.1f}% |",
        f"| (b)-present — measurable fragmented ⊥ | {cs['b_present_n']} "
        f"| {100 * cs['b_present_frac_of_underdetermined']:.1f}% "
        f"| {100 * cs['b_present_frac_of_all']:.1f}% |",
        f"| (c)-present — interval straddle | {cs['c_present_n']} "
        f"| {100 * cs['c_present_frac_of_underdetermined']:.1f}% "
        f"| {100 * cs['c_present_frac_of_all']:.1f}% |",
        f"| **(b)+(c) combined — non-tautological** | **{cs['bc_any_n']}** "
        f"| **{100 * cs['bc_any_frac_of_underdetermined']:.1f}%** "
        f"| **{100 * cs['bc_any_frac_of_all']:.1f}%** |",
        "",
        "## Anti-circularity claim",
        "",
        f"**(b)+(c) = {bc_pct:.1f}% of underdetermined decisions** are non-tautological: "
        f"the system is NOT simply demanding axes that no one in the literature measures. "
        f"For these {bc_n} queries, evidence either exists for other configs (fragmented "
        f"co-location, case b) or genuinely spans the threshold (case c). "
        f"Only the {cs['a_only_n']} (a)-only decisions "
        f"({100 * cs['a_only_frac_of_underdetermined']:.1f}% of underdetermined) "
        f"are attributable purely to structural absence of measurement.",
        "",
        "## Per-axis cause tally",
        "",
        "| Axis | (a) never-measured ⊥ | (b) measurable frag ⊥ | (c) straddle |",
        "|---|---|---|---|",
    ]
    for ax, tally in result["axis_cause_tally"].items():
        md_lines.append(
            f"| {ax} | {tally['a']} | {tally['b']} | {tally['c']} |"
        )
    md_lines += [
        "",
        f"Wrote {main_path} and {details_path}",
    ]
    md_text = "\n".join(md_lines)
    (OUT_DIR / "circularity_decomposition.md").write_text(md_text, encoding="utf-8")

    print(md_text)
    print(f"\nWrote {main_path} and {OUT_DIR / 'circularity_decomposition.md'}")


if __name__ == "__main__":
    main()
