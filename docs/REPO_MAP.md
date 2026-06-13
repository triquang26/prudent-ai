# REPO_MAP.md — orientation for Calibrated Transfer + Live Acquisition Loop

Map of the existing `prudent_ai` codebase, produced before any new algorithmic code
(GATE 0). Downstream phases reference the **real** names below, not the placeholder
names in the hand-off spec. Test suite: **`PYTHONNOUSERSITE=1 uv run pytest -q` → 79
passed** (16 files) at the time of mapping.

All paths are under `/mnt/data/sftp/data/quangpt3/prudent-ai-workspace/prudent-ai`.

## 1. Substrate / belief / φ layer

| Concept | Real name | File:line | Signature / notes |
|---|---|---|---|
| 3-fn interface | `Substrate` | `src/prudent_ai/substrate/substrate.py:143–234` | `candidates(tau)->list[Candidate]`, `cell(x,a)->list[Observation]`, `required_fields(bundle)->set[str]`. κ-free, φ-free. |
| Observation | `Observation` | `substrate/substrate.py` | fields incl. `value_num: float\|None`, `confidence: str` (H/M/L), `axis`, `config_id`, `context`. |
| Belief | `Belief` | `solver/beliefs.py:39–59` | `Belief(is_bottom, lo, hi, point, n_obs)`; `BOTTOM = Belief(is_bottom=True)`; `.is_present`. |
| φ aggregation | `aggregate` | `solver/beliefs.py:72–98` | `aggregate(observations, kappa=DEFAULT_KAPPA, phi=Phi.INTERVAL)->Belief`. INTERVAL → `[min,max]`, point=midpoint; POINT → median. ⊥ if κ-filtered set empty. |
| φ mode | `Phi` | `solver/beliefs.py:32–36` | `Phi.INTERVAL`, `Phi.POINT`. |
| κ filter | `kappa_filter` | `solver/beliefs.py:62–69` | `DEFAULT_KAPPA=("H","M")`. |
| Cache wrapper | `CachedSubstrate` | `solver/cache.py:23–59` | Memoizes `candidates`/`cell`, passes `required_fields` through, `__getattr__` delegates. **C7-preserving** (caches verbatim). |

**Axes.** `ALL_AXES` / `FULL` in `solver/regimes.py:16–39` =
`{quality, latency_p95, throughput, cost, energy, memory_hw, governance, reviewer_burden}`.
Note the real axis name is **`latency_p95`** (not `latency`).

**Structural / unmeasurable set.** `UNMEASURABLE_AXES` in
`analysis/empirical_prior_map.py:80–82` =
`{governance, reviewer_burden, memory_hw, energy, throughput}`. These carry zero
κ-qualifying evidence corpus-wide → transfer **must refuse** to emit an interval here.

**Quality units (OPEN UNKNOWN → resolved).** Quality is **[0,1] accuracy** (mean
per-prompt correctness). Grounded thresholds: `general-qa|quality≈0.553`,
`function-calling|quality≈0.355`; observed quality spans ≈0.35–0.87. So an interval of
width 0.1 = 10 accuracy points.

**Interval-injection hook (OPEN UNKNOWN → resolved): NONE exists.** `aggregate()` is the
only belief constructor and reads only stored observations. To feed a calibrated
interval into a fragmented-⊥ cell **without mutating the frozen store**, add an
**`OverlayedSubstrate`** wrapper (mirror `CachedSubstrate`): override `cell(x,a)` to
return *synthetic* `Observation`s (two rows valued `lo` and `hi`, confidence in κ) for
registered `(config_id, axis)` overlays when the base cell is empty; pass `candidates`
and `required_fields` through. Wrap order: `CachedSubstrate(OverlayedSubstrate(base, overlays))`.
Then the existing `aggregate`/`classify_query` runs unchanged and the verdict machinery
is untouched — only the belief assigned to the overlaid ⊥ cell changes.

## 2. Verdict engine + VoI

| Concept | Real name | File:line | Notes |
|---|---|---|---|
| Query verdict (Defn 1) | `classify_query` | `solver/decidability.py:71–171` | `(sub, query, kappa=DEFAULT_KAPPA, phi=Phi.INTERVAL, regime=FULL)->DecidabilityResult`. |
| Verdict result | `DecidabilityResult` | `decidability.py:54–68` | `.label: Decidability`, `.blocking_axes: frozenset[str]`, `.argmin_config`, candidate counts. |
| Verdict enum | `Decidability` | `decidability.py:48–51` | `DECIDABLE / UNDERDETERMINED / INFEASIBLE`. |
| Candidate verdict | `classify_candidate` | `solver/feasibility.py:93–141` | `->CandidateVerdict(config_id, state: FeasState, pending_fields, cost_belief)`. Off-regime axis → `Belief(is_bottom=True)`. |
| Certify constraint | `_certify_numeric` | `feasibility.py:51–90` | `->'sat'\|'violated'\|'straddle'`. INTERVAL: whole `[lo,hi]` must clear; ⊥ → straddle. |
| Query types | `Query`,`Constraint`,`Bundle`,`make_query` | `solver/query.py:22–49`, `substrate.py:80–86` | `Constraint(axis,op,value)`, `op∈{ge,le,...}` (also accepts `">="/"<="`). |
| VoI per axis | `voi_for_axis` | `solver/voi.py:130–197` | two-world minimax regret; closed form `δλ/(δ+λ)`. |
| Minimax | `_minimax_two_world` | `voi.py:95–127` | mixed-strategy game value. |
| Ranking | `voi_ranking` | `voi.py:200–218` | `->list[AxisVoI(axis,voi,acquisition_cost,voi_per_cost)]`, sorted by VoI/cost. |
| Acq-cost table | `ACQUISITION_COST` | `voi.py:68–77` | cost .05, latency/throughput .1, energy .15, memory_hw .2, quality .3, reviewer .8, governance 1.0. |
| Selective proc | `right_size` | `solver/procedure.py:57–83` | `->Recommendation(action: Action, committed_config, blocking_axes, voi_ranking)`; `Action.COMMIT/ABSTAIN/INFEASIBLE`. |
| Regimes | `regimes.py:16–54` | ladder ACCURACY_ONLY→ACC_COST→…→FULL; `in_regime(axis,regime)`. |
| Grounded thresholds | `observed_thresholds`, `generate_queries` | `analysis/decidability_map.py:129–234` | percentile thresholds (`_GRID_PCT=50`), `_NOMINAL=1.0` for ⊥ axes. |

