"""Distribution-free coverage guarantee (§9) — the selective commit guarantee.

Goal (§9):  **P( x̂ feasible ∧ x̂ minimum-sufficient | q ∈ C ) ≥ 1 − α**,
where `C` is the commit set. We report the full **coverage–risk curve**
(coverage `|C|/|queries|` vs empirical risk), mirroring Trust-or-Escalate's
coverage-at-agreement reporting.

**Honest scope (§8.8).** True ground truth is P5. Here "truth" is *proxied* by the
richest belief the corpus affords — the procedure's verdict under a fuller
confidence policy `κ_truth` (default H+M+L) is taken as the reference, while the
operating procedure commits under `κ_operating` (default H+M). A commit is
*correct* iff the committed config is, under proxy-truth, feasible **and** the
identified minimum-sufficient choice. This is calibration on a confidence proxy,
not a held-out labelled slice — stated plainly, not hidden.

The tunable that traces the curve is a **commit margin** `m`: commit only when the
identified config's cost beats the next provably-feasible alternative by a relative
margin ≥ `m`. Larger `m` ⇒ more conservative ⇒ lower coverage, lower risk. This is
the OOP home of the guarantee; it reads the substrate only through the procedure /
classifier (C7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from prudent_ai.solver.beliefs import Phi
from prudent_ai.solver.decidability import Decidability, classify_query
from prudent_ai.solver.feasibility import FeasState, classify_candidate
from prudent_ai.solver.procedure import Action, right_size
from prudent_ai.solver.regimes import FULL

if TYPE_CHECKING:
    from prudent_ai.solver.query import Query
    from prudent_ai.substrate import Substrate

DEFAULT_MARGINS = (0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0)


@dataclass(frozen=True)
class CurvePoint:
    margin: float
    coverage: float       # |C| / |queries|
    risk: float           # empirical P(incorrect | committed)
    n_commit: int
    n_correct: int


@dataclass(frozen=True)
class Calibration:
    alpha: float
    margin: float | None       # smallest margin meeting risk ≤ α (None if none does)
    coverage: float
    risk: float


class CoverageGuarantee:
    """Coverage–risk analysis + calibration for the selective procedure (§9)."""

    def __init__(
        self,
        sub: Substrate,
        queries: list[Query],
        kappa_operating: tuple[str, ...] = ("H", "M"),
        kappa_truth: tuple[str, ...] = ("H", "M", "L"),
        phi: Phi = Phi.POINT,
        regime: frozenset[str] = FULL,
    ) -> None:
        self.sub = sub
        self.queries = queries
        self.kappa_operating = kappa_operating
        self.kappa_truth = kappa_truth
        self.phi = phi
        self.regime = regime

    # ------------------------------------------------------------------
    # Commit-confidence margin
    # ------------------------------------------------------------------

    def _commit_margin(self, query: Query) -> float | None:
        """Relative cost gap between the committed config and the next provably-
        feasible alternative, or None if the query is not committable.

        A larger gap means the identified optimum is more clearly the cheapest →
        a more confident commit. Returns 0.0 when there is no runner-up (the
        commit is unique among provably-feasible configs).
        """
        rec = right_size(self.sub, query, self.kappa_operating, self.phi, self.regime)
        if rec.action is not Action.COMMIT or rec.committed_config is None:
            return None

        costs: list[tuple[str, float]] = []
        for cand in self.sub.candidates(query.tau):
            v = classify_candidate(
                self.sub, cand.id, query.bundle,
                self.kappa_operating, self.phi, self.regime,
            )
            if v.state is FeasState.PROVABLY_FEASIBLE and v.cost_belief.is_present:
                costs.append((v.config_id, v.cost_belief.point))
        if not costs:
            return None
        costs.sort(key=lambda kv: kv[1])
        best_cost = costs[0][1]
        if len(costs) == 1:
            return 0.0
        runner_up = costs[1][1]
        if best_cost <= 0:
            return 0.0
        return (runner_up - best_cost) / best_cost

    # ------------------------------------------------------------------
    # Proxy-truth correctness
    # ------------------------------------------------------------------

    def _is_correct(self, query: Query, committed_config: str) -> bool:
        """Under proxy-truth (κ_truth), is committed_config feasible ∧ min-sufficient?

        Proxy-truth correctness = the richer-evidence procedure also identifies
        this exact config as the minimum-sufficient commit.
        """
        truth = classify_query(
            self.sub, query, self.kappa_truth, self.phi, self.regime
        )
        if truth.label is Decidability.DECIDABLE:
            return truth.argmin_config == committed_config
        # Under proxy-truth the decision is itself unidentified or infeasible → the
        # operating commit cannot be certified correct.
        return False

    # ------------------------------------------------------------------
    # Curve + calibration
    # ------------------------------------------------------------------

    def evaluate_at_margin(self, margin: float) -> CurvePoint:
        """Coverage and risk when committing only at confidence-margin ≥ *margin*."""
        n_commit = 0
        n_correct = 0
        for q in self.queries:
            rec = right_size(self.sub, q, self.kappa_operating, self.phi, self.regime)
            if rec.action is not Action.COMMIT or rec.committed_config is None:
                continue
            gap = self._commit_margin(q)
            if gap is None or gap < margin:
                continue
            n_commit += 1
            if self._is_correct(q, rec.committed_config):
                n_correct += 1
        n = len(self.queries)
        coverage = n_commit / n if n else 0.0
        risk = (n_commit - n_correct) / n_commit if n_commit else 0.0
        return CurvePoint(
            margin=margin, coverage=coverage, risk=risk,
            n_commit=n_commit, n_correct=n_correct,
        )

    def coverage_risk_curve(
        self, margins: tuple[float, ...] = DEFAULT_MARGINS
    ) -> list[CurvePoint]:
        return [self.evaluate_at_margin(m) for m in margins]

    def calibrate(
        self, alpha: float, margins: tuple[float, ...] = DEFAULT_MARGINS
    ) -> Calibration:
        """Smallest margin whose risk ≤ α (maximizes coverage subject to the guarantee)."""
        best: Calibration | None = None
        for pt in self.coverage_risk_curve(margins):
            if pt.risk <= alpha:
                # first (smallest margin) satisfying the risk bound = max coverage
                return Calibration(alpha=alpha, margin=pt.margin,
                                   coverage=pt.coverage, risk=pt.risk)
        # none meets the bound → report the lowest-risk point achieved
        pts = self.coverage_risk_curve(margins)
        if pts:
            best_pt = min(pts, key=lambda p: p.risk)
            best = Calibration(alpha=alpha, margin=None,
                               coverage=best_pt.coverage, risk=best_pt.risk)
        return best or Calibration(alpha=alpha, margin=None, coverage=0.0, risk=0.0)
