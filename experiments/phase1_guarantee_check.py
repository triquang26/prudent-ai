"""Phase 1 — split-conformal guarantee check on held-out RouterBench truth.

Mirrors the existing calibrated-margin check (validation/gt_guarantee, Figure 7 right):
calibrate the conformal radius τ_α on one half of the RouterBench quality cells, then on
the DISJOINT held-out half verify

  (i)  interval coverage ≥ 1 − α   (the conformal guarantee), and
  (ii) feasibility error among decisive-satisfied commits ≤ α
       (the decision-level guarantee P(committed config infeasible | commit) ≤ α),

swept over α ∈ {0.05, 0.10, 0.20}. No frozen artifact is mutated.

Run:  PYTHONNOUSERSITE=1 uv run python experiments/phase1_guarantee_check.py
Out:  outputs/phase1/guarantee_check.json
"""

from __future__ import annotations

import json
from pathlib import Path

from prudent_ai.transfer import CalibratedTransfer

REPO = Path(__file__).parents[1]
PKL = REPO / "data/routerbench_0shot.pkl"
OUT = REPO / "outputs/phase1/guarantee_check.json"
ALPHAS = (0.05, 0.10, 0.20)


def main() -> None:
    transfer = CalibratedTransfer.fit_from_pkl(PKL)
    rows = [transfer.test_guarantee(a) for a in ALPHAS]

    result = {
        "metadata": {
            "experiment": "phase1_guarantee_check",
            "split": "seeded 50/50 calib/test over RouterBench quality cells (seed 2024)",
            "note": "Split-conformal: τ_α from calibration residuals; coverage and "
                    "decision-level feasibility error measured on the disjoint test half. "
                    "Guarantee predicts coverage ≥ 1−α and feasibility-error ≤ α.",
        },
        "alpha_sweep": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))

    print("split-conformal guarantee on held-out RouterBench truth:")
    print("  α     test-coverage (≥1−α?)   feas-error (≤α?)   n_commit")
    for r in rows:
        cov_ok = "OK" if r["interval_coverage"] >= r["target_coverage"] - 0.02 else "LOW"
        fe_ok = "OK" if r["feasibility_error"] <= r["alpha"] + 0.02 else "HIGH"
        print(f"  {r['alpha']:.2f}  {r['interval_coverage']:.3f} "
              f"(t {r['target_coverage']:.2f}) [{cov_ok}]    "
              f"{r['feasibility_error']:.3f} [{fe_ok}]     {r['n_decisive_commit']}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
