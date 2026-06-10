"""Run the real-GT, per-prompt-resampling coverage guarantee (W4 hardening).

Replaces the κ-proxy truth of `scripts/run_p4_guarantee.py` with genuine measured
ground truth from the cached RouterBench raw frame: truth = full-sample per-model
quality + cost; operating evidence = a seeded bootstrap subsample of K prompts.

It traces the coverage–risk curve over many seeded resamples × several benchmarks ×
several q* percentiles, then CALIBRATES the commit margin for a target risk α on a
held-out 50/50 split (C8 — no leakage) and reports TEST-split coverage/risk at
α ∈ {0.05, 0.10}.

Writes:
  - outputs/p4/coverage_risk_gt.json — curve + per-α calibration + provenance.
  - outputs/p4/coverage_risk_gt.md   — the real-GT coverage–risk curve + α tables.

Run with:
    PYTHONNOUSERSITE=1 uv run python scripts/run_p4_guarantee_gt.py
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from prudent_ai.validation.gt_guarantee import (
    COST_TOL,
    DEFAULT_MARGINS,
    MODELS,
    GTCoverageGuarantee,
    render_markdown,
)

OUT_DIR = Path("outputs/p4")
PROVENANCE = "P4-guarantee-GT"
ALPHAS = (0.05, 0.10)
SPLIT_SEED = 2024


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    guarantee = GTCoverageGuarantee()

    print("[load] reading per-prompt RouterBench truth + building decision battery...")
    outcomes = guarantee.generate_outcomes()
    total_n = len(outcomes)
    print(
        f"[battery] {total_n} well-posed decision instances "
        f"({len(guarantee.benchmarks)} benchmarks × {len(guarantee.q_percentiles)} "
        f"q*-percentiles × {guarantee.n_seeds} seeded resamples, minus unsatisfiable)."
    )

    # Full-battery curve (for the descriptive coverage–risk plot/table).
    curve = guarantee.coverage_risk_curve(outcomes, DEFAULT_MARGINS)
    print("\n[curve] margin -> coverage / FEASIBILITY-risk / min-suff-risk:")
    for p in curve:
        print(
            f"  m={p.margin:>5g}  cov={100 * p.coverage:5.1f}%  "
            f"feas_risk={100 * p.risk:5.1f}%  "
            f"min_suff_risk={100 * p.risk_min_sufficient:5.1f}%  "
            f"(commit {p.n_commit}, feas {p.n_feasible})"
        )

    # Seeded disjoint 50/50 calibrate/test split, then calibrate margin per α.
    calib, test = guarantee.split(outcomes, split_seed=SPLIT_SEED)
    print(
        f"\n[split] seed={SPLIT_SEED}: calib n={len(calib)}, test n={len(test)} "
        f"(disjoint, C8)."
    )

    calibrations = [
        guarantee.calibrate(calib, test, alpha, DEFAULT_MARGINS) for alpha in ALPHAS
    ]
    print("\n[calibration] FEASIBILITY (margin chosen on calib, reported on TEST):")
    for c in calibrations:
        margin_s = "none" if c.margin is None else f"{c.margin:g}"
        print(
            f"  α={c.alpha:g}  margin={margin_s}  "
            f"test_cov={100 * c.test_coverage:5.1f}%  "
            f"test_feas_risk={100 * c.test_risk:5.1f}%  "
            f"test_min_suff_risk={100 * c.test_risk_min_sufficient:5.1f}%  "
            f"(commit {c.test_n_commit}/{c.test_n_queries})"
        )

    metadata = {
        "provenance": PROVENANCE,
        "pkl_path": guarantee.pkl_path,
        "models": list(MODELS),
        "n_models": len(MODELS),
        "benchmarks": list(guarantee.benchmarks),
        "k_subsample": guarantee.k_subsample,
        "q_percentiles": list(guarantee.q_percentiles),
        "n_seeds": guarantee.n_seeds,
        "base_seed": guarantee.base_seed,
        "split_seed": SPLIT_SEED,
        "cost_tol": COST_TOL,
        "margins": list(DEFAULT_MARGINS),
        "alphas": list(ALPHAS),
        "total_n": total_n,
        "calib_n": len(calib),
        "test_n": len(test),
        "truth_is_proxy": False,
        "primary_risk": "feasibility (committed config truly clears q*; no hidden violation)",
        "secondary_risk": (
            f"strict min-sufficiency (feasible AND true cost ≤ (1+{COST_TOL:g})·"
            "min-cost-feasible cost)"
        ),
        "truth_note": (
            "truth = FULL-SAMPLE measured per-model quality+cost; operating = seeded "
            "bootstrap subsample of K prompts. Genuine real-GT conformal-style "
            "calibration, not a κ-proxy. Calibration targets the PRIMARY feasibility "
            "risk (conformal-controllable); the secondary strict min-sufficiency risk "
            "is reported as a diagnostic and does NOT fall with the margin (a one-sided "
            "quality margin over-provisions, breaking cost-optimality — honest, not "
            "forced). Reads pkl directly for scoring (no substrate query → C7 not "
            "engaged)."
        ),
    }

    payload = {
        "metadata": metadata,
        "curve": [asdict(p) for p in curve],
        "calibrations": [asdict(c) for c in calibrations],
    }

    json_path = OUT_DIR / "coverage_risk_gt.json"
    json_path.write_text(json.dumps(payload, indent=2))
    print(f"\n[write] {json_path}")

    md = render_markdown(guarantee, curve, calibrations, total_n)
    md_path = OUT_DIR / "coverage_risk_gt.md"
    md_path.write_text(md)
    print(f"[write] {md_path}")

    # Final honest verdict line.
    holds = [
        c for c in calibrations if c.margin is not None and c.test_risk <= c.alpha
    ]
    if holds:
        print(
            f"\n[verdict] guarantee TRANSFERS on the held-out test split for "
            f"α ∈ {{{', '.join(str(c.alpha) for c in holds)}}}."
        )
    else:
        print(
            "\n[verdict] no target α attainable with non-trivial coverage on test — "
            "see the curve for why (reported honestly, not forced)."
        )


if __name__ == "__main__":
    main()
