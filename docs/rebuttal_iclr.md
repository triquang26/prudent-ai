# Author response — draft (review rating 6, confidence 4)

We thank the reviewer for an unusually careful review; the three requested
analyses (masked-cost validation, verdict-sensitivity ablation, multi-blocker
scoring of the VoI ranking) have all been run and are now in the paper
(new Appendix G; pointers from §5, §7.2, §7.3, §8). No published number changed.

## W2 / Q4 — masked-COST validation (the §5↔§7 bridge)

We ran the identical battery (30 RouterBench per-benchmark slices, 510
decisions, matched percentiles) binding quality **and** cost and hiding
**cost** — the map's most frequent blocker (1,289/1,716 queries). Result:

- **Observed-Pareto, imputation, and the cost–quality frontier degenerate to
  coverage 0 on every query**: their objective is unobservable, there is
  nothing left to rank by. This is the map's prediction realized — when the
  objective axis is ⊥, current practice does not silently violate, it cannot
  produce an answer at all (and a constant median fill cannot rank, so
  imputation degenerates identically).
- The de-facto fallback — accuracy-only leaderboard ranking — commits
  everywhere and **hidden-violates the budget cap on 88.4%** of commitments
  (slice-clustered 95% CI [79.2, 96.1]).
- The selective procedure abstains and names cost on 510/510; measuring it
  closes full coverage at **zero violations, 510/510 minimum-sufficient**
  (paired vs. fallback: 451 disagreements, all favoring the pipeline).

So the bridge holds in both failure modes the map distinguishes: hiding a
*constraint* axis produces silent violations (57.1%); hiding the *objective*
produces degeneracy-or-worse (0 coverage, or 88.4% violations under the
fallback). Both are repaired by the same named measurement.

## W4 / Q1 / Q2 — verdict sensitivity (ties and thresholds)

Re-running the full 1,716-query FULL-regime map: the underdetermination count
is **bit-identical (1,563/1,716 = 91.1%)** under every threshold-grounding
percentile in {p25, p40, p50, p60, p75} and under a relative cost-tie
tolerance ε ∈ {0, 0.01, 0.05, 0.10, 0.20} (a rival flips the argmin only when
it undercuts the best sure option by more than ε; ε=0 cross-checks
bit-identical against the published classifier on all 1,716 queries). The
verdict is driven by which axes carry evidence at all — consistent with 72.4%
of queries being blocked by a corpus-wide-⊥ axis — not by threshold placement
or tie-breaking. (Direct answer to Q1: there is no ε below which the headline
moves, up to 20% relative.)

## W3 / Q5 — multi-blocker scoring of the VoI ordering

We constructed the setting the reviewer suggests: hide quality **and** cost
simultaneously on the same 510 decisions. The blocking set is {quality, cost}
on 510/510, and a necessity ablation confirms **neither measurement alone
resolves any query**. Following the procedure's ranked plan (re-ranked after
each reveal) resolves every query in **2.0 measurements at cumulative
acquisition cost 0.35** (the plan names cost first on 510/510, as VoI-per-cost
implies); revealing uniformly random axes until commitment needs **6.0
measurements at cost 2.06** on average. Every plan-final commitment is
feasible and minimum-sufficient (510/510). The ordering now has an empirical
score, not only the closed-form identity.

## W1 / Q3 — declared vs. binding governance

Two answers. (i) The anecdotal evidence requested: a conservative keyword scan
of the 954 governance-tagged case studies finds **72 (7.5%) with explicit
candidate-discriminating governance language** — e.g., a legal-tech deployment
whose client data "cannot sit on third-party" infrastructure; a finance
deployment routing all LLM traffic through a self-hosted proxy for "full data
sovereignty"; a pharma deployment selecting self-hosted open-source models for
regulatory reasons. This is a floor (paraphrases escape keyword patterns).
(ii) We agree the 91.1% conflates "evidence is silent" with "the silence
matters" *for the never-measured axes specifically*, and the paper now says so
more sharply; we note the conflation is bounded by the binding-independent
attribution (72.4% blocked by a ⊥ axis, with cost — a measurable axis — the
single most frequent blocker) and by the negative-control prior (12.4%).
Whether declared governance binds at each optimum is unverifiable precisely
because the axis is unmeasured — which is the paper's point, now stated as
such rather than implied.

