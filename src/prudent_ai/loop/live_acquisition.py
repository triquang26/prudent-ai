"""LiveAcquisitionLoop — close the selective procedure's loop with real measurement.

Given an underdetermined query under a masked substrate, the loop:
  1. classify_query → if DECIDABLE commit, if INFEASIBLE stop;
  2. else VoI-rank the blocking axes (existing `voi_ranking`) and pick the top
     **measurable** axis (refuse the never-measured structural axes);
  3. **acquire** that axis: read its true measured value (the oracle) for each candidate
     and write it into a scratch overlay — an `OverlayedSubstrate`, never the frozen db;
  4. re-run the verdict; repeat until commit / infeasible / probe budget.

The acquisition is real in the sense the spec means for an offline GT corpus: the value is
genuinely revealed from measured RouterBench ground truth and re-entered into the store,
versus the simulated probe-count. Governance and the other structural axes have no
measurement path here (Appendix: no config↔governance audit data), so if the only way
forward is a structural axis the loop raises `NoMeasurementPathError` rather than fake it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from prudent_ai.analysis.empirical_prior_map import UNMEASURABLE_AXES
from prudent_ai.solver.beliefs import Phi
from prudent_ai.solver.decidability import Decidability, classify_query
from prudent_ai.solver.query import Query
from prudent_ai.solver.voi import ACQUISITION_COST, voi_ranking
from prudent_ai.transfer.overlay import OverlayedSubstrate

# the loop reads measured ground truth (κ={H,M}) and uses interval semantics
_KAPPA = ("H", "M")
_PHI = Phi.INTERVAL


class NoMeasurementPathError(RuntimeError):
    """Raised when the only blocking axes are structurally unmeasurable (e.g. governance).

    The loop refuses to invent a measurement that does not exist (no config↔audit data).
    """


@dataclass
class LoopResult:
    action: str                       # "commit" | "infeasible" | "abstain_no_path"
    committed_config: str | None = None
    probes: list[str] = field(default_factory=list)   # axes acquired, in order
    acquisition_cost: float = 0.0
    hidden_violation: bool | None = None    # filled by the scorer
    min_sufficient: bool | None = None      # filled by the scorer


class LiveAcquisitionLoop:
    """Run the real acquire→re-verdict→commit loop on one masked query."""

    def __init__(
        self,
        oracle: Callable[[str, str], float | None],
        max_probes: int = 8,
    ) -> None:
        # oracle(config_id, axis) -> true measured value (or None if genuinely unknown).
        self._oracle = oracle
        self._max_probes = max_probes

    def run(self, masked_sub, query: Query) -> LoopResult:
        revealed: dict[tuple[str, str], tuple[float, float]] = {}
        probes: list[str] = []
        cost = 0.0

        for _ in range(self._max_probes + 1):
            sub = OverlayedSubstrate(masked_sub, revealed)
            res = classify_query(sub, query, kappa=_KAPPA, phi=_PHI)

            if res.label is Decidability.DECIDABLE:
                return LoopResult("commit", res.argmin_config, probes, round(cost, 4))
            if res.label is Decidability.INFEASIBLE:
                return LoopResult("infeasible", None, probes, round(cost, 4))

            # underdetermined → VoI-rank, pick the top MEASURABLE blocking axis
            ranking = voi_ranking(sub, query, res.blocking_axes, kappa=_KAPPA, phi=_PHI)
            axis = next((r.axis for r in ranking
                         if r.axis not in UNMEASURABLE_AXES), None)
            if axis is None:
                # every remaining blocker is structurally unmeasurable → cannot loop
                raise NoMeasurementPathError(
                    f"only structural blockers remain: {sorted(res.blocking_axes)}; "
                    "no measurement path (e.g. governance has no config↔audit data)."
                )

            # ACQUIRE: reveal the true value for every candidate's cell on this axis,
            # writing into the scratch overlay (never the frozen store).
            for cand in sub.candidates(query.tau):
                v = self._oracle(cand.id, axis)
                if v is not None:
                    revealed[(cand.id, axis)] = (v, v)  # point belief = measured value
            probes.append(axis)
            cost += ACQUISITION_COST.get(axis, 0.5)

        # ran out of probe budget while still underdetermined
        return LoopResult("abstain_no_path", None, probes, round(cost, 4))
