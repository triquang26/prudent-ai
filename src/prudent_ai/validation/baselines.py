"""Baseline lattice B1–B6 + the selective rule (§14) — decision rules for V1.

Each rule, given a query and a *visible* evidence regime (one axis masked out),
predicts a committed config or abstains. They differ in how they treat the masked
(unobservable) axis — which is exactly what the validation stresses:

  B1 accuracy-only   : argmax quality, ignore cost & every constraint.        (strawman)
  B2 observed-Pareto : min visible-cost s.t. VISIBLE constraints; ignore the   (MUST beat)
                       masked axis entirely → commits even if it binds.
  B3 imputation      : impute the masked axis (global median) then decide.     (MUST beat)
  B4 missing-as-fail : a masked binding constraint = violated → abstain.       (conservative)
  B5 oracle          : sees the TRUE masked values → true min-cost feasible.   (regret floor)
  B6 cost-accuracy   : min cost s.t. quality only; drop latency/energy/gov.    (FrugalGPT-style)
  selective (ours)   : P4 right_size under the visible regime — COMMIT iff
                       decidable, else ABSTAIN.

C7: every rule reads the substrate only through candidates/cell (via the solver
helpers). Masking is realized as an evidence-regime restriction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from prudent_ai.solver.beliefs import aggregate
from prudent_ai.solver.feasibility import FeasState, classify_candidate
from prudent_ai.solver.procedure import Action, right_size
from prudent_ai.solver.regimes import ALL_AXES

if TYPE_CHECKING:
    from prudent_ai.solver.beliefs import Phi
    from prudent_ai.solver.query import Query
    from prudent_ai.substrate import Substrate


def _cost_of(sub, cid, kappa, phi, regime):
    b = aggregate(sub.cell(cid, "cost"), kappa, phi) if "cost" in regime else None
    return b.point if (b and b.is_present) else None


class DecisionRule(ABC):
    name: str = "rule"
    sees_masked: bool = False   # only the oracle (B5) sees the masked axis

    @abstractmethod
    def decide(
        self, sub: Substrate, query: Query, visible_regime: frozenset[str],
        kappa: tuple[str, ...], phi: Phi,
    ) -> str | None:
        """Return committed config_id, or None to abstain."""


class B1AccuracyOnly(DecisionRule):
    name = "B1_accuracy_only"

    def decide(self, sub, query, visible_regime, kappa, phi):
        best, best_q = None, None
        for c in sub.candidates(query.tau):
            b = aggregate(sub.cell(c.id, "quality"), kappa, phi)
            if b.is_present and (best_q is None or b.point > best_q):
                best, best_q = c.id, b.point
        return best


class B2ObservedPareto(DecisionRule):
    name = "B2_observed_pareto"

    def decide(self, sub, query, visible_regime, kappa, phi):
        # min visible-cost among configs satisfying the VISIBLE constraints,
        # silently ignoring any constraint on the masked axis.
        best, best_cost = None, None
        for c in sub.candidates(query.tau):
            v = classify_candidate(sub, c.id, query.bundle, kappa, phi, visible_regime)
            # treat pending (masked) axes as satisfied — the B2 blind spot
            if v.state is FeasState.PROVABLY_INFEASIBLE:
                continue
            cost = _cost_of(sub, c.id, kappa, phi, visible_regime)
            if cost is None:
                continue
            if best_cost is None or cost < best_cost:
                best, best_cost = c.id, cost
        return best


class B3Imputation(DecisionRule):
    name = "B3_imputation"

    def decide(self, sub, query, visible_regime, kappa, phi):
        masked = ALL_AXES - visible_regime
        # impute each masked axis with its global median over the tau's configs
        imputed: dict[str, float] = {}
        for ax in masked:
            vals = []
            for c in sub.candidates(query.tau):
                b = aggregate(sub.cell(c.id, ax), kappa, phi)
                if b.is_present:
                    vals.append(b.point)
            if vals:
                vals.sort()
                imputed[ax] = vals[len(vals) // 2]
        # decide as B2 but apply masked constraints against the imputed value
        best, best_cost = None, None
        for c in sub.candidates(query.tau):
            ok = True
            for con in query.bundle:
                ax = con.axis
                if ax in visible_regime:
                    b = aggregate(sub.cell(c.id, ax), kappa, phi)
                    val = b.point if b.is_present else None
                else:
                    val = imputed.get(ax)
                if val is None:
                    continue
                if not _satisfies(con.op, val, float(con.value)):
                    ok = False
                    break
            if not ok:
                continue
            cost = _cost_of(sub, c.id, kappa, phi, visible_regime)
            if cost is None:
                continue
            if best_cost is None or cost < best_cost:
                best, best_cost = c.id, cost
        return best


class B4MissingAsFail(DecisionRule):
    name = "B4_missing_as_fail"

    def decide(self, sub, query, visible_regime, kappa, phi):
        # a masked binding constraint is treated as violated → such configs drop out
        masked_bind = {c.axis for c in query.bundle} - visible_regime
        if masked_bind:
            return None  # conservatively abstain when a binding axis is unobservable
        best, best_cost = None, None
        for c in sub.candidates(query.tau):
            v = classify_candidate(sub, c.id, query.bundle, kappa, phi, visible_regime)
            if v.state is not FeasState.PROVABLY_FEASIBLE:
                continue
            cost = _cost_of(sub, c.id, kappa, phi, visible_regime)
            if cost is None:
                continue
            if best_cost is None or cost < best_cost:
                best, best_cost = c.id, cost
        return best


class B5Oracle(DecisionRule):
    name = "B5_oracle"
    sees_masked = True   # oracle-full-evidence: the regret floor

    def decide(self, sub, query, visible_regime, kappa, phi):
        # full evidence: true min-cost truly-feasible config (the regret floor)
        best, best_cost = None, None
        for c in sub.candidates(query.tau):
            v = classify_candidate(sub, c.id, query.bundle, kappa, phi, ALL_AXES)
            if v.state is not FeasState.PROVABLY_FEASIBLE:
                continue
            cost = _cost_of(sub, c.id, kappa, phi, ALL_AXES)
            if cost is None:
                continue
            if best_cost is None or cost < best_cost:
                best, best_cost = c.id, cost
        return best


class B6CostAccuracy(DecisionRule):
    name = "B6_cost_accuracy"

    def decide(self, sub, query, visible_regime, kappa, phi):
        # min cost s.t. the quality constraint only — drops latency/energy/gov/masked
        q_cons = [c for c in query.bundle if c.axis == "quality"]
        best, best_cost = None, None
        for c in sub.candidates(query.tau):
            ok = True
            for con in q_cons:
                b = aggregate(sub.cell(c.id, "quality"), kappa, phi)
                if b.is_present and not _satisfies(con.op, b.point, float(con.value)):
                    ok = False
                    break
            if not ok:
                continue
            cost = _cost_of(sub, c.id, kappa, phi, visible_regime)
            if cost is None:
                continue
            if best_cost is None or cost < best_cost:
                best, best_cost = c.id, cost
        return best


class SelectiveRule(DecisionRule):
    name = "selective"

    def decide(self, sub, query, visible_regime, kappa, phi):
        rec = right_size(sub, query, kappa, phi, visible_regime)
        return rec.committed_config if rec.action is Action.COMMIT else None


def _satisfies(op: str, val: float, target: float) -> bool:
    if op == ">=":
        return val >= target
    if op == "<=":
        return val <= target
    if op == "==":
        return val == target
    return False


ALL_RULES: list[DecisionRule] = [
    B1AccuracyOnly(), B2ObservedPareto(), B3Imputation(),
    B4MissingAsFail(), B5Oracle(), B6CostAccuracy(), SelectiveRule(),
]
