# Mock Review — APT (Evidence-Decidability of AI Deployment Right-Sizing)

> **Venue / bar:** ICLR, Oral track. **Reviewer stance:** Area-Chair-level, adversarial-but-fair.
> **Purpose:** harden the paper before submission, not flatter it. Every weakness below is scored
> for severity (Critical / Major / Minor) and paired with the authors' best available response and
> the evidence that would actually close it. Numbers are taken verbatim from the draft
> (`docs/paper/*.md`), the findings docs (P3/P4/P5), and the master plan §16/§18.

---

## 1. Summary of contributions

The paper studies one question the evaluation literature has left implicit: *given the evidence
that actually exists, is a deployment right-sizing decision identified at all?* It reframes
right-sizing from an **estimate-quality** problem (sharpen the belief about each axis) into an
**identifiability** problem (does the evidence determine the argmin-cost feasible configuration),
and delivers three coupled contributions:

- **C1 (measurement).** A three-state decidability map (decidable / underdetermined /
  infeasible-under-E) over `{archetype × evidence-regime × confidence}`. On a query prior derived
  from **1716 real LLM-deployment case studies** (ZenML LLMOps DB), **91.1%** of right-sizing
  queries (1563/1716) remain evidence-underdetermined at the FULL regime, **100%** under an
  accuracy-only (leaderboard) regime, with decidability topping out at **8.9%** and plateauing once
  cost+latency enter. The cause is characterized as *structured* missingness: three
  deployment-gating axes (`governance`, `reviewer_burden`, `memory_hw`) are ⊥ at miss-rate **1.000**
  corpus-wide, yet `governance` binds **55.6%** and `reviewer_burden` **43.8%** of real traffic.

- **C2 (validation).** A mask-and-predict falsification on co-located ground-truth slices: bind two
  axes, hide one binding axis, score each rule's commit against the hidden truth. Across **7 biting
  slices (119 queries)** the honest-practice baseline B2 (observed-Pareto) and its defences B3
  (imputation) and B6 (cost-accuracy) hidden-violate at a pooled **88.2%** while the selective
  procedure abstains and hidden-violates at **0%**. The gap **0.8824 [0.8235, 0.9412]** is
  significant against both must-beat baselines (McNemar **105/0**, one-sided exact-binomial
  **p ≈ 0**), and significant on every individual slice.

- **C3 (method).** A three-state selective right-sizing procedure that COMMITs the identified
  minimum-sufficient config, else ABSTAINs *informatively* — returning the blocking set and a
  cost-aware VoI-ranked acquisition plan — under a distribution-free coverage guarantee
  `P(feasible ∧ min-sufficient | commit) ≥ 1−α`. The acquisition is anchored to a limit theorem by
  an **exact** identity, `VoI(a*) = Δ(R) = δλ/(δ+λ)`, pinned to `rel_tol=1e-9` over four `(δ,λ)`
  points.

This is a genuinely well-constructed, honest, and internally disciplined paper. The reframe is
sharp, the C7 firewall is enforced (not merely asserted), and the threats section pre-empts most of
the obvious attacks. The question for an Oral is whether the *surprise* and the *necessity* are as
load-bearing as the framing promises. My read: this is a strong **Spotlight** as written, an Oral
only if one structural gap (the per-instance binding gap, below) is closed or convincingly bounded,
and one internal inconsistency between §1 and §7 is fixed.

---

## 2. Strengths (specific, with the real numbers)

1. **The reframe is the right kind of novel.** "Is the decision *identified* by the evidence" is a
   genuinely different axis from "is the per-axis estimate precise," and the paper makes it
   *measurable* rather than rhetorical. The decidability/underdetermination definition via
   completions (§3.5: ∃ e₁,e₂ ∈ Comp(E) with x*(q|e₁) ≠ x*(q|e₂)) is a clean, falsifiable construct,
   not a slogan. This clears the §18.1 "'undecidable' is overclaiming" attack — they never say
   undecidable; they say non-identifiable, statistically anchored.