## W5 — governance as a category error

We agree in part and have reframed the prescription (§8): some axes may be
inherently deployer-side measurements; the claim is not that leaderboards
should measure governance, but that decision rules should *know they have
not* and return the measurement to the deployer. This strengthens rather than
weakens the selective framing.

## Q6 — primary inference

Agreed; the slice-clustered bootstrap CI now carries the claim throughout
(abstract, Fig. 1, §7.2, Table 1), with the paired exact test reported
descriptively at equal final coverage.

## W6 — external validity of the prior

Acknowledged as a limitation; the adversarial governance-light prior (95.7%)
and uniform prior (98.5%) bound the re-weighting risk, and a second
independent deployment corpus is the natural next step.

---

# Author response — round 2 (rating 6, confidence 4)

## W1 / Q3 — declared vs binding, correlated overcounting

We ran both variants the review implies, through the identical classification
path. Deleting the governance AND reviewer-burden mappings **simultaneously**
(tags and the industry rule — the correlated-overcounting test single deletions
cannot perform) leaves **75.1%** of the 1,716 decisions underdetermined.
Restricting governance to bind only on the 73 case studies whose text contains
explicit candidate-excluding language (the keyword floor) leaves **87.3%**;
both restrictions together leave **75.9%**. Under the most skeptical reading
the taxonomy admits, three quarters of decisions remain underdetermined, and
the modal blocker is **cost — a measurable axis** whose evidence is absent
from most candidate pools. The 91.1% headline is an upper reading of a
quantity whose skeptical floor is ~75%; both numbers are now in the paper
(Section 5 robustness (vii); Appendix G).

## W4 / Q2 — learned imputation

We ran the strongest learned imputer the setting supports: leave-one-benchmark-
out per-model mean quality, under a per-slice mask that keeps cross-benchmark
cells visible to the imputer (the realistic reading). It cuts the pooled
hidden-violation rate roughly in half — 53.3% to **30.6%** (clustered CI
[12.9, 30.4]; paired McNemar 171/8 vs. the median fill) — while its coverage
drops to 0.70. Learning helps but does not repair blind commitment: a third of
its commitments still silently violate, **with no signal distinguishing
which**, and on the never-measured axes there is no cross-context signal to
learn from. The claim in the paper is now stated exactly this way.

## W3 — wins by construction

Agreed, and restructured: the two-blocker plan scoring (2.0 measurements /
0.35 acquisition cost vs. 6.0 / 2.06 unplanned, necessity-ablated) is now the
primary acquisition result in Section 7.3; the single-blocker 527/527 is
explicitly labeled a near-tautological end-to-end sanity check; the identity
figure is described as an implementation check, not evidence.

## W5 — p-values and "prove"

Done: the abstract states the theorem scope ("on a minimal two-world family");
p-values are removed from the abstract, Figure 1, and Table 1; the slice-
clustered CI is the primary inference throughout, with the McNemar count kept
as a descriptive quantity.

## W2 — framing discipline

The abstract now scopes the harm sentence ("costly on the axes where ground
truth lets us measure it"), and the introduction states explicitly that on the
blind-spot axes this validation is impossible — which is the finding.

## W6 / Q4 — prescription

Appendix G now specifies units and publishers: a governance observation as an
audit outcome per (configuration, jurisdiction); reviewer burden as
human-minutes per output from a pilot; published to compliance registries
(model-card / conformity-documentation style) rather than leaderboards. We
agree this shifts part of the prescription deployer-side; the decision-layer
contribution (rules that know what has not been measured and price the next
measurement) is unchanged.

## Q1 — thresholds

Constraint values are grounded at corpus percentiles because deployment texts
rarely state numeric targets; the verdict is bit-identical from p25 to p75 and
under cost-tie tolerances to 20% (Appendix G), so no threshold choice carries
the headline.

---

# Author response — round 3 (rating 6, confidence 4)

This round was almost entirely framing, and the reviewer was right: the paper
claimed more, and more loudly, than its honest core supports. We have rebalanced
rather than added apparatus. No published number changed; one new robustness
experiment (whole-industry deletion) was run for W7.

## W1 / W3 / W8 — headline reads like a constant; lead with the floor; statistics-saturated

We agree and have rewritten the abstract, the introduction, and the §5 headline
to **lead with scope** ("given this corpus and this requirement taxonomy") and to
present the result as a **range whose load-bearing end is the ~75% floor** resting
on cost — a measurable axis — rather than 91.1% as a number of record. The abstract
now carries ~4 statistics (1,716; 91.1%; 75.1%; and the calibrated-margin pair),
with secondary numbers moved to the body. The §5 headline opens "The number below
is a property of *this* corpus read under *this* taxonomy, not a constant of
deployment in general."

## W4 — "provable value of refusal" oversells the theory

Agreed. The theorem and the VoI identity are now described throughout as an
**anchoring identity on a minimal two-world family, verified to machine precision,
not a general guarantee**. Contribution 4 is retitled "a selective procedure whose
refusal is *informative*," and foregrounds the two-blocker acquisition result (2.0
vs 6.0 measurements) ahead of the identity.

