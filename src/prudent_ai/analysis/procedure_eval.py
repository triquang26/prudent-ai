"""Selective-procedure evaluation (§6 / §7 / §10) — does the procedure behave?

P4 builds the *selective* right-sizing procedure (`solver.procedure.right_size`):
each query is either COMMITted to a config, ABSTAINed-on (with a VoI-ranked
acquisition suggestion), or declared INFEASIBLE. This module runs that procedure
over a query battery and summarizes its behaviour as the P4 deliverable:

  - `run`      — action rates (commit = coverage), and over the ABSTAIN queries the
                 distribution of `acquire_next` (the axis the procedure says to
                 measure next), the top-RAW-VoI axis distribution, and the mean
                 top-VoI / VoI-per-cost.
  - `voi_lift` — the §10 "VoI predicts the field worth measuring" check (a P5
                 preview): per ABSTAIN query, compare the regret reduction from
                 measuring the top-VoI axis against measuring a *random* blocking
                 axis. A positive lift means the VoI ranking is doing real work —
                 it picks fields whose measurement actually reduces decision regret.

C7. Every verdict goes through `right_size` → `classify_query` → the solver layer.
No raw SQL feeds any decision. Determinism: `voi_lift` seeds its own
`random.Random` so the random-axis baseline is reproducible.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import TYPE_CHECKING

from prudent_ai.analysis.decidability_map import AXES, generate_queries
from prudent_ai.analysis.empirical_prior_map import grounded_thresholds, load_prior
from prudent_ai.queries.query_prior import to_query
from prudent_ai.solver.beliefs import Phi
from prudent_ai.solver.procedure import Action, right_size
from prudent_ai.solver.regimes import FULL
from prudent_ai.solver.voi import DEFAULT_LAMBDA

if TYPE_CHECKING:
    from prudent_ai.solver.query import Query
    from prudent_ai.substrate import Substrate


class ProcedureEvaluator:
    """Runs the selective procedure over a query battery and summarizes its behaviour."""

    def __init__(
        self,
        sub: Substrate,
        queries: list[Query],
        kappa: tuple[str, ...] = ("H", "M"),
        phi: Phi = Phi.POINT,
        regime: frozenset[str] = FULL,
        lam: float = DEFAULT_LAMBDA,
    ) -> None:
        self.sub = sub
        self.queries = queries
        self.kappa = kappa
        self.phi = phi
        self.regime = regime
        self.lam = lam
        # Cache the per-query recommendations so run()/voi_lift() share one pass.
        self._recs: list | None = None

    # -- internal -----------------------------------------------------------

    def _recommendations(self) -> list:
        """Classify every query once via right_size; memoize the recommendations."""
        if self._recs is None:
            self._recs = [
                right_size(
                    self.sub, q, self.kappa, self.phi, self.regime, self.lam
                )
                for q in self.queries
            ]
        return self._recs

    @staticmethod
    def _abstentions(recs: list) -> list:
        return [r for r in recs if r.action is Action.ABSTAIN]

    @staticmethod
    def _top_raw_voi_axis(rec) -> str | None:
        """Single highest-RAW-VoI axis for an abstention (ignores cost weighting)."""
        if not rec.voi_ranking:
            return None
        best = max(rec.voi_ranking, key=lambda a: (a.voi, a.axis))
        return best.axis

    @staticmethod
    def _regime_name(regime: frozenset[str]) -> str:
        return "full" if regime == FULL else "+".join(sorted(regime))

    # -- deliverables -------------------------------------------------------

    def run(self) -> dict:
        """Classify the battery and summarize the procedure's behaviour."""
        recs = self._recommendations()
        n = len(recs)

        n_commit = sum(1 for r in recs if r.action is Action.COMMIT)
        n_abstain = sum(1 for r in recs if r.action is Action.ABSTAIN)
        n_infeasible = sum(1 for r in recs if r.action is Action.INFEASIBLE)

        action_rates = {
            "commit": (n_commit / n if n else 0.0),
            "abstain": (n_abstain / n if n else 0.0),
            "infeasible": (n_infeasible / n if n else 0.0),
        }

        abstentions = self._abstentions(recs)

        # The axis the procedure says to measure next (top VoI/cost), per abstention.
        acquire_next: Counter[str] = Counter()
        # The single highest-RAW-VoI axis, per abstention.
        top_blocking: Counter[str] = Counter()

        top_vois: list[float] = []
        vois_per_cost: list[float] = []
        for r in abstentions:
            nxt = r.acquire_next
            if nxt is not None:
                acquire_next[nxt] += 1
            raw = self._top_raw_voi_axis(r)
            if raw is not None:
                top_blocking[raw] += 1
            if r.voi_ranking:
                top_vois.append(max(a.voi for a in r.voi_ranking))
                # The procedure's chosen axis is voi_ranking[0] (top VoI/cost).
                vois_per_cost.append(r.voi_ranking[0].voi_per_cost)

        n_ab = len(abstentions)
        return {
            "regime": self._regime_name(self.regime),
            "n": n,
            "kappa": list(self.kappa),
            "phi": self.phi.value,
            "lam": self.lam,
            "counts": {
                "commit": n_commit,
                "abstain": n_abstain,
                "infeasible": n_infeasible,
            },
            "action_rates": action_rates,
            "coverage": action_rates["commit"],
            "n_abstain": n_ab,
            "acquire_next_distribution": dict(
                sorted(acquire_next.items(), key=lambda kv: (-kv[1], kv[0]))
            ),
            "top_blocking_distribution": dict(
                sorted(top_blocking.items(), key=lambda kv: (-kv[1], kv[0]))
            ),
            "mean_top_voi": (sum(top_vois) / len(top_vois) if top_vois else 0.0),
            "mean_voi_per_cost": (
                sum(vois_per_cost) / len(vois_per_cost) if vois_per_cost else 0.0
            ),
        }

    def voi_lift(self, seed: int = 12345) -> dict:
        """§10 check: VoI ranking beats a random blocking-axis baseline.

        Per ABSTAIN query, the regret reduction from measuring the top-VoI axis is
        the max VoI over its blocking axes; the baseline measures a *randomly*
        chosen blocking axis and gets that axis's VoI. The lift is the mean
        difference. A positive lift means VoI ranking points at fields whose
        measurement actually reduces decision regret (the P5 preview).

        Two readings are reported:
          - RAW VoI (the headline keys): the regret reduction of the *field* alone.
            In this substrate the blocking axes of a given query are corpus-wide-⊥
            and carry the *same* raw two-world regret, so raw VoI does not by itself
            discriminate which field to measure — raw lift is ~0. That is an honest
            finding: the §8.7 regret is a property of the query's binding structure,
            not of which ⊥ axis you pick.
          - COST-AWARE VoI-per-cost (the `cost_aware` block): the procedure's actual
            acquisition key. Cheap axes (cost, latency) break the raw-VoI ties, so
            the cost-aware ranking *does* beat a random pick — this is where the
            "which field to measure next" signal lives, and it is what drives the
            `acquire_next` distribution.
        """
        recs = self._recommendations()
        abstentions = self._abstentions(recs)

        def _lift(metric, rng_seed: int) -> dict:
            rng = random.Random(rng_seed)
            top_vals: list[float] = []
            random_vals: list[float] = []
            n_pairs = 0
            for r in abstentions:
                if not r.voi_ranking:
                    continue
                by_axis = {a.axis: metric(a) for a in r.voi_ranking}
                top_vals.append(max(by_axis.values()))
                # Random blocking axis (seeded; sorted → deterministic choice space).
                chosen = rng.choice(sorted(by_axis))
                random_vals.append(by_axis[chosen])
                n_pairs += 1
            mt = sum(top_vals) / len(top_vals) if top_vals else 0.0
            mr = sum(random_vals) / len(random_vals) if random_vals else 0.0
            return {
                "n_abstain_with_ranking": n_pairs,
                "mean_top": mt,
                "mean_random": mr,
                "lift": mt - mr,
                "lift_ratio": (mt / mr if mr > 0 else None),
            }

        raw = _lift(lambda a: a.voi, seed)
        cost_aware = _lift(lambda a: a.voi_per_cost, seed)
        return {
            "seed": seed,
            "n_abstain_with_ranking": raw["n_abstain_with_ranking"],
            # Headline (raw VoI — regret reduction of the field itself).
            "mean_top_voi": raw["mean_top"],
            "mean_random_voi": raw["mean_random"],
            "lift": raw["lift"],
            "lift_ratio": raw["lift_ratio"],
            # Cost-aware reading — where the acquisition signal actually lives.
            "cost_aware": {
                "mean_top_voi_per_cost": cost_aware["mean_top"],
                "mean_random_voi_per_cost": cost_aware["mean_random"],
                "lift": cost_aware["lift"],
                "lift_ratio": cost_aware["lift_ratio"],
            },
        }


# ---------------------------------------------------------------------------
# Query-battery builders
# ---------------------------------------------------------------------------


def build_empirical_queries(sub: Substrate) -> list[Query]:
    """Build the empirical-prior query battery (1716 ZenML-derived queries).

    Loads the frozen ZenML prior, grounds per-(τ, axis) thresholds through the C7
    interface, and turns every derived query into a runnable Query. This is the
    real-traffic battery the selective procedure is evaluated on.
    """
    _rows, prior = load_prior()
    taus = list(prior.tau_distribution().keys())
    thresholds = grounded_thresholds(sub, taus, list(AXES))
    return [to_query(dq, thresholds) for dq in prior.derived]


def build_grid_queries(sub: Substrate) -> list[Query]:
    """Build the P3 hand-grid query battery, pooled over every archetype τ.

    Reuses `decidability_map.generate_queries` (single-axis probes + curated
    pairwise bundles) for the grid-vs-empirical comparison row.
    """
    from prudent_ai.analysis.decidability_map import ARCHETYPES

    queries: list[Query] = []
    for tau in ARCHETYPES(sub):
        queries.extend(generate_queries(sub, tau))
    return queries


__all__ = [
    "ProcedureEvaluator",
    "build_empirical_queries",
    "build_grid_queries",
]
