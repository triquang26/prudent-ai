"""W4-residual tests — the two-sided band controls min-sufficiency (synthetic Outcomes).

No pkl needed: we build Outcome objects directly to exercise `decide_two_sided`. The
biting case: a cheap config is truly feasible but its noisy quality dipped below the
margin, so a one-sided rule over-provisions (commits the dearer config). The band must
turn that over-provisioning commit into an ABSTAIN.
"""

from __future__ import annotations

from prudent_ai.validation.gt_guarantee import MODELS
from prudent_ai.validation.minsuff_guarantee import (
    MinSuffGuarantee,
    decide_two_sided,
)

CHEAP, DEAR = MODELS[0], MODELS[1]


def _outcome(noisy_q_cheap, *, q_star=0.5):
    """cheap: cost 1, TRUE quality 0.55 (feasible), noisy quality = arg.
       dear:  cost 5, TRUE quality 0.95 (feasible), noisy quality 0.95.
       all other models: quality 0, cost huge (never eligible / never cheaper)."""
    nq = {m: 0.0 for m in MODELS}
    nc = {m: 1e6 for m in MODELS}
    tq = {m: 0.0 for m in MODELS}
    tc = {m: 1e6 for m in MODELS}
    nq[CHEAP], nc[CHEAP], tq[CHEAP], tc[CHEAP] = noisy_q_cheap, 1.0, 0.55, 1.0
    nq[DEAR], nc[DEAR], tq[DEAR], tc[DEAR] = 0.95, 5.0, 0.95, 5.0
    from prudent_ai.validation.gt_guarantee import Outcome
    return Outcome(
        benchmark="b", q_star=q_star, seed=0,
        noisy_quality=nq, noisy_cost=nc,
        truth_min_cost_feasible=CHEAP, truth_min_cost=1.0,
        truth_quality=tq, truth_cost=tc, has_truth_feasible=True,
    )


def test_one_sided_over_provisions_band_abstains():
    # cheap is truly feasible (0.55 ≥ 0.5) but noisy quality 0.48 < q*+margin → skipped.
    o = _outcome(0.48, q_star=0.5)
    margin = 0.05  # eligible needs noisy_q ≥ 0.55 → only DEAR qualifies

    # one-sided (band=0 but cheap noisy 0.48 < q*=0.5 so b=0 does NOT catch it): commits DEAR
    d0 = decide_two_sided(o, margin, band=0.0)
    assert d0.committed and d0.feasible
    assert not d0.min_sufficient          # over-provisioned: DEAR cost 5 ≫ min-cost 1

    # band=0.05 → guard threshold q*−b = 0.45; cheap noisy 0.48 ≥ 0.45 ⇒ abstain
    d1 = decide_two_sided(o, margin, band=0.05)
    assert not d1.committed               # the band catches the over-provisioning risk


def test_band_commits_when_truly_min_sufficient():
    # cheap noisy quality clears the margin → it IS the committed (cheapest eligible)
    o = _outcome(0.60, q_star=0.5)
    d = decide_two_sided(o, margin=0.05, band=0.05)
    assert d.committed and d.feasible and d.min_sufficient


def test_band_point_monotone_risk():
    """Risk_min_sufficient is non-increasing as the band widens (on a small battery)."""
    outs = [_outcome(0.48), _outcome(0.49), _outcome(0.60), _outcome(0.62)]
    g = MinSuffGuarantee()
    r_small = g.band_point(outs, 0.05, 0.0).risk_min_sufficient
    r_large = g.band_point(outs, 0.05, 0.05).risk_min_sufficient
    assert r_large <= r_small
