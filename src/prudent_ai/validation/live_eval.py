"""V3 — prospective LIVE evaluation on held-out future traffic (real prompt-split).

P5 V1 validates by *masking* an axis on a fixed slice. V3 asks the harder, prospective
question: a config is committed from the evidence available *now*; does it actually hold
up on the traffic that arrives *next*? With no model-serving stack, the honest surrogate
is a **disjoint prompt-split** of real RouterBench per-prompt data:

  * **MEASURE** set — the first `k_measure` prompts (seeded shuffle): the noisy evidence
    available at decision time. The procedure decides here.
  * **LIVE** set — the remaining, DISJOINT prompts: subsequent traffic the committed
    config actually serves. We score the *realized* outcome here.

The decision is genuinely out-of-sample: the procedure never sees the LIVE prompts. We
compare two rules on the SAME live traffic:

  * **selective(m)** — commit the cheapest config whose MEASURE quality clears `q*` by a
    safety margin `m`, else ABSTAIN;
  * **blind cost-min (m=0)** — current leaderboard practice: commit the cheapest config
    that clears `q*` on the noisy sample, no safety buffer (it always commits if any does).

Each committed config is scored on LIVE: realized feasibility (LIVE quality ≥ q*) and
realized cost-regret vs the LIVE-optimal (cheapest truly-LIVE-feasible config). The claim:
the safety margin transfers to genuinely future traffic — selective commits are
LIVE-feasible far more often than the blind rule — and selective abstains exactly where a
blind commit would fail live.

Direct pkl scoring (C7 not engaged); MEASURE and LIVE are disjoint (C8, no leakage).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from prudent_ai.validation.gt_guarantee import DEFAULT_PKL, MODELS

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class RuleLiveStats:
    rule: str
    margin: float
    n_queries: int
    n_commit: int
    n_live_feasible: int          # commits whose committed config truly clears q* on LIVE
    coverage: float
    live_feasibility_rate: float  # n_live_feasible / n_commit (the prospective guarantee)
    live_violation_rate: float    # 1 − live_feasibility_rate (blind commits that fail live)
    mean_live_regret_rel: float   # mean relative cost overshoot vs LIVE-optimal (feasible commits)


@dataclass
class LiveEval:
    """Prospective live evaluation via a disjoint MEASURE/LIVE prompt-split (V3)."""

    pkl_path: str = DEFAULT_PKL
    benchmarks: tuple[str, ...] = (
        "mmlu-professional-law",
        "arc-challenge",
        "winogrande",
        "grade-school-math",
        "hellaswag",
        "mmlu-moral-scenarios",
    )
    k_measure: int = 64
    q_percentiles: tuple[float, ...] = (0.40, 0.55, 0.70, 0.85)
    n_splits: int = 40
    base_seed: int = 11
    margins: tuple[float, ...] = (0.0, 0.05, 0.10)
    _q: dict[str, np.ndarray] = field(default_factory=dict, init=False, repr=False)
    _c: dict[str, np.ndarray] = field(default_factory=dict, init=False, repr=False)
    _truth_q: dict[str, dict[str, float]] = field(default_factory=dict, init=False, repr=False)

    def _load(self) -> None:
        if self._q:
            return
        import numpy as np
        import pandas as pd

        df = pd.read_pickle(self.pkl_path)
        for bench in self.benchmarks:
            sub = df[df["eval_name"] == bench].reset_index(drop=True)
            if len(sub) == 0:
                raise ValueError(f"benchmark {bench!r} not in {self.pkl_path}")
            q = np.column_stack([sub[m].astype(float).to_numpy() for m in MODELS])
            c = np.column_stack([sub[f"{m}|total_cost"].astype(float).to_numpy() for m in MODELS])
            self._q[bench] = q
            self._c[bench] = c
            self._truth_q[bench] = {m: float(q[:, j].mean()) for j, m in enumerate(MODELS)}

    def q_star_for(self, bench: str, percentile: float) -> float:
        """q* = a percentile of the 11 FULL-sample truth qualities (a fixed floor)."""
        import numpy as np
        self._load()
        tq = self._truth_q[bench]
        return float(np.quantile([tq[m] for m in MODELS], percentile))

    @staticmethod
    def _means(mat: np.ndarray, idx: list[int]) -> dict[str, float]:
        import numpy as np
        sub = mat[np.asarray(idx)]
        col = sub.mean(axis=0)
        return {m: float(col[j]) for j, m in enumerate(MODELS)}

    @staticmethod
    def _commit(meas_q, meas_c, q_star: float, margin: float) -> str | None:
        eligible = [m for m in MODELS if meas_q[m] >= q_star + margin]
        if not eligible:
            return None
        return min(eligible, key=lambda m: meas_c[m])

    @staticmethod
    def _live_optimum_cost(live_q, live_c, q_star: float) -> float | None:
        feas = [m for m in MODELS if live_q[m] >= q_star]
        if not feas:
            return None
        return min(live_c[m] for m in feas)

    def run(self) -> dict:
        """Decide on MEASURE, score on the disjoint LIVE split, per rule (margin)."""
        self._load()
        # accumulators per margin
        acc = {
            m: {"n": 0, "commit": 0, "live_feas": 0, "regret_sum": 0.0, "regret_n": 0}
            for m in self.margins
        }
        seed = self.base_seed
        n_skipped_small = 0
        for bench in self.benchmarks:
            n_prompts = self._q[bench].shape[0]
            if n_prompts <= self.k_measure + 1:
                n_skipped_small += 1
                continue
            for pct in self.q_percentiles:
                q_star = self.q_star_for(bench, pct)
                for _ in range(self.n_splits):
                    rng = random.Random(seed)
                    seed += 1
                    order = list(range(n_prompts))
                    rng.shuffle(order)
                    measure_idx = order[: self.k_measure]
                    live_idx = order[self.k_measure:]
                    meas_q = self._means(self._q[bench], measure_idx)
                    meas_c = self._means(self._c[bench], measure_idx)
                    live_q = self._means(self._q[bench], live_idx)
                    live_c = self._means(self._c[bench], live_idx)
                    live_opt = self._live_optimum_cost(live_q, live_c, q_star)
                    if live_opt is None:
                        continue  # no config is live-feasible → ill-posed for this split
                    for margin in self.margins:
                        a = acc[margin]
                        a["n"] += 1
                        committed = self._commit(meas_q, meas_c, q_star, margin)
                        if committed is None:
                            continue
                        a["commit"] += 1
                        if live_q[committed] >= q_star:
                            a["live_feas"] += 1
                            reg = max(0.0, (live_c[committed] - live_opt) / live_opt)
                            a["regret_sum"] += reg
                            a["regret_n"] += 1
        stats: list[RuleLiveStats] = []
        for margin in self.margins:
            a = acc[margin]
            nc = a["commit"]
            lf = a["live_feas"]
            stats.append(RuleLiveStats(
                rule=("blind_cost_min" if margin == 0.0 else f"selective(m={margin:g})"),
                margin=margin, n_queries=a["n"], n_commit=nc, n_live_feasible=lf,
                coverage=(nc / a["n"] if a["n"] else 0.0),
                live_feasibility_rate=(lf / nc if nc else 0.0),
                live_violation_rate=((nc - lf) / nc if nc else 0.0),
                mean_live_regret_rel=(a["regret_sum"] / a["regret_n"] if a["regret_n"] else 0.0),
            ))
        return {
            "meta": {
                "pkl": self.pkl_path, "benchmarks": list(self.benchmarks),
                "k_measure": self.k_measure, "q_percentiles": list(self.q_percentiles),
                "n_splits": self.n_splits, "base_seed": self.base_seed,
                "margins": list(self.margins), "n_skipped_small": n_skipped_small,
                "construction": "disjoint MEASURE/LIVE prompt-split; decide on MEASURE, "
                                "score realized outcome on LIVE",
            },
            "rules": [s for s in stats],
        }