## W5 — some results near-tautological; foreground the two-blocker setting

Already promoted in round 2 and now leads §7.3; the single-blocker 527/527 is
labeled a near-tautological sanity check and its redundant re-statement was cut.

## W6 — practical payoff modest; this is a diagnosis, not a deployed tool

Agreed, and this is the round's most consequential change. The paper now positions
the contribution explicitly as **"a diagnosis of the evaluation ecosystem and a
decision discipline that prices the next measurement, rather than a deployed
right-sizing tool"** (end of the contributions list, and the conclusion). The
formal machinery is correspondingly de-emphasized relative to the empirical
diagnosis.

## W2 — the two empirical halves describe different axes (central evidentiary gap)

We cannot close this with data — there is no governance ground truth, which is the
finding — so we close it by **discipline**. A new paragraph in §7.2 ("What links
the two halves") states that the connective tissue is the binding mechanism
(Proposition 1), **not a shared number**: an unmeasured binding axis both renders a
query underdetermined (the map, over all axes) and, where measurable, makes blind
commitment violate (the validation). We therefore **explicitly disclaim** that the
57.1% transfers to governance; it is the measurable-axis instantiation of a
corpus-wide failure mode, and the governance claim stays one of decidability.

## W7 — external validity of the prior; corpus selection bias not addressed

We separate the concern into three layers and address what is addressable. (a)
*Query re-weighting* — bounded by the uniform (98.5%) and adversarial (95.7%)
priors. (b) *Composition* — a **new experiment** (E5) deletes whole industries
from the corpus and re-runs the identical classifier: removing all five regulated
industries (the governance drivers) leaves **88.8%** underdetermined; removing the
dominant Tech majority leaves **96.8%**; the per-industry headline ranges 86–100%
and every leave-one-industry-out complement stays ≥90%, with **cost the modal
blocker in every partition**. So the headline is not an artifact of which
deployments are indexed. (c) *Publication self-selection* — only companies that
publish a case study appear — is addressed by neither (a) nor (b) and **cannot be**
without a second independently-collected deployment corpus, which does not exist on
hand (MedHELM, the one candidate, was access-gated and entered only as an evidence
source). We now state (c) as **the key external-validity limitation**, noting the
likely bias direction favors the finding (published deployers are plausibly *more*
governance-aware). New robustness item §5(viii); detail in Appendix G; limitation
in §8.

---

# Author response — round 4 (rating 6, lean accept; Soundness 3/4, Presentation 2/4)

We thank the reviewer for the sharpest review in the cycle. It asked for real
experiments, not only framing; we ran four. **No published number changed; the
frozen substrate was never mutated.**

## W3 / Q1 — separate cheaply-fixable cost from structurally-unmeasured (recommendation a)

We decompose the 1,563 underdetermined decisions by their complete blocking set and
ask what survives **granting cost as determined** (E6, new script). On the published
headline, only **8.9%** are cost-only (resolved by granting cost); **82.2%** remain
underdetermined with a non-cost blocker — **72.4%** on a never-measured axis (the
structural core), 9.8% on another co-located measurable axis. So the headline is
overwhelmingly structural, **not** a cost-co-location artifact. The reviewer's
intuition is correct only for the **skeptical floor**: on the joint-drop prior,
granting cost resolves **38.2%** and the residual structural share is just 1.2%. We
now (i) state this decomposition in the §5 accounting, (ii) treat 75.1% explicitly
as a maximally-skeptical bound and the structural 91.1%/72.4% as load-bearing, and
(iii) answer Q3: the floor is **bit-identical at 75.1%** across cost-grounding
percentiles p25–p75 (E8), so it is not a cost-threshold artifact either.

## W7 / Q4 — add a Bayesian / expected-regret baseline (recommendation c)

We added B7 (E7, new script): a per-model Normal posterior over the masked axis,
committing the config that minimizes expected feasibility-weighted regret (closed-form
Normal CDF, λ-swept). On the masked-quality battery it drives the hidden-violation
rate to **4.7%** — but **only by over-provisioning**: minimum-sufficient on **0%** of
decisions, mean **70× the cheapest-sufficient cost** (identical at λ=1 and λ=4). A
Bayesian prior converts feasibility violations into gross cost overshoot; it does not
recover the cheapest-sufficient configuration (the right-sizing target), and on the
never-measured axes the posterior collapses to the prior because no cross-context
signal exists. Added to §7.2 and Appendix G. This strengthens, not weakens, the
never-impute claim: even the strongest probabilistic competitor cannot right-size.

## W1 / Q2 — definition vs. measurement (the headline as near-tautology)

Agreed and stated explicitly (§5): the decidability definition supplies the rigor
(every rate a certified lower bound), but the empirical content is the measured
*mismatch* — 44–56% requirement rates on axes reported by zero sources — not the
definition, which would be vacuous absent that gap. The contribution is the
measurement, not the formalism.

## W5 — theory is decorative relative to its prominence (recommendation b)

Done. Figure 5 is retitled "**Correctness anchors (implementation checks, not
results)**"; §3 now calls the machine-precision VoI match "a correctness check on the
implementation, not a finding about the query distribution." (Round 3 already
softened "provable value"; this finishes it.)

