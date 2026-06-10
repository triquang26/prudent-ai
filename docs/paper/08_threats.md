# 8. Threats to Validity

We separate threats to the **measurement** (Claim C1: is the 91.1% real?), to the **validation**
(Claims C2/C3: is the mis-sizing real and the gap attributable?), and the explicit
**reviewer-attack/defence** ledger. Throughout, the design choices that bound each threat are
conservative — where a threat could only push a number in one direction, we report the direction
so the headline is read as a floor or a ceiling, never as a point estimate flattered by a choice.

## 8.1 Threats to the measurement (C1)

**Extraction bias.** The substrate is populated by semi-automatic extraction from leaderboards
and papers, and extraction is known to be lossy — automatic methods miss 59.7%/48.3%/88.6% of
GPU number/type/hours, AXCELL reaches F1 25.8 on (task, dataset, metric, value), and only 3/24
papers in one study were reproducible. We mitigate by (i) recording provenance and a confidence
tier on *every* observation (high/medium/low), (ii) admitting only H+M for claims, and (iii)
reporting inter-annotator agreement (κ) and an extraction error rate as a quality appendix. The
key robustness fact is that extraction error cannot manufacture the headline: the three
load-bearing blind-spot axes (`governance`, `reviewer_burden`, `memory_hw`) are ⊥ at miss-rate
**1.000** — extraction did not *fail* to find sparse evidence, there is *no* public evidence to
find, so no improvement in extraction recall changes the result.

**Query-distribution bias.** The decidability headline is conditional on a query mixture, and a
cherry-picked mixture could inflate underdetermination. We close this (open gate Q2) by deriving
the prior from **1716 real LLM-deployment case studies** (ZenML LLMOps database, frozen snapshot)
under a fully documented, auditable tag→axis taxonomy, rather than hand-building it. The result is
robust to the taxonomy — dropping any single tag→axis mapping leaves underdetermination ≥83.2%
(largest single effect: `human_in_the_loop`→`reviewer_burden`, −7.9%) — and *grounding sharpens
it* (85.7% on the uniform grid → 91.1% on real traffic), because real deployments load the
off-evidence axes more heavily than a uniform grid does. **The per-instance-binding caveat is
stated plainly:** a deployment tag is evidence that an axis is *declared a hard requirement*, a
conservative over-approximation of *binding at the optimum* (`bind(q)` = active-at-optimum). We
close Q2 at the *distribution* level, not the per-instance level; the deeper recovery of `bind(q)`
from the constraint bundle and observed Pareto structure is future work. The distribution-level
claim does not depend on resolving it, since the decisive off-evidence axes are ⊥ in every τ
regardless, and `throughput`/`energy` are deliberately left ⊥-able (never bound from a tag), which
can only *under*-state underdetermination.

**Hardware confounder.** Energy evidence comes overwhelmingly from ML.ENERGY, which is H100/vLLM
only, so the `energy` axis is hardware-specific. This does not affect the C1 headline (energy is
never the recovered binding axis on the decidable slice and the result plateaus before energy
enters the regime), but any future cross-hardware energy claim must control for the tier; we keep
metric name/direction/unit/dataset/split/hardware on every observation (C6) so a confounded
comparison is detectable rather than silent.

**Selection bias across sources.** The corpus mixes four source families (BFCL, MLPerf,
ML.ENERGY, HELM) sliced by *evidence-source* archetype, while ZenML is sliced by
*deployment-application* archetype, and we map application→source coarsely (first-match, default
general-qa). The archetype mismatch is real and *itself reported as a finding* — there is no clean
bijection between what people deploy and what evaluation sources measure — and the result is robust
to it only because the decisive off-evidence axes are ⊥ in *every* τ, so the coarse map cannot
manufacture or hide the headline. A finer alignment could shift the per-τ split without moving the
pooled number.

## 8.2 Threats to the validation (C2/C3)

**Leakage.** The validation slice's own measured values are used **only to score**, never to tune
any rule (C8). Masking is enforced at the read level by `MaskedSubstrate` — a masked axis returns
`[]` for every rule, the oracle (B5) being the sole `sees_masked=True` exception that defines the
regret floor — so no rule, baseline or selective, can peek at the hidden axis. There is no held-out
hyper-parameter fit to the slice; the procedure's knobs (φ, κ, regime, λ, margin) are fixed by
config before the slice is touched.