2. **The measurement is surprising in the way an Oral needs.** It is not "% of cells missing" (which
   would be the boring §3 ❌ result). It is **% of *decisions* underdetermined = 91.1%**, with the
   degenerate-CI signature `[1.000, 1.000]` on the two archetypes lacking a measurable objective
   axis — that bracket is *not* bootstrap noise, it is the fingerprint of a structural gap, and the
   paper correctly reads it that way.

3. **The structuredness argument is strong and direction-aware.** Three axes ⊥ at miss-rate **1.000**
   across every source, no config spanning `quality ∧ cost ∧ energy`, and crucially the
   **grid→empirical Δ = +5.4%** (85.7% grid → 91.1% real): grounding the prior *sharpens* the result,
   which is the opposite of cherry-picking and largely defuses the query-distribution attack.

4. **C2 is genuinely the Oral pillar, and it now has statistics.** The pilot's fatal gap was a single
   n=5 slice with no test. The scaled battery clears exactly that: **7 biting slices, 119 queries**,
   pooled gap **0.8824 [0.82, 0.94]** excluding zero, **McNemar 105/0**, **p ≈ 0**, *every slice
   individually significant* (p ∈ [7.6e-06, 2.4e-04]). The per-benchmark RouterBench restriction was
   the right move — it removes the cross-benchmark cost confound and turns one corpus into six
   independent biting slices.

5. **The "imputation solves it" attack is refuted with a number, not a hand-wave.** B3 HVR is
   *identical to B2* on every slice (0.8824 pooled) — imputing the global median commits the same
   blind config. That is the sharpest single rebuttal in the paper.

6. **VoI = Δ(R) is proven exact, not asserted.** A passing parametrized test (`rel_tol=1e-9`, four
   `(δ,λ)` points) unifies the abstention machinery and the limit bound into one object. This is
   exactly the discipline that separates a "theorem-shaped gesture" from a contribution.

7. **Reproducibility and the C7 firewall are real.** The interface-invariance test (two solvers issue
   a byte-identical multiset of substrate calls) makes the substrate↔solver separation executable.
   Frozen, seeded artifacts throughout. This is above the bar for the venue.

---

## 3. Weaknesses and attacks (scored by severity)

I work through every §18.1 reviewer attack, mark which are adequately discharged, then add new ones.

### W1 — The per-instance binding gap (Open-Q2). **Severity: CRITICAL for Oral.**
This is the load-bearing weakness, and the authors know it (§5.9, §8.1). The entire C1 headline rests
on `bind(q)` — the axes *active at the optimum*. But the ZenML prior recovers only the *mentioned* /
*declared* axes from tags: a `regulatory_compliance` tag is taken to bind `governance`. The paper is
explicit that a tag is a **conservative over-approximation** of binding, "salient not binding." The
problem: **the 91.1% headline is computed on the over-approximation.** If a governance tag is salient
but *not* active at the optimum (the cheapest feasible config happens to satisfy it), that query is
*not* actually underdetermined by governance — it only looks so because the tag was counted as a bind.
Since `governance` (55.6%) and `reviewer_burden` (43.8%) are precisely the ⊥ axes driving the
headline, and precisely the axes most likely to be *declared but co-satisfied*, this gap can
mechanically inflate underdetermination.
- **How damaging:** directly attacks the headline number. An adversarial reviewer will say "91.1% is
  the underdetermination of *declared* constraints, and you have no evidence the declared constraints
  bind." The authors' own §7.5 no-bite control (`mask=latency`, cheap⇒fast ⇒ *not* a bite because the
  hidden axis is co-satisfied) proves this mechanism is real and material — declared ≠ binding is
  exactly what makes a slice not bite.