## W6 — the validation comparison is favorable by construction

Stated plainly (§7.2): the equal-coverage win is *measure-versus-guess* by
construction — the pipeline acquires the hidden truth the baselines are denied, so
the McNemar 272/0 is near-definitional; the non-trivial claim is that the procedure
**knows when** it must measure and prices it.

## Q5 — the plan ordering depends on the assumed acquisition-cost table

Empirically it does not (E9, new script). Across perturbations — cost×5, cost×20
(dearer than quality), quality cheap, all-equal, per-axis random ×[0.5,2] — the plan
resolves in **2.0** measurements vs 6.0 random, names cost first on **100%**, and
stays feasible + minimum-sufficient on **100%**. Both genuine blockers must be
revealed to commit, so the count is structural; cost is named first because its VoI
dominates, surviving a 40× swing in the table. Appendix G.

## W2 — two halves connect by mechanism, not empirically (re-affirmed)

Unchanged from round 3 and we keep it honest: the link is Proposition 1, not a shared
number; we explicitly disclaim that 57.1% transfers to governance.

## W4 / W8 — presentation (Presentation 2/4 → aimed at 3/4, recommendation d)

The abstract is rewritten into shorter sentences with far fewer inline parentheticals
(same length, one paragraph), and the headline **scoping** is now legible in the
abstract and §5 without reconstruction from the appendix. Main text held at exactly
9 pages, 0 overfull.

---

# Author response — round 5 (Weak Accept / Accept, lean accept)

We thank the reviewer; the Strengths section already credits the round-4 work
(Bayesian 70× over-provisioning, the ~75% floor cleanly separated from the headline,
whole-industry deletion, the two-world VoI anchor). The residual weaknesses are
honest limitations we disclose (proxy-axis harm validation; single corpus) or items
already addressed (VoI = implementation check → "Correctness anchors"). We answer the
three concrete questions with new analysis, all in appendices; **no published number
changed, frozen substrate never mutated.**

## Q1 — a fully governance-agnostic headline (cost + co-location only)