**Proxy ground truth.** "Truth" on the validation slice is the substrate's co-located H/M-confidence
measurements (BFCL is M-confidence), not an external held-out oracle, and the coverage guarantee in
§6 calibrates against a richer-κ proxy (κ_truth = H+M+L) rather than a labelled slice. We state this
as calibration on the richest evidence available, not as an independent oracle; real held-out
ground-truth calibration and live V3 runs (vLLM energy + a governance/burden human study) remain the
stretch.

**Masking is a simulation of missingness.** We *withhold* an axis we actually measured to model the
structural missingness C1 found in the wild. It is a faithful read-level simulation, not a
naturally-missing slice — which is exactly why V3 (real missing axes on local AI boxes) is the
honest next step rather than a closed result.

**Significance — the gating gap, stated as a threat to ourselves.** The C2 bite (1.0 vs 0.0 hidden
violation) and the C3 VoI lift (1.0 vs 0.2) are **categorical but on a single small slice (n=5,
M-confidence BFCL) with no significance test run**. We do not claim Oral-level significance: the
direction is decisive, the statistics are not yet computed. Per our Go/No-Go discipline this is a
**GO on the C2/C3 demonstration, HOLD on Oral significance**; closing it requires scaling the
battery, a significance test on hidden-violation-rate, and more biting slices (a per-benchmark
RouterBench restriction, on-prem/energy-bound slices). We name this gap rather than paper over it.

## 8.3 Reviewer-attack ledger (anticipated objections and defences)

1. **"Missing metrics is obvious."** The surprise is not that metrics are missing but that a
   community-standard rule **commits anyway and mis-sizes measurably** — B2/B3/B6 hidden-violate
   100% on the biting slice while the procedure abstains to 0%. The finding is at the *decision*
   level (% of decisions underdetermined), not the *data* level (% of cells missing).
2. **"'Undecidable' is overclaiming."** We do not use undecidability; we use **evidence-underdetermination
   / non-identifiability**, statistically anchored: a query is underdetermined iff a missing or
   straddling axis could flip the cost-minimizing argmin across completions (§3), with bootstrap CIs.
3. **"It's just chance-constrained optimization with a label."** The novelty is not the solver but
   the *decidability measurement* on a real-traffic prior, the **three-state** (not binary) outcome,
   and the **informative VoI abstention** over an evidential substrate — the optimization is
   deliberately textbook so the identifiability regime is the contribution.
4. **"Imputation solves it."** Refuted with a number: B3 (global-median imputation) hidden-violates
   **1.0 — identical to B2** — on the biting slice, because imputing a missing axis on *structured*
   missingness commits the same blind, infeasible config. Filling in the gap does not recover the
   decision; it hides the violation.
5. **"The guarantee is just ported selective classification."** The decided object is multi-constraint
   feasibility **and** minimum-sufficiency under missingness (harder than selective binary agreement),
   the guarantee is keyed to the **evidence regime** not sample size, and the abstention is
   **informative** (VoI names the field), none of which selective classification provides.
6. **"The limit theorem is trivial."** It is anchored, not asserted: the implemented VoI of an omitted
   binding axis equals the irreducible regret `VoI(a*) = Δ(R) = δλ/(δ+λ)` exactly on the two-world
   gadget (pinned to rel_tol 1e-9 over four (δ,λ) points), and the regime-ladder plateau is its
   empirical shadow on real traffic. If the theorem fails to be clean-and-nontrivial we drop the
   Pillar and retreat to the measurement-as-thesis venue — stated as an explicit honest flag.
7. **"HAL already did this."** HAL measures the agent *better* (cost-aware, 21,730 rollouts); we ask
   *when a deployment conclusion is valid on the evidence at all*. HAL is an evidence source, a model
   paper for the infrastructure framing, **and** the nearest threat — orthogonal, not subsumed.
8. **"No real deployment / governance and burden are never validated."** That absence *is* the C1
   finding: governance binds 55.6% and reviewer_burden 43.8% of real traffic yet are ⊥ corpus-wide,
   so a decision binding on them cannot be validated at all — the correct action is to abstain and name
   the axis. Validation runs only on the **4 measurable axes** where ground truth exists; the guarantee
   plus the empirical mis-sizing on that slice (V1/V2) carry the method claim, with V3 live runs as the
   stretch.

These defences are doctrine, not decoration: each maps to a number or a design constraint already
in the paper (the hidden-violation table for #1/#4, the bootstrap-CI decidability map for #2, the
`VoI = Δ(R)` test for #6), and where a defence is *not yet* fully discharged — significance (§8.2),
per-instance binding (§8.1), V3 (§8.2) — we mark it open rather than claim it closed.