- **Authors' best response:** (i) the *structural* facts (which axes are ⊥, fragmentation,
  corpus-wide blind spots, §5.3) are distribution- and binding-independent and survive regardless;
  (ii) `throughput`/`energy` are deliberately *never* bound, which under-states; (iii) the attribution
  result — **72.4%** underdetermined because a binding axis is unmeasurable *corpus-wide*, **16.0%**
  blocked *only* by unmeasurable axes — is the part that does not depend on per-instance resolution,
  because those axes are ⊥ in *every* τ. **The fix:** demote the 91.1% from headline to "decidability
  of declared constraints," and *promote the 72.4%/16.0% attribution* (or better, a Pareto-recovered
  `bind(q)` lower bound) to the headline. That number is far more defensible and still extraordinary.
- **Evidence that closes it:** recover `bind(q)` first-class on a subsample — from the constraint
  bundle *and* the observed Pareto structure — and show the underdetermination fraction on
  *truly-binding* axes is still high. Even a few-hundred-query hand-audited subsample with IAA would
  largely close this. Without it, the Oral claim is one over-approximation deep.

### W2 — The §1↔§7 inconsistency: which C2 number is the headline? **Severity: MAJOR.**
§1 (Introduction, contribution 4) and §1 paragraph 5 report C2 as **hidden-violation 1.0 (5/5)** for
B2/B3/B6 and the VoI lift as **5/5 (1.0) vs 1/5 (0.2)** — i.e. the *pilot* BFCL n=5 numbers. But §7
(the evaluation pillar) reports the *scaled* battery: B2/B3/B6 pooled **0.8824**, gap **0.8824 [0.82,
0.94]**, McNemar 105/0, p ≈ 0. The abstract-level story (§1) is built on the weaker, single-slice
pilot, while the strong, significance-backed result lives in §7.
- **How damaging:** an Oral reviewer reads §1, sees "1.0 (5/5)," and concludes the validation is a
  toy. They may never reach the §7 scaled result; worse, the discrepancy reads as the intro not having
  been updated after the battery was scaled. It undersells the paper's single strongest result and
  invites a "n=5" dismissal that the work has actually already overcome.
- **Authors' best response:** none — this is just an editing debt. The §7 scaled numbers are strictly
  stronger and significance-backed.
- **Fix (this is the single most important thing to fix before submission, see §5):** rewrite §1's C2
  paragraph and contribution 4 to lead with the **7-slice, 119-query, pooled 0.8824 [0.82, 0.94],
  McNemar 105/0, p ≈ 0** result, with the BFCL pilot demoted to an illustrative instance. The VoI lift
  (5/5 vs 1/5) is *still* pilot-scale (n=5) and should be flagged as such in §1, not stated as if it
  were the headline.

### W3 — Single-corpus query prior (ZenML only). **Severity: MAJOR.**
The C8 "justified distribution" defence rests entirely on *one* corpus (ZenML LLMOps DB). MedHELM
returned HTTP 401 at snapshot time (§5.9). The whole 55.6%-governance load — the empirical heart of
C1 — is ZenML's industry/tag composition.
- **How damaging:** a reviewer can argue the governance load is an artifact of ZenML's selection
  (which case studies get written up and indexed). The drop-one-tag robustness (≥83.2%) controls for
  *tag-mapping* fragility but not for *corpus-selection* bias — a different deployment corpus could
  have a very different τ-mix.
- **Authors' best response:** the direction argument — a medical/high-governance corpus (MedHELM)
  would, if anything, *raise* the 55.6% governance load, so ZenML is conservative for the governance
  claim. And the structural facts (§5.3) are corpus-independent.
- **Evidence that closes it:** a second, independent deployment corpus (MedHELM once the 401 is
  resolved, or a second LLMOps index) showing the headline is stable across priors. One replication
  corpus would move this from Major to Minor.