Reported (new). A prior that binds **only measurable axes** — no governance, reviewer
burden, memory/hw, energy, or throughput able to bind at all — still leaves **75.1%**
of decisions underdetermined, by construction entirely cost and measurable
co-location; granting cost on top still leaves **36.5%** from co-location alone. So
even the most skeptical, fully-governance-agnostic reading keeps three quarters of
decisions underdetermined. Stated in §5 and Appendix G (cost-vs-structural
decomposition).

## Q2 — structural decomposition × strict-binding (jointly)

Reported (new). Running the cost-vs-structural decomposition on the **strict_joint**
variant (governance restricted to the 73 keyword-explicit cases **and** reviewer
burden dropped): 75.9% underdetermined, of which only **5.3%** is structural (that
keyword-explicit governance) and the remainder is cost + co-location — consistent with
Q1 and with the 87.3%/75.9% strict-binding figures. Appendix G.

## Q3 — graded bite (beyond the binary no-bite control)

New experiment (`run_graded_bite.py`, Appendix G + Figure 7). Per slice we score a
continuous **trade-off strength** = Spearman correlation between a config's true cost
and quality (positive ⇒ cheaper configs are lower-quality ⇒ committing the cheapest
tends to violate). The blind-commit violation rate rises smoothly with it
(across-slice Spearman **0.63**): weak tercile **29.4%** → mid 48.2% → strong
**82.3%**. Complementarily, violation rate vs the quality-constraint percentile is
monotone from **10%** (p10) to **93%** (p90). The pooled 57.1% is therefore a
slice-average over a graded spectrum, with the no-bite control at the weak-trade-off
end — not a binary cliff.

## On the remaining weaknesses (we agree, and they are disclosed)

- **Harm validated on a measurable proxy axis only** — true and necessary (no
  governance ground truth exists; that is the finding). A live deployment study is
  flagged as the natural next step. Q3 at least shows the proxy result is a graded,
  mechanism-consistent phenomenon, not a cliff.
- **Single corpus / publication self-selection** — the key external-validity
  limitation, stated in §8; composition is stress-tested (whole-industry deletion) but
  selection-into-corpus needs a second independently-collected corpus, which does not
  exist on hand.
- **Dense prose** — taken seriously, but the main text is at exactly 9 pages; the
  round-5 additions are appendix-only, so main-text density is unchanged, and we did
  not cut claims to loosen prose.

---

# Author response — round 6 (6/10, lean accept; Soundness Good, Presentation Fair)

We thank the reviewer for the most penetrating review of the cycle. It raised one new,
correct critique (criterion-dependence of the headline), one fair gap (infeasible verdict),
and an excellent question (Q4) that exposes a strength. **No published number changed; frozen
substrate read-only via the immutable interface.**

## W1 / Q1 — the headline is criterion-dependent (completion semantics)

Agreed, and we ran the requested sensitivity (E10, new). The criterion completes each ⊥ cell
over its **entire** domain — the conservative, lower-bound-certified, but adversarial reading.
Confining ⊥ cells on the **measurable** axes (quality, cost, latency) to their observed corpus
range instead — a bounded-prior reading, queries and thresholds unchanged, under interval
semantics — lowers the headline from **91.1%** to **56.9%**, and this is **robust to the bound
width** (point p50, [p40,p60], [p25,p75], [p10,p90] all give 56.9%). So roughly a third of the
full figure is the adversarial-completion tail on the measurable axes; the **56.9%** that
survives any bounded belief is the criterion-robust core, of which **47.3 points** are blocked
by a never-measured axis — which admits **no** bounded range at all, there being no evidence to
bound it with. We now frame 91.1% as the conservative certified headline and **56.9% as its
any-reasonable-belief floor**, and report the sweep in Appendix G with a one-clause pointer in
§5. This is the honest separation the reviewer asked for: it is less flattering than 91.1% but
still shows that, under the most generous belief about the measurable axes, most decisions are
underdetermined and the never-measured axes dominate.

## W6 — the infeasible verdict gets no empirical discussion

Fixed. **0/1,716** queries are infeasible at FULL regime; we state this in Appendix G — the
binding question is always decidable-versus-underdetermined on this corpus, never "no feasible
candidate exists."

