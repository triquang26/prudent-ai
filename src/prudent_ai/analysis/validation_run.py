"""P5 validation runner (§15) — V1 mask-and-predict + V2 VoI-guided acquisition.

`ValidationRunner` orchestrates the two P5 validations over the ground-truth slices:

  V1 (DV2/DV3 — the baseline lattice).  For each GT slice and each
  (bind_axes, masked_axis) configuration we run `MaskAndPredict.run` and collect
  the per-rule metrics.  The biting case (BFCL, bind quality+latency, MASK quality)
  is where the *commit-while-blind* baselines (B2 observed-Pareto, B3 imputation,
  B6 cost-accuracy) silently commit configs that violate the masked truth, while
  the selective rule abstains — the C2 verdict
  ``hidden_violation(selective) << hidden_violation(B2/B3/B6)``.

  V2 (§10 — VoI predicts the field worth measuring).  On the biting case we mask
  *all* binding axes, let the procedure ABSTAIN and rank the blocking axes by
  cost-aware VoI, then "measure" the top-VoI axis (un-mask it) and re-run the
  selective rule, recording whether it now COMMITs a truly-feasible config.  We
  compare that against revealing a *random* bind axis (seeded).  Because the
  selective rule must certify *every* binding axis before it commits, revealing a
  single axis out of a 2-axis bind cannot un-block it — so the single-reveal
  commit-correct fraction is structurally degenerate on a 2-binding-axis slice.
  We report that honestly with the numbers, and *also* surface the procedure's
  cost-aware VoI ranking (the actual §10 signal): VoI correctly prefers the
  cheaper measurable field even where one reveal cannot flip the decision.

Everything reads the substrate ONLY through the solver/validation layer (C7):
masking is realized via `MaskedSubstrate`, decisions via `right_size` /
`DecisionRule.decide`, truth scoring via `MaskAndPredict.true_feasible`.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from prudent_ai.solver import Phi
from prudent_ai.solver.procedure import Action, right_size
from prudent_ai.solver.regimes import ALL_AXES
from prudent_ai.validation.baselines import ALL_RULES, SelectiveRule
from prudent_ai.validation.harness import MaskAndPredict, MaskedSubstrate

if TYPE_CHECKING:
    from prudent_ai.solver.query import Query


class RevealOnly:
    """Substrate proxy that reveals ONLY *reveal_axes* among *bind_axes*.

    Composes :class:`MaskedSubstrate` once per axis in ``bind_axes`` that is NOT
    in ``reveal_axes`` — i.e. every binding axis the simulated agent has not yet
    "measured" stays hidden at the read level.  Non-binding axes are untouched
    (they are visible exactly as the underlying substrate holds them).  C7-shaped:
    same interface, just a chosen subset withheld.
    """

    def __init__(
        self, sub, bind_axes: tuple[str, ...], reveal_axes: frozenset[str]
    ) -> None:
        proxy = sub
        for axis in bind_axes:
            if axis not in reveal_axes:
                proxy = MaskedSubstrate(proxy, axis)
        self._proxy = proxy

    def candidates(self, tau):
        return self._proxy.candidates(tau)

    def cell(self, x, a):
        return self._proxy.cell(x, a)

    def required_fields(self, bundle):
        return self._proxy.required_fields(bundle)

    def __getattr__(self, name):
        return getattr(self._proxy, name)


# The (slice, bind_axes, masked_axis) V1 configurations.  Each tuple is a row in
# the validation: the binding constraints, and which one binding axis is masked.
V1_CASES: list[tuple[str, str, tuple[str, ...], str, bool]] = [
    # (key, tau, bind_axes, masked_axis, is_biting)
    (
        "BFCL/bind=quality+latency/mask=quality",
        "function-calling",
        ("quality", "latency_p95"),
        "quality",
        True,   # the biting case — masked axis binds, baselines commit blind
    ),
    (
        "BFCL/bind=quality+latency/mask=latency_p95",
        "function-calling",
        ("quality", "latency_p95"),
        "latency_p95",
        False,  # control — in BFCL cheap==fast, so masking latency does not bite
    ),
    (
        "routerbench/bind=quality+cost/mask=quality",
        "routerbench",
        ("quality", "cost"),
        "quality",
        True,   # corroboration on the H-confidence slice (cost objective + masked quality)
    ),
]

# Baselines whose hidden-violation the selective rule must beat (C2).
_MUST_BEAT = ("B2_observed_pareto", "B3_imputation", "B6_cost_accuracy")


class ValidationRunner:
    """Runs V1 (mask-and-predict over GT slices) and V2 (VoI-guided acquisition)."""

    def __init__(
        self, sub, kappa: tuple[str, ...] = ("H", "M"), phi: Phi = Phi.POINT
    ) -> None:
        self.sub = sub
        self.kappa = kappa
        self.phi = phi
        self.mp = MaskAndPredict(sub, kappa=kappa, phi=phi)

    # ------------------------------------------------------------------ V1 ----

    def v1(self) -> dict:
        """Run the baseline lattice over every V1 case.

        Returns ``{slice_key: {"meta": {...}, "rules": {rule: metrics}}}``.  Each
        case's ``meta`` carries the C2 verdict comparison: the selective rule's
        hidden-violation rate against the must-beat baselines (B2/B3/B6).
        """
        out: dict[str, dict] = {}
        for key, tau, bind_axes, masked_axis, is_biting in V1_CASES:
            queries = self.mp.generate_queries(tau, bind_axes)
            report = self.mp.run(
                ALL_RULES, tau, bind_axes, masked_axis, queries=queries
            )
            rules = report.rules
            sel_hv = rules["selective"]["hidden_violation_rate"]
            beat = {
                name: rules[name]["hidden_violation_rate"]
                for name in _MUST_BEAT
                if name in rules
            }
            # Did ANY must-beat baseline actually bite (commit a hidden violation)?
            baselines_bite = any(hv > 0.0 for hv in beat.values())
            if not baselines_bite:
                c2_verdict = "no-bite"  # nothing to beat on this (slice, mask)
            elif all(sel_hv < hv for hv in beat.values() if hv > 0.0):
                c2_verdict = "holds"
            else:
                c2_verdict = "fails"
            out[key] = {
                "meta": {
                    "tau": tau,
                    "bind_axes": list(bind_axes),
                    "masked_axis": masked_axis,
                    "is_biting": is_biting,
                    "n_queries": len(queries),
                    "selective_hidden_violation_rate": sel_hv,
                    "must_beat_hidden_violation_rate": beat,
                    "baselines_bite": baselines_bite,
                    "c2_verdict": c2_verdict,
                },
                "rules": rules,
            }
        return out

    # ------------------------------------------------------------------ V2 ----

    def _selective_commit_correct(
        self, query: Query, rule: SelectiveRule, sub, visible: frozenset[str]
    ) -> tuple[bool, bool]:
        """(committed, commit_was_truly_feasible) for the selective rule on *sub*."""
        pred = rule.decide(sub, query, visible, self.kappa, self.phi)
        if pred is None:
            return (False, False)
        return (True, self.mp.true_feasible(query, pred))

    def v2_acquisition(self, seed: int = 12345) -> dict:
        """VoI-guided acquisition on the BFCL biting case (bind quality+latency).

        Construction (§10):
          1. MASK all binding axes (quality, latency) → selective ABSTAINs.
          2. Ask the procedure (`right_size` on the masked substrate) for the
             cost-aware VoI ranking of the blocking axes; ``acquire_next`` is the
             top-VoI axis.
          3. "Measure top-VoI axis" = reveal ONLY that axis (RevealOnly) and re-run
             the selective rule; record COMMIT and whether the commit is truly
             feasible (`true_feasible` against full truth).
          4. Compare against revealing a RANDOM bind axis (seeded).

        Because the selective rule certifies *every* binding axis before it
        commits, a single reveal out of a 2-axis bind cannot un-block it — the
        single-reveal commit-correct fraction is structurally degenerate (0 for
        both top-VoI and random) on this slice.  We report that honestly and also
        surface the procedure's VoI ranking, which IS the §10 signal: VoI prefers
        the cheaper measurable field even where one reveal cannot flip the verdict.
        """
        tau = "function-calling"
        bind_axes = ("quality", "latency_p95")
        rng = random.Random(seed)
        sel = SelectiveRule()
        queries = self.mp.generate_queries(tau, bind_axes)

        # Step 1: everything masked → selective must abstain (sanity).
        all_masked = RevealOnly(self.sub, bind_axes, frozenset())
        visible_none = ALL_AXES - set(bind_axes)

        per_query: list[dict] = []
        n_abstained = 0
        n_topvoi_commit_correct = 0
        n_random_commit_correct = 0
        n_topvoi_commits = 0
        n_random_commits = 0
        voi_picks_cheaper = 0  # times top-VoI axis has strictly higher voi_per_cost

        for q in queries:
            rec = right_size(all_masked, q, self.kappa, self.phi, visible_none)
            if rec.action is not Action.ABSTAIN:
                # Not an abstention under full masking — skip (off the biting case).
                continue
            n_abstained += 1

            top_axis = rec.acquire_next
            ranking = [
                {"axis": a.axis, "voi": a.voi, "voi_per_cost": a.voi_per_cost}
                for a in rec.voi_ranking
            ]
            # Random alternative among the bind axes (the candidate fields).
            rand_axis = rng.choice(list(bind_axes))

            # VoI correctly orders fields when top axis has the max voi_per_cost.
            if ranking and top_axis == max(
                ranking, key=lambda r: r["voi_per_cost"]
            )["axis"] and len({r["voi_per_cost"] for r in ranking}) > 1:
                voi_picks_cheaper += 1

            # Reveal ONLY the top-VoI axis, re-run selective.
            top_sub = RevealOnly(self.sub, bind_axes, frozenset({top_axis}))
            visible_top = ALL_AXES - (set(bind_axes) - {top_axis})
            top_commit, top_ok = self._selective_commit_correct(
                q, sel, top_sub, visible_top
            )

            # Reveal ONLY a random bind axis, re-run selective.
            rand_sub = RevealOnly(self.sub, bind_axes, frozenset({rand_axis}))
            visible_rand = ALL_AXES - (set(bind_axes) - {rand_axis})
            rand_commit, rand_ok = self._selective_commit_correct(
                q, sel, rand_sub, visible_rand
            )

            n_topvoi_commits += int(top_commit)
            n_random_commits += int(rand_commit)
            n_topvoi_commit_correct += int(top_ok)
            n_random_commit_correct += int(rand_ok)

            per_query.append(
                {
                    "query": q.label,
                    "top_voi_axis": top_axis,
                    "random_axis": rand_axis,
                    "voi_ranking": ranking,
                    "topvoi_commit": top_commit,
                    "topvoi_commit_correct": top_ok,
                    "random_commit": rand_commit,
                    "random_commit_correct": rand_ok,
                }
            )

        n = n_abstained
        topvoi_frac = n_topvoi_commit_correct / n if n else 0.0
        random_frac = n_random_commit_correct / n if n else 0.0
        degenerate = (n_topvoi_commits == 0 and n_random_commits == 0)

        return {
            "meta": {
                "tau": tau,
                "bind_axes": list(bind_axes),
                "construction": "mask-all-bind / reveal-top-VoI-vs-random / re-run-selective",
                "seed": seed,
                "n_abstained": n,
            },
            "single_reveal": {
                "n": n,
                "topvoi_commit": n_topvoi_commits,
                "random_commit": n_random_commits,
                "topvoi_commit_correct": n_topvoi_commit_correct,
                "random_commit_correct": n_random_commit_correct,
                "topvoi_commit_correct_frac": round(topvoi_frac, 4),
                "random_commit_correct_frac": round(random_frac, 4),
                "degenerate": degenerate,
            },
            "voi_signal": {
                # The §10 signal that DOES discriminate: does the cost-aware VoI
                # ranking prefer the cheaper measurable field?
                "queries_where_voi_prefers_cheaper_field": voi_picks_cheaper,
                "n": n,
                "frac": round(voi_picks_cheaper / n, 4) if n else 0.0,
            },
            "per_query": per_query,
        }