## 3. Masked-validation harness + RouterBench + conformal pattern

| Concept | Real name | File:line | Notes |
|---|---|---|---|
| Harness | `MaskAndPredict` | `validation/harness.py:144–273` | `.run(rules, tau, bind_axes, masked_axis, queries=None)->SliceReport`; `score_rule()` computes HVR. |
| Read-level mask | `MaskedSubstrate` | `harness.py:74–98` | `cell(x,a)->[]` when `a==masked_axis`. |
| Slice restrict | `BenchmarkSubstrate` | `harness.py:38–71` | restrict RouterBench τ to one benchmark's 11 models. |
| Baselines | `validation/baselines.py:42–213` | B1AccuracyOnly, **B2ObservedPareto**, **B3Imputation** (global-median fill, :86–126), B4MissingAsFail, B5Oracle (`sees_masked=True`), B6CostAccuracy, SelectiveRule; `ALL_RULES`. |
| HVR | `RuleMetrics.hidden_violation_rate` | `harness.py:117–119` | `n_hidden_violation / n_commit`. |
| **Conformal pattern** | `gt_guarantee.py:105–401` | `Outcome`, `Calibration`, `split(seed=2024)` 50/50, `calibrate(calib,test,alpha,margins)`, `Outcome.decide(margin)`. **Mirror this for split-conformal intervals.** k_subsample=64, q_percentiles=(.40,.55,.70,.85), n_seeds=40, base_seed=7. |

**RouterBench table.**
- Raw: `data/routerbench_0shot.pkl` (95 MB pandas). Per-prompt cols: `{model}` (0/1 correct), `{model}|total_cost` (USD), `eval_name`.
- Parser: `substrate/routerbench/parser.py` `RouterBenchParser.parse(df)->list[RouterBenchConfig(model, benchmark, quality, cost, n_prompts)]`. `quality`=mean correctness **[0,1]**; `cost`=**mean USD per prompt** aggregated per (model,benchmark) — **per-prompt, not per-config** (OPEN UNKNOWN resolved). MMLU subtopics collapsed via `benchmark_group()`.
- Models: 11 (`substrate/routerbench/models.py:MODELS`). Config id `rb-{model}-{benchmark}`, obs confidence `"H"`.
- This (model × benchmark) quality matrix is the leave-one-benchmark-out input for Phase 0.

## 4. Frozen artifacts & figure convention

Convention: **seeded script → JSON artifact → figure** (`scripts/make_paper_figures.py`).
- `data/apt_substrate.db` (frozen substrate; **md5 `140231fefda2c06e0642a529dff611d9`**, never mutate).
- `outputs/p3/*.json` (prior/decidability map, binding annotations).
- `outputs/p4/coverage_risk_gt.json` (Fig 7 right; calibration+test), `general_voi.json`.
- `outputs/p5/validation_scaled.json` (hidden-violation slices), `multi_blocker.json` (2.0 vs 6.0), `masked_cost.json`, `masked_governance.json`.

## 5. VoI acquisition demo (Phase-2 target)

- `scripts/run_multi_blocker.py`: masks quality+cost, `_commit_at(sub, query, revealed)`, plan-rollout (follow VoI/cost, re-rank) vs random-rollout → `multi_blocker.json` (2.0 vs 6.0). This is the **simulated** loop Phase 2 closes for real.
- `scripts/run_acqcost_sensitivity.py`: perturbs `ACQUISITION_COST`, confirms count invariance.

## 6. Tests

- Command: `PYTHONNOUSERSITE=1 uv run pytest -q` → **79 passed**.
- C7 gates: `tests/test_invariance.py::test_interface_invariance` (call-multiset equality), `test_procedure.py`/`test_decidability.py` C7 read-only tests.
- New code must add tests and keep this green; a **transfer-OFF determinism test** must assert the decidability map is bit-identical to baseline when the transfer flag is OFF.

## 7. Resolved open unknowns
1. **Quality units** = [0,1] accuracy (≈0.35–0.87 observed). Interval width interpretable in accuracy points.
2. **φ external interval** = no hook; add `OverlayedSubstrate` (synthetic obs for ⊥ cells), wrap inside `CachedSubstrate`.
3. **RouterBench cost** = mean **per-prompt** USD, aggregated per (model,benchmark). Min-sufficiency in Phase 2 scores cost on this.
4. **Real names** filled above (`classify_query`, `right_size`, `voi_for_axis`, `aggregate`, `_certify_numeric`, `MaskAndPredict`, `gt_guarantee`).