## Q4 — does the VoI ranking also have nothing to compute on never-measured axes?

No — and this is a strength we now make explicit (Appendix G). The VoI of a ⊥ axis is the
two-world regret, which needs only the **cost spread and violation penalty**, not an estimate
of the axis's value. So the procedure ranks a governance measurement precisely **where
imputation, lacking any cross-context signal, has nothing to compute.** The Bayesian baseline
collapses to the prior there; the VoI does not, because it prices the *decision*, not the
*value*.

## Q2 — reconciling the 75–91% range with the small structural-only residual

Added (§5/Appendix G): the operationally relevant floor depends on what a deployer can cheaply
acquire. Under price-sheet (cost) access the irreducible remainder is the structural residual;
75–91% is what the evidence **as published** leaves before any acquisition. The numbers are not
in tension — they are the same quantity read at different acquisition budgets.

## On the weaknesses we cannot close here (acknowledged, not papered over)

- **W2 (harm validated on a measurable proxy axis):** necessary — there is no governance ground
  truth; that is the finding. The graded-bite result (round 5) at least shows the proxy harm is
  a mechanism-consistent, continuous phenomenon, not a cliff.
- **W3 (diverse acquisition blocking structures):** not data-feasible. RouterBench has
  co-located ground truth only for quality+cost; other axis pairs lack co-located truth (the
  blind spot again), so a diverse-blocking validation cannot be run honestly.
- **W4 / Q5 (publication self-selection; second corpus):** the key external-validity limitation;
  no second independently-collected deployment corpus is on hand (MedHELM was access-gated). We
  state it plainly and note the likely bias favors the finding.
- **W5 (methods novelty modest):** accepted — this is a measurement-and-diagnosis paper; the
  contribution is the reframing and the evidence, not a new method or theorem.
- **W6 (prose density, Figure 1 legibility):** the main text is at exactly 9 pages; round-6
  additions are appendix-only, and we trimmed §5/§8 rather than add density.

---

# Round 7 — author response (referee: weak accept ≈6; Soundness Good, Contribution Good, Presentation Fair)

We thank the reviewer for the most precise read of the cycle — including the round-6 appendix
(the 56.9% bounded-completion figure). We agree with the assessment that the paper is strongest
as a *diagnosis of the evaluation ecosystem*, and that its ceiling is the unfalsifiability of the
governance axis (W1) and the harm being validated on a different axis than the headline (W2).
Those are structural and we disclose them. The actionable asks we address below; two we close
with new experiments, the rest with framing the reviewer is right to demand.

## The one change that most affects how the paper reads (W2 / Q1): headline as a range, two conservatisms disentangled

The reviewer is correct that a reader stopping at the abstract takes 91.1% as "at least this bad"
when, across completion semantics, the any-reasonable-belief floor is **56.9%**. We have:

- **Led the abstract, contributions, and conclusion with the range [56.9%, 91.1%]** — "from 56.9%
  under any bounded belief about the unmeasured axes to 91.1% under the conservative full-domain
  reading" — rather than the bare 91.1%.
- **Disentangled the two senses of "conservative"** in a dedicated appendix paragraph: (i)
  *witness-based flagging* (within a fixed completion semantics, we flag only when we can exhibit
  a flipping completion → every rate a lower bound on flagging), and (ii) *choice of completion
  semantics* (full-domain is the most adversarial; bounded-prior floors at 56.9%). 91.1% is the
  witness-based bound *under* the full-domain semantics; 56.9% is the bound that survives *any*
  bounded belief. We cite the pair, not one number.

**Which single number?** We recommend the **range**, with 56.9% as the criterion-robust core
(dominated by never-measured axes, which admit no bounded range) and 91.1% as the conservative
certified headline. We resisted collapsing to one number precisely because the reviewer's point is
that the spread *is* the content.

## Q2 (chance-constrained Bayesian): the wall is the posterior, not the objective — NEW experiment (B8)

The reviewer asks whether the Bayesian rule's 70× over-provisioning is the *expected-regret
objective* or the *wide posterior*, and whether a chance constraint `P(violate) ≤ α` recovers
min-sufficiency. We ran it (`run_chance_constrained.py`, identical posterior/mask/slices as B7):

