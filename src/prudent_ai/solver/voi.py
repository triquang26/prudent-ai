"""Value of Information (§7 / §8.7) — abstention that names what to measure.

For an underdetermined query, VoI(f) is the expected reduction in decision regret
from measuring a blocking field f:

    VoI(f) = E[ L(x̂_E) ] − E_observe-f[ L(x̂_{E ∪ {f}}) ]              (§7)

with decision loss  L(x̂) = max(0, cost(x̂) − cost(x*)) + λ · violation(x̂).

Operationalization (bounding model, isolates f's effect). Resolving the blocking
axis f splits the completions of E into two worlds — the §8.2 gadget:
  W_fav   : f resolves so that f-pending candidates SATISFY their f-constraint;
  W_unfav : f resolves so that they VIOLATE it.
Holding every *other* uncertainty optimistic (so we measure f's contribution
alone), the procedure that cannot see f must commit one (randomized) action robust
to both worlds; its minimax regret is the pre-measurement loss. Once f is measured
the true world is revealed and the world-optimum is committed (regret 0 within this
isolation). Hence

    VoI(f) = minimax_committed_regret_over_{W_fav, W_unfav}.

On the two-candidate gadget (x_cheap cost 1, x_safe cost 1+δ, binding latency)
this yields exactly **VoI(latency) = δλ/(δ+λ) = Δ(R)** — the §8.7 identity
(irreducible regret of an evidence regime = VoI of the binding axis it omits).
That identity is pinned by tests/test_procedure.py.

Cost-aware acquisition (§7): rank by VoI(f) / cost(measure f) — cheap axes first,
pay to measure an expensive axis only when it earns its cost.

C7: reads the substrate only through `classify_candidate` (→ candidates/cell).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from prudent_ai.solver.beliefs import DEFAULT_KAPPA, Phi
from prudent_ai.solver.feasibility import FeasState, classify_candidate
from prudent_ai.solver.regimes import FULL

if TYPE_CHECKING:
    from prudent_ai.solver.query import Query
    from prudent_ai.substrate import Substrate

# Default violation penalty (cost units). The regret of committing an infeasible
# config; a tunable risk-aversion knob. The §8.7 identity holds for any λ > 0.
DEFAULT_LAMBDA = 1.0

# ---------------------------------------------------------------------------
# Acquisition-cost table (§7 cost-aware ranking) — documented, not fabricated
# evidence. Relative cost of *measuring* each axis once for a config, on a 0–1+
# scale. Cheap axes are benchmarkable; the hard-to-observe A_h axes cost a human
# audit / study and are deliberately expensive.
# ---------------------------------------------------------------------------
# Relative acquisition costs, grounded in published real-world figures (cited in
# Appendix; affects only plan ORDERING, never the commit/abstain verdict):
#   cost      ~free: read a token price sheet.
#   latency/throughput/memory: a few GPU-hours of micro-benchmarking
#     (A100 $0.60-$4.09/hr, H100 $1.49-$6.98/hr) -> single-digit to tens of $.
#   energy:   measured by FREE open-source software (Zeus/NVML/RAPL) piggybacking
#     on the same GPU-time as the micro-benchmarks -> NOT a costly axis (corrected
#     from an earlier 0.4; real energy instrumentation is essentially free).
#   quality:  run an eval suite (HELM per-model $85-$11k) -> the costliest compute axis.
#   reviewer_burden: sustained expert human review ($40+/hr, hundreds-thousands per batch).
#   governance: a SOC 2 Type II ($20k-$80k) or HIPAA assessment ($100k-$500k+) audit
#     -> the most expensive axis by 1-3 orders of magnitude.
ACQUISITION_COST: dict[str, float] = {
    "cost": 0.05,            # arithmetic from a token price sheet (~free)
    "latency_p95": 0.1,      # micro-benchmark (GPU-hours)
    "throughput": 0.1,       # micro-benchmark (GPU-hours)
    "energy": 0.15,          # free software (Zeus/NVML) on the same GPU-time
    "memory_hw": 0.2,        # profiling
    "quality": 0.3,          # run an eval suite (HELM per-model $85-$11k)
    "reviewer_burden": 0.8,  # sustained expert human review (A_h)
    "governance": 1.0,       # SOC 2 / HIPAA compliance audit (A_h), most expensive
}
_DEFAULT_ACQ_COST = 0.5


@dataclass(frozen=True)
class AxisVoI:
    axis: str
    voi: float            # expected regret reduction from measuring this axis
    acquisition_cost: float
    voi_per_cost: float   # VoI / cost(measure) — the cost-aware ranking key


def regret(cost_x: float, cost_opt: float, infeasible: bool, lam: float) -> float:
    """L(x) = max(0, cost(x) − cost(x*)) + λ·violation(x)."""
    overshoot = max(0.0, cost_x - cost_opt)
    return overshoot + (lam if infeasible else 0.0)


def _minimax_two_world(
    regret_fav: dict[str, float], regret_unfav: dict[str, float]
) -> float:
    """Randomized minimax regret over two worlds (§8.4).

    Each action (commit a candidate) has a regret in each world. The rule may
    randomize. Returns min over mixed strategies of the worst-world expected
    regret. For two worlds the optimum mixes the best-in-fav and best-in-unfav
    actions; closed form.
    """
    if not regret_fav:
        return 0.0
    u = min(regret_fav, key=lambda a: regret_fav[a])   # best action in W_fav
    v = min(regret_unfav, key=lambda a: regret_unfav[a])  # best action in W_unfav
    if u == v:
        # one action dominates both worlds → pure strategy
        return max(regret_fav[u], regret_unfav[u])

    # mix u and v with weight p on u: minimize max(R_fav(p), R_unfav(p))
    # R_fav(p)   = p·rf_u + (1-p)·rf_v
    # R_unfav(p) = p·ru_u + (1-p)·ru_v
    rf_u, rf_v = regret_fav[u], regret_fav[v]
    ru_u, ru_v = regret_unfav[u], regret_unfav[v]
    # endpoints
    best = min(max(rf_u, ru_u), max(rf_v, ru_v))
    # interior crossing where R_fav(p) == R_unfav(p)
    denom = (rf_u - rf_v) - (ru_u - ru_v)
    if denom != 0.0:
        p = (ru_v - rf_v) / denom
        if 0.0 <= p <= 1.0:
            val = p * rf_u + (1 - p) * rf_v
            best = min(best, val)
    return best


def voi_for_axis(
    sub: Substrate,
    query: Query,
    axis_f: str,
    kappa: tuple[str, ...] = DEFAULT_KAPPA,
    phi: Phi = Phi.INTERVAL,
    regime: frozenset[str] = FULL,
    lam: float = DEFAULT_LAMBDA,
) -> float:
    """VoI of measuring *axis_f* for *query* (expected regret reduction)."""
    verdicts = [
        classify_candidate(sub, c.id, query.bundle, kappa, phi, regime)
        for c in sub.candidates(query.tau)
    ]
    # Candidates not provably-infeasible are the decision set.
    maybe = [v for v in verdicts if v.state is not FeasState.PROVABLY_INFEASIBLE]
    if not maybe:
        return 0.0

    def cost_of(v) -> float | None:
        return v.cost_belief.point if v.cost_belief.is_present else None

    # Feasibility of candidate v in a world where axis_f resolves `f_ok`,
    # holding all OTHER pending axes optimistic (feasible) to isolate f.
    def feasible_in_world(v, f_ok: bool) -> bool:
        if v.state is FeasState.PROVABLY_FEASIBLE:
            return True
        # possibly-feasible: depends on its pending fields
        if axis_f in v.pending_fields:
            if not f_ok:
                return False
        # other pending axes held optimistic → feasible
        return True

    def world_optimum_cost(f_ok: bool) -> float | None:
        costs = [
            cost_of(v)
            for v in maybe
            if feasible_in_world(v, f_ok) and cost_of(v) is not None
        ]
        return min(costs) if costs else None

    opt_fav = world_optimum_cost(True)
    opt_unfav = world_optimum_cost(False)

    # Committable actions = candidates with a known cost (we can only commit to a
    # config we can both name and price).
    actions = [v for v in maybe if cost_of(v) is not None]
    if not actions:
        return 0.0

    regret_fav: dict[str, float] = {}
    regret_unfav: dict[str, float] = {}
    for v in actions:
        c = cost_of(v)
        # If a world has no feasible candidate, committing anything is infeasible
        # → regret = λ (the violation penalty). Otherwise regret vs that world's
        # optimum, charging λ if this candidate is itself infeasible in the world.
        regret_fav[v.config_id] = (
            lam if opt_fav is None
            else regret(c, opt_fav, not feasible_in_world(v, True), lam)
        )
        regret_unfav[v.config_id] = (
            lam if opt_unfav is None
            else regret(c, opt_unfav, not feasible_in_world(v, False), lam)
        )

    return _minimax_two_world(regret_fav, regret_unfav)


def voi_ranking(
    sub: Substrate,
    query: Query,
    blocking_axes: frozenset[str],
    kappa: tuple[str, ...] = DEFAULT_KAPPA,
    phi: Phi = Phi.INTERVAL,
    regime: frozenset[str] = FULL,
    lam: float = DEFAULT_LAMBDA,
) -> list[AxisVoI]:
    """Rank blocking axes by cost-aware VoI (the acquisition suggestion, §7)."""
    out: list[AxisVoI] = []
    for f in sorted(blocking_axes):
        v = voi_for_axis(sub, query, f, kappa, phi, regime, lam)
        acq = ACQUISITION_COST.get(f, _DEFAULT_ACQ_COST)
        out.append(AxisVoI(axis=f, voi=v, acquisition_cost=acq,
                           voi_per_cost=v / acq if acq > 0 else float("inf")))
    # rank by cost-aware value, then raw VoI, descending
    out.sort(key=lambda a: (a.voi_per_cost, a.voi), reverse=True)
    return out
