"""E5 — corpus-composition robustness of the headline (node: round-3 framing).

Round-3 review, point #7 (external validity of the prior). The published
robustness suite re-weights the query distribution WITHIN the single ZenML
corpus (uniform / adversarial / benchmark priors); it never removes a whole
sub-population of deployments. This script tests the stronger question a
reviewer asks about corpus selection: is 91.1% an artifact of WHICH deployments
are indexed?

It does NOT, and cannot, address the irreducible part of the concern --- that
every row is a company that chose to PUBLISH a ZenML case study. There is no
second, independently-collected deployment corpus on disk (MedHELM was gated and
entered only as an evidence source). So this isolates the part that IS testable:
composition. We delete entire industries and recompute the published classifier.

Partitions (all classified through the IDENTICAL published path: derive_query
-> to_query -> classify_query, FULL regime, kappa=H+M, phi=POINT, grounded
thresholds, same taxonomy --- only the ROW SET changes):
  baseline        --- all rows (cross-checks 91.1%).
  drop_regulated  --- delete Healthcare/Finance/Legal/Insurance/Government
                      entirely: the industries that DRIVE governance binding are
                      gone. Stronger than the adversarial re-weighting (removal,
                      not down-weighting). If the headline survives, the finding
                      is not a governance-industry artifact.
  drop_tech       --- delete the dominant Tech majority (~53% of rows): does the
                      headline survive without the modal sub-population?
  per_industry    --- headline computed within each industry with >= MIN_ROWS
                      rows (the across-slice range).
  loio            --- leave-one-industry-out: headline on the complement of each
                      industry (composition-jackknife).

Outputs: outputs/p3/corpus_composition.{json,md}. Frozen db read-only via the
solver interface; no row mutated; no imputation.

Run:  PYTHONNOUSERSITE=1 uv run python scripts/run_corpus_composition.py
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
    REGULATED_INDUSTRIES,
    build_query_prior,
    to_query,
)
from prudent_ai.solver import Decidability, Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.decidability import classify_query
from prudent_ai.solver.regimes import FULL
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p3")
PROVENANCE = "E5-corpus-composition"
KAPPA: tuple[str, ...] = ("H", "M")
PHI = Phi.POINT
MIN_ROWS = 30  # report a per-industry headline only when the slice is non-tiny

AXES = ["quality", "latency_p95", "throughput", "cost",
        "energy", "memory_hw", "governance", "reviewer_burden"]


def _industry(row: dict) -> str:
    return (row.get("industry") or "").strip()


def classify(sub, rows, th) -> dict:
    """Run the published classifier over a ROW SUBSET; tally blockers."""
    prior = build_query_prior(rows)
    n = prior.n
    n_und = 0
    n_attrib = 0
    blockers: Counter[str] = Counter()
    for dq in prior.derived:
        q = to_query(dq, th)
        res = classify_query(sub, q, kappa=KAPPA, phi=PHI, regime=FULL)
        if res.label is Decidability.UNDERDETERMINED:
            n_und += 1
            bset = set(res.blocking_axes)
            if bset & UNMEASURABLE_AXES:
                n_attrib += 1
            for a in bset:
                blockers[a] += 1
    modal = blockers.most_common(1)[0] if blockers else ("--", 0)
    return {
        "n": n,
        "underdetermined": n_und,
        "frac_underdetermined": round(n_und / n, 4) if n else 0.0,
        "frac_attributable_unmeasurable": round(n_attrib / n, 4) if n else 0.0,
        "modal_blocker": modal[0],
        "modal_blocker_count": modal[1],
        "blockers": dict(blockers.most_common()),
    }


def main() -> None:
    sub = CachedSubstrate(Substrate(DB_PATH))
    rows, base_prior = load_prior()
    taus = sorted({d.tau for d in base_prior.derived})
    th = grounded_thresholds(sub, taus, AXES, KAPPA)

    industries = Counter(_industry(r) for r in rows)
    regulated = sorted(REGULATED_INDUSTRIES)

    partitions: dict[str, list[dict]] = {
        "baseline": rows,
        "drop_regulated": [r for r in rows
                           if _industry(r) not in REGULATED_INDUSTRIES],
        "drop_tech": [r for r in rows if _industry(r) != "Tech"],
    }

    out: dict[str, dict] = {}
    for name, subset in partitions.items():
        cell = classify(sub, subset, th)
        cell["dropped"] = {
            "drop_regulated": regulated,
            "drop_tech": ["Tech"],
        }.get(name, [])
        out[name] = cell
        print(f"{name:>16}: {cell['underdetermined']}/{cell['n']} = "
              f"{100 * cell['frac_underdetermined']:.1f}%  "
              f"(blind-spot-attributable {100 * cell['frac_attributable_unmeasurable']:.1f}%; "
              f"modal blocker {cell['modal_blocker']})")

    # per-industry headline (non-tiny slices) + leave-one-industry-out complement
    per_industry: dict[str, dict] = {}
    loio: dict[str, dict] = {}
    for ind, cnt in industries.most_common():
        if not ind:
            continue
        if cnt >= MIN_ROWS:
            sub_rows = [r for r in rows if _industry(r) == ind]
            per_industry[ind] = classify(sub, sub_rows, th)
        comp = [r for r in rows if _industry(r) != ind]
        loio[ind] = classify(sub, comp, th)

    pi_vals = [v["frac_underdetermined"] for v in per_industry.values()]
    loio_vals = [v["frac_underdetermined"] for v in loio.values()]
    summary = {
        "per_industry_min": round(min(pi_vals), 4) if pi_vals else None,
        "per_industry_max": round(max(pi_vals), 4) if pi_vals else None,
        "loio_min": round(min(loio_vals), 4) if loio_vals else None,
        "loio_max": round(max(loio_vals), 4) if loio_vals else None,
        "n_industries_total": len([i for i in industries if i]),
        "n_industries_reported": len(per_industry),
        "min_rows": MIN_ROWS,
    }

    res = {
        "metadata": {"provenance": PROVENANCE, "db_path": DB_PATH,
                     "phi": PHI.value, "kappa": list(KAPPA), "regime": "full",
                     "n_rows": len(rows), "regulated_industries": regulated,
                     "industry_counts": dict(industries.most_common())},
        "partitions": out,
        "per_industry": per_industry,
        "leave_one_industry_out": loio,
        "summary": summary,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "corpus_composition.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    lines = ["# E5 — corpus-composition robustness (delete whole sub-populations)",
             "",
             "Published taxonomy, FULL regime, kappa=H+M; only the ROW SET changes.",
             "",
             "## Whole-sub-population deletions",
             "",
             "| partition | n | underdetermined | blind-spot-attributable | "
             "modal blocker |", "|---|---|---|---|---|"]
    for name, c in out.items():
        lines.append(
            f"| {name} | {c['n']} | "
            f"{c['underdetermined']}/{c['n']} = {100 * c['frac_underdetermined']:.1f}% | "
            f"{100 * c['frac_attributable_unmeasurable']:.1f}% | {c['modal_blocker']} |")
    lines += ["",
              f"- per-industry headline range (>= {MIN_ROWS} rows, "
              f"{summary['n_industries_reported']} industries): "
              f"{100 * summary['per_industry_min']:.1f}% – "
              f"{100 * summary['per_industry_max']:.1f}%",
              f"- leave-one-industry-out complement range: "
              f"{100 * summary['loio_min']:.1f}% – {100 * summary['loio_max']:.1f}%",
              "",
              "## Per-industry headline (non-tiny slices)",
              "",
              "| industry | n | underdetermined | modal blocker |",
              "|---|---|---|---|"]
    for ind, c in sorted(per_industry.items(),
                         key=lambda kv: -kv[1]["n"]):
        lines.append(
            f"| {ind} | {c['n']} | "
            f"{100 * c['frac_underdetermined']:.1f}% | {c['modal_blocker']} |")
    (OUT_DIR / "corpus_composition.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n" + "\n".join(lines[4:14]))
    print(f"\nWrote {OUT_DIR / 'corpus_composition.json'} and .md")


if __name__ == "__main__":
    main()
