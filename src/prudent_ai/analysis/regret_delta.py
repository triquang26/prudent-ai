"""Q3 — realized mis-sizing regret vs the limit theorem Δ(R), with REAL slice geometry.

The §8 limit theorem says any rule operating under an evidence regime that omits a
binding axis pays at least the irreducible regret **Δ(R) = δλ/(δ+λ)** (the randomized
minimax over the two-world gadget, §8.4; the exact VoI identity, §8.7). Open-Q3 asks
whether *real* leaderboard mis-sizing on the slice exceeds this floor — an empirical
question, not a corollary.

Here we instantiate the gadget with parameters **read from real RouterBench truth**:
on a biting slice (the cheapest config is infeasible at q*), the binding-axis stakes are

  * **δ = the price of caution** = cost(true min-cost-feasible) − cost(global-cheapest):
    the extra real cost a rule pays to *guarantee* feasibility instead of grabbing the
    cheapest (infeasible) config. Measured, per slice.
  * **λ = the violation penalty** (the declared cost of committing an infeasible config;
    `DEFAULT_LAMBDA`, stated not fit).

Δ(R) = δλ/(δ+λ) is then the irreducible regret of *any* regime-restricted rule. Two
naive rules realize strictly more: the leaderboard **cost-minimizer** pays worst-world
regret **λ** (it commits the cheap config, infeasible), the cautious **over-provisioner**
pays **δ** (it commits the dear feasible config, overshooting) — both ≥ Δ(R) since
Δ(R) ≤ min(δ,λ). The **selective procedure** abstains (regret 0) and the VoI it would
pay to resolve the gamble equals Δ(R) exactly — measurable and *acquirable*, not paid
blind. This reuses the proven gadget loss (`solver/voi`), so the floor is the same
quantity as the VoI=Δ(R) identity, now carrying real δ.

Reads full-sample RouterBench truth via `GTCoverageGuarantee.truth` (direct pkl scoring,
C7 not engaged).
"""

from __future__ import annotations

from dataclasses import dataclass

from prudent_ai.solver.voi import DEFAULT_LAMBDA, _minimax_two_world


def delta_R(delta: float, lam: float) -> float:
    """The §8.7 irreducible regret Δ(R) = δλ/(δ+λ) (0 if both are 0)."""
    if delta <= 0.0 or lam <= 0.0:
        return 0.0
    return delta * lam / (delta + lam)


def gadget_minimax(delta: float, lam: float) -> float:
    """Δ(R) via the proven two-world minimax (consistency check for `delta_R`).

    Worlds: W_fav (cheap feasible) and W_unfav (cheap infeasible). Actions:
    commit-cheap → regret {fav:0, unfav:λ}; commit-safe → regret {fav:δ, unfav:0}.
    """
    regret_fav = {"cheap": 0.0, "safe": delta}
    regret_unfav = {"cheap": lam, "safe": 0.0}
    return _minimax_two_world(regret_fav, regret_unfav)


@dataclass(frozen=True)
class SliceRegret:
    benchmark: str
    q_star: float
    delta: float              # price of caution (real cost gap)
    lam: float                # violation penalty (declared)
    delta_R: float            # irreducible floor δλ/(δ+λ)
    regret_costmin: float     # leaderboard cost-minimizer worst-world regret (= λ)
    regret_overprov: float    # cautious over-provisioner worst-world regret (= δ)
    overshoot_rel: float      # relative cost of caution = (cost_feas-cost_cheap)/cost_feas
    cost_cheap: float
    cost_feas: float


def slice_regret(
    benchmark: str,
    quality: dict[str, float],
    cost: dict[str, float],
    q_star: float,
    lam: float = DEFAULT_LAMBDA,
) -> SliceRegret | None:
    """Per-slice δ/λ/Δ(R) + naive-rule realized regret on a BITING slice.

    Returns None when the query is unsatisfiable, or non-biting (the global-cheapest
    config is already feasible → no binding-axis regret).
    """
    models = list(quality)
    feasible = [m for m in models if quality[m] >= q_star]
    if not feasible:
        return None
    c_feas = min(feasible, key=lambda m: cost[m])
    c_cheap = min(models, key=lambda m: cost[m])
    if quality[c_cheap] >= q_star:
        return None  # cheapest is feasible → not biting
    cost_feas = cost[c_feas]
    cost_cheap = cost[c_cheap]
    delta = max(0.0, cost_feas - cost_cheap)
    dr = delta_R(delta, lam)
    return SliceRegret(
        benchmark=benchmark, q_star=q_star, delta=delta, lam=lam, delta_R=dr,
        regret_costmin=lam, regret_overprov=delta,
        overshoot_rel=(delta / cost_feas if cost_feas else 0.0),
        cost_cheap=cost_cheap, cost_feas=cost_feas,
    )
