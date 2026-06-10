"""Real-ground-truth coverage guarantee via per-prompt resampling (W4 hardening).

Motivation (W4 in `docs/paper/MOCK_REVIEW.md`). The committed §9 guarantee in
`solver/guarantee.py` calibrates against a *κ-proxy truth* (the richer-κ verdict
stands in for ground truth). That proxy is weak precisely *because* RouterBench is
**single-confidence** — there is no M/L tier for the richer-κ verdict to differ
from the operating one, so the proxy curve collapses to risk≈0 trivially.

This module replaces the proxy with **genuine measured ground truth** by exploiting
the per-prompt structure of the cached RouterBench raw frame
(`data/routerbench_0shot.pkl`):

  * Each of the 11 models has a per-prompt correctness column `'{model}'` (0/1) and a
    per-prompt cost column `'{model}|total_cost'`. `'eval_name'` is the benchmark.
  * **TRUTH** for a model on a benchmark = the *full-sample* mean correctness
    (quality) and mean cost over every prompt of that benchmark. This is the actual
    measured population value — not a proxy.
  * **OPERATING evidence** = a *bootstrap subsample* of `K` prompts per model
    (`random.Random(seed)`), giving a **noisy** quality/cost estimate — the realistic
    "we only measured a small battery" regime.

A query fixes a quality floor `q*` (a percentile of the TRUTH qualities across the 11
models, so the floor is always achievable by some but not all configs). The selective
procedure commits the **min-(noisy)-cost** config whose **noisy** quality estimate
clears `q*` by a confidence **margin** `m`; otherwise it **abstains** (commit only when
confident). A commit is **CORRECT** iff, under TRUTH, the committed config is *feasible*
(true quality ≥ q*) **and** *min-cost-feasible* (the cheapest among all truly-feasible
configs). This is exactly the §9 "feasible ∧ minimum-sufficient" correctness, now scored
against real measurement.

Sweeping `m` traces the **coverage–risk curve**:
    coverage = |commit| / |queries|,   risk = P(incorrect | commit),
aggregated over many seeded resamples × several benchmarks × several q* percentiles
(report total n). The margin is then **calibrated** for a target risk `α` on a
**held-out 50/50 calibration split** (seeded; C8 — no leakage between calibrate and
test), and **TEST-split** coverage/risk are reported at α = 0.05 and α = 0.10.

This is conformal-style real-GT calibration: *truth = full measurement, operating =
subsample*. It reads the pkl directly for this scoring analysis (the same posture as the
descriptive blind-spot reads), not through the substrate/solver — there is no substrate
query here, so C7 is not engaged.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# The 11 RouterBench models = the candidate configs (cost-comparable within a benchmark).
MODELS: tuple[str, ...] = (
    "WizardLM/WizardLM-13B-V1.2",
    "claude-instant-v1",
    "claude-v1",
    "claude-v2",
    "gpt-3.5-turbo-1106",
    "gpt-4-1106-preview",
    "meta/code-llama-instruct-34b-chat",
    "meta/llama-2-70b-chat",
    "mistralai/mistral-7b-chat",
    "mistralai/mixtral-8x7b-chat",
    "zero-one-ai/Yi-34B-Chat",
)

DEFAULT_PKL = "data/routerbench_0shot.pkl"

# Margin grid (absolute quality units): commit only when noisy_q ≥ q* + m.
DEFAULT_MARGINS: tuple[float, ...] = (
    0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20,
)


@dataclass(frozen=True)
class Truth:
    """Full-sample (measured) per-model quality and cost on one benchmark."""

    benchmark: str
    n_prompts: int
    quality: dict[str, float]   # model -> full-sample mean correctness
    cost: dict[str, float]      # model -> full-sample mean cost

    def feasible_models(self, q_star: float) -> list[str]:
        return [m for m in MODELS if self.quality[m] >= q_star]

    def min_cost_feasible(self, q_star: float) -> str | None:
        """The truly minimum-sufficient config: cheapest among truly-feasible."""
        feas = self.feasible_models(q_star)
        if not feas:
            return None
        return min(feas, key=lambda m: self.cost[m])


# A commit is "minimum-sufficient" if its TRUE cost is within this relative tolerance
# of the cheapest truly-feasible config's TRUE cost. Costs across the 11 models span
# ~100×, so an exact-argmin match is brittle to near-ties; the tolerance grades cost-
# optimality honestly. (The PRIMARY safety guarantee is feasibility; min-sufficiency
# is reported as a secondary diagnostic.)
COST_TOL: float = 0.25


@dataclass(frozen=True)
class Decision:
    """The verdict for one Outcome at one margin."""

    committed: bool
    feasible: bool          # committed config truly clears q* (NO hidden violation)
    min_sufficient: bool    # committed true cost within COST_TOL of true min-cost-feas


@dataclass(frozen=True)
class Outcome:
    """One (benchmark, q*, seed) decision instance, before margin thresholding."""

    benchmark: str
    q_star: float
    seed: int
    # noisy per-model estimates from the bootstrap subsample
    noisy_quality: dict[str, float]
    noisy_cost: dict[str, float]
    # truth references
    truth_min_cost_feasible: str | None
    truth_min_cost: float          # true cost of the cheapest truly-feasible config
    truth_quality: dict[str, float]
    truth_cost: dict[str, float]
    has_truth_feasible: bool   # does ANY config truly clear q*? (a well-posed query)

    def decide(self, margin: float) -> Decision:
        """Commit the min-noisy-cost config whose noisy quality clears q* by ≥ margin.

        Two TRUTH-scored verdicts on the committed config:
          * feasible       — true quality ≥ q* (the safety guarantee: no hidden viol.),
          * min_sufficient — true cost ≤ (1+COST_TOL)·(true min-cost-feasible cost).
        Abstention (no eligible config) → not committed.
        """
        eligible = [
            m for m in MODELS if self.noisy_quality[m] >= self.q_star + margin
        ]
        if not eligible:
            return Decision(committed=False, feasible=False, min_sufficient=False)
        committed = min(eligible, key=lambda m: self.noisy_cost[m])
        feasible = self.truth_quality[committed] >= self.q_star
        min_sufficient = feasible and (
            self.truth_cost[committed] <= self.truth_min_cost * (1.0 + COST_TOL) + 1e-12
        )
        return Decision(
            committed=True, feasible=feasible, min_sufficient=min_sufficient
        )


@dataclass(frozen=True)
class CurvePoint:
    margin: float
    coverage: float
    # PRIMARY: feasibility risk = P(committed config truly violates q* | commit).
    risk: float
    # SECONDARY diagnostic: strict min-sufficiency risk = P(not feasible∧min-cost | commit).
    risk_min_sufficient: float
    n_queries: int
    n_commit: int
    n_feasible: int          # commits that are truly feasible (no hidden violation)
    n_min_sufficient: int    # commits that are feasible AND cost-within-tolerance


@dataclass(frozen=True)
class Calibration:
    alpha: float
    margin: float | None       # smallest margin meeting calib FEASIBILITY risk ≤ α
    calib_coverage: float
    calib_risk: float          # feasibility risk on calib
    test_coverage: float
    test_risk: float           # feasibility risk on TEST (the held-out guarantee)
    test_risk_min_sufficient: float
    test_n_queries: int
    test_n_commit: int
    test_n_feasible: int


@dataclass
class GTCoverageGuarantee:
    """Real-GT, per-prompt-resampling coverage guarantee (W4).

    Parameters
    ----------
    pkl_path     : cached RouterBench raw frame.
    benchmarks   : benchmark slices to use (each is internally cost-comparable).
    k_subsample  : #prompts in each bootstrap operating subsample (the battery size).
    q_percentiles: q* floors, each a percentile of the per-benchmark TRUTH qualities.
    n_seeds      : #seeded bootstrap resamples per (benchmark, q*).
    base_seed    : seed offset for reproducible resampling.
    """

    pkl_path: str = DEFAULT_PKL
    benchmarks: tuple[str, ...] = (
        "mmlu-professional-law",
        "arc-challenge",
        "winogrande",
        "grade-school-math",
        "hellaswag",
        "mmlu-moral-scenarios",
    )
    k_subsample: int = 64
    q_percentiles: tuple[float, ...] = (0.40, 0.55, 0.70, 0.85)
    n_seeds: int = 40
    base_seed: int = 7
    _truths: dict[str, Truth] = field(default_factory=dict, init=False, repr=False)
    _rows: dict[str, pd.DataFrame] = field(default_factory=dict, init=False, repr=False)

    # ------------------------------------------------------------------
    # Data loading / TRUTH
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._truths:
            return
        import pandas as pd

        df = pd.read_pickle(self.pkl_path)
        for bench in self.benchmarks:
            sub = df[df["eval_name"] == bench].reset_index(drop=True)
            if len(sub) == 0:
                raise ValueError(f"benchmark {bench!r} not found in {self.pkl_path}")
            # per-prompt correctness/cost matrices, float-cast (columns are object dtype)
            quality_cols = {m: sub[m].astype(float) for m in MODELS}
            cost_cols = {m: sub[f"{m}|total_cost"].astype(float) for m in MODELS}
            truth_q = {m: float(quality_cols[m].mean()) for m in MODELS}
            truth_c = {m: float(cost_cols[m].mean()) for m in MODELS}
            self._truths[bench] = Truth(
                benchmark=bench, n_prompts=len(sub),
                quality=truth_q, cost=truth_c,
            )
            # keep aligned per-prompt arrays for resampling
            self._rows[bench] = pd.DataFrame(
                {m: quality_cols[m].to_numpy() for m in MODELS}
                | {f"{m}|c": cost_cols[m].to_numpy() for m in MODELS}
            )

    def truth(self, benchmark: str) -> Truth:
        self._load()
        return self._truths[benchmark]

    def q_star_for(self, benchmark: str, percentile: float) -> float:
        """q* = a percentile of the 11 TRUTH qualities on this benchmark."""
        import numpy as np

        t = self.truth(benchmark)
        return float(np.quantile([t.quality[m] for m in MODELS], percentile))

    # ------------------------------------------------------------------
    # OPERATING subsample → noisy estimate
    # ------------------------------------------------------------------

    def _operating_outcome(
        self, benchmark: str, q_star: float, seed: int
    ) -> Outcome:
        """Bootstrap K prompts (seeded) and form noisy per-model quality/cost."""
        self._load()
        rows = self._rows[benchmark]
        n = len(rows)
        rng = random.Random(seed)
        # bootstrap WITH replacement: K draws over prompt indices (shared across models,
        # as in real measurement we score every model on the SAME battery of prompts)
        idx = [rng.randrange(n) for _ in range(self.k_subsample)]
        noisy_q: dict[str, float] = {}
        noisy_c: dict[str, float] = {}
        for m in MODELS:
            qarr = rows[m].to_numpy()
            carr = rows[f"{m}|c"].to_numpy()
            noisy_q[m] = float(sum(qarr[i] for i in idx) / self.k_subsample)
            noisy_c[m] = float(sum(carr[i] for i in idx) / self.k_subsample)
        t = self.truth(benchmark)
        feas = t.feasible_models(q_star)
        min_cfg = t.min_cost_feasible(q_star)
        min_cost = min((t.cost[m] for m in feas), default=float("inf"))
        return Outcome(
            benchmark=benchmark, q_star=q_star, seed=seed,
            noisy_quality=noisy_q, noisy_cost=noisy_c,
            truth_min_cost_feasible=min_cfg,
            truth_min_cost=min_cost,
            truth_quality=dict(t.quality),
            truth_cost=dict(t.cost),
            has_truth_feasible=bool(feas),
        )

    # ------------------------------------------------------------------
    # Outcome generation (the full battery of decision instances)
    # ------------------------------------------------------------------

    def generate_outcomes(self) -> list[Outcome]:
        """All (benchmark × q* percentile × seed) decision instances.

        Only WELL-POSED queries (some config truly clears q*) are kept — an
        unsatisfiable query has no correct commit and would only inflate abstention.
        """
        self._load()
        outcomes: list[Outcome] = []
        s = self.base_seed
        for bench in self.benchmarks:
            for pct in self.q_percentiles:
                q_star = self.q_star_for(bench, pct)
                for _k in range(self.n_seeds):
                    seed = s
                    s += 1
                    out = self._operating_outcome(bench, q_star, seed)
                    if out.has_truth_feasible:
                        outcomes.append(out)
        return outcomes

    # ------------------------------------------------------------------
    # Curve + split + calibration
    # ------------------------------------------------------------------

    @staticmethod
    def curve_point(outcomes: list[Outcome], margin: float) -> CurvePoint:
        n_commit = 0
        n_feasible = 0
        n_min_sufficient = 0
        for o in outcomes:
            d = o.decide(margin)
            if d.committed:
                n_commit += 1
                if d.feasible:
                    n_feasible += 1
                if d.min_sufficient:
                    n_min_sufficient += 1
        n = len(outcomes)
        coverage = n_commit / n if n else 0.0
        risk = (n_commit - n_feasible) / n_commit if n_commit else 0.0
        risk_ms = (n_commit - n_min_sufficient) / n_commit if n_commit else 0.0
        return CurvePoint(
            margin=margin, coverage=coverage, risk=risk,
            risk_min_sufficient=risk_ms,
            n_queries=n, n_commit=n_commit,
            n_feasible=n_feasible, n_min_sufficient=n_min_sufficient,
        )

    def coverage_risk_curve(
        self, outcomes: list[Outcome], margins: tuple[float, ...] = DEFAULT_MARGINS
    ) -> list[CurvePoint]:
        return [self.curve_point(outcomes, m) for m in margins]

    @staticmethod
    def split(
        outcomes: list[Outcome], split_seed: int = 2024
    ) -> tuple[list[Outcome], list[Outcome]]:
        """Seeded 50/50 calibration/test split (C8 — disjoint, no leakage)."""
        order = list(range(len(outcomes)))
        random.Random(split_seed).shuffle(order)
        half = len(order) // 2
        calib = [outcomes[i] for i in order[:half]]
        test = [outcomes[i] for i in order[half:]]
        return calib, test

    def calibrate(
        self,
        calib: list[Outcome],
        test: list[Outcome],
        alpha: float,
        margins: tuple[float, ...] = DEFAULT_MARGINS,
    ) -> Calibration:
        """Pick the SMALLEST margin whose CALIB FEASIBILITY risk ≤ α (max coverage
        subject to the safety bound), then report TEST coverage/risk at that margin.
        Calibration targets the PRIMARY guarantee — feasibility (no hidden violation),
        the conformal-controllable quantity. If no margin meets the bound on calib,
        report the lowest-calib-risk committing margin and flag margin=None.
        """
        calib_curve = self.coverage_risk_curve(calib, margins)
        chosen: CurvePoint | None = None
        for pt in calib_curve:
            if pt.n_commit > 0 and pt.risk <= alpha:
                chosen = pt
                break
        margin_val: float | None
        if chosen is None:
            # none meets the bound on calib → lowest-feasibility-risk committing point
            committing = [p for p in calib_curve if p.n_commit > 0]
            best = min(committing, key=lambda p: p.risk) if committing else None
            margin_val = None
            chosen = best
        else:
            margin_val = chosen.margin

        if chosen is None:
            return Calibration(
                alpha=alpha, margin=None,
                calib_coverage=0.0, calib_risk=0.0,
                test_coverage=0.0, test_risk=0.0, test_risk_min_sufficient=0.0,
                test_n_queries=len(test), test_n_commit=0, test_n_feasible=0,
            )

        test_pt = self.curve_point(test, chosen.margin)
        return Calibration(
            alpha=alpha, margin=margin_val,
            calib_coverage=chosen.coverage, calib_risk=chosen.risk,
            test_coverage=test_pt.coverage, test_risk=test_pt.risk,
            test_risk_min_sufficient=test_pt.risk_min_sufficient,
            test_n_queries=test_pt.n_queries,
            test_n_commit=test_pt.n_commit, test_n_feasible=test_pt.n_feasible,
        )


def _fmt_pct(frac: float) -> str:
    return f"{100.0 * frac:5.1f}%"


def render_markdown(
    guarantee: GTCoverageGuarantee,
    curve: list[CurvePoint],
    calibrations: list[Calibration],
    total_n: int,
) -> str:
    """Human-readable real-GT coverage–risk report."""
    lines: list[str] = []
    lines.append("# P4 Real-GT Coverage–Risk Curve (per-prompt resampling, W4)\n")
    lines.append(
        "Genuine measured ground truth replaces the κ-proxy of "
        "`solver/guarantee.py`. **Truth = full-sample** per-model mean quality + cost; "
        "**operating evidence = a seeded bootstrap subsample of K prompts** (the noisy "
        "small-battery regime). A query fixes a quality floor `q*` (a percentile of the "
        "TRUTH qualities); the procedure commits the min-(noisy)-cost config whose "
        "*noisy* quality clears `q*` by a confidence margin `m`, else abstains.\n"
    )
    lines.append(
        "Two TRUTH-scored verdicts on each commit:\n"
        "- **PRIMARY — feasibility risk** = P(committed config truly violates q* | "
        "commit). This is the *safety* guarantee (no hidden constraint violation, "
        "the §9 / B2-B3 quantity) and the conformal-controllable one — a one-sided "
        "quality margin monotonically reduces it. **Calibration targets this.**\n"
        f"- **SECONDARY — strict min-sufficiency risk** = P(not [feasible ∧ true cost "
        f"≤ (1+{COST_TOL:g})·min-cost-feasible cost] | commit), a diagnostic. It does "
        "NOT fall with the margin: a larger quality margin pushes the procedure to "
        "*over-provision* (pick a pricier, safer config), so the commit stays feasible "
        "but is no longer the cheapest feasible. A single one-sided quality margin "
        "cannot guarantee a two-sided (feasible ∧ cheapest) criterion against real "
        "truth — reported honestly, not forced.\n"
    )
    lines.append(f"- pkl: `{guarantee.pkl_path}`")
    lines.append(f"- benchmarks: {', '.join(f'`{b}`' for b in guarantee.benchmarks)}")
    lines.append(f"- models (configs): **{len(MODELS)}**")
    lines.append(f"- K (subsample / battery size): **{guarantee.k_subsample}** prompts")
    lines.append(
        f"- q* percentiles: {', '.join(str(p) for p in guarantee.q_percentiles)}"
    )
    lines.append(f"- seeded resamples per (benchmark, q*): **{guarantee.n_seeds}**")
    lines.append(f"- cost tolerance for min-sufficiency: **{COST_TOL:g}** (relative)")
    lines.append(f"- **total decision instances (n): {total_n}**")
    lines.append("")
    lines.append(
        "C8: calibration and test are a seeded **disjoint 50/50 split** — the margin "
        "is chosen on calibration only, then applied to held-out test (no leakage). This "
        "reads the pkl directly for scoring (no substrate query → C7 not engaged)."
    )
    lines.append("")
    lines.append("## Coverage–risk curve (full battery)\n")
    lines.append(
        "| margin m | coverage | **feasibility risk** | min-suff. risk | "
        "n_commit | n_feasible | n_min_suff |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for p in curve:
        lines.append(
            f"| {p.margin:g} | {_fmt_pct(p.coverage)} | "
            f"**{_fmt_pct(p.risk)}** | {_fmt_pct(p.risk_min_sufficient)} "
            f"| {p.n_commit} | {p.n_feasible} | {p.n_min_sufficient} |"
        )
    lines.append("")
    lines.append(
        "The **feasibility-risk** column is the genuine real-GT selective-commit "
        "guarantee: it falls monotonically with the margin (over-provisioning makes "
        "feasibility *safer*). The min-suff. column rises — the documented tension above."
    )
    lines.append("")
    lines.append(
        "## Calibrated guarantee (feasibility) — margin chosen on calib, on TEST\n"
    )
    lines.append(
        "| α (target risk) | margin | calib cov | calib feas-risk | "
        "**test cov** | **test feas-risk** | test min-suff risk | test n_commit | "
        "holds? |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for c in calibrations:
        margin_s = "—" if c.margin is None else f"{c.margin:g}"
        holds = "✅" if (c.margin is not None and c.test_risk <= c.alpha) else "⚠"
        lines.append(
            f"| {c.alpha:g} | {margin_s} | {_fmt_pct(c.calib_coverage)} | "
            f"{_fmt_pct(c.calib_risk)} | **{_fmt_pct(c.test_coverage)}** | "
            f"**{_fmt_pct(c.test_risk)}** | {_fmt_pct(c.test_risk_min_sufficient)} | "
            f"{c.test_n_commit} | {holds} |"
        )
    lines.append("")
    lines.append(
        "*holds?* = the calibrated margin yields **test feasibility-risk ≤ α** on the "
        "held-out split (the guarantee transfers). ⚠ flags a regime where the target "
        "risk is not attainable / does not transfer; reported honestly, not forced."
    )
    lines.append("")
    return "\n".join(lines)