### W4 — "Truth" is proxy, not real ground truth. **Severity: MAJOR.**
Two distinct proxy-truth uses, both honestly flagged but both real: (a) the coverage guarantee
calibrates against a *richer-κ proxy* (`κ_truth = H+M+L`), so the "0.0% committed risk" is risk
against the fuller-evidence procedure's *own verdict*, not a held-out oracle; (b) V1's "truth" is the
slice's own co-located H/M measurements (BFCL is *M-confidence*), an internal richest-evidence reading,
not external GT.
- **How damaging:** the guarantee `P(feasible ∧ min-sufficient | commit) ≥ 1−α` is the C3 selling
  point with a Trust-or-Escalate lineage, but "0% risk against my own richer self" is a weaker
  statement than Trust-or-Escalate's calibration against human agreement labels. A reviewer will note
  the guarantee is not yet validated against any independent oracle.
- **Authors' best response:** stated plainly (§6.5, §6.8, §8.2) as calibration on the richest evidence
  available; real held-out GT calibration is explicitly P5/V3 future work. The C2 *direction* (88%
  pooled HVR vs 0%) does not depend on the proxy — it is scored against the unmasked measured value,
  which is as close to GT as the corpus has.
- **Evidence that closes it:** the V3 live runs (vLLM + ML.ENERGY energy + a small governance/burden
  human study) the paper already names. Until then the guarantee should be framed as
  "self-consistency calibration," not "reliability guarantee," wherever the distinction matters.

### W5 — M-confidence BFCL drives the flagship slice. **Severity: MAJOR.**
The flagship BFCL biting slice is **M-confidence** (leaderboard/paper-reported), not measured. The
H-only κ-sweep (§5.4) *removes all decidability* (map → 1.000 underdetermined) because the decidable
function-calling cases rest entirely on M-tier cost/latency. So the one archetype that ever becomes
decidable does so on the *weakest* evidence tier.
- **How damaging:** a skeptic reads this two ways. Pro-paper: even the *only* decidable cases evaporate
  under strict evidence, strengthening C1. Anti-paper: the C2 bite on BFCL is computed on M-tier
  "truth," so the hidden-violation scoring inherits leaderboard noise. The RouterBench slices are
  H-confidence and carry the significance, which mitigates — but the *headline* BFCL slice is the soft
  one.
- **Authors' best response:** lead C2 with the **6 H-confidence RouterBench slices** (which already
  carry the pooled significance) and present BFCL as the harder/illustrative case, noting the H-only
  sweep *strengthens* C1 rather than weakening it.
- **Evidence that closes it:** report the pooled significance *restricted to the H-confidence RouterBench
  slices alone* (drop BFCL) — if it survives (it almost certainly does, 6/7 slices), the C2 claim no
  longer depends on any M-tier truth.

### W6 — Small-ish batteries (119 queries, 7 slices, 11 models, V2 n=5). **Severity: MAJOR.**
119 queries across 7 slices, with the RouterBench slices each only **11 models** and **17 queries**;
the V2 VoI-lift is **n=5 abstentions on one bind**. McNemar 105/0 is a strong *internal* signal, but
the discordant-pair count is driven by the structural all-or-nothing separation (commit-blind always
violates on the biting axis; abstain never does), so the test is in some sense measuring a designed
inevitability rather than a noisy effect.
- **How damaging:** an Oral reviewer expects either breadth (many independent settings) or a stress
  test that *could have failed*. The 0.71–1.00 per-slice HVR with selective always at 0.0 is so
  categorical that p ≈ 0 is unsurprising — the question becomes "is the *experiment* falsifiable," and
  the answer ("yes — the no-bite controls") is in §7.7 but easy to miss.
- **Authors' best response:** the no-bite controls (mask-latency, mixed-RouterBench confound) are
  genuine falsification opportunities the design *passed by failing to bite*; the result is categorical
  *because* structural missingness is categorical, which is the point of C1.
