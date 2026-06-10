"""Evidence-decidability classifier (§5 / §8) — the anchor of Claim C1.

Given a query `q = (τ, c)`, a confidence filter κ, an aggregation mode φ, and an
evidence regime R, classify the *decision* (not the estimate) into:

  DECIDABLE          — ∃ provably-feasible x whose argmin-cost is invariant across
                       all completions of E (the optimal decision is identified).
  UNDERDETERMINED    — the minimum-sufficient decision is non-identifiable:
                       a missing/straddling field could flip the argmin.
  INFEASIBLE         — no candidate is provably-feasible across all completions.

Operationalization of "completions" (§5). We bound `Comp(E)` by best/worst case:
  - A candidate with a pending field (⊥ or straddling on a required axis) *could*
    become feasible under an optimistic completion and infeasible under a
    pessimistic one.
  - A candidate with ⊥ cost has an unknown objective value; optimistically it is
    arbitrarily cheap (lower-bounded at 0, since costs are non-negative).

The query is DECIDABLE iff there is a candidate that is feasible *for sure* and
costed *for sure*, and no completion of any pending/⊥-cost candidate can produce
a feasible-and-strictly-cheaper alternative. Otherwise a missing field flips the
argmin ⇒ UNDERDETERMINED. This is exactly the §8.6 characterization made
operational: decidable ⇔ every binding axis is certifiable from the regime.

C7: reads cells only via `classify_candidate`, which reads only via the substrate
interface. No DB access, aggregation, or certification happens in the substrate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from prudent_ai.solver.beliefs import DEFAULT_KAPPA, Phi
from prudent_ai.solver.feasibility import (
    FeasState,
    classify_candidate,
)
from prudent_ai.solver.regimes import FULL

if TYPE_CHECKING:
    from prudent_ai.solver.feasibility import CandidateVerdict
    from prudent_ai.solver.query import Query
    from prudent_ai.substrate import Substrate


class Decidability(StrEnum):
    DECIDABLE = "decidable"
    UNDERDETERMINED = "underdetermined"
    INFEASIBLE = "infeasible"


@dataclass(frozen=True)
class DecidabilityResult:
    """The label plus the *cause*, so the map is informative not just labelled."""

    label: Decidability
    # Axes responsible for underdetermination (pending on a maybe-feasible
    # candidate, or 'cost' when the objective itself is ⊥). Empty for DECIDABLE
    # and INFEASIBLE.
    blocking_axes: frozenset[str] = frozenset()
    n_candidates: int = 0
    n_provably_feasible: int = 0     # sure-feasible AND sure-costed
    n_possibly_feasible: int = 0
    n_provably_infeasible: int = 0
    # The committed config under the optimistic reading (for audit), or None.
    argmin_config: str | None = None


def classify_query(
    sub: Substrate,
    query: Query,
    kappa: tuple[str, ...] = DEFAULT_KAPPA,
    phi: Phi = Phi.INTERVAL,
    regime: frozenset[str] = FULL,
) -> DecidabilityResult:
    """Classify a query as decidable / underdetermined / infeasible (§5)."""
    verdicts: list[CandidateVerdict] = [
        classify_candidate(sub, cand.id, query.bundle, kappa, phi, regime)
        for cand in sub.candidates(query.tau)
    ]
    n_total = len(verdicts)
    n_pinf = sum(1 for v in verdicts if v.state is FeasState.PROVABLY_INFEASIBLE)
    n_poss = sum(1 for v in verdicts if v.state is FeasState.POSSIBLY_FEASIBLE)

    maybe = [v for v in verdicts if v.state is not FeasState.PROVABLY_INFEASIBLE]

    # INFEASIBLE — nothing can be feasible even under an optimistic completion.
    if not maybe:
        return DecidabilityResult(
            label=Decidability.INFEASIBLE,
            n_candidates=n_total,
            n_provably_feasible=0,
            n_possibly_feasible=0,
            n_provably_infeasible=n_pinf,
        )

    # Provably-feasible AND cost known → the only options we can *commit* to.
    pf_costed = [
        v
        for v in maybe
        if v.state is FeasState.PROVABLY_FEASIBLE and v.cost_belief.is_present
    ]

    # No sure-and-costed option → the best choice hinges on a ⊥/straddling field.
    if not pf_costed:
        blocking: set[str] = set()
        for v in maybe:
            blocking |= v.pending_fields
            if v.cost_belief.is_bottom:
                blocking.add("cost")
        return DecidabilityResult(
            label=Decidability.UNDERDETERMINED,
            blocking_axes=frozenset(blocking),
            n_candidates=n_total,
            n_provably_feasible=0,
            n_possibly_feasible=n_poss,
            n_provably_infeasible=n_pinf,
        )

    n_pf = len(pf_costed)
    # Worst-case cost of the best guaranteed option (min over sure options of their
    # guaranteed-achievable cost = cost_hi).
    best_sure = min(pf_costed, key=lambda v: v.cost_belief.hi)
    best_sure_cost = best_sure.cost_belief.hi

    # Could any completion of a pending / ⊥-cost candidate undercut best_sure_cost?
    blocking = set()
    for v in maybe:
        if v.state is FeasState.PROVABLY_FEASIBLE and v.cost_belief.is_present:
            # Sure-feasible & sure-costed: it cannot flip via a ⊥ field. Its own
            # cost interval could still make the argmin among sure options ambiguous.
            if v is best_sure:
                continue
            if v.cost_belief.lo < best_sure_cost:
                # interval overlap → which sure option is cheapest depends on the
                # realized cost ⇒ argmin not invariant.
                blocking.add("cost")
            continue
        # v has a pending field or ⊥ cost → optimistic cost is its lower bound.
        optimistic_cost = (
            v.cost_belief.lo if v.cost_belief.is_present else 0.0
        )
        if optimistic_cost < best_sure_cost:
            # A completion makes v feasible (pending resolves) and strictly cheaper
            # → it would win → argmin flips ⇒ underdetermined.
            blocking |= v.pending_fields
            if v.cost_belief.is_bottom:
                blocking.add("cost")

    if blocking:
        return DecidabilityResult(
            label=Decidability.UNDERDETERMINED,
            blocking_axes=frozenset(blocking),
            n_candidates=n_total,
            n_provably_feasible=n_pf,
            n_possibly_feasible=n_poss,
            n_provably_infeasible=n_pinf,
            argmin_config=best_sure.config_id,
        )

    return DecidabilityResult(
        label=Decidability.DECIDABLE,
        blocking_axes=frozenset(),
        n_candidates=n_total,
        n_provably_feasible=n_pf,
        n_possibly_feasible=n_poss,
        n_provably_infeasible=n_pinf,
        argmin_config=best_sure.config_id,
    )
