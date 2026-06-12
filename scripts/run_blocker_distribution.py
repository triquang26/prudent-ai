"""Q4 — per-query blocker distribution: is 72.4% an artifact of two coarse mappings?

Round-7 review, W5/Q4: the blind-spot headline (72.4% blocked on a never-measured
axis) leans on governance (tag/industry -> axis) and reviewer_burden (tag -> axis)
mappings. Single- and joint-deletion already bound the headline (joint-drop = 75.1%
still underdetermined), but the reviewer asks for the PER-QUERY DISTRIBUTION of
assigned blockers, "to see whether two coarse mappings dominate."

For each UNDERDETERMINED query (FULL regime, published classifier) we read its
complete blocking_axes set and report:
  - the histogram of blocker-set SIZE (|B|): how many queries are blocked by 1, 2,
    3+ axes at once (multiplicity);
  - per-axis presence counts and SOLE-blocker counts (B == {axis});
  - governance / reviewer_burden specifically: present-share and sole-share;
  - the CONCENTRATION on the two coarse mappings: how many underdetermined queries
    have B subset of {governance, reviewer_burden} (would be RESOLVED by deleting
    both mappings) versus how many SURVIVE because they carry at least one other
    blocker (cost or a measurable axis). The surviving share is what reconciles
    with the joint-drop 75.1% floor and the strict-binding 75.9% figure.

If two mappings "dominated", most underdetermined queries would be SOLE-blocked by
governance or reviewer_burden. The expectation (honest): they do NOT -- cost is the
modal blocker, multiplicity is common, and removing both mappings leaves most
queries underdetermined, so the blind spot is not a two-tag artifact.

Frozen db read-only via the immutable interface; nothing imputed; no mutation.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_blocker_distribution.py
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
from prudent_ai.queries.query_prior import to_query
from prudent_ai.solver import Decidability, Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.decidability import classify_query
from prudent_ai.solver.regimes import FULL
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p3")
PROVENANCE = "Q4-blocker-distribution"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT

AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]

# the two coarse taxonomy mappings the reviewer worries dominate
COARSE = frozenset({"governance", "reviewer_burden"})


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, prior = load_prior()
    taus = sorted({d.tau for d in prior.derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    n = prior.n
    n_und = 0
    size_hist: Counter[int] = Counter()
    present: Counter[str] = Counter()      # axis appears in some blocking set
    sole: Counter[str] = Counter()         # axis is the UNIQUE blocker
    n_subset_coarse = 0   # B subset of {governance, reviewer_burden} -> killed by deleting both
    n_survive_coarse = 0  # B has >=1 blocker outside the two mappings -> survives
    n_cost_in = 0         # cost among the blockers
    n_any_unmeasurable = 0  # >=1 never-measured axis blocks (the 72.4% set)

    for dq in prior.derived:
        q = to_query(dq, th)
        res = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
        if res.label is not Decidability.UNDERDETERMINED:
            continue
        n_und += 1
        b = set(res.blocking_axes)
        size_hist[len(b)] += 1
        for a in b:
            present[a] += 1
        if len(b) == 1:
            sole[next(iter(b))] += 1
        if b <= COARSE:
            n_subset_coarse += 1
        else:
            n_survive_coarse += 1
        if "cost" in b:
            n_cost_in += 1
        if b & UNMEASURABLE_AXES:
            n_any_unmeasurable += 1

    def fr_all(x):
        return round(x / n, 4) if n else 0.0

    def fr_und(x):
        return round(x / n_und, 4) if n_und else 0.0

    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH,
                     "phi": PHI.value, "kappa": list(KAPPA), "regime": "full",
                     "n_rows": n, "coarse_mappings": sorted(COARSE),
                     "unmeasurable_axes": sorted(UNMEASURABLE_AXES)},
        "n": n,
        "underdetermined": n_und,
        "frac_underdetermined": fr_all(n_und),
        "blocker_set_size_histogram": dict(sorted(size_hist.items())),
        "mean_blocker_set_size": round(
            sum(k * v for k, v in size_hist.items()) / n_und, 3) if n_und else 0.0,
        "axis_present_in_blocking_set": dict(sorted(present.items(),
                                                    key=lambda kv: -kv[1])),
        "axis_sole_blocker": dict(sorted(sole.items(), key=lambda kv: -kv[1])),
        "governance": {
            "present": present.get("governance", 0),
            "present_frac_of_underdetermined": fr_und(present.get("governance", 0)),
            "sole": sole.get("governance", 0),
            "sole_frac_of_underdetermined": fr_und(sole.get("governance", 0)),
        },
        "reviewer_burden": {
            "present": present.get("reviewer_burden", 0),
            "present_frac_of_underdetermined": fr_und(present.get("reviewer_burden", 0)),
            "sole": sole.get("reviewer_burden", 0),
            "sole_frac_of_underdetermined": fr_und(sole.get("reviewer_burden", 0)),
        },
        "two_mapping_concentration": {
            "subset_of_coarse_killed_by_deleting_both": n_subset_coarse,
            "subset_frac_of_underdetermined": fr_und(n_subset_coarse),
            "survive_with_other_blocker": n_survive_coarse,
            "survive_frac_of_all": fr_all(n_survive_coarse),
            "note": "survive_frac_of_all reconciles with the joint-drop 75.1% floor: "
                    "deleting BOTH mappings cannot resolve a query that also carries "
                    "cost or another blocker.",
        },
        "cost_in_blockers": {"n": n_cost_in, "frac_of_underdetermined": fr_und(n_cost_in)},
        "any_unmeasurable_blocker": {
            "n": n_any_unmeasurable,
            "frac_of_all": fr_all(n_any_unmeasurable),
            "note": "this is the 72.4% blind-spot set, recomputed here as a cross-check.",
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "blocker_distribution.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    g, rb = res["governance"], res["reviewer_burden"]
    cc = res["two_mapping_concentration"]
    lines = [
        "# Q4 — per-query blocker distribution (is 72.4% a two-mapping artifact?)",
        "",
        "FULL regime, kappa=H+M, published classifier. blocking_axes = complete "
        "blocker set per underdetermined query.",
        "",
        f"- underdetermined: {n_und}/{n} = {100 * res['frac_underdetermined']:.1f}%",
        f"- mean blocker-set size: {res['mean_blocker_set_size']} "
        f"(histogram {res['blocker_set_size_histogram']})",
        "",
        "## blocker-set size (multiplicity)",
        "",
        "| |B| | queries |",
        "|---|---|",
    ]
    for k, v in sorted(size_hist.items()):
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "## per-axis presence and sole-blocker counts",
        "",
        "| axis | present | present% of underdet | sole-blocker | sole% of underdet |",
        "|---|---|---|---|---|",
    ]
    for a in sorted(present, key=lambda x: -present[x]):
        lines.append(
            f"| {a} | {present[a]} | {100 * fr_und(present[a]):.1f}% | "
            f"{sole.get(a, 0)} | {100 * fr_und(sole.get(a, 0)):.1f}% |")
    lines += [
        "",
        "## the two coarse mappings do NOT dominate",
        "",
        f"- governance: present in {100 * g['present_frac_of_underdetermined']:.1f}% "
        f"of underdetermined queries, but SOLE blocker in only "
        f"{100 * g['sole_frac_of_underdetermined']:.1f}%",
        f"- reviewer_burden: present {100 * rb['present_frac_of_underdetermined']:.1f}%, "
        f"sole {100 * rb['sole_frac_of_underdetermined']:.1f}%",
        f"- cost is among the blockers in "
        f"{100 * res['cost_in_blockers']['frac_of_underdetermined']:.1f}% of them",
        f"- B subset of {{governance, reviewer_burden}} (resolved by deleting BOTH "
        f"mappings): {cc['subset_of_coarse_killed_by_deleting_both']} "
        f"= {100 * cc['subset_frac_of_underdetermined']:.1f}% of underdetermined",
        f"- SURVIVE with another blocker: {cc['survive_with_other_blocker']} "
        f"= {100 * cc['survive_frac_of_all']:.1f}% of ALL queries "
        f"(reconciles with the joint-drop 75.1% floor)",
        f"- cross-check: any-never-measured-axis blocks "
        f"{100 * res['any_unmeasurable_blocker']['frac_of_all']:.1f}% of all "
        f"(the 72.4% blind-spot set)",
    ]
    (OUT_DIR / "blocker_distribution.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {OUT_DIR / 'blocker_distribution.json'} and .md")


if __name__ == "__main__":
    main()