- **Evidence that closes it:** scale V2 across all 7 slices (currently a §7.7 stretch item) and add at
  least one energy-bound / on-prem slice where the binding axis is `energy` rather than `quality`, to
  show the bite is not quality-specific.

### W7 — The theorem is gadget-level; §8.6 closure is open. **Severity: MAJOR (for the ICLR-Oral "necessity" pillar).**
The "limit theorem" is the ICLR pillar (master plan §11, §17.2). What is actually *proven exact* is
`VoI(a*) = Δ(R)` on a **two-candidate, two-world gadget** (`x_cheap` cost 1, `x_safe` cost 1+δ). The
general necessity statement — "no R-restricted rule achieves expected regret below Δ(R) on the class
Q_R(a*)" — and the closure characterization `decidable ⇔ bind(q) ⊆ cl(R)` (§8.6) are, per the draft,
*empirically confirmed* (the regime-ladder plateau) but the §8.6 closure is flagged **open**.
- **How damaging:** for an *Oral at ICLR*, the master plan itself (§18.1, §11 honest flag) says: if the
  theorem is not clean-and-nontrivial, **drop the pillar and retreat to NeurIPS-ED**. A gadget identity
  + empirical shadow is closer to "well-motivated heuristic anchored to a toy bound" than to a theorem
  carrying the necessity claim. A theory-minded AC will press exactly here: is Δ(R) > 0 a *theorem*
  about a query class, or an *identity* on a 2-point construction generalized by analogy?
- **Authors' best response:** the exact identity is more than most applied papers carry, and the paper
  is *scrupulously honest* — it calls the regime-ladder an "empirical shadow," never a corollary (§8.8
  discipline), and it explicitly reserves the retreat-to-NeurIPS-ED option. The contribution stands as
  C1+C2 even if the theorem is downgraded.
- **Evidence that closes it:** a clean proof of the general lower bound (indistinguishability /
  two-world argument lifted off the gadget to the query class Q_R) and a proof — not an empirical read
  — of the §8.6 closure. Absent that, the paper should *not* foreground "limit theorem" in the
  abstract; it should foreground the measurement (C1) and the validated falsification (C2), with
  VoI=Δ(R) as a clean anchoring identity rather than a necessity theorem.

### W8 — RouterBench benchmark cherry-pick risk. **Severity: MINOR-to-MAJOR.**
The per-benchmark restriction is the right experiment, but it also *selects* the slices where the
global cost-minimizer picks the weakest model. The mixed-benchmark slice is reported as "ill-posed"
(§7.7.5). A reviewer could read this as: the experiment was constructed precisely on the restriction
that makes the bite appear, and the un-restricted slice (which does *not* bite cleanly) is set aside.
- **How damaging:** moderate. It is defensible (the mixed slice is genuinely ill-posed for right-sizing
  — cost varies by benchmark, not model), but the framing "we found 6 new biting slices" can read as
  "we found 6 slicings under which it bites."
- **Authors' best response:** the restriction is *principled and stated a priori* (hold the task fixed
  so models are cost-comparable), not data-snooped, and all 6 benchmarks bite (HVR 0.71–1.00) — it is
  not a cherry-pick among slicings, it is the *only* well-posed slicing.
- **Evidence that closes it:** show the bite holds across *all* benchmark-fixed slicings present in
  RouterBench (it appears to — all 6 reported), and report the per-slice spread (0.71–1.00) prominently
  so the reader sees it is not one lucky benchmark.

### W9 — Mask-and-predict as a simulation of missingness. **Severity: MAJOR.**
The entire C2 validation withholds an axis the authors *actually measured* to simulate the structural
missingness C1 found in the wild. It is read-level faithful (`MaskedSubstrate` returns `[]`, oracle is
the sole `sees_masked=True` path), but it is a *simulation*: no naturally-missing slice is ever
decided.
- **How damaging:** the §18.1 "no real deployment" attack lands partially here. C1 says the wild
  missingness is on `governance`/`reviewer_burden` — axes that are ⊥ *everywhere* and therefore can
  *never* be unmasked or scored. So C2 necessarily validates on the *measurable* axes (`quality`,
  masked), which are exactly the axes that are *not* the structural blind spots. There is a logical gap
  between "the blind spots are governance/burden (C1)" and "we prove mis-sizing by masking quality
  (C2)" — the validation cannot touch the axes the diagnosis is about.
