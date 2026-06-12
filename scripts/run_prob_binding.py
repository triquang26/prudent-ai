"""E12 — declared-implies-binding sensitivity: sweep the binding probability p.

Round-8 review, W2/Q1: on the axes that DRIVE the headline (governance, reviewer
burden) the framework assumes "declared in a tag" implies "binds at the optimum,"
and concedes it cannot test this. The reviewer asks for "a clean decomposition
assuming declared-implies-binding holds with probability p." This provides it.

We sweep p in {0, 0.25, 0.5, 0.75, 1.0} = the probability that a DECLARED governance
or reviewer-burden requirement actually binds at the optimum. For each query we keep
each declared governance/reviewer-burden binding (tag-derived and the industry
governance rule) with probability p (seeded), reclassify all 1,716 queries, and
report the underdetermination headline and the blind-spot share. This turns the
binary declared-implies-binding assumption into a measured sensitivity curve.

Anchors (cross-check): p=1 reproduces the published 91.1% headline; p=0 reproduces
the joint-drop skeptical floor 75.1% (governance and reviewer burden never bind).

Frozen db read-only via the immutable interface; nothing imputed; no mutation.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_prob_binding.py
Run empirical: PYTHONNOUSERSITE=1 uv run python scripts/run_prob_binding.py --empirical
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

from prudent_ai.analysis.empirical_prior_map import (
    UNMEASURABLE_AXES,
    grounded_thresholds,
    load_prior,
)
from prudent_ai.queries.query_prior import (
    ARCHETYPE_MAP,
    DEFAULT_TAU,
    REGULATED_INDUSTRIES,
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
PROVENANCE = "E12-prob-binding-sensitivity"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
SEED = 12345
P_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)

AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]
_PROB_AXES = {"governance", "reviewer_burden"}


def _tags(row, field):
    return [t.strip() for t in (row.get(field) or "").split(",") if t.strip()]


def derive_prob_binding(row: dict, p: float, rng: random.Random) -> DerivedQuery:
    """Published taxonomy, but each DECLARED governance/reviewer binding is kept
    with probability p (tag mappings and the industry governance rule)."""
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
        if t not in TAG_TO_AXIS:
            continue
        ax = TAG_TO_AXIS[t]
        if ax in _PROB_AXES:
            if rng.random() < p:   # declared governance/reviewer binds w.p. p
                axes.add(ax)
        else:
            axes.add(ax)           # measurable declared axes always bind
    industry = (row.get("industry") or "").strip()
    if industry in REGULATED_INDUSTRIES and rng.random() < p:
        axes.add("governance")
    return DerivedQuery(tau=tau, binding_axes=frozenset(axes),
                        title=(row.get("title") or "")[:80], industry=industry)


def classify_headline(sub, prior: QueryPrior, th) -> dict:
    n = prior.n
    n_und = 0
    n_blindspot = 0
    for dq in prior.derived:
        q = to_query(dq, th)
        res = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
        if res.label is not Decidability.UNDERDETERMINED:
            continue
        n_und += 1
        if set(res.blocking_axes) & UNMEASURABLE_AXES:
            n_blindspot += 1
    return {"n": n, "underdetermined": n_und,
            "frac_underdetermined": round(n_und / n, 4) if n else 0.0,
            "blindspot_attributable": n_blindspot,
            "frac_blindspot": round(n_blindspot / n, 4) if n else 0.0}


ANN_PATH = Path("outputs/p3/binding_annotation_per_case.json")
P_HAT = 0.0797  # measured binding rate from LLM annotations (31/954 BINDING cases)


def _normalize_title(s: str) -> str:
    """Case-insensitive, alphanum+space only, first 40 chars — for fuzzy matching."""
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s[:40]


def build_labels_by_title(ann_path: Path = ANN_PATH) -> dict[str, str]:
    """Load per-case annotations and return {normalized_title: majority_label}."""
    data = json.loads(ann_path.read_text(encoding="utf-8"))
    return {_normalize_title(case["title"]): case["final_label"]
            for case in data["per_case"]}


def derive_empirical_binding(
    row: dict,
    labels_by_title: dict[str, str],
    conservative: bool = False,
) -> DerivedQuery:
    """Like derive_prob_binding but uses LLM annotation labels instead of a p-sweep.

    Governance and reviewer_burden axes bind ONLY when the measured annotation for
    the case is BINDING (strict mode) or BINDING/UNDETERMINED (conservative mode).
    Cases not found in labels_by_title are treated as UNDETERMINED (keep binding
    conservatively — same as conservative=True).

    Args:
        row: a row dict from load_prior().
        labels_by_title: mapping from normalized title to majority_label string.
        conservative: if True, treat UNDETERMINED as binding (conservative); if False,
            treat UNDETERMINED as non-binding (strict — only BINDING labels bind).
    """
    app = _tags(row, "application_tags")
    tech = _tags(row, "techniques_tags")
    all_tags = set(app) | set(tech)
    tau = DEFAULT_TAU
    for t in app:
        if t in ARCHETYPE_MAP:
            tau = ARCHETYPE_MAP[t]
            break

    # Look up annotation label for this case
    norm_title = _normalize_title(row.get("title") or "")
    label = labels_by_title.get(norm_title)
    # If not found, treat as UNDETERMINED
    if label is None:
        label = "UNDETERMINED"

    # Determine whether declared governance/reviewer axes should bind
    if conservative:
        keep_binding = label in ("BINDING", "UNDETERMINED")
    else:
        keep_binding = label == "BINDING"

    axes = set(UNIVERSAL_AXES)
    for t in all_tags:
        if t not in TAG_TO_AXIS:
            continue
        ax = TAG_TO_AXIS[t]
        if ax in _PROB_AXES:
            if keep_binding:
                axes.add(ax)
        else:
            axes.add(ax)  # measurable declared axes always bind

    industry = (row.get("industry") or "").strip()
    # Industry governance rule: only add governance if annotation says binding
    if industry in REGULATED_INDUSTRIES and keep_binding:
        axes.add("governance")

    return DerivedQuery(tau=tau, binding_axes=frozenset(axes),
                        title=(row.get("title") or "")[:80], industry=industry)


def main_empirical() -> None:
    """Run classification using measured LLM annotation labels instead of a p-sweep."""
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, base_prior = load_prior()
    taus = sorted({d.tau for d in base_prior.derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    labels_by_title = build_labels_by_title()

    # Compute match statistics
    n_rows = len(rows)
    n_matched = sum(
        1 for r in rows
        if _normalize_title(r.get("title") or "") in labels_by_title
    )
    n_unmatched = n_rows - n_matched
    print(f"Title matching: {n_matched}/{n_rows} rows matched "
          f"({n_unmatched} unmatched → treated as UNDETERMINED)")

    # Load existing p-sweep reference for cross-check
    p_sweep_ref: dict = {}
    prob_binding_path = OUT_DIR / "prob_binding.json"
    if prob_binding_path.exists():
        existing = json.loads(prob_binding_path.read_text(encoding="utf-8"))
        sweep = existing.get("sweep", {})
        p_sweep_ref = {
            "p0":    sweep.get("p0",    {}).get("frac_underdetermined"),
            "p0.25": sweep.get("p0.25", {}).get("frac_underdetermined"),
            "p0.5":  sweep.get("p0.5",  {}).get("frac_underdetermined"),
            "p0.75": sweep.get("p0.75", {}).get("frac_underdetermined"),
            "p1":    sweep.get("p1",    {}).get("frac_underdetermined"),
        }

    results: dict[str, dict] = {}
    for variant, conservative in (("strict", False), ("conservative", True)):
        prior_emp = QueryPrior(derived=[
            derive_empirical_binding(r, labels_by_title, conservative=conservative)
            for r in rows
        ])
        headline = classify_headline(sub, prior_emp, th)
        results[variant] = headline
        label_desc = "BINDING" if not conservative else "BINDING+UNDETERMINED"
        print(f"\n[{variant}] keep_binding when label in {{{label_desc}}}")
        print(f"  n={headline['n']}, underdetermined={headline['underdetermined']} "
              f"({100 * headline['frac_underdetermined']:.1f}%), "
              f"blind-spot={headline['blindspot_attributable']} "
              f"({100 * headline['frac_blindspot']:.1f}%)")

    out = {
        "metadata": {
            "provenance": PROVENANCE + "-empirical",
            "db_path": DB_PATH,
            "phi": PHI.value,
            "kappa": list(KAPPA),
            "regime": "full",
            "ann_path": str(ANN_PATH),
            "n_rows_total": n_rows,
            "n_rows_matched": n_matched,
            "n_rows_unmatched": n_unmatched,
            "note": (
                "Empirical variant: governance/reviewer_burden axes bind ONLY when "
                "LLM-annotation label is BINDING (strict) or BINDING/UNDETERMINED "
                "(conservative). Unmatched titles treated as UNDETERMINED."
            ),
        },
        "strict": results["strict"],
        "conservative": results["conservative"],
        "p_hat_used": P_HAT,
        "p_sweep_reference": p_sweep_ref,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "prob_binding_empirical.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # Print summary table
    print("\n# E12-empirical — measured-label binding (p̂ = 0.0797)")
    print("")
    print("| variant | underdetermined | blind-spot-attributable |")
    print("|---|---|---|")
    for variant in ("strict", "conservative"):
        s = results[variant]
        print(f"| {variant} | {100 * s['frac_underdetermined']:.1f}% "
              f"({s['underdetermined']}/{s['n']}) | "
              f"{100 * s['frac_blindspot']:.1f}% |")
    if p_sweep_ref:
        print("")
        print("p-sweep reference:")
        for pk, pv in p_sweep_ref.items():
            if pv is not None:
                print(f"  {pk}: {100 * pv:.1f}%")
    print(f"\nWrote {out_path}")


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, base_prior = load_prior()
    taus = sorted({d.tau for d in base_prior.derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    sweep = {}
    for i, p in enumerate(P_GRID):
        rng = random.Random(SEED + i)
        prior_p = QueryPrior(derived=[derive_prob_binding(r, p, rng) for r in rows])
        sweep[f"p{p:g}"] = classify_headline(sub, prior_p, th)

    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH, "phi": PHI.value,
                     "kappa": list(KAPPA), "seed": SEED, "regime": "full",
                     "p_grid": list(P_GRID), "n_rows": len(rows),
                     "prob_axes": sorted(_PROB_AXES),
                     "note": "p = probability a DECLARED governance/reviewer-burden "
                             "requirement binds at the optimum. p=1 reproduces the "
                             "91.1% headline; p=0 reproduces the 75.1% joint-drop floor."},
        "sweep": sweep,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "prob_binding.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# E12 — declared-implies-binding sensitivity (sweep p)", "",
             "p = probability a DECLARED governance/reviewer-burden requirement binds "
             "at the optimum. FULL regime, kappa=H+M.", "",
             "| p | underdetermined | blind-spot-attributable |",
             "|---|---|---|"]
    for p in P_GRID:
        s = sweep[f"p{p:g}"]
        lines.append(f"| {p:g} | {100 * s['frac_underdetermined']:.1f}% "
                     f"({s['underdetermined']}/{s['n']}) | "
                     f"{100 * s['frac_blindspot']:.1f}% |")
    lines += [
        "",
        f"- anchor check: p=1 -> {100 * sweep['p1']['frac_underdetermined']:.1f}% "
        f"(published 91.1%); p=0 -> {100 * sweep['p0']['frac_underdetermined']:.1f}% "
        f"(joint-drop floor 75.1%)",
        "- the headline is a MONOTONE function of how often declared governance/reviewer "
        "constraints actually bind; even if only HALF of declared constraints bind "
        f"(p=0.5), the headline is {100 * sweep['p0.5']['frac_underdetermined']:.1f}%.",
    ]
    (OUT_DIR / "prob_binding.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {OUT_DIR / 'prob_binding.json'} and .md")


if __name__ == "__main__":
    if "--empirical" in sys.argv:
        main_empirical()
    else:
        main()