| α | coverage | HVR | min-suff | mean overshoot |
|---|---|---|---|---|
| 0.01 | 0% (abstains) | — | — | — |
| 0.05 | 29% | 0% | **0%** | **127×** |
| 0.10 | 42% | 0% | **0%** | 15× |
| 0.20 | 52% | 16.5% | 63.5% | 9.4× |

**No α achieves both low violations and min-sufficiency.** At tight α the constraint over-provisions
even *more* than B7 (127× at α=0.05); the only α that recovers min-sufficiency (0.20) re-admits
violations. The wall is the width of the posterior over the unmeasured axis — a partial-identification
wall — not the objective. This is exactly what a *missing* (vs. imprecise) axis predicts, and it
strengthens the never-impute argument. (Appendix G, "Chance-constrained variant.")

## Q4 / W5 (do two coarse mappings dominate 72.4%?): no — NEW analysis (per-query blocker distribution)

We report the per-query distribution of blocking axes over the 1,563 underdetermined queries
(`run_blocker_distribution.py`). Mean blocker-set size **2.3** (multiplicity is the norm). Governance
is present in 61.0% but the **sole** blocker in only **4.7%**; reviewer burden present 48.0%, sole
**8.6%**. Cost is the modal blocker (present 82.5%). Only **17.5%** of underdetermined queries have a
blocking set inside {governance, reviewer_burden} — i.e. would be resolved by deleting both mappings —
and the other **75.1% of all queries** survive on a different blocker, reconciling exactly with the
joint-drop floor; the never-measured-axis cross-check independently recovers the published **72.4%**.
Two mappings do not carry the headline. (Appendix G, "Per-query blocker distribution.")

## Closed in prose (the reviewer is right; arguments, not assertions)

- **Q3 (direction of publication-self-selection bias):** we now give a *mechanism*. Teams that
  publish case studies are disproportionately the better-instrumented ones (they ran the evals that
  make a case study worth writing), so the published corpus *over*-represents well-measured
  deployments; the unpublished tail is plausibly *less* measured → *more* underdetermined, not fewer.
  Blind-spot axes are unmeasured regardless of publication. So the bias plausibly favors the finding.
- **W3 (de-emphasize the near-definitional 57.1% vs 0%):** done. §7 now foregrounds the load-bearing
  results — acquisition efficiency (2.0 vs 6.0 probes) and held-out risk control (4.7% at 89%
  coverage) — and explicitly labels the McNemar 272/0 gap as near-definitional, not the contribution.
- **W6 (contribution item-4 oversells the theory):** tightened to "a numerically verified two-world
  identity … (a solver-precision check, not a general guarantee)," matching the in-text scoping.
- **W8 (n-cascade hard to track):** added an experiment→n map table (Appendix G, Table 8).
- **Q5 (noisy measurement):** acknowledged as a scope boundary — the possible-worlds machinery
  extends (a noisy measurement *narrows*, not collapses, the completion set), but calibrating the
  residual and a value-of-noisy-information is future work.
- **Q6 (cheap configs that co-satisfy a hidden axis):** the ≈42.9% co-satisfaction (= 1 − 0.571)
  shrinks realized harm, but it is luck the decider cannot see ex ante — the same blind rule loses
  on the complementary 57.1% with no signal to tell them apart.
- **W7 (operational value when the top blocker is one expensive governance measurement):** the
  contribution there is decision discipline — certifying the decision is genuinely unidentified,
  naming the audit, pricing it, and declining the confident-looking blind commitment imputation
  would produce.

## Acknowledged, not closable here

- **W1 (governance unfalsifiable) / W2 (harm on a measurable axis):** structural and disclosed; the
  proof is on cost/quality, the claim on governance is one of decidability via Proposition 1, not a
  harm demonstration — we state this explicitly and do not claim the 57.1% transfers to governance.
- **Fit / no new learned component:** accepted — a measurement-and-diagnosis paper for ICLR's
  broadened scope; the imputer and Bayesian/chance-constrained rules are baselines, not contributions.

No published number changed. Main text holds at exactly 9 pages (0 overfull, 0 undefined refs);
all new content is appendix-only. 79/79 tests pass.