- **Authors' best response:** §8.3#8 — the *absence* of governance/burden evidence *is* the C1 finding;
  validation necessarily runs on the 4 measurable axes where any GT exists; the masking models the
  *mechanism* (a binding axis is hidden ⇒ blind commit mis-sizes) on the axes where it can be checked,
  and the mechanism is axis-agnostic. The guarantee + the masked-axis mis-sizing carry the method
  claim; V3 is the honest next step.
- **Evidence that closes it:** the V3 governance/reviewer-burden human study (even small) — to show the
  mechanism on a *naturally* missing axis, not a withheld measurable one. Until then, the paper should
  state crisply that C2 demonstrates the *mechanism* on measurable axes and *transfers* to the blind
  spots by the structural argument, not by direct measurement.

### W10 — DV2 (regret) is degenerate; the claim rides on DV3 alone. **Severity: MINOR.**
On the biting slices `mean_regret = 0.0` across the board because a blind commit contributes a
hidden-violation, not a feasible-overshoot sample. So of the two C2 dependent variables, only DV3
carries weight; DV4/DV5 are pilot or low-coverage.
- **How damaging:** minor but worth pre-empting — the master plan's "claim cứng" (§14) wanted
  `regret(proc) < regret(B2)` *and* the hidden-violation gap. The regret leg is vacuous here.
- **Authors' response:** §7.7.3 explains it (regret-over-feasible degenerate when violations dominate),
  which is correct; just make sure §1 does not imply a regret win that the data does not show.

### W11 (new) — Coverage is fixed at ~9-10%, so the method's *positive* action is rarely exercised.
**Severity: MAJOR.**
The procedure COMMITs on only **8.9%** of real traffic and the guarantee holds at **~10.5%** coverage
(α∈{0.05,0.10}, margin 0). On the biting slices it commits **0%**. So across the entire paper, the
"COMMIT the identified minimum-sufficient config" branch is exercised on a tiny minority, and *never*
on the validation slices. The paper is overwhelmingly a paper about *when to abstain*.
- **How damaging:** a reviewer can ask "is the COMMIT branch ever shown to be *correct* on an
  independent slice?" The 0%-coverage-on-biting-slices means the procedure's value-add over B4
  (missing-as-fail, which also abstains and also has 0 violations) is *only* the informative VoI
  ranking — and that is the n=5 V2 result. B4 gets 0 hidden-violations *for free*; the entire delta
  over B4 is the informative abstention, which is the least-validated component.
- **Authors' best response:** the delta over B4 is real and is the whole C3 point (B4 abstains
  *mutely*; the procedure abstains *informatively* and the VoI pick converts abstention→correct commit
  5/5 vs 1/5). But this needs to be said *loudly* — right now B4 quietly matches the procedure on DV3,
  and a sharp reviewer will notice.
- **Evidence that closes it:** (i) a slice where the procedure COMMITs *and is correct* against
  independent GT (currently absent — every biting slice has 0% commit); (ii) the scaled V2 to make the
  "informative > mute" delta significant, not n=5.

