"""Mask-and-predict validation harness (§15 P5 V1) — DV2 regret + DV3 hidden-violation.

On a ground-truth slice (configs with co-located measured axes), we:
  1. take a query whose constraints bind a chosen axis `a`,
  2. MASK `a` (make it invisible to the rule — a regime restriction),
  3. let each rule predict a committed config from the remaining evidence,
  4. SCORE the prediction against the TRUE values (full regime):
       - hidden violation: the rule commits a config that violates the true `a`-constraint,
       - decision regret: cost overshoot vs the true minimum-sufficient config (oracle).

"Truth" is the substrate's own measured (high-confidence) values on the slice; the
slice is used ONLY to score, never to tune any rule (C8 — no leakage).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from prudent_ai.solver.beliefs import Phi, aggregate
from prudent_ai.solver.query import Query, make_query
from prudent_ai.solver.regimes import ALL_AXES

if TYPE_CHECKING:
    from prudent_ai.substrate import Substrate
    from prudent_ai.validation.baselines import DecisionRule

# Direction of each axis constraint when generating queries.
_AXIS_OP: dict[str, str] = {
    "quality": ">=", "throughput": ">=",
    "latency_p95": "<=", "cost": "<=", "energy": "<=", "memory_hw": "<=",
}

# Penalty (in cost units) charged for a hidden-violation commit, for combined loss.
VIOLATION_PENALTY = 1.0


class MaskedSubstrate:
    """Substrate proxy that hides one axis — `cell(x, masked)` returns [].

    Enforces the mask uniformly at the read level so NO rule (regardless of how it
    reads) can see the masked axis. The oracle (sees_masked) is handed the real
    substrate instead. C7-shaped: same interface, just one axis withheld.
    """

    def __init__(self, sub, masked_axis: str) -> None:
        self._sub = sub
        self._masked = masked_axis

    def candidates(self, tau):
        return self._sub.candidates(tau)

    def cell(self, x, a):
        if a == self._masked:
            return []
        return self._sub.cell(x, a)

    def required_fields(self, bundle):
        return self._sub.required_fields(bundle)

    def __getattr__(self, name):
        return getattr(self._sub, name)


@dataclass
class RuleMetrics:
    rule: str
    masked_axis: str
    n_queries: int = 0
    n_commit: int = 0
    n_abstain: int = 0
    n_hidden_violation: int = 0
    sum_regret_feasible: float = 0.0   # over truly-feasible commits
    n_regret_feasible: int = 0

    @property
    def coverage(self) -> float:
        return self.n_commit / self.n_queries if self.n_queries else 0.0

    @property
    def hidden_violation_rate(self) -> float:
        # over committed queries — fraction of commits that silently violate truth
        return self.n_hidden_violation / self.n_commit if self.n_commit else 0.0

    @property
    def mean_regret(self) -> float:
        return (self.sum_regret_feasible / self.n_regret_feasible
                if self.n_regret_feasible else 0.0)

    def as_dict(self) -> dict:
        return {
            "rule": self.rule, "masked_axis": self.masked_axis,
            "n_queries": self.n_queries, "coverage": round(self.coverage, 4),
            "hidden_violation_rate": round(self.hidden_violation_rate, 4),
            "n_hidden_violation": self.n_hidden_violation,
            "mean_regret": round(self.mean_regret, 6),
            "n_commit": self.n_commit, "n_abstain": self.n_abstain,
        }


@dataclass
class SliceReport:
    tau: str
    masked_axis: str
    rules: dict[str, dict] = field(default_factory=dict)


class MaskAndPredict:
    """Run the mask-and-predict experiment over a GT slice."""

    def __init__(
        self, sub: Substrate, kappa: tuple[str, ...] = ("H",), phi: Phi = Phi.POINT
    ) -> None:
        self.sub = sub
        self.kappa = kappa
        self.phi = phi

    # ---- truth helpers (full regime, measured values) ----

    def _true_val(self, cid: str, axis: str) -> float | None:
        b = aggregate(self.sub.cell(cid, axis), self.kappa, self.phi)
        return b.point if b.is_present else None

    def true_feasible(self, query: Query, cid: str) -> bool:
        for con in query.bundle:
            val = self._true_val(cid, con.axis)
            if val is None:
                return False  # truly unknown ⇒ cannot certify feasible
            if not _satisfies(con.op, val, float(con.value)):
                return False
        return True

    def oracle_cost(self, query: Query) -> float | None:
        best = None
        for c in self.sub.candidates(query.tau):
            if not self.true_feasible(query, c.id):
                continue
            cost = self._true_val(c.id, "cost")
            if cost is None:
                continue
            if best is None or cost < best:
                best = cost
        return best

    # ---- query battery ----

    def observed_percentiles(self, tau: str, axis: str, pcts: list[int]) -> dict[int, float]:
        vals: list[float] = []
        for c in self.sub.candidates(tau):
            b = aggregate(self.sub.cell(c.id, axis), self.kappa, self.phi)
            if b.is_present:
                vals.append(b.point)
        if not vals:
            return {}
        vals.sort()
        out = {}
        for p in pcts:
            idx = min(len(vals) - 1, max(0, int(round((p / 100.0) * (len(vals) - 1)))))
            out[p] = vals[idx]
        return out

    def generate_queries(
        self, tau: str, bind_axes: tuple[str, ...],
        pcts: tuple[int, ...] = (30, 40, 50, 60, 70),
    ) -> list[Query]:
        """Queries binding every axis in *bind_axes* at matching percentiles.

        Masking one of these binding axes (in run/score) is what stresses each
        rule: a rule blind to a binding axis may commit a config that violates it.
        """
        pctmap = {ax: self.observed_percentiles(tau, ax, list(pcts)) for ax in bind_axes}
        if any(not pctmap[ax] for ax in bind_axes):
            return []
        queries = []
        for p in pcts:
            cons = [(ax, _AXIS_OP.get(ax, "<="), pctmap[ax][p]) for ax in bind_axes]
            queries.append(make_query(tau, cons, label="+".join(bind_axes) + f"@p{p}"))
        return queries

    # ---- scoring ----

    def score_rule(
        self, rule: DecisionRule, queries: list[Query], masked_axis: str
    ) -> RuleMetrics:
        visible = ALL_AXES - {masked_axis}
        # Oracle sees everything; every other rule reads through the mask.
        rule_sub = self.sub if getattr(rule, "sees_masked", False) else \
            MaskedSubstrate(self.sub, masked_axis)
        m = RuleMetrics(rule=rule.name, masked_axis=masked_axis, n_queries=len(queries))
        for q in queries:
            pred = rule.decide(rule_sub, q, visible, self.kappa, self.phi)
            if pred is None:
                m.n_abstain += 1
                continue
            m.n_commit += 1
            if not self.true_feasible(q, pred):
                m.n_hidden_violation += 1
                continue
            oc = self.oracle_cost(q)
            pc = self._true_val(pred, "cost")
            if oc is not None and pc is not None:
                m.sum_regret_feasible += max(0.0, pc - oc)
                m.n_regret_feasible += 1
        return m

    def run(
        self, rules: list[DecisionRule], tau: str, bind_axes: tuple[str, ...],
        masked_axis: str, queries: list[Query] | None = None,
    ) -> SliceReport:
        """Bind *bind_axes*, mask *masked_axis*, score every rule. masked_axis ∈ bind_axes."""
        qs = queries if queries is not None else self.generate_queries(tau, bind_axes)
        rep = SliceReport(tau=tau, masked_axis=masked_axis)
        for rule in rules:
            rep.rules[rule.name] = self.score_rule(rule, qs, masked_axis).as_dict()
        return rep


def _satisfies(op: str, val: float, target: float) -> bool:
    if op == ">=":
        return val >= target
    if op == "<=":
        return val <= target
    if op == "==":
        return val == target
    return False
