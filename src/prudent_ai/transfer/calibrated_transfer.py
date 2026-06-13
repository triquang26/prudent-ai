"""CalibratedTransfer — leave-one-benchmark-out predictor + split-conformal intervals.

Predicts a calibrated quality interval for a RouterBench (model, benchmark) cell from the
same model's quality on its OTHER benchmarks (two-way additive model), then wraps it in a
split-conformal radius τ_α so the interval covers the true value with probability ≥ 1−α.

The interval is the belief injected (via `OverlayedSubstrate`) for a fragmented-⊥ quality
cell; the existing verdict then commits only if the interval does not straddle the
threshold, which yields P(committed config infeasible | commit) ≤ α (finite-sample,
distribution-free) by conformal coverage.

Structural-axis refusal is explicit: `predict_interval` returns None for any axis in
`UNMEASURABLE_AXES` and for any non-`quality` axis — there is no cross-context signal to
transfer from on the never-measured axes, so the method abstains there by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from prudent_ai.analysis.empirical_prior_map import UNMEASURABLE_AXES
from prudent_ai.substrate.routerbench.parser import RouterBenchParser

# Only quality is transfer-predictable in this corpus (cost is cheaply acquirable, the
# structural axes have no cross-context signal). Refuse everything else.
TRANSFERABLE_AXES: frozenset[str] = frozenset({"quality"})
QUALITY_DOMAIN = (0.0, 1.0)
DEFAULT_SPLIT_SEED = 2024


@dataclass(frozen=True)
class TransferReport:
    alpha: float
    tau: float
    interval_width: float
    calib_coverage: float
    n_cells: int
    n_calib: int


def _config_id(model_slug: str, benchmark: str) -> str:
    """Match the RouterBench seeder id format `rb-{model_slug}-{benchmark}`."""
    return f"rb-{model_slug}-{benchmark}"


def _lobo_additive(Q: np.ndarray) -> np.ndarray:
    """Leave-one-benchmark-out two-way additive prediction for every cell.

    q̂[m,B] = coleff[B] (benchmark difficulty from other models) + rowresid[m] (model m's
    skill from its OTHER benchmarks, each de-meaned by its own col-effect). No value of
    the target cell enters its own prediction.
    """
    n_m, n_b = Q.shape
    P = np.full_like(Q, np.nan)
    # precompute, for each column, the leave-one-model-out column means
    for i in range(n_m):
        for j in range(n_b):
            if np.isnan(Q[i, j]):
                continue
            col = Q[:, j].copy()
            col[i] = np.nan
            coleff_j = np.nanmean(col)
            resids = []
            for jj in range(n_b):
                if jj == j or np.isnan(Q[i, jj]):
                    continue
                cjj = Q[:, jj].copy()
                cjj[i] = np.nan
                resids.append(Q[i, jj] - np.nanmean(cjj))
            rowresid_i = float(np.mean(resids)) if resids else 0.0
            P[i, j] = coleff_j + rowresid_i
    return P


def _split_conformal_tau(scores: np.ndarray, alpha: float) -> float:
    """Split-conformal radius: ceil((n+1)(1−α))/n empirical quantile of |residual|."""
    n = len(scores)
    if n == 0:
        return float("inf")
    s = np.sort(scores)
    k = min(max(int(np.ceil((n + 1) * (1 - alpha))), 1), n)
    return float(s[k - 1])


class CalibratedTransfer:
    """Fit once on the RouterBench quality matrix; emit calibrated intervals per cell."""

    def __init__(self, split_seed: int = DEFAULT_SPLIT_SEED) -> None:
        self.split_seed = split_seed
        self._point: dict[str, float] = {}          # config_id -> q̂
        self._abs_resid_calib: np.ndarray = np.array([])
        # held-out TEST half (disjoint from calibration) for the guarantee check:
        # (config_id, q_true, q_hat) — used to verify coverage ≥ 1−α / feas-err ≤ α.
        self._test_pairs: list[tuple[str, float, float]] = []
        self._fitted = False

    @classmethod
    def fit_from_pkl(
        cls, pkl_path: str | Path = "data/routerbench_0shot.pkl",
        split_seed: int = DEFAULT_SPLIT_SEED,
    ) -> CalibratedTransfer:
        self = cls(split_seed=split_seed)
        cfgs = RouterBenchParser().parse(pd.read_pickle(pkl_path))
        models = sorted({c.model for c in cfgs})
        benches = sorted({c.benchmark for c in cfgs})
        mi = {m: i for i, m in enumerate(models)}
        bj = {b: j for j, b in enumerate(benches)}
        Q = np.full((len(models), len(benches)), np.nan)
        slug = {}
        for c in cfgs:
            Q[mi[c.model], bj[c.benchmark]] = c.quality
            slug[c.model] = c.model_slug

        P = _lobo_additive(Q)
        mask = ~np.isnan(Q) & ~np.isnan(P)
        # store per-config predictions and a parallel cell list (mask/row-major order)
        inv_m = {i: m for m, i in mi.items()}
        inv_b = {j: b for b, j in bj.items()}
        cells: list[tuple[str, float, float]] = []  # (config_id, q_true, q_hat)
        for i in range(len(models)):
            for j in range(len(benches)):
                if mask[i, j]:
                    cid = _config_id(slug[inv_m[i]], inv_b[j])
                    self._point[cid] = float(P[i, j])
                    cells.append((cid, float(Q[i, j]), float(P[i, j])))

        # seeded half-split (the gt_guarantee discipline): calibrate τ on one half,
        # hold out the other for the guarantee check.
        abs_resid = np.abs(np.array([qt - qh for _, qt, qh in cells]))
        idx = np.arange(len(cells))
        rng = np.random.default_rng(split_seed)
        rng.shuffle(idx)
        half = len(idx) // 2
        calib_i, test_i = idx[:half], idx[half:]
        self._abs_resid_calib = abs_resid[calib_i]
        self._test_pairs = [cells[k] for k in test_i]
        self._fitted = True
        return self

    def test_guarantee(self, alpha: float) -> dict:
        """On the held-out test half: realized interval coverage and the decision-level
        feasibility error among decisive-satisfied commits, swept over query thresholds
        (p10..p90 of each cell's value is not available here, so we use a fixed grid in
        [0,1]). The conformal guarantee predicts coverage ≥ 1−α and feas-error ≤ α."""
        t = self.tau(alpha)
        n = len(self._test_pairs)
        covered = sum(1 for _, qt, qh in self._test_pairs if qh - t <= qt <= qh + t)
        grid = [round(0.1 * k, 2) for k in range(1, 10)]  # thresholds 0.1..0.9
        n_commit = n_infeas = 0
        for _, qt, qh in self._test_pairs:
            lo = max(QUALITY_DOMAIN[0], qh - t)
            for qstar in grid:
                if lo >= qstar:  # interval entirely satisfies q≥qstar → commit
                    n_commit += 1
                    if qt < qstar:  # true value violates → infeasible commit
                        n_infeas += 1
        return {
            "alpha": alpha,
            "n_test": n,
            "interval_coverage": round(covered / n, 4) if n else 0.0,
            "target_coverage": round(1 - alpha, 4),
            "n_decisive_commit": n_commit,
            "feasibility_error": round(n_infeas / n_commit, 4) if n_commit else 0.0,
        }

    def tau(self, alpha: float) -> float:
        if not self._fitted:
            raise RuntimeError("CalibratedTransfer not fitted")
        return _split_conformal_tau(self._abs_resid_calib, alpha)

    def report(self, alpha: float) -> TransferReport:
        t = self.tau(alpha)
        return TransferReport(
            alpha=alpha, tau=round(t, 6), interval_width=round(2 * t, 6),
            calib_coverage=float("nan"), n_cells=len(self._point),
            n_calib=len(self._abs_resid_calib),
        )

    def predict_point(self, config_id: str) -> float | None:
        return self._point.get(config_id)

    def predict_interval(
        self, config_id: str, axis: str, alpha: float,
    ) -> tuple[float, float] | None:
        """Calibrated [lo, hi] for (config, axis), or None (refusal).

        Refuses on structural axes and on any non-quality axis (no cross-context signal),
        and on configs with no transfer prediction. Otherwise returns the conformal
        interval clipped to the quality domain [0,1].
        """
        if axis in UNMEASURABLE_AXES or axis not in TRANSFERABLE_AXES:
            return None  # structural / non-transferable → refuse, abstain by construction
        pt = self._point.get(config_id)
        if pt is None:
            return None
        t = self.tau(alpha)
        lo = max(QUALITY_DOMAIN[0], pt - t)
        hi = min(QUALITY_DOMAIN[1], pt + t)
        return (lo, hi)

    def build_overlays(
        self, alpha: float, axis: str = "quality",
        config_ids: list[str] | None = None,
    ) -> dict[tuple[str, str], tuple[float, float]]:
        """Map {(config_id, axis): (lo, hi)} for the requested configs (default: all)."""
        cids = config_ids if config_ids is not None else list(self._point)
        out: dict[tuple[str, str], tuple[float, float]] = {}
        for cid in cids:
            iv = self.predict_interval(cid, axis, alpha)
            if iv is not None:
                out[(cid, axis)] = iv
        return out