### W12 (new) — "HAL already did this" / orthogonality is asserted, not stress-tested.
**Severity: MINOR.**
HAL (21,730 rollouts, ~$40k) is positioned as evidence source + threat + model paper. The paper says
HAL improves the *estimate* while APT asks *when a conclusion is valid on the evidence*. True — but
HAL is *not ingested* into the substrate (the corpus is BFCL/MLPerf/ML.ENERGY/HELM/RouterBench). A
reviewer may ask: if you ingested HAL's per-cell accuracy+cost+tokens, would your decidability map
change materially? The orthogonality claim would be stronger if HAL evidence were *in* the substrate
and the headline survived.
- **Authors' response:** HAL still has zero `governance`/`reviewer_burden`/`memory_hw` evidence, so the
  ⊥-driven headline (72.4% on unmeasurable axes) is unaffected by adding HAL. State this explicitly.

---

### §18.1 attack ledger — disposition summary

| §18.1 attack | Status in this draft | Residual severity |
|---|---|---|
| "Missing metrics is obvious" | Discharged — C2 is decision-level mis-sizing, not cell-level missingness | Minor |
| "'Undecidable' overclaiming" | Discharged — non-identifiability + bootstrap CIs | Resolved |
| "Just chance-constrained opt with a label" | Mostly discharged — 3-state + VoI + measurement is the contribution | Minor |
| "Imputation solves it" | **Strongly discharged** — B3 HVR ≡ B2 (0.8824) | Resolved |
| "Guarantee = ported selective classification" | Discharged — multi-constraint object, evidence-regime-indexed, informative abstention | Minor |
| "Limit theorem trivial" | **Partially open** — exact only on gadget; §8.6 closure open (W7) | Major |
| "HAL already did this" | Discharged by argument, not stress-tested (W12) | Minor |
| "No real deployment" | Partially open — proxy-truth + simulated missingness (W4, W9) | Major |
| "Governance/burden never validated" | Reframed as *the* C1 finding — but C2 can't touch them (W9) | Major |

---

## 4. Scores

| Dimension | Score | Justification |
|---|---|---|
| **Novelty** | **8/10** | The identifiability reframe and the decidability map are a genuinely new axis; VoI=Δ(R) is a clean unifying identity. Capped below 9 because the optimization is (deliberately) textbook and the "limit theorem" is gadget-level, so the *theoretical* novelty is anchoring-identity-grade, not theorem-grade. |
| **Soundness** | **7/10** | Methodologically careful, C7 firewall enforced, significance properly computed, threats unusually honest. Capped at 7 by: the per-instance binding gap (W1) sitting *under* the headline; proxy-truth (W4); the §1↔§7 number inconsistency (W2); and the open §8.6 closure (W7). |
| **Significance** | **8/10** | If the reframe holds, it reshapes how the field reasons about deployment evidence — "the decision isn't identified" is a different and more actionable failure mode than "the estimate is noisy." Capped by W1 (the magnitude rides on declared-not-binding constraints) and W11 (the positive COMMIT branch is barely exercised). |
| **Clarity** | **8/10** | Exceptionally well-organized, honest, and self-aware; the threats ledger is a model. Docked for the §1↔§7 inconsistency (an alert reader will trip on it) and for burying the strongest C2 numbers behind the weaker pilot numbers in the intro. |

---

## 5. Recommendation

**Spotlight** (leaning Oral-if-revised), **conditional on closing W1 and fixing W2.**

