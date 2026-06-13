"""Phase 0 — pilot the cross-benchmark transfer signal (the GO/NO-GO gate).

The Tier-1 "calibrated transfer" idea is only viable if calibrated intervals predicted
for a fragmented-⊥ quality cell are TIGHT enough to not straddle the query threshold on
a meaningful fraction of co-location-blocked decisions. If quality is unpredictable
cross-benchmark, intervals are wide, everything straddles, and the method always
abstains -> Tier-1 recovers nothing.

This script measures the honest signal on the RouterBench quality matrix
(11 models × 30 benchmarks, quality ∈ [0,1]):

  1. Leave-one-benchmark-out (LOBO) two-way additive prediction of each cell.
  2. Point-prediction quality: R², MAE (pooled + per-model).
  3. Split-conformal intervals at α ∈ {0.05, 0.10, 0.20}; interval width + realized
     coverage on a held-out split (mirrors validation/gt_guarantee split discipline).
  4. recovery_rate@α: over co-location-blocked quality cells × grounded query thresholds
     (percentiles 10..90 of each benchmark's quality), the fraction whose calibrated
     interval does NOT straddle the threshold (i.e., the decision is resolved without
     any new measurement).
  5. Structural-axis refusal: confirm the predictor emits NO interval for the
     never-measured axes (governance, reviewer_burden, energy, throughput, memory_hw).

Honest predictor only (no gate-chasing): a standard two-way additive model. If the
signal is weak that is a finding, not a bug.

Run:  PYTHONNOUSERSITE=1 uv run python experiments/phase0_transfer_signal.py
Out:  outputs/phase0/transfer_signal.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from prudent_ai.analysis.empirical_prior_map import UNMEASURABLE_AXES
from prudent_ai.substrate.routerbench.parser import RouterBenchParser

REPO = Path(__file__).parents[1]
PKL = REPO / "data/routerbench_0shot.pkl"
OUT = REPO / "outputs/phase0/transfer_signal.json"
ALPHAS = (0.05, 0.10, 0.20)
SPLIT_SEED = 2024  # mirror validation/gt_guarantee.split
THRESH_PCTS = tuple(range(10, 91, 10))  # grounded query thresholds, p10..p90


def load_matrix() -> tuple[list[str], list[str], np.ndarray]:
    """Return (models, benchmarks, Q) where Q[i,j] = quality, NaN if absent."""
    cfgs = RouterBenchParser().parse(pd.read_pickle(PKL))
    models = sorted({c.model for c in cfgs})
    benches = sorted({c.benchmark for c in cfgs})
    mi = {m: i for i, m in enumerate(models)}
    bi = {b: j for j, b in enumerate(benches)}
    Q = np.full((len(models), len(benches)), np.nan)
    for c in cfgs:
        Q[mi[c.model], bi[c.benchmark]] = c.quality
    return models, benches, Q


def lobo_predict(Q: np.ndarray) -> np.ndarray:
    """Leave-one-benchmark-out two-way additive prediction for every cell.

    q̂[m,B] = coleff[B] + rowresid[m], where
      coleff[B]   = mean over models m'≠m of q[m',B]   (benchmark difficulty, no leak),
      rowresid[m] = mean over benches B'≠B of (q[m,B'] − coleff_full[m,B'])
                    (model m's skill relative to difficulty, from its OTHER benchmarks).
    No value of the target cell (m,B) enters its own prediction.
    """
    n_m, n_b = Q.shape
    P = np.full_like(Q, np.nan)
    for i in range(n_m):
        for j in range(n_b):
            if np.isnan(Q[i, j]):
                continue
            # coleff[B=j] from other models
            col = Q[:, j].copy()
            col[i] = np.nan
            coleff_j = np.nanmean(col)
            # rowresid[m=i] from m's other benchmarks, each de-meaned by ITS coleff
            resids = []
            for jj in range(n_b):
                if jj == j or np.isnan(Q[i, jj]):
                    continue
                coljj = Q[:, jj].copy()
                coljj[i] = np.nan
                ceff = np.nanmean(coljj)
                resids.append(Q[i, jj] - ceff)
            rowresid_i = float(np.mean(resids)) if resids else 0.0
            P[i, j] = coleff_j + rowresid_i
    return P


def split_conformal_tau(scores: np.ndarray, alpha: float) -> float:
    """Split-conformal radius: the ceil((n+1)(1−α))/n empirical quantile of |residual|."""
    n = len(scores)
    s = np.sort(scores)
    k = int(np.ceil((n + 1) * (1 - alpha)))
    k = min(max(k, 1), n)
    return float(s[k - 1])


def _pct(vals: np.ndarray, p: int) -> float:
    return float(np.percentile(vals, p))


def main() -> None:
    models, benches, Q = load_matrix()
    P = lobo_predict(Q)

    mask = ~np.isnan(Q) & ~np.isnan(P)
    q_true = Q[mask]
    q_hat = P[mask]
    resid = q_true - q_hat
    abs_resid = np.abs(resid)

    # --- point-prediction quality ---
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((q_true - q_true.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    mae = float(np.mean(abs_resid))
    per_model = {}
    for i, m in enumerate(models):
        row = ~np.isnan(Q[i]) & ~np.isnan(P[i])
        if row.sum() == 0:
            continue
        rr = Q[i][row] - P[i][row]
        per_model[m] = {"mae": round(float(np.mean(np.abs(rr))), 4), "n": int(row.sum())}

    # --- split-conformal: calib / eval halves (seeded, like gt_guarantee.split) ---
    idx = np.arange(len(q_true))
    rng = np.random.default_rng(SPLIT_SEED)
    rng.shuffle(idx)
    half = len(idx) // 2
    calib_i, eval_i = idx[:half], idx[half:]

    # grounded query thresholds per benchmark (p10..p90 of the 11 models' quality)
    bench_thresholds = {
        j: [_pct(Q[:, j][~np.isnan(Q[:, j])], p) for p in THRESH_PCTS]
        for j in range(len(benches))
    }
    # map each flat masked-cell index back to its (model_i, bench_j)
    cell_ij = list(zip(*np.where(mask), strict=True))  # list of (i,j) in mask order

    # per-benchmark difficulty spread σ_B (std of the 11 models' quality on B),
    # used for the heteroskedastic / normalized-conformal diagnostic variant.
    sigma_B = {j: max(float(np.nanstd(Q[:, j])), 1e-3) for j in range(len(benches))}

    def recovery_for_intervals(lo_arr, hi_arr) -> tuple[float, float, int, int]:
        """Decisive (non-straddling) rate + decisive-feasibility-error over
        eval cells × grounded thresholds, given per-eval-index [lo,hi]."""
        n_pairs = n_dec = n_dec_correct = 0
        for pos, k in enumerate(eval_i):
            i, j = cell_ij[k]
            ql, qh = lo_arr[pos], hi_arr[pos]
            for qstar in bench_thresholds[j]:
                n_pairs += 1
                if (ql >= qstar) or (qh < qstar):
                    n_dec += 1
                    if (ql >= qstar) == (q_true[k] >= qstar):
                        n_dec_correct += 1
        rec = n_dec / n_pairs if n_pairs else 0.0
        ferr = (1 - n_dec_correct / n_dec) if n_dec else 0.0
        return rec, ferr, n_dec, n_pairs

    bench_of_eval = np.array([cell_ij[k][1] for k in eval_i])
    sig_eval = np.array([sigma_B[j] for j in bench_of_eval])
    sig_calib = np.array([sigma_B[cell_ij[k][1]] for k in calib_i])

    alpha_results = {}
    for alpha in ALPHAS:
        # --- primary: global split-conformal (constant radius) ---
        tau = split_conformal_tau(abs_resid[calib_i], alpha)
        lo = q_hat[eval_i] - tau
        hi = q_hat[eval_i] + tau
        coverage = float(np.mean((q_true[eval_i] >= lo) & (q_true[eval_i] <= hi)))
        rec, ferr, n_dec, n_pairs = recovery_for_intervals(lo, hi)

        # --- diagnostic: normalized (heteroskedastic) split-conformal ---
        # score = |resid| / σ_B ; interval = q̂ ± τ_n·σ_B (adaptive width).
        norm_scores = abs_resid[calib_i] / sig_calib
        tau_n = split_conformal_tau(norm_scores, alpha)
        lo_n = q_hat[eval_i] - tau_n * sig_eval
        hi_n = q_hat[eval_i] + tau_n * sig_eval
        cov_n = float(np.mean((q_true[eval_i] >= lo_n) & (q_true[eval_i] <= hi_n)))
        rec_n, ferr_n, n_dec_n, _ = recovery_for_intervals(lo_n, hi_n)

        alpha_results[f"{alpha:g}"] = {
            "global": {
                "tau": round(tau, 4),
                "interval_width": round(2 * tau, 4),
                "eval_coverage": round(coverage, 4),
                "target_coverage": round(1 - alpha, 4),
                "recovery_rate": round(rec, 4),
                "n_decisive": n_dec,
                "n_pairs": n_pairs,
                "decisive_feasibility_error": round(ferr, 4),
            },
            "normalized_diagnostic": {
                "tau_normalized": round(tau_n, 4),
                "mean_interval_width": round(float(np.mean(2 * tau_n * sig_eval)), 4),
                "eval_coverage": round(cov_n, 4),
                "recovery_rate": round(rec_n, 4),
                "n_decisive": n_dec_n,
                "decisive_feasibility_error": round(ferr_n, 4),
            },
        }

    # --- structural-axis refusal ---
    def predict_interval(axis: str):
        """Refuse (None) on never-measured axes — no cross-context signal to transfer."""
        if axis in UNMEASURABLE_AXES:
            return None
        return "interval"  # measurable axis → would emit an interval

    refusal = {a: (predict_interval(a) is None) for a in sorted(UNMEASURABLE_AXES)}
    refusal["quality"] = predict_interval("quality") is None  # must be False
    assert all(refusal[a] for a in UNMEASURABLE_AXES), "structural axes must refuse"
    assert refusal["quality"] is False, "quality must emit an interval"

    result = {
        "metadata": {
            "experiment": "phase0_transfer_signal",
            "predictor": "leave-one-benchmark-out two-way additive (col-effect + row-resid)",
            "n_models": len(models),
            "n_benchmarks": len(benches),
            "n_cells": int(mask.sum()),
            "split_seed": SPLIT_SEED,
            "threshold_percentiles": list(THRESH_PCTS),
            "quality_units": "accuracy [0,1]",
        },
        "point_prediction": {"r2": round(r2, 4), "mae": round(mae, 4),
                             "per_model_mae": per_model},
        "conformal": alpha_results,
        "structural_refusal": refusal,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))

    # --- console summary + the GO/NO-GO number ---
    print(f"LOBO additive: R²={r2:.3f}  MAE={mae:.3f}  (n={int(mask.sum())} cells)")
    for a, r in alpha_results.items():
        g, nd = r["global"], r["normalized_diagnostic"]
        print(f"  α={a} [global]: width={g['interval_width']:.3f}  "
              f"cov={g['eval_coverage']:.3f}(t{g['target_coverage']})  "
              f"recovery={100*g['recovery_rate']:.1f}%  "
              f"feas-err={100*g['decisive_feasibility_error']:.1f}%")
        print(f"  α={a} [norm ]: meanW={nd['mean_interval_width']:.3f}  "
              f"cov={nd['eval_coverage']:.3f}  "
              f"recovery={100*nd['recovery_rate']:.1f}%  "
              f"feas-err={100*nd['decisive_feasibility_error']:.1f}%")
    print(f"structural refusal OK: {all(refusal[a] for a in UNMEASURABLE_AXES)}")
    g05 = alpha_results["0.05"]["global"]["recovery_rate"]
    n05 = alpha_results["0.05"]["normalized_diagnostic"]["recovery_rate"]
    print(f"\n>>> recovery_rate@0.05: global={100*g05:.1f}%  normalized={100*n05:.1f}%  "
          f"(GO≥~30–40%, NO-GO<~15%)")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
