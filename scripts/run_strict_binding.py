"""F2 — joint-drop and strict-binding variants of the headline (node b5uiav).

Round-2 review, W1/Q3. Two objections the single-deletion ablation cannot answer:
  (a) correlated overcounting: dropping ONE governance-ish mapping at a time never
      tests removing governance AND reviewer burden together;
  (b) declared vs binding: what if governance counts as a constraint only where
      the case-study text contains candidate-discriminating language (the E4
      keyword floor, 72/954)?

Variants (all classified through the IDENTICAL C7 path: classify_query, FULL
regime, kappa=H+M, phi=POINT, median-grounded thresholds, same 1,716 rows):
  baseline      — the published taxonomy (cross-checks 91.1%).
  joint_drop    — NO governance (all four tags + the industry rule) and NO
                  reviewer_burden (human_in_the_loop) anywhere.
  strict_gov    — governance binds ONLY on rows matched by the E4 keyword scan;
                  everything else as published.
  strict_joint  — strict_gov AND reviewer_burden dropped entirely (the most
                  conservative reading the reviewer's framing implies).

Outputs: outputs/p3/strict_binding.{json,md}

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_strict_binding.py
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
PROVENANCE = "F2-strict-binding"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
E4_HITS = "outputs/p3/governance_bindingness.json"

AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]

GOV_TAGS = {t for t, a in TAG_TO_AXIS.items() if a == "governance"}
REV_TAGS = {t for t, a in TAG_TO_AXIS.items() if a == "reviewer_burden"}


def _tags(row, field):
    return [t.strip() for t in (row.get(field) or "").split(",") if t.strip()]


def derive_variant(row: dict, variant: str, strict_keys: set[tuple[str, str]]):
    app = _tags(row, "application_tags")
    tech = _tags(row, "techniques_tags")
    all_tags = set(app) | set(tech)
    tau = DEFAULT_TAU
    for t in app:
        if t in ARCHETYPE_MAP:
            tau = ARCHETYPE_MAP[t]
            break
    axes = set(UNIVERSAL_AXES)
    industry = (row.get("industry") or "").strip()
    key = ((row.get("company") or "").strip(), (row.get("title") or "").strip())

    for t in all_tags:
        if t not in TAG_TO_AXIS:
            continue
        ax = TAG_TO_AXIS[t]
        if variant in ("joint_drop", "strict_joint") and ax == "reviewer_burden":
            continue
        if ax == "governance":
            if variant == "joint_drop":
                continue
            if variant in ("strict_gov", "strict_joint") and key not in strict_keys:
                continue
        axes.add(ax)

    if industry in REGULATED_INDUSTRIES:
        if variant == "baseline":
            axes.add("governance")
        elif variant in ("strict_gov", "strict_joint") and key in strict_keys:
            axes.add("governance")
        # joint_drop: never

    return DerivedQuery(tau=tau, binding_axes=frozenset(axes),
                        title=(row.get("title") or "")[:80], industry=industry)


def classify(sub, prior, thresholds):
    n_und = 0
    n_attrib = 0
    for dq in prior.derived:
        q = to_query(dq, thresholds)
        res = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
        if res.label is Decidability.UNDERDETERMINED:
            n_und += 1
            if set(res.blocking_axes) & UNMEASURABLE_AXES:
                n_attrib += 1
    n = prior.n
    return {"n": n, "underdetermined": n_und,
            "frac_underdetermined": round(n_und / n, 4),
            "frac_attributable_unmeasurable": round(n_attrib / n, 4)}


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, base_prior = load_prior()
    taus = sorted({d.tau for d in base_prior.derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    hits = json.load(open(E4_HITS, encoding="utf-8"))["hits"]
    strict_keys = {((h.get("company") or "").strip(),
                    (h.get("title") or "").strip()) for h in hits}

    out = {}
    for variant in ("baseline", "joint_drop", "strict_gov", "strict_joint"):
        prior = QueryPrior(derived=[derive_variant(r, variant, strict_keys)
                                    for r in rows])
        bind = prior.axis_binding_frequency()
        cell = classify(sub, prior, th)
        out[variant] = {
            **cell,
            "binding": {a: bind.get(a, 0) for a in
                        ("governance", "reviewer_burden", "cost",
                         "latency_p95", "quality")},
        }
        print(f"{variant:>12}: underdetermined {cell['underdetermined']}/"
              f"{cell['n']} = {100*cell['frac_underdetermined']:.1f}%  "
              f"(bot-attributable {100*cell['frac_attributable_unmeasurable']:.1f}%)  "
              f"gov-bind {bind.get('governance',0)}  rev-bind "
              f"{bind.get('reviewer_burden',0)}")

    res = {"metadata": {"provenance": PROVENANCE, "db_path": DB_PATH,
                        "phi": PHI.value, "kappa": list(KAPPA),
                        "regime": "full", "n_rows": len(rows),
                        "strict_keys_matched": len(strict_keys)},
           "variants": out}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "strict_binding.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# F2 — joint-drop and strict-binding headline variants", ""]
    lines.append("| variant | gov binds | rev binds | underdetermined | "
                 "bot-attributable |")
    lines.append("|---|---|---|---|---|")
    for v, c in out.items():
        lines.append(
            f"| {v} | {c['binding']['governance']} | "
            f"{c['binding']['reviewer_burden']} | "
            f"{c['underdetermined']}/{c['n']} = "
            f"{100*c['frac_underdetermined']:.1f}% | "
            f"{100*c['frac_attributable_unmeasurable']:.1f}% |")
    (OUT_DIR / "strict_binding.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {OUT_DIR/'strict_binding.json'} and .md")


if __name__ == "__main__":
    main()