**Honest justification.** The master-plan Oral bar (§3, §18.2) is the intersection of *sharp reframe ×
surprising measurement × validation beating the baseline (× theorem + guarantee)*. This paper clears
the first three convincingly: the reframe is sharp, 91.1%/100% is surprising, and C2 beats B2 *and* B3
*with significance* across 7 slices (the §18.2 gate is met — "beat B2/B3 with significance across the
battery"). What keeps it from a clean Oral *as written* are two things. (1) The fourth Oral leg — the
**limit theorem** — is gadget-level with an open closure (W7); by the authors' *own* §11/§18.1 honest
flag, that argues for the NeurIPS-ED framing rather than an ICLR-Oral theorem claim, OR for
foregrounding C1+C2 and demoting the theorem to a clean anchoring identity. (2) The headline magnitude
rides on an *over-approximation* of binding (W1): 91.1% is the underdetermination of *declared*
constraints, and the paper's own no-bite control proves declared ≠ binding is material. Promote the
binding-independent attribution numbers (72.4% / 16.0%) and the structural facts to the headline, and
the claim becomes Oral-robust; leave 91.1% as the headline and a hostile reviewer sinks it in one move.

If W1 is closed (a Pareto-recovered or hand-audited `bind(q)` lower bound that keeps underdetermination
high on *truly-binding* axes) and W2 is fixed, I would raise this to **Oral**. As it stands it is a
strong **Spotlight**.

**The single most important thing to fix before submission:** **resolve W2 — make the Introduction and
Contribution 4 lead with the scaled C2 result (7 slices, 119 queries, pooled hidden-violation gap
0.8824 [0.8235, 0.9412], McNemar 105/0, one-sided exact-binomial p ≈ 0, every slice individually
significant), not the n=5 BFCL pilot numbers (1.0, 5/5) currently in §1.** The strongest, most
defensible, significance-backed result in the paper is buried in §7 while the abstract-facing §1 still
tells the pilot story — this both undersells the work and invites an unwarranted "n=5 toy" dismissal of
the very result that meets the Oral significance gate.

---

## 6. Required-before-Oral / Recommended-before-submission

- **[Required, Oral]** Close or bound W1: recover a `bind(q)` lower bound (Pareto-structure or audited
  subsample + IAA) and re-report underdetermination on truly-binding axes; or demote 91.1% to "declared
  constraints" and headline the 72.4%/16.0% attribution.
- **[Required, submission]** Fix W2: rewrite §1 C2 paragraph + Contribution 4 to the scaled numbers.
- **[Strongly recommended]** W5/W8: report pooled C2 significance restricted to the 6 H-confidence
  RouterBench slices (drop M-confidence BFCL) — shows the claim does not depend on M-tier truth.
- **[Strongly recommended]** W7: either prove the general lower bound + §8.6 closure, or stop calling it
  a "limit theorem" in the abstract and frame VoI=Δ(R) as an anchoring identity; decide the
  ICLR-vs-NeurIPS-ED venue per the §18.2 honest flag.
- **[Recommended]** W11: add one slice where the procedure COMMITs and is independently correct, and
  scale V2 so the informative-abstention delta over B4 (mute abstain) is significant, not n=5.
- **[Recommended]** W3: a second deployment corpus (MedHELM once the 401 clears) to show prior-stability.

---

## Bottom line

- **Overall recommendation:** **Spotlight** (Oral-if-revised: close W1, fix W2, settle the theorem/venue question of W7).
- **Top-3 weaknesses:**
  1. **W1 — the per-instance binding gap (CRITICAL).** The 91.1% headline is computed on *declared* (salient) constraints, a conservative over-approximation of *binding* axes; the paper's own mask-latency no-bite control proves declared ≠ binding is material. Promote the binding-independent attribution (72.4%/16.0%) or recover `bind(q)`.
  2. **W2 — §1↔§7 inconsistency (MAJOR; highest-priority fix).** The Introduction leads with the n=5 BFCL pilot numbers (1.0, 5/5) while the strong significance-backed result (7 slices, 119 queries, gap 0.8824 [0.82,0.94], McNemar 105/0, p≈0) lives only in §7 — undersells the work and invites a "n=5 toy" dismissal.
  3. **W7 — the limit theorem is gadget-level, §8.6 closure open (MAJOR for the ICLR-Oral necessity pillar).** VoI=Δ(R) is proven *exact only on a two-world gadget*; the general necessity statement and the `decidable ⇔ bind(q) ⊆ cl(R)` closure are empirically-shadowed, not proven. By the authors' own §11/§18.1 flag this argues for downgrading the theorem claim (or retreating to NeurIPS-ED) rather than asserting an Oral-grade theorem.
