"""Selective right-sizing procedure (§6 / §9) — the method, method-as-star.

Wraps the P3 decidability classifier into a *selective* decision rule that either
commits or abstains-informatively:

  - q DECIDABLE        → COMMIT(x̂)            — the identified minimum-sufficient config.
  - q UNDERDETERMINED  → ABSTAIN(F, VoI-rank) — name the blocking fields AND rank which
                          to measure next by cost-aware VoI (§7). This is the informative
                          abstention that exceeds Trust-or-Escalate: it does not merely
                          decline, it points at the field to acquire.
  - q INFEASIBLE       → INFEASIBLE.

This is the §9 interface-kit `solve_selective` skeleton, realized. It reads the
substrate only through the C7 interface (via classify_query / classify_candidate);
φ, κ, regime, α, λ are all solver-side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from prudent_ai.solver.beliefs import DEFAULT_KAPPA, Phi
from prudent_ai.solver.decidability import Decidability, classify_query
from prudent_ai.solver.regimes import FULL
from prudent_ai.solver.voi import DEFAULT_LAMBDA, AxisVoI, voi_ranking

if TYPE_CHECKING:
    from prudent_ai.solver.query import Query
    from prudent_ai.substrate import Substrate


class Action(StrEnum):
    COMMIT = "commit"
    ABSTAIN = "abstain"
    INFEASIBLE = "infeasible"


@dataclass(frozen=True)
class Recommendation:
    """The procedure's output for one query."""

    action: Action
    # COMMIT
    committed_config: str | None = None
    # ABSTAIN — the blocking-field set F and the cost-aware VoI acquisition ranking
    blocking_axes: frozenset[str] = frozenset()
    voi_ranking: tuple[AxisVoI, ...] = field(default_factory=tuple)

    @property
    def acquire_next(self) -> str | None:
        """The single axis the procedure recommends measuring next (top VoI/cost)."""
        return self.voi_ranking[0].axis if self.voi_ranking else None


def right_size(
    sub: Substrate,
    query: Query,
    kappa: tuple[str, ...] = DEFAULT_KAPPA,
    phi: Phi = Phi.INTERVAL,
    regime: frozenset[str] = FULL,
    lam: float = DEFAULT_LAMBDA,
) -> Recommendation:
    """Run the selective procedure on one query (§6/§9)."""
    res = classify_query(sub, query, kappa, phi, regime)

    if res.label is Decidability.DECIDABLE:
        return Recommendation(
            action=Action.COMMIT,
            committed_config=res.argmin_config,
        )

    if res.label is Decidability.INFEASIBLE:
        return Recommendation(action=Action.INFEASIBLE)

    # UNDERDETERMINED → abstain, but name what to measure next (VoI-ranked).
    ranking = voi_ranking(sub, query, res.blocking_axes, kappa, phi, regime, lam)
    return Recommendation(
        action=Action.ABSTAIN,
        blocking_axes=res.blocking_axes,
        voi_ranking=tuple(ranking),
    )
