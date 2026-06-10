"""Q3 tests — Δ(R) closed form, gadget consistency, and the biting-slice regret."""

from __future__ import annotations

from prudent_ai.analysis.regret_delta import delta_R, gadget_minimax, slice_regret


def test_delta_R_closed_form():
    # δ=λ=1 → 1·1/(1+1) = 0.5
    assert delta_R(1.0, 1.0) == 0.5
    assert delta_R(0.0, 1.0) == 0.0
    assert delta_R(2.0, 4.0) == (2.0 * 4.0) / (2.0 + 4.0)


def test_closed_form_matches_proven_gadget_minimax():
    for d, lam in [(0.5, 1.0), (2.0, 0.3), (1.0, 1.0), (0.1, 5.0)]:
        assert abs(delta_R(d, lam) - gadget_minimax(d, lam)) < 1e-12


def test_floor_below_both_naive_rules():
    # Δ(R) ≤ min(δ,λ) strictly when both positive (both naive rules exceed the floor)
    d, lam = 3.0, 1.0
    dr = delta_R(d, lam)
    assert dr < min(d, lam)


def test_slice_regret_biting():
    # cheap(cost 1, q 0.4) infeasible at q*=0.6; feasible: mid(cost 4, q 0.7) is min-cost.
    quality = {"cheap": 0.4, "mid": 0.7, "dear": 0.95}
    cost = {"cheap": 1.0, "mid": 4.0, "dear": 9.0}
    s = slice_regret("b", quality, cost, q_star=0.6, lam=1.0)
    assert s is not None
    assert s.delta == 3.0                      # cost_feas(mid 4) − cost_cheap(1)
    assert s.delta_R == delta_R(3.0, 1.0)
    assert s.regret_costmin == 1.0             # = λ
    assert s.regret_overprov == 3.0            # = δ
    assert s.delta_R <= s.regret_costmin and s.delta_R <= s.regret_overprov
    assert abs(s.overshoot_rel - 3.0 / 4.0) < 1e-12


def test_slice_regret_non_biting_returns_none():
    # cheapest is already feasible at q*=0.3 → not biting
    quality = {"cheap": 0.4, "dear": 0.95}
    cost = {"cheap": 1.0, "dear": 9.0}
    assert slice_regret("b", quality, cost, q_star=0.3, lam=1.0) is None
    # unsatisfiable query → None
    assert slice_regret("b", quality, cost, q_star=0.99, lam=1.0) is None
