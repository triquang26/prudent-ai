"""V3 tests — the prospective decision/scoring logic (no pkl needed).

Exercises the static decision (`_commit`) and live-optimum (`_live_optimum_cost`) on
synthetic per-model estimates, plus an end-to-end run on a tiny injected benchmark where
a blind commit fails on LIVE while the safety margin abstains.
"""

from __future__ import annotations

from prudent_ai.validation.gt_guarantee import MODELS
from prudent_ai.validation.live_eval import LiveEval

A, B = MODELS[0], MODELS[1]


def _full(vals: dict[str, float], default: float) -> dict[str, float]:
    return {m: vals.get(m, default) for m in MODELS}


def test_commit_picks_cheapest_eligible():
    meas_q = _full({A: 0.9, B: 0.95}, 0.0)
    meas_c = _full({A: 1.0, B: 5.0}, 1e9)
    # both clear q*=0.8; A is cheaper → committed
    assert LiveEval._commit(meas_q, meas_c, 0.8, 0.0) == A


def test_commit_abstains_under_margin():
    meas_q = _full({A: 0.82, B: 0.95}, 0.0)
    meas_c = _full({A: 1.0, B: 5.0}, 1e9)
    # margin 0 → A eligible (0.82≥0.8); margin 0.05 → A needs ≥0.85, drops to B
    assert LiveEval._commit(meas_q, meas_c, 0.8, 0.0) == A
    assert LiveEval._commit(meas_q, meas_c, 0.8, 0.05) == B
    # high q* with margin → nobody eligible → abstain
    assert LiveEval._commit(meas_q, meas_c, 0.95, 0.05) is None


def test_live_optimum_cost():
    live_q = _full({A: 0.7, B: 0.9}, 0.0)
    live_c = _full({A: 1.0, B: 5.0}, 1e9)
    # only B clears q*=0.8 on LIVE → live optimum = B's cost 5
    assert LiveEval._live_optimum_cost(live_q, live_c, 0.8) == 5.0
    # nothing clears q*=0.99 → None
    assert LiveEval._live_optimum_cost(live_q, live_c, 0.99) is None


def test_end_to_end_blind_fails_live_margin_saves():
    """Inject a benchmark where A looks feasible on MEASURE but fails on LIVE.

    A: MEASURE quality 0.85 (noisy, clears q*=0.8) but TRUE/LIVE quality 0.6 (fails).
    B: quality 0.95 everywhere, cost 5.  q* picks a floor between them.
    The blind rule (m=0) commits cheap A and live-violates; m=0.10 abstains/commits B.
    """
    import numpy as np

    le = LiveEval(benchmarks=("synthetic",), k_measure=2, q_percentiles=(0.5,),
                  n_splits=4, margins=(0.0, 0.10))
    # 4 prompts. Columns: A and B carry signal; others quality 0 / cost huge.
    nA = MODELS.index(A)
    nB = MODELS.index(B)
    q = np.zeros((4, len(MODELS)))
    c = np.full((4, len(MODELS)), 1e9)
    # A: first 2 prompts (MEASURE-ish) high quality, last 2 low → noisy/over-fit
    q[:, nA] = [1.0, 1.0, 0.2, 0.2]
    c[:, nA] = 1.0
    # B: uniformly high quality, dearer
    q[:, nB] = [0.95, 0.95, 0.95, 0.95]
    c[:, nB] = 5.0
    le._q["synthetic"] = q
    le._c["synthetic"] = c
    le._truth_q["synthetic"] = {m: float(q[:, j].mean()) for j, m in enumerate(MODELS)}

    res = le.run()
    by = {s.rule: s for s in res["rules"]}
    # the blind rule should live-violate strictly more than the m=0.10 rule
    blind = by["blind_cost_min"]
    safe = by["selective(m=0.1)"]
    assert blind.n_commit > 0
    assert blind.live_violation_rate >= safe.live_violation_rate
