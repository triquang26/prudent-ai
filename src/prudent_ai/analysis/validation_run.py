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
from prudent_ai.validation.binding import is_pareto_binding
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
    #   (key, tau, bind_axes, masked_axis, benchmark|None, confidence)
    # benchmark=None → use the substrate as-is (BFCL). benchmark set → wrap in
    # BenchmarkSubstrate to hold the RouterBench benchmark fixed (cost comparable).
    #
    # Confidence tier (W5): RouterBench slices carry REAL measured ground truth
    # (the 11 models × benchmark accuracy is the published RouterBench GT) → "H".
    # BFCL function-calling quality is M-confidence (semi-derived) → "M". The
    # H-only pooled block is the flagship: it does not depend on any M data.

    # RouterBench config_ids are ``rb-{model}-{benchmark}``; a benchmark is a
    # candidate-set restriction with 11 models. We DISCOVER the benchmark groups
    # from the substrate (C7: via candidates) so the battery scales to all ~30
    # RouterBench groups instead of a hardcoded six.
    _ROUTERBENCH_MODELS: tuple[str, ...] = (
        "rb-claude-instant-v1", "rb-claude-v1", "rb-claude-v2",
        "rb-gpt-3-5-turbo-1106", "rb-gpt-4-1106-preview",
        "rb-meta-code-llama-instruct-34b-chat", "rb-meta-llama-2-70b-chat",
        "rb-mistralai-mistral-7b-chat", "rb-mistralai-mixtral-8x7b-chat",
        "rb-wizardlm-wizardlm-13b-v1-2", "rb-zero-one-ai-yi-34b-chat",
    )
    # Minimum cost-comparable configs for a slice to be non-degenerate.
    _MIN_FEASIBLE_CONFIGS: int = 6

    def discover_routerbench_benchmarks(self) -> list[str]:
        """All RouterBench benchmark groups present in the substrate (C7).

        Reads the ``routerbench`` candidate set via ``candidates`` (the C7 solver
        interface) and parses ``rb-{model}-{benchmark}`` config_ids by stripping
        the known model prefixes. Returns the benchmark suffixes sorted, so the
        battery enumerates every ~30 RouterBench group automatically.
        """
        cands = self.sub.candidates("routerbench")
        benches: set[str] = set()
        models = sorted(self._ROUTERBENCH_MODELS, key=len, reverse=True)
        for c in cands:
            cid = c.id
            for m in models:
                if cid.startswith(m + "-"):
                    benches.add(cid[len(m) + 1:])
                    break
        return sorted(benches)

    def _scale_slices(
        self, benchmarks: tuple[str, ...] | None,
    ) -> list[tuple[str, str, tuple[str, ...], str, str | None, str]]:
        """Build the (key, tau, bind, mask, benchmark, confidence) slice list.

        ``benchmarks=None`` → discover ALL RouterBench groups from the substrate.
        BFCL stays in the battery and is tagged M-confidence; every RouterBench
        per-benchmark slice is tagged H-confidence.
        """
        if benchmarks is None:
            benchmarks = tuple(self.discover_routerbench_benchmarks())
        slices: list[tuple[str, str, tuple[str, ...], str, str | None, str]] = [
            (
                "BFCL/bind=quality+latency/mask=quality",
                "function-calling",
                ("quality", "latency_p95"),
                "quality",
                None,
                "M",   # function-calling quality is M-confidence
            ),
        ]
        for bench in benchmarks:
            slices.append((
                f"routerbench[{bench}]/bind=quality/mask=quality",
                "routerbench",
                ("quality",),
                "quality",
                bench,
                "H",   # RouterBench accuracy is real measured GT
            ))
        return slices

    @staticmethod
    def _pool(
        base_pq: list[dict], sel_pq: list[dict], rng: random.Random,
    ) -> dict:
        """Pool per-query pairs into a baseline-vs-selective significance block."""
        if not base_pq:
            return {"n": 0}
        base_hv = sum(int(x["hidden_violation"]) for x in base_pq) / len(base_pq)
        sel_hv = sum(int(x["hidden_violation"]) for x in sel_pq) / len(sel_pq)
        stats = ValidationRunner._paired_significance(base_pq, sel_pq, rng)
        return {
            "baseline_hidden_violation_rate": round(base_hv, 6),
            "selective_hidden_violation_rate": round(sel_hv, 6),
            **stats,
        }

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

    def scale_v1(
        self,
        seed: int = 12345,
        benchmarks: tuple[str, ...] | None = None,
        min_feasible_configs: int | None = None,
    ) -> dict:
        """Scaled V1 battery with significance + multiple biting slices.

        Larger per-slice battery (pcts 10..90 step 5 ≈ 17 queries), over BFCL plus
        per-benchmark RouterBench slices. ``benchmarks=None`` (default) DISCOVERS
        every RouterBench benchmark group in the substrate (~30 groups) and
        includes each one; degenerate slices with fewer than
        ``min_feasible_configs`` cost-comparable candidates are skipped. A bigger
        battery → bigger n. Pass an explicit ``benchmarks`` tuple to override.

        For each slice we run ALL_RULES (per-rule coverage + hidden_violation_rate
        + counts) and collect the per-query baseline-vs-selective pairs for the
        must-beat baselines (B2, B3). A slice is "biting" iff some must-beat
        baseline actually hidden-violates on it; significance and pooling are
        computed over biting slices only, where there is something to beat.

        Each slice is tagged with a confidence tier (W5): RouterBench slices are
        H-confidence (real measured GT), BFCL is M-confidence. We pool TWICE:
          * ``pooled`` — over ALL biting slices (H + M);
          * ``pooled_h_only`` — over H-confidence biting slices only (the
            RouterBench slices), the FLAGSHIP that does not depend on any
            M-confidence data (closes W5).
        """
        pcts = tuple(range(10, 95, 5))
        rng = random.Random(seed)
        min_cfg = (
            self._MIN_FEASIBLE_CONFIGS if min_feasible_configs is None
            else min_feasible_configs
        )

        slices_out: dict[str, dict] = {}
        # Pooled per-query pairs across biting slices, per must-beat baseline.
        # Tracked separately for ALL biting slices and H-confidence-only.
        pooled_base_pq: dict[str, list[dict]] = {b: [] for b in _MUST_BEAT_SCALE}
        pooled_sel_pq: dict[str, list[dict]] = {b: [] for b in _MUST_BEAT_SCALE}
        pooled_h_base_pq: dict[str, list[dict]] = {b: [] for b in _MUST_BEAT_SCALE}
        pooled_h_sel_pq: dict[str, list[dict]] = {b: [] for b in _MUST_BEAT_SCALE}

        for key, tau, bind_axes, masked_axis, bench, conf in self._scale_slices(
            benchmarks
        ):
            sub = BenchmarkSubstrate(self.sub, bench) if bench else self.sub
            n_candidates = len(sub.candidates(tau))
            # Skip degenerate slices: too few cost-comparable configs to right-size.
            if n_candidates < min_cfg:
                slices_out[key] = {
                    "meta": {
                        "tau": tau, "benchmark": bench, "confidence": conf,
                        "bind_axes": list(bind_axes), "masked_axis": masked_axis,
                        "n_queries": 0, "n_candidates": n_candidates,
                        "selective_hidden_violation_rate": 0.0,
                        "must_beat_hidden_violation_rate": {},
                        "baselines_bite": False, "c2_verdict": "degenerate",
                        "skipped": True,
                    },
                    "rules": {}, "significance": {},
                }
                continue
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
                    if conf == "H":
                        pooled_h_base_pq[name].extend(base_pq)
                        pooled_h_sel_pq[name].extend(sel_pq)

            slices_out[key] = {
                "meta": {
                    "tau": tau,
                    "benchmark": bench,
                    "confidence": conf,
                    "bind_axes": list(bind_axes),
                    "masked_axis": masked_axis,
                    "n_queries": len(queries),
                    "n_candidates": n_candidates,
                    "selective_hidden_violation_rate": sel_hv,
                    "must_beat_hidden_violation_rate": beat,
                    "baselines_bite": baselines_bite,
                    "c2_verdict": c2_verdict,
                },
                "rules": rules,
                "significance": sig,
            }

        # --- pooled across biting slices (ALL) and H-confidence-only ---
        pooled: dict[str, dict] = {}
        pooled_h_only: dict[str, dict] = {}
        for name in _MUST_BEAT_SCALE:
            pooled[name] = self._pool(
                pooled_base_pq[name], pooled_sel_pq[name], rng
            )
            pooled_h_only[name] = self._pool(
                pooled_h_base_pq[name], pooled_h_sel_pq[name], rng
            )

        biting = [
            k for k, v in slices_out.items() if v["meta"]["baselines_bite"]
        ]
        biting_h = [
            k for k in biting if slices_out[k]["meta"]["confidence"] == "H"
        ]
        skipped = [
            k for k, v in slices_out.items()
            if v["meta"].get("skipped", False)
        ]
        total_q = sum(slices_out[k]["meta"]["n_queries"] for k in slices_out)
        biting_q = sum(slices_out[k]["meta"]["n_queries"] for k in biting)
        biting_h_q = sum(slices_out[k]["meta"]["n_queries"] for k in biting_h)
        return {
            "meta": {
                "seed": seed,
                "pcts": list(pcts),
                "n_slices": len(slices_out),
                "n_benchmarks_discovered": len(
                    [s for s in slices_out if slices_out[s]["meta"]["benchmark"]]
                ),
                "biting_slices": biting,
                "n_biting_slices": len(biting),
                "biting_slices_h": biting_h,
                "n_biting_slices_h": len(biting_h),
                "skipped_slices": skipped,
                "total_queries": total_q,
                "biting_queries": biting_q,
                "biting_queries_h": biting_h_q,
                "must_beat": list(_MUST_BEAT_SCALE),
            },
            "slices": slices_out,
            "pooled": pooled,
            "pooled_h_only": pooled_h_only,
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

    # ---------------------------------------------------------- V2 (scaled) ----

    @staticmethod
    def _commit_correct(
        mp: MaskAndPredict, query: Query, rule: SelectiveRule, sub,
        visible: frozenset[str], kappa: tuple[str, ...], phi: Phi,
    ) -> tuple[bool, bool]:
        """(committed, commit_truly_feasible) for *rule* reading *sub* under *visible*."""
        pred = rule.decide(sub, query, visible, kappa, phi)
        if pred is None:
            return (False, False)
        return (True, mp.true_feasible(query, pred))

    @staticmethod
    def _voi_significance(pairs: list[tuple[bool, bool]]) -> dict:
        """McNemar one-sided exact-binomial test that VoI-pick beats a random axis.

        ``pairs = [(topvoi_commit_correct, random_commit_correct), ...]`` over the
        abstained queries. ``b`` = queries where the VoI pick yields a correct commit
        and a random axis does not; ``c`` = the reverse. The one-sided exact binomial
        ``P(X >= b)``, ``X ~ Binom(b+c, 0.5)``, tests H1: VoI-pick strictly better on
        the discordant pairs. ``significant`` iff ``b>c`` and ``p<0.05``.
        """
        n = len(pairs)
        topvoi_cc = sum(1 for t, _ in pairs if t)
        random_cc = sum(1 for _, r in pairs if r)
        b = sum(1 for t, r in pairs if t and not r)
        c = sum(1 for t, r in pairs if r and not t)
        nd = b + c
        p_value = _binom_sf_ge(b, nd, 0.5) if nd else 1.0
        return {
            "n": n,
            "topvoi_commit_correct": topvoi_cc,
            "random_commit_correct": random_cc,
            "topvoi_commit_correct_frac": round(topvoi_cc / n, 4) if n else 0.0,
            "random_commit_correct_frac": round(random_cc / n, 4) if n else 0.0,
            "mcnemar_b": b,
            "mcnemar_c": c,
            "binom_p_one_sided": round(p_value, 8),
            "significant": bool(nd > 0 and b > c and p_value < 0.05),
        }

    def scale_v2(
        self,
        seed: int = 12345,
        benchmarks: tuple[str, ...] | None = None,
        min_feasible_configs: int | None = None,
    ) -> dict:
        """Scaled VoI-guided acquisition (§10) with significance — lifts the n=5 pilot.

        Same construction as :meth:`v2_acquisition` (mask the biting binding axis,
        let the procedure ABSTAIN, then "measure" the top-VoI axis vs a random axis
        and re-decide), but run over BFCL PLUS every per-benchmark RouterBench slice
        (discovered from the substrate via the C7 interface), pooling the per-query
        ``(VoI-pick-correct, random-correct)`` pairs into a McNemar one-sided binomial
        test. Pooled twice — over ALL slices and over H-confidence slices only
        (RouterBench) — mirroring ``scale_v1``'s W5 flagship discipline.
        """
        pcts = tuple(range(10, 95, 5))
        rng = random.Random(seed)
        all_axes = sorted(ALL_AXES)
        sel = SelectiveRule()
        min_cfg = (
            self._MIN_FEASIBLE_CONFIGS if min_feasible_configs is None
            else min_feasible_configs
        )

        slices_out: dict[str, dict] = {}
        pooled_pairs: list[tuple[bool, bool]] = []
        pooled_h_pairs: list[tuple[bool, bool]] = []

        for key, tau, bind_axes, masked_axis, bench, conf in self._scale_slices(
            benchmarks
        ):
            sub = BenchmarkSubstrate(self.sub, bench) if bench else self.sub
            n_candidates = len(sub.candidates(tau))
            if n_candidates < min_cfg:
                slices_out[key] = {
                    "meta": {
                        "tau": tau, "benchmark": bench, "confidence": conf,
                        "masked_axis": masked_axis, "n_candidates": n_candidates,
                        "skipped": True,
                    },
                    "acquisition": {"n": 0},
                }
                continue
            mp = MaskAndPredict(sub, kappa=self.kappa, phi=self.phi)
            queries = mp.generate_queries(tau, bind_axes, pcts=pcts)
            masked_sub = MaskedSubstrate(sub, masked_axis)
            visible_masked = ALL_AXES - {masked_axis}

            pairs: list[tuple[bool, bool]] = []
            for q in queries:
                rec = right_size(masked_sub, q, self.kappa, self.phi, visible_masked)
                if rec.action is not Action.ABSTAIN:
                    continue
                top_axis = rec.acquire_next
                rand_axis = rng.choice(all_axes)
                # reveal: un-mask only if the measured axis is the blocking one;
                # measuring any other field leaves the blocking axis still hidden.
                ts, tr = (
                    (sub, ALL_AXES) if top_axis == masked_axis
                    else (masked_sub, visible_masked)
                )
                _, top_ok = self._commit_correct(
                    mp, q, sel, ts, tr, self.kappa, self.phi
                )
                rs, rr = (
                    (sub, ALL_AXES) if rand_axis == masked_axis
                    else (masked_sub, visible_masked)
                )
                _, rand_ok = self._commit_correct(
                    mp, q, sel, rs, rr, self.kappa, self.phi
                )
                pairs.append((top_ok, rand_ok))

            slices_out[key] = {
                "meta": {
                    "tau": tau, "benchmark": bench, "confidence": conf,
                    "bind_axes": list(bind_axes), "masked_axis": masked_axis,
                    "n_candidates": n_candidates, "n_abstained": len(pairs),
                },
                "acquisition": self._voi_significance(pairs),
            }
            pooled_pairs.extend(pairs)
            if conf == "H":
                pooled_h_pairs.extend(pairs)

        n_with_signal = sum(
            1 for v in slices_out.values() if v["acquisition"].get("n", 0) > 0
        )
        return {
            "meta": {
                "seed": seed,
                "pcts": list(pcts),
                "n_slices": len(slices_out),
                "n_slices_with_abstentions": n_with_signal,
                "construction":
                    "mask-blocking-axis / measure-VoI-pick-vs-random / re-decide",
            },
            "slices": slices_out,
            "pooled": self._voi_significance(pooled_pairs),
            "pooled_h_only": self._voi_significance(pooled_h_pairs),
        }

    # ------------------------------------------------ COMMIT-branch validity ----

    def commit_validation(
        self,
        benchmarks: tuple[str, ...] | None = None,
        min_feasible_configs: int | None = None,
    ) -> dict:
        """Exercise + score the POSITIVE COMMIT action of the procedure (closes W11).

        On every biting GT slice (the slices ``scale_v1`` masks), run the selective
        procedure under the FULL evidence regime — where the binding axis IS observed
        — so it COMMITs instead of abstaining, and score each commit against ground
        truth:
          * ``feasible``        — the committed config truly satisfies the bound axes
            (``true_feasible``); the selective rule must never commit a violation;
          * ``min_sufficient``  — its true cost equals the B5-oracle min-cost feasible
            config (zero decision-regret): the commit is not merely feasible but the
            CHEAPEST feasible config.
        Each query is also re-run under the masked regime to record the DUAL: the same
        slice forces ABSTAIN when the binding axis is hidden (selective coverage 0).
        Together — abstains when blind, commits correctly when sighted — this closes
        the gap that the COMMIT branch was never validated on a biting slice.
        """
        pcts = tuple(range(10, 95, 5))
        min_cfg = (
            self._MIN_FEASIBLE_CONFIGS if min_feasible_configs is None
            else min_feasible_configs
        )

        slices_out: dict[str, dict] = {}
        agg = {"n_commit": 0, "n_feasible": 0, "n_min_sufficient": 0,
               "sum_regret": 0.0, "n_regret": 0, "n_queries": 0,
               "n_masked_abstain": 0}
        agg_h = dict(agg)

        for key, tau, bind_axes, masked_axis, bench, conf in self._scale_slices(
            benchmarks
        ):
            sub = BenchmarkSubstrate(self.sub, bench) if bench else self.sub
            n_candidates = len(sub.candidates(tau))
            if n_candidates < min_cfg:
                slices_out[key] = {
                    "meta": {
                        "tau": tau, "benchmark": bench, "confidence": conf,
                        "masked_axis": masked_axis, "n_candidates": n_candidates,
                        "skipped": True,
                    },
                    "commit": {},
                }
                continue
            mp = MaskAndPredict(sub, kappa=self.kappa, phi=self.phi)
            queries = mp.generate_queries(tau, bind_axes, pcts=pcts)
            masked_sub = MaskedSubstrate(sub, masked_axis)
            visible_masked = ALL_AXES - {masked_axis}

            n_q = len(queries)
            n_commit = n_feas = n_minsuf = n_reg = n_masked_abstain = 0
            sum_reg = 0.0
            for q in queries:
                rec = right_size(sub, q, self.kappa, self.phi, ALL_AXES)
                if rec.action is Action.COMMIT:
                    n_commit += 1
                    cid = rec.committed_config
                    if mp.true_feasible(q, cid):
                        n_feas += 1
                        oc = mp.oracle_cost(q)
                        pc = mp._true_val(cid, "cost")
                        if oc is not None and pc is not None:
                            reg = max(0.0, pc - oc)
                            sum_reg += reg
                            n_reg += 1
                            if reg <= 1e-9:
                                n_minsuf += 1
                # dual: hide the binding axis → the selective rule should abstain.
                mrec = right_size(masked_sub, q, self.kappa, self.phi, visible_masked)
                if mrec.action is Action.ABSTAIN:
                    n_masked_abstain += 1

            n_commit_safe = n_commit or 0
            slices_out[key] = {
                "meta": {
                    "tau": tau, "benchmark": bench, "confidence": conf,
                    "bind_axes": list(bind_axes), "masked_axis": masked_axis,
                    "n_candidates": n_candidates, "n_queries": n_q,
                },
                "commit": {
                    "n_commit": n_commit,
                    "coverage": round(n_commit / n_q, 4) if n_q else 0.0,
                    "feasible_frac": round(n_feas / n_commit_safe, 4) if n_commit else 0.0,
                    "min_sufficient_frac": round(n_minsuf / n_feas, 4) if n_feas else 0.0,
                    "mean_regret": round(sum_reg / n_reg, 6) if n_reg else 0.0,
                    "n_feasible": n_feas,
                    "n_min_sufficient": n_minsuf,
                    "n_masked_abstain": n_masked_abstain,
                    "dual_validated": bool(n_commit > 0 and n_masked_abstain == n_q),
                },
            }
            for a in ((agg, agg_h) if conf == "H" else (agg,)):
                a["n_commit"] += n_commit
                a["n_feasible"] += n_feas
                a["n_min_sufficient"] += n_minsuf
                a["sum_regret"] += sum_reg
                a["n_regret"] += n_reg
                a["n_queries"] += n_q
                a["n_masked_abstain"] += n_masked_abstain

        def _summ(a: dict) -> dict:
            nc, nf, nr = a["n_commit"], a["n_feasible"], a["n_regret"]
            return {
                "n_queries": a["n_queries"],
                "n_commit": nc,
                "coverage": round(nc / a["n_queries"], 4) if a["n_queries"] else 0.0,
                "n_feasible": nf,
                "feasible_frac": round(nf / nc, 4) if nc else 0.0,
                "n_min_sufficient": a["n_min_sufficient"],
                "min_sufficient_frac": round(a["n_min_sufficient"] / nf, 4) if nf else 0.0,
                "mean_regret": round(a["sum_regret"] / nr, 6) if nr else 0.0,
                "n_masked_abstain": a["n_masked_abstain"],
            }

        return {
            "meta": {
                "pcts": list(pcts),
                "n_slices": len(slices_out),
                "construction":
                    "full-regime COMMIT scored vs GT (feasible + min-sufficient); "
                    "masked-regime dual = ABSTAIN",
            },
            "slices": slices_out,
            "pooled": _summ(agg),
            "pooled_h_only": _summ(agg_h),
        }

    # --------------------------------------------- per-instance binding (W1) ----

    def binding_certification(
        self,
        benchmarks: tuple[str, ...] | None = None,
        min_feasible_configs: int | None = None,
    ) -> dict:
        """Recover `bind(q)` per instance from Pareto structure and test bite⟺binding (W1).

        For each query on each slice, certify whether the masked axis is **Pareto-
        binding** (`is_pareto_binding`: dropping its constraint strictly lowers the true
        min-cost) and whether the must-beat baseline B2 **bites** (hidden-violates). We
        run the biting slices (mask the binding axis) PLUS a non-binding **control**
        (BFCL mask=`latency_p95`, where cheap==fast so latency is slack), and build the
        2×2 confusion of (certified-binding × baseline-bites). The C2 mechanism predicts
        the diagonal: bite ⇔ the masked axis is Pareto-binding — an independent,
        data-recovered certificate that the biting axes really bind, not just declared.

        Also reports C2 **restricted to certified-binding queries**: selective vs B2
        hidden-violation, to show the gap is undiminished on the truly-binding subset.
        """
        pcts = tuple(range(10, 95, 5))
        min_cfg = (
            self._MIN_FEASIBLE_CONFIGS if min_feasible_configs is None
            else min_feasible_configs
        )
        sel = _SELECTIVE
        b2 = _MUST_BEAT_RULES["B2_observed_pareto"]

        control = [(
            "BFCL/bind=quality+latency/mask=latency_p95 [CONTROL: non-binding]",
            "function-calling", ("quality", "latency_p95"), "latency_p95", None, "M",
        )]
        all_slices = list(self._scale_slices(benchmarks)) + control

        slices_out: dict[str, dict] = {}
        confusion = {"bind_bite": 0, "bind_nobite": 0,
                     "nobind_bite": 0, "nobind_nobite": 0}
        restr = {"n": 0, "sel_hv": 0, "b2_hv": 0}

        for key, tau, bind_axes, masked_axis, bench, conf in all_slices:
            is_control = "CONTROL" in key
            sub = BenchmarkSubstrate(self.sub, bench) if bench else self.sub
            n_candidates = len(sub.candidates(tau))
            if n_candidates < min_cfg:
                slices_out[key] = {
                    "meta": {
                        "tau": tau, "benchmark": bench, "confidence": conf,
                        "masked_axis": masked_axis, "is_control": is_control,
                        "n_candidates": n_candidates, "skipped": True,
                    },
                }
                continue
            mp = MaskAndPredict(sub, kappa=self.kappa, phi=self.phi)
            queries = mp.generate_queries(tau, bind_axes, pcts=pcts)
            b2pq = mp.score_rule_per_query(b2, queries, masked_axis)
            selpq = mp.score_rule_per_query(sel, queries, masked_axis)

            n_cert = n_bite = 0
            for q, bq, sq in zip(queries, b2pq, selpq, strict=True):
                cert = is_pareto_binding(sub, q, masked_axis, self.kappa, self.phi)
                bite = bool(bq["hidden_violation"])
                n_cert += int(cert)
                n_bite += int(bite)
                bucket = ("bind" if cert else "nobind") + ("_bite" if bite else "_nobite")
                confusion[bucket] += 1
                if cert:
                    restr["n"] += 1
                    restr["sel_hv"] += int(sq["hidden_violation"])
                    restr["b2_hv"] += int(bq["hidden_violation"])

            nq = len(queries)
            slices_out[key] = {
                "meta": {
                    "tau": tau, "benchmark": bench, "confidence": conf,
                    "bind_axes": list(bind_axes), "masked_axis": masked_axis,
                    "is_control": is_control, "n_queries": nq,
                    "n_candidates": n_candidates,
                    "certified_binding": n_cert,
                    "certified_binding_frac": round(n_cert / nq, 4) if nq else 0.0,
                    "baseline_bites": n_bite,
                },
            }

        total = sum(confusion.values())
        agree = (
            (confusion["bind_bite"] + confusion["nobind_nobite"]) / total
            if total else 0.0
        )
        return {
            "meta": {
                "pcts": list(pcts),
                "n_slices": len(slices_out),
                "definition":
                    "bind(q) = {a : min_cost(q\\{a}) < min_cost(q)} (Pareto active "
                    "constraint on the GT slice)",
            },
            "slices": slices_out,
            "confusion": confusion,
            "bite_iff_binding_agreement": round(agree, 4),
            "c2_restricted_to_certified_binding": {
                "n": restr["n"],
                "selective_hidden_violation_rate":
                    round(restr["sel_hv"] / restr["n"], 4) if restr["n"] else 0.0,
                "b2_hidden_violation_rate":
                    round(restr["b2_hv"] / restr["n"], 4) if restr["n"] else 0.0,
            },
        }
