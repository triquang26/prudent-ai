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
from prudent_ai.validation.harness import (
    BenchmarkSubstrate,
    MaskAndPredict,
    MaskedSubstrate,
)

if TYPE_CHECKING:
    from prudent_ai.solver.query import Query


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
        "routerbench/bind=quality/mask=quality",
        "routerbench",
        ("quality",),
        "quality",
        False,  # CONFOUNDED: RouterBench cost varies by BENCHMARK (an easy/short
                # benchmark is cheap regardless of model), so the global cost-min
                # picks the cheapest *benchmark* (high quality) not the weakest
                # model — cross-benchmark cost is not comparable, so this mixed
                # slice does not bite. A per-benchmark restriction (future work)
                # would be the valid right-sizing slice. BFCL carries the C2 result.
    ),
]

# Baselines whose hidden-violation the selective rule must beat (C2).
_MUST_BEAT = ("B2_observed_pareto", "B3_imputation", "B6_cost_accuracy")

# The two baselines the scaled significance test pairs selective against (§14):
# B2 observed-Pareto (honest current practice) and B3 imputation ("fill it in").
_MUST_BEAT_SCALE = ("B2_observed_pareto", "B3_imputation")
_MUST_BEAT_RULES = {r.name: r for r in ALL_RULES if r.name in _MUST_BEAT_SCALE}
_SELECTIVE = next(r for r in ALL_RULES if r.name == "selective")


