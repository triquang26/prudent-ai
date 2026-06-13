"""Phase 0b — scoped/stratified transfer signal (transparent NO-GO follow-up).

Phase 0 found recovery@0.05 = 2.5% on ALL 30 RouterBench benchmarks: good mean
prediction (R²=0.81) but heavy-tailed residuals (a cluster of near-unpredictable
benchmarks) force a wide distribution-free interval. This follow-up asks, transparently:

  (A) STRATIFIED: if we keep only the K best-transferring benchmarks (lowest LOBO MAE),
      recalibrating split-conformal WITHIN that stratum (Mondrian, so the ≤α guarantee
      still holds), how does recovery@0.05 move as a function of K? Reported as a full
      curve with the population share, NOT a single cherry-picked cutoff.
  (B) PREDICTOR: does a kNN-in-benchmark-space predictor (vs the additive model) change
      the point signal or recovery?

This is reported ALONGSIDE the full-set NO-GO, never replacing it. Excluding benchmarks
narrows the population; the curve makes that explicit.

Run:  PYTHONNOUSERSITE=1 uv run python experiments/phase0b_transfer_stratified.py
Out:  outputs/phase0/transfer_stratified.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from phase0_transfer_signal import (  # noqa: E402
    SPLIT_SEED,
    THRESH_PCTS,
    load_matrix,
    lobo_predict,
    split_conformal_tau,
)

REPO = Path(__file__).parents[1]
OUT = REPO / "outputs/phase0/transfer_stratified.json"
ALPHA = 0.05
KEEP_GRID = (30, 25, 20, 18, 15, 12, 10)


def knn_predict(Q: np.ndarray, k: int = 5) -> np.ndarray:
    """kNN-in-benchmark-space LOBO prediction.

    For target cell (m,B): similarity(B,B') = Pearson corr of the two benchmark
    columns over models m'≠m (no leak of m). Predict q̂[m,B] = similarity-weighted
    mean of q[m,B'] over the top-k most-similar benchmarks B'≠B.
    """
    n_m, n_b = Q.shape
    P = np.full_like(Q, np.nan)
    for i in range(n_m):
        for j in range(n_b):
            if np.isnan(Q[i, j]):
                continue
            sims = []
            for jj in range(n_b):
                if jj == j or np.isnan(Q[i, jj]):
                    continue
                a = Q[:, j].copy()
                b = Q[:, jj].copy()
                a[i] = np.nan
                b[i] = np.nan
                ok = ~np.isnan(a) & ~np.isnan(b)
                if ok.sum() < 3:
                    continue
                av, bv = a[ok], b[ok]
                if av.std() < 1e-9 or bv.std() < 1e-9:
                    s = 0.0
                else:
                    s = float(np.corrcoef(av, bv)[0, 1])
                sims.append((s, Q[i, jj]))
            if not sims:
                P[i, j] = np.nanmean(Q[i])
                continue
            sims.sort(key=lambda t: t[0], reverse=True)
            top = sims[:k]
            w = np.array([max(s, 0.0) + 1e-6 for s, _ in top])
            v = np.array([val for _, val in top])
            P[i, j] = float(np.sum(w * v) / np.sum(w))
    return P


def per_benchmark_mae(Q: np.ndarray, P: np.ndarray, n_b: int) -> dict[int, float]:
    out = {}
    for j in range(n_b):
        m = ~np.isnan(Q[:, j]) & ~np.isnan(P[:, j])
        if m.sum():
            out[j] = float(np.mean(np.abs(Q[:, j][m] - P[:, j][m])))
    return out


def recovery_in_stratum(Q, P, benches, keep_js, thresh):
    """Mondrian split-conformal recovery@ALPHA restricted to benchmarks in keep_js."""
    cells = [(i, j) for j in keep_js for i in range(Q.shape[0])
             if not np.isnan(Q[i, j]) and not np.isnan(P[i, j])]
    if len(cells) < 20:
        return None
    idx = np.arange(len(cells))
    rng = np.random.default_rng(SPLIT_SEED)
    rng.shuffle(idx)
    half = len(idx) // 2
    calib, ev = idx[:half], idx[half:]
    ar = np.array([abs(Q[cells[k][0], cells[k][1]] - P[cells[k][0], cells[k][1]])
                   for k in range(len(cells))])
    tau = split_conformal_tau(ar[calib], ALPHA)
    n_pairs = n_dec = n_dec_ok = n_cov = 0
    for k in ev:
        i, j = cells[k]
        qt = Q[i, j]
        qh = P[i, j]
        ql, qh2 = qh - tau, qh + tau
        n_cov += int(ql <= qt <= qh2)
        for qstar in thresh[j]:
            n_pairs += 1
            if (ql >= qstar) or (qh2 < qstar):
                n_dec += 1
                if (ql >= qstar) == (qt >= qstar):
                    n_dec_ok += 1
    return {
        "n_benchmarks": len(keep_js),
        "pop_share": round(len(keep_js) / Q.shape[1], 3),
        "tau": round(tau, 4),
        "interval_width": round(2 * tau, 4),
        "eval_coverage": round(n_cov / len(ev), 4),
        "recovery_rate": round(n_dec / n_pairs, 4) if n_pairs else 0.0,
        "decisive_feasibility_error": round(1 - n_dec_ok / n_dec, 4) if n_dec else 0.0,
    }


def main() -> None:
    models, benches, Q = load_matrix()
    n_b = len(benches)
    P_add = lobo_predict(Q)
    P_knn = knn_predict(Q)

    # point signal comparison
    def pt(P):
        m = ~np.isnan(Q) & ~np.isnan(P)
        r = Q[m] - P[m]
        sst = float(np.sum((Q[m] - Q[m].mean()) ** 2))
        return {"r2": round(1 - float(np.sum(r ** 2)) / sst, 4),
                "mae": round(float(np.mean(np.abs(r))), 4)}

    add_mae = per_benchmark_mae(Q, P_add, n_b)
    # rank benchmarks easiest→hardest by additive LOBO MAE
    ranked = sorted(add_mae, key=lambda j: add_mae[j])
    thresh = {j: [float(np.percentile(Q[:, j][~np.isnan(Q[:, j])], p))
                  for p in THRESH_PCTS] for j in range(n_b)}

    # (A) stratified recovery curve (additive predictor)
    curve = []
    for keep in KEEP_GRID:
        js = ranked[:keep]
        res = recovery_in_stratum(Q, P_add, benches, js, thresh)
        if res:
            res["kept_benchmarks"] = [benches[j] for j in js]
            res["max_benchmark_mae_in_stratum"] = round(max(add_mae[j] for j in js), 4)
            curve.append(res)

    # (B) kNN predictor recovery on the FULL set (global conformal, like phase0)
    knn_full = recovery_in_stratum(Q, P_knn, benches, list(range(n_b)), thresh)

    hardest = [{"benchmark": benches[j], "mae": round(add_mae[j], 4)}
               for j in ranked[-8:]]
    result = {
        "metadata": {"experiment": "phase0b_transfer_stratified", "alpha": ALPHA,
                     "predictors": ["additive", "knn"], "keep_grid": list(KEEP_GRID)},
        "point_signal": {"additive": pt(P_add), "knn": pt(P_knn)},
        "stratified_recovery_curve_additive": curve,
        "knn_full_set_recovery": knn_full,
        "hardest_benchmarks": hardest,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))

    print(f"point signal: additive {pt(P_add)}  |  knn {pt(P_knn)}")
    print("\nStratified recovery@0.05 (Mondrian conformal within kept stratum):")
    print(" keep  share  width  cov    recovery  feas-err   max-MAE-in-stratum")
    for r in curve:
        print(f"  {r['n_benchmarks']:>3}  {r['pop_share']:.2f}  {r['interval_width']:.3f}"
              f"  {r['eval_coverage']:.3f}  {100*r['recovery_rate']:>5.1f}%"
              f"  {100*r['decisive_feasibility_error']:>5.1f}%     "
              f"{r['max_benchmark_mae_in_stratum']:.3f}")
    print(f"\nkNN full-set recovery@0.05 = "
          f"{100*knn_full['recovery_rate']:.1f}% (feas-err "
          f"{100*knn_full['decisive_feasibility_error']:.1f}%)")
    print("hardest benchmarks (additive MAE):",
          ", ".join(f"{h['benchmark']}={h['mae']}" for h in hardest))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
