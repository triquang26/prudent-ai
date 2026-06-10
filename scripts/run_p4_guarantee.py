"""Trace the P4 coverage–risk curve over the empirical (ZenML) query prior.

Drives the committed `CoverageGuarantee` (§9): for each commit margin `m`, report
coverage `|C|/|queries|` and empirical risk `P(incorrect | committed)`, then
calibrate the smallest margin meeting risk ≤ α for α ∈ {0.05, 0.10}.

**Honest scope.** "Truth" here is the richer-κ proxy (κ_truth = H+M+L) per
`guarantee.py`'s docstring — NOT a held-out ground-truth slice (that is P5). This
is calibration on a confidence proxy, stated plainly.

The empirical prior is the 1716 ZenML LLMOps case studies → (τ, binding-axes)
queries. Every verdict reads the substrate ONLY through the solver layer (C7); the
substrate is wrapped as `CachedSubstrate` so the repeated cell/candidate reads do
not hang.

Writes:
  - outputs/p4/coverage_risk.json — curve points + calibrations + provenance metadata.
  - outputs/p4/coverage_risk.md   — coverage–risk table + α calibrations + honest scope.

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_p4_guarantee.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from prudent_ai.analysis.decidability_map import AXES
from prudent_ai.analysis.empirical_prior_map import grounded_thresholds, load_prior
from prudent_ai.queries.query_prior import to_query
from prudent_ai.solver import FULL, Phi
from prudent_ai.solver.cache import CachedSubstrate
from prudent_ai.solver.guarantee import CoverageGuarantee
from prudent_ai.substrate import Substrate

DB_PATH = "data/apt_substrate.db"
OUT_DIR = Path("outputs/p4")
PROVENANCE = "P4-guarantee"
PHI = Phi.POINT
KAPPA_OPERATING: tuple[str, ...] = ("H", "M")
KAPPA_TRUTH: tuple[str, ...] = ("H", "M", "L")

# Optional seeded subsample of the prior for speed. Set to None to use all 1716.
SAMPLE_N: int | None = 600
SAMPLE_SEED = 12345

ALPHAS = (0.05, 0.10)


def _fmt_pct(frac: float) -> str:
    return f"{100.0 * frac:5.1f}%"


def _build_queries(sub: CachedSubstrate) -> tuple[list, int, bool]:
    """Build runnable empirical queries; returns (queries, n_total_prior, sampled)."""
    _rows, prior = load_prior()
    n_total = prior.n
    derived = list(prior.derived)

    sampled = False
    if SAMPLE_N is not None and SAMPLE_N < n_total:
        rng = random.Random(SAMPLE_SEED)
        derived = rng.sample(derived, SAMPLE_N)
        sampled = True
        print(
            f"[sampling] SEEDED subsample of the prior: N={SAMPLE_N} "
            f"(of {n_total}), seed={SAMPLE_SEED}."
        )
    else:
        print(f"[sampling] using ALL {n_total} empirical queries (no subsample).")

    taus = sorted({dq.tau for dq in derived})
    thresholds = grounded_thresholds(sub, taus, list(AXES), KAPPA_OPERATING)
    queries = [to_query(dq, thresholds) for dq in derived]
    return queries, n_total, sampled


def _render_md(
    curve: list,
    cals: dict[float, object],
    n_queries: int,
    n_total: int,
    sampled: bool,
) -> str:
    lines: list[str] = []
    lines.append("# P4 Coverage–Risk Curve (selective commit guarantee, §9)")
    lines.append("")
    lines.append(f"- Provenance: `{PROVENANCE}`")
    lines.append(f"- DB: `{DB_PATH}`")
    lines.append(f"- φ (aggregation): `{PHI.value}`")
    lines.append(f"- κ_operating: `{'+'.join(KAPPA_OPERATING)}`")
    lines.append(f"- κ_truth (proxy): `{'+'.join(KAPPA_TRUTH)}`")
    lines.append("- regime: `FULL`")
    if sampled:
        lines.append(
            f"- Prior: **{n_queries}** empirical queries "
            f"(SEEDED subsample of {n_total}, seed={SAMPLE_SEED})."
        )
    else:
        lines.append(f"- Prior: **{n_queries}** empirical queries (full prior).")
    lines.append("")
    lines.append(
        "Coverage `|C|/|queries|` and empirical risk `P(incorrect | committed)` as a "
        "function of the commit margin `m` (commit only when the identified config's "
        "cost beats the next provably-feasible alternative by ≥ `m`). Every verdict "
        "reads the substrate only through the solver / classifier (C7)."
    )
    lines.append("")
    lines.append(
        "**Honest scope.** \"Truth\" is the *richer-κ proxy* (κ_truth = H+M+L), not a "
        "held-out labelled slice — that is P5. A commit is *correct* iff the fuller-"
        "evidence procedure identifies the same minimum-sufficient config. This is "
        "calibration on a confidence proxy, stated plainly (per `guarantee.py` docstring)."
    )
    lines.append("")

    lines.append("## Coverage–risk curve")
    lines.append("")
    lines.append("| margin | coverage | risk | n_commit | n_correct |")
    lines.append("|---|---|---|---|---|")
    for pt in curve:
        lines.append(
            f"| {pt.margin:g} | {_fmt_pct(pt.coverage)} | {_fmt_pct(pt.risk)} "
            f"| {pt.n_commit} | {pt.n_correct} |"
        )
    lines.append("")

    lines.append("## Calibration — smallest margin with risk ≤ α")
    lines.append("")
    lines.append("| α | margin | coverage | risk |")
    lines.append("|---|---|---|---|")
    for alpha in ALPHAS:
        c = cals[alpha]
        margin_str = "—" if c.margin is None else f"{c.margin:g}"
        note = " (no margin meets α; lowest-risk point)" if c.margin is None else ""
        lines.append(
            f"| {alpha:g} | {margin_str} | {_fmt_pct(c.coverage)} | {_fmt_pct(c.risk)} |"
            f"{note}"
        )
    lines.append("")
    lines.append(
        "**Trust-or-Escalate shape.** A distribution-free guarantee is available only "
        "by *abstaining* on most traffic: risk at the committed slice is low, but "
        "coverage is small (≈9% in the FULL regime — the empirical-prior decidable "
        "fraction). The procedure commits on the decidable minority and escalates the "
        "rest, exactly as the §9 selective-commit guarantee intends."
    )
    lines.append("")
    return "\n".join(lines)


def _print_summary(
    curve: list,
    cals: dict[float, object],
    n_queries: int,
    n_total: int,
    sampled: bool,
) -> None:
    print("=" * 72)
    print(
        f"P4 COVERAGE–RISK CURVE  (provenance={PROVENANCE}, phi={PHI.value}, "
        f"kappa_op={'+'.join(KAPPA_OPERATING)}, kappa_truth={'+'.join(KAPPA_TRUTH)})"
    )
    print("=" * 72)
    if sampled:
        print(f"Prior: {n_queries} queries (SEEDED subsample of {n_total}, "
              f"seed={SAMPLE_SEED})")
    else:
        print(f"Prior: {n_queries} queries (full prior)")
    print(f"  {'margin':>8}  {'coverage':>9} {'risk':>7}  {'n_commit':>8} {'n_correct':>9}")
    for pt in curve:
        print(
            f"  {pt.margin:>8g}  {_fmt_pct(pt.coverage):>9} {_fmt_pct(pt.risk):>7}  "
            f"{pt.n_commit:>8} {pt.n_correct:>9}"
        )
    print("-" * 72)
    print("Calibration (smallest margin with risk ≤ α):")
    for alpha in ALPHAS:
        c = cals[alpha]
        margin_str = "none" if c.margin is None else f"{c.margin:g}"
        print(
            f"  alpha={alpha:<5g} margin={margin_str:>6}  "
            f"coverage={_fmt_pct(c.coverage)}  risk={_fmt_pct(c.risk)}"
        )
    print("=" * 72)


def main() -> None:
    # CachedSubstrate memoizes cell()/candidates(): the guarantee re-classifies every
    # query under both κ_operating and κ_truth across many margins, issuing repeated
    # reads over the FROZEN snapshot. C7 preserved; no network calls.
    sub = CachedSubstrate(Substrate(DB_PATH))

    queries, n_total, sampled = _build_queries(sub)
    n_queries = len(queries)

    g = CoverageGuarantee(
        sub,
        queries,
        kappa_operating=KAPPA_OPERATING,
        kappa_truth=KAPPA_TRUTH,
        phi=PHI,
        regime=FULL,
    )

    curve = g.coverage_risk_curve()
    cals = {alpha: g.calibrate(alpha) for alpha in ALPHAS}

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "metadata": {
            "provenance": PROVENANCE,
            "db_path": DB_PATH,
            "phi": PHI.value,
            "kappa_operating": list(KAPPA_OPERATING),
            "kappa_truth": list(KAPPA_TRUTH),
            "regime": "FULL",
            "prior_n_total": n_total,
            "n_queries": n_queries,
            "sampled": sampled,
            "sample_n": SAMPLE_N if sampled else None,
            "sample_seed": SAMPLE_SEED if sampled else None,
            "truth_is_proxy": True,
            "truth_note": (
                "truth = richer-κ proxy (κ_truth=H+M+L), not held-out GT (P5)"
            ),
        },
        "curve": [
            {
                "margin": pt.margin,
                "coverage": pt.coverage,
                "risk": pt.risk,
                "n_commit": pt.n_commit,
                "n_correct": pt.n_correct,
            }
            for pt in curve
        ],
        "calibrations": {
            f"{alpha:g}": {
                "alpha": cals[alpha].alpha,
                "margin": cals[alpha].margin,
                "coverage": cals[alpha].coverage,
                "risk": cals[alpha].risk,
            }
            for alpha in ALPHAS
        },
    }
    json_path = OUT_DIR / "coverage_risk.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")

    md_path = OUT_DIR / "coverage_risk.md"
    md_path.write_text(
        _render_md(curve, cals, n_queries, n_total, sampled), encoding="utf-8"
    )

    _print_summary(curve, cals, n_queries, n_total, sampled)
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