def _binom_sf_ge(k: int, n: int, p: float) -> float:
    """One-sided exact binomial tail P(X >= k) for X ~ Binomial(n, p)."""
    if n <= 0:
        return 1.0
    if k <= 0:
        return 1.0
    from math import comb
    return sum(
        comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i)) for i in range(k, n + 1)
    )


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

    # ---------------------------------------------------------- V1 (scaled) ----

    # The scaled biting battery. Each entry is a slice that should BITE under
    # mask=quality: a cost-comparable candidate set where the cheapest config is a
    # weak model, so a quality-blind cost-minimizer commits an infeasible config.
    #   (key, tau, bind_axes, masked_axis, benchmark|None)
    # benchmark=None → use the substrate as-is (BFCL). benchmark set → wrap in
    # BenchmarkSubstrate to hold the RouterBench benchmark fixed (cost comparable).
    _SCALE_BENCHMARKS: tuple[str, ...] = (
        "mmlu", "hellaswag", "arc-challenge", "winogrande", "mbpp",
        "grade-school-math",
    )

    def _scale_slices(self) -> list[tuple[str, str, tuple[str, ...], str, str | None]]:
        slices: list[tuple[str, str, tuple[str, ...], str, str | None]] = [
            (
                "BFCL/bind=quality+latency/mask=quality",
                "function-calling",
                ("quality", "latency_p95"),
                "quality",
                None,
            ),
        ]
        for bench in self._SCALE_BENCHMARKS:
            slices.append((
                f"routerbench[{bench}]/bind=quality/mask=quality",
                "routerbench",
                ("quality",),
                "quality",
                bench,
            ))
        return slices

    @staticmethod
    def _paired_significance(
        baseline_pq: list[dict], selective_pq: list[dict], rng: random.Random,
        n_boot: int = 10000,
    ) -> dict:
        """One-sided paired test that selective hidden-violates less than baseline.

        Per query we form the paired indicator
        ``d_i = baseline.hidden_violation - selective.hidden_violation`` ∈ {-1,0,1}.
        Two reports:
          * McNemar-style discordant count — ``b`` = queries where baseline
            hidden-violates and selective does not, ``c`` = the reverse; a
            one-sided exact binomial p-value on (b, b+c) tests H1: b>c (selective
            strictly better on the discordant pairs).
          * Bootstrap 95% CI on the mean hidden-violation-rate DIFFERENCE
            (baseline − selective), resampling queries with replacement (seeded).
            ``significant`` iff the CI lower bound excludes 0.
        """
        diffs = [
            int(b["hidden_violation"]) - int(s["hidden_violation"])
            for b, s in zip(baseline_pq, selective_pq, strict=True)
        ]
        n = len(diffs)
        b_disc = sum(1 for d in diffs if d > 0)   # baseline violates, selective not
        c_disc = sum(1 for d in diffs if d < 0)   # selective violates, baseline not
        mean_diff = sum(diffs) / n if n else 0.0

        # One-sided exact binomial p-value: P(X >= b) under X~Binom(b+c, 0.5).
        nd = b_disc + c_disc
        p_value = _binom_sf_ge(b_disc, nd, 0.5) if nd else 1.0

        # Bootstrap CI on the mean difference.
        boot: list[float] = []
        if n:
            for _ in range(n_boot):
                s = 0
                for _ in range(n):
                    s += diffs[rng.randrange(n)]
                boot.append(s / n)
            boot.sort()
            lo = boot[int(0.025 * len(boot))]
            hi = boot[min(len(boot) - 1, int(0.975 * len(boot)))]
        else:
            lo = hi = 0.0
        return {
            "n": n,
            "mean_diff": round(mean_diff, 6),
            "ci95_lo": round(lo, 6),
            "ci95_hi": round(hi, 6),
            "ci_excludes_zero": bool(lo > 0.0),
            "mcnemar_b": b_disc,
            "mcnemar_c": c_disc,
            "binom_p_one_sided": round(p_value, 8),
            "significant": bool(lo > 0.0 and p_value < 0.05),
        }

    def scale_v1(self, seed: int = 12345) -> dict:
        """Scaled V1 battery with significance + multiple biting slices.

        Larger per-slice battery (pcts 10..90 step 5 ≈ 17 queries), over BFCL plus
        the six per-benchmark RouterBench slices. For each slice we run ALL_RULES
        (per-rule coverage + hidden_violation_rate + counts) and collect the
        per-query baseline-vs-selective pairs for the must-beat baselines (B2, B3).
        A slice is a "biting" slice iff some must-beat baseline actually
        hidden-violates on it; significance and pooling are computed over biting
        slices only, where there is something to beat.
        """
        pcts = tuple(range(10, 95, 5))
        rng = random.Random(seed)

        slices_out: dict[str, dict] = {}
        # Pooled per-query pairs across biting slices, per must-beat baseline.
        pooled_base_pq: dict[str, list[dict]] = {b: [] for b in _MUST_BEAT_SCALE}
        pooled_sel_pq: dict[str, list[dict]] = {b: [] for b in _MUST_BEAT_SCALE}

        for key, tau, bind_axes, masked_axis, bench in self._scale_slices():
            sub = BenchmarkSubstrate(self.sub, bench) if bench else self.sub
            mp = MaskAndPredict(sub, kappa=self.kappa, phi=self.phi)
            queries = mp.generate_queries(tau, bind_axes, pcts=pcts)
            report = mp.run(ALL_RULES, tau, bind_axes, masked_axis, queries=queries)
            rules = report.rules

            sel_pq = mp.score_rule_per_query(_SELECTIVE, queries, masked_axis)
            sel_hv = rules["selective"]["hidden_violation_rate"]
            beat = {
                name: rules[name]["hidden_violation_rate"]
                for name in _MUST_BEAT_SCALE if name in rules
            }
            baselines_bite = any(hv > 0.0 for hv in beat.values())
            if not baselines_bite:
                c2_verdict = "no-bite"
            elif all(sel_hv < hv for hv in beat.values() if hv > 0.0):
                c2_verdict = "holds"
            else:
                c2_verdict = "fails"

            # Per-slice significance for each must-beat baseline (biting slices only).
            sig: dict[str, dict] = {}
            if baselines_bite:
                for name, rule in _MUST_BEAT_RULES.items():
                    base_pq = mp.score_rule_per_query(rule, queries, masked_axis)
                    sig[name] = self._paired_significance(base_pq, sel_pq, rng)
                    pooled_base_pq[name].extend(base_pq)
                    pooled_sel_pq[name].extend(sel_pq)

            slices_out[key] = {
                "meta": {
                    "tau": tau,
                    "benchmark": bench,
                    "bind_axes": list(bind_axes),
                    "masked_axis": masked_axis,
                    "n_queries": len(queries),
                    "n_candidates": len(sub.candidates(tau)),
                    "selective_hidden_violation_rate": sel_hv,
                    "must_beat_hidden_violation_rate": beat,
                    "baselines_bite": baselines_bite,
                    "c2_verdict": c2_verdict,
                },
                "rules": rules,
                "significance": sig,
            }

        # --- pooled across biting slices ---
        pooled: dict[str, dict] = {}
        for name in _MUST_BEAT_SCALE:
            base_pq = pooled_base_pq[name]
            sel_pq = pooled_sel_pq[name]
            if not base_pq:
                pooled[name] = {"n": 0}
                continue
            base_hv = sum(int(x["hidden_violation"]) for x in base_pq) / len(base_pq)
            sel_hv = sum(int(x["hidden_violation"]) for x in sel_pq) / len(sel_pq)
            stats = self._paired_significance(base_pq, sel_pq, rng)
            pooled[name] = {
                "baseline_hidden_violation_rate": round(base_hv, 6),
                "selective_hidden_violation_rate": round(sel_hv, 6),
                **stats,
            }

        biting = [k for k, v in slices_out.items() if v["meta"]["baselines_bite"]]
        total_q = sum(
            slices_out[k]["meta"]["n_queries"] for k in slices_out
        )
        biting_q = sum(slices_out[k]["meta"]["n_queries"] for k in biting)
        return {
            "meta": {
                "seed": seed,
                "pcts": list(pcts),
                "n_slices": len(slices_out),
                "biting_slices": biting,
                "n_biting_slices": len(biting),
                "total_queries": total_q,
                "biting_queries": biting_q,
                "must_beat": list(_MUST_BEAT_SCALE),
            },
            "slices": slices_out,
            "pooled": pooled,
        }

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
        """VoI-guided acquisition on the BFCL biting case (§10).

        Construction. Bind quality+latency, MASK only the binding axis `quality`
        (the V1 biting setup) — latency stays visible, so the *single* blocking
        axis is quality and the procedure ABSTAINs. Then simulate "measuring one
        field":
          - measure the procedure's VoI pick (`acquire_next`, = quality) → un-mask
            it → re-run selective → it can now decide;
          - measure a RANDOM axis (seeded, drawn from all 8) → only helps in the
            rare case it happens to be the blocking axis; otherwise quality stays ⊥
            and selective still abstains.
        Score each re-decision as COMMIT and truly-feasible (`true_feasible`).

        This isolates the §10 claim cleanly: VoI points at the field that actually
        unblocks the decision, so measuring the VoI pick yields a correct commit far
        more often than measuring a random field.
        """
        tau = "function-calling"
        bind_axes = ("quality", "latency_p95")
        masked_axis = "quality"
        all_axes = sorted(ALL_AXES)
        rng = random.Random(seed)
        sel = SelectiveRule()
        queries = self.mp.generate_queries(tau, bind_axes)

        masked_sub = MaskedSubstrate(self.sub, masked_axis)
        visible_masked = ALL_AXES - {masked_axis}

        def reveal(axis: str):
            """(substrate, regime) after 'measuring' *axis* — un-mask it if it was masked."""
            if axis == masked_axis:
                return self.sub, ALL_AXES               # blocking axis now known
            return masked_sub, visible_masked           # irrelevant field — no change

        per_query: list[dict] = []
        n = 0
        n_topvoi_cc = 0
        n_random_cc = 0

        for q in queries:
            rec = right_size(masked_sub, q, self.kappa, self.phi, visible_masked)
            if rec.action is not Action.ABSTAIN:
                continue
            n += 1
            top_axis = rec.acquire_next
            ranking = [
                {"axis": a.axis, "voi": a.voi, "voi_per_cost": a.voi_per_cost}
                for a in rec.voi_ranking
            ]
            rand_axis = rng.choice(all_axes)

            ts, tr = reveal(top_axis)
            top_commit, top_ok = self._selective_commit_correct(q, sel, ts, tr)
            rs, rr = reveal(rand_axis)
            rand_commit, rand_ok = self._selective_commit_correct(q, sel, rs, rr)

            n_topvoi_cc += int(top_ok)
            n_random_cc += int(rand_ok)
            per_query.append({
                "query": q.label, "top_voi_axis": top_axis, "random_axis": rand_axis,
                "voi_ranking": ranking,
                "topvoi_commit_correct": top_ok, "random_commit_correct": rand_ok,
            })

        return {
            "meta": {
                "tau": tau, "bind_axes": list(bind_axes), "masked_axis": masked_axis,
                "construction": "mask-blocking-axis / measure-VoI-pick-vs-random / re-decide",
                "seed": seed, "n_abstained": n,
            },
            "acquisition": {
                "n": n,
                "topvoi_commit_correct": n_topvoi_cc,
                "random_commit_correct": n_random_cc,
                "topvoi_commit_correct_frac": round(n_topvoi_cc / n, 4) if n else 0.0,
                "random_commit_correct_frac": round(n_random_cc / n, 4) if n else 0.0,
            },
            "per_query": per_query,
        }
