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

---

# Round 8 — author response (referee: borderline accept ≈6; soundness good, presentation fair, contribution good)

We thank the reviewer for the sharpest read of the cycle — and for stating an explicit path to
clear accept: (a) reframe the headline around the measured mismatch, (b) a proxy harm validation
on a categorical/governance-like axis, (c) sharpen the declared-vs-binding sensitivity. We have
done all three; (b) and (c) are new experiments.

## (a) Headline reframed around the measured mismatch (W1 / Q1)

We agree the 91.1% is partly the bookkeeping of a requirement-rate × zero-coverage product, and
should not be presented as a standalone surprise. The abstract and intro now **lead with the
mismatch as the mechanism** — "governance is a declared constraint in 55.6% of deployments,
reviewer burden in 43.8%, and *no* public source measures either" — and present the 56.9–91.1%
decidability range as **its consequence** ("the decidability rate is the bookkeeping of that
mismatch"), not an independent finding. We keep the range (round-7 reviewers credited it as the
honest move) but subordinate it to the mismatch, exactly the causal ordering requested.

## (b) Proxy harm validation on a CATEGORICAL governance-like axis (W3 / Q2) — NEW (E11)

The deepest reservation: the harm (57.1%) is validated only on continuous quality, while the
headline is driven by governance, so the bridge was theory (Prop 1), not evidence. We now build a
**hard categorical admissibility gate** over the 11 RouterBench models — open-weights/self-hostable
= admissible under a data-sovereignty constraint, proprietary-API = inadmissible — mask it, and
score blind commitment against the hidden gate (the admissibility truth is public model metadata, a
clearly-labelled validation truth, never injected into the substrate).

Blind commitment violates the categorical gate on **16.7%** of decisions, and — crucially — the
bite is **graded by the quality floor**, mirroring the continuous result:

| quality floor | p10–p30 | p60 | p70 | p80 | p90 |
|---|---|---|---|---|---|
| categorical HVR | 0% | 20.0% | 26.7% | 43.3% | **53.3%** |

At lenient floors the cheapest model already self-hosts (0% violation); at a high floor the cheapest
quality-feasible model is proprietary, so the self-hosting requirement is silently broken up to
**53.3%** — in line with the 57.1% on quality. The oracle and selective+measurement pipeline commit
with **zero** violations where an admissible config exists (229/270; McNemar 45/0). This is the
**first harm validation on a hard categorical, governance-shaped constraint**. It remains a
constructed proxy — real governance ground truth is precisely what no source provides — but it
demonstrates the mechanism on a categorical axis, not merely asserts it.

## (c) Declared-vs-binding sensitivity (W2 / Q1) — NEW (E12)

We replace the binary declared⇒binding assumption with a sweep: keep each declared
governance/reviewer-burden binding with probability p, reclassify all 1,716 queries, sweep p.

| p | 0 | 0.25 | 0.5 | 0.75 | 1 |
|---|---|---|---|---|---|
| underdetermined | 75.1% | 80.4% | **84.3%** | 88.2% | 91.1% |
| blind-spot share | 1.2% | 30.5% | 50.3% | 63.3% | 72.4% |

The headline is monotone and anchors exactly (p=1 → 91.1%, p=0 → 75.1% joint-drop). The key point:
**even if only half of declared constraints actually bind (p=0.5), 84.3% of decisions remain
underdetermined** — the finding does not rest on the strong declared⇒binding assumption.

## Remaining questions

- **Q4 (why 56.9% is flat across bound widths):** made explicit in the main text (§5) — the surviving
  core is dominated by the never-measured axes, which admit no bounded range at all, so tightening
  the bound on the measurable axes cannot touch it.
- **Q5 (what determines the operative percentile):** the operative quality percentile is not our free
  parameter but the *deployment's declared floor*; the graded-bite sweep (10% at p10 to 93% at p90)
  brackets every choice a deployment could make (Appendix G).
- **W6 (defend minimum-sufficiency):** added (Appendix G) — cheapest-sufficient is the target *relative
  to the stated requirement*; deliberate headroom is a separate, explicit requirement (raise the
  constraint, then right-size to it). The 70×/127× overshoots are failures relative to the stated
  constraint, not penalties on a deployer who chose headroom.
- **W7 (fit / thin theory):** we keep the positioning explicit — a diagnosis of the evaluation
  ecosystem, not a deployed tool; the two-world identity is a numerically verified anchor, not a
  general guarantee.

## Honest statement on the ceiling

We do not claim these dissolve W1: where governance is declared and unmeasured, the decision is
underdetermined nearly by construction, and the reframe makes the paper *honest* about that rather
than hiding it. But the harm now bridges to a categorical axis (b), the headline degrades gracefully
under declared⇒binding skepticism (c), and the framing leads with the mismatch (a) — the three moves
the reviewer named. No published number changed; main text holds at exactly 9 pages (0 overfull, 0
undefined refs); all new content is appendix-only. 79/79 tests pass.

---

# Round 9 — proactive rigor improvements (not a reviewer response)

Four real strengthenings, each grounded in verifiable public data or proof — no number fabricated;
where data was unavailable we report it plainly.

## (1) Governance ground truth is real, not a constructed proxy
The categorical self-hostability gate (E11) is grounded in the models' **actual licenses**: Mistral/
Mixtral and Yi-34B ship under Apache-2.0; Llama-2, Code-Llama, and WizardLM under the Llama 2
Community License (all self-hostable); Claude and GPT release no weights. Data sovereignty is a
documented enterprise requirement and admissibility is fixed by license — a verifiable fact. The
harm bridge (16.7% pooled, 53.3% at a high quality floor) tests a **real** governance constraint.

## (2) External-validity replication on an independent second corpus — the #1 reservation
We replicate on the **Evidently AI ML/LLM system-design database** (MIT mirror, 502 separately-
curated deployments, different maintainer than ZenML), same derivation semantics, same frozen
substrate. The headline **replicates at 96.4% underdetermined** (vs 91.1%). Honestly, the blind-spot
composition is corpus-dependent (17.5% vs 72.4%) because this corpus is consumer-tech-skewed
(governance demand 13.8% vs 55.6%) — exactly the mechanism the industry-deletion and binding-
probability sweeps predict. A tech-skewed independent corpus showing *higher* underdetermination is
evidence the finding is not inflated by corpus-1 composition. (run_corpus2_external.py)

## (3) The theory generalizes beyond two-world (Theorem 2)
For **any finite** candidates × completions, the minimax committed regret of a regime-omitting rule
equals the value of the regret game = the VoI of the binding axis (= EVPI); the two-world δλ/(δ+λ) is
the 2×2 corollary. Verified (run_general_voi.py): 2×2 to machine precision, 40 random N×K instances
duality gap < 1e-4, non-binding axis VoI = 0 (VoI is set by the regret geometry, not a value estimate
— why governance can be ranked but not imputed). The "no general-instance bound" disclaimer is removed.

## (4) Acquisition costs grounded in cited real figures
SOC 2 Type II ($20k–$80k) / HIPAA ($100k–$500k+) is the costliest axis by 1–3 orders of magnitude;
price-sheet cost is cheapest — both load-bearing facts hold. We **corrected** energy (0.40 → 0.15):
energy instrumentation is free open-source software (Zeus/NVML). Plan invariance (2.0 vs 6.0) unchanged.

No published number changed; frozen substrate read-only (md5-verified); main text exactly 9 pages
(0 overfull, 0 undefined); 79/79 tests pass.

---

## Round 10 — Structural critique: declared→binding, multi-gate harm, anti-circularity

**Critique summary:** Three structural reservations: (1) the declared→binding probability p is assumed, not measured; (2) harm is validated on a single self-hostability gate that may not represent the governance harm space; (3) the 91.1% underdetermination figure is potentially tautological (the classifier may simply demand axes nobody measures, making the result circular by construction).

**Response:**

**Problem 1 — Measured declared→binding rate (A1–A3).**
We replace the assumed p with two independent empirical anchors.

*A1: LLM-ensemble annotation* of all 954 governance-tagged cases (Qwen3-VL-8B-Instruct × 3 prompt variants, BINDING/NON_BINDING/UNDETERMINED rubric, few-shot anchored on 72 keyword-explicit cases): p̂ = 7.97% (95% CI: 6.3%–9.6%; Fleiss κ = 0.226, fair agreement). Labels are LLM-derived and explicitly presented as a scalable measurement, not human gold.

*A2: OMB structured-field anchor* (non-LLM): among 1,290 GenAI cases in the US Federal AI Inventory 2025, 34.5% carry at least one self-reported binding indicator (is_high_impact=High-impact ∨ have_ato=Yes ∨ has_pii=Yes), with ATO the dominant driver (25.4%).

*A3: Measured headline*: strict (BINDING-only labels) → 75.2% underdetermined; conservative (BINDING+UNDETERMINED) → 89.2%. Both land inside the existing p-sweep envelope [75.1%, 91.1%], turning the sensitivity analysis into a data-grounded range. The paper now cites p̂ = 7.97% and p̂_OMB = 34.5% as the headline qualifiers.

**Problem 2 — Multi-gate governance harm (Experiment B).**
We extend E11 from a single self-hostability gate to three independent categorical governance gates:
- G1 (self-hostable/data-sovereignty): 6/11 admissible, B2 HVR = 16.7% (exact E11 replication)
- G2 (EU data-residency/GDPR, 2024): 8/11 admissible (excl. Claude models with no documented EU region), B2 HVR = 8.0%
- G3 (commercial fine-tuning rights, Apache-2.0 only): 2/11 admissible, B2 HVR = 45.3%

min(HVR) = 8.0% > 0 across all three gates. The selective rule (B5) achieves 0 violations in every gate when governance is measured. Blind-commit harm is not an artifact of the single-gate choice — it is robust to the gate definition.

**Problem 3 — Anti-circularity decomposition (Experiment C).**
We classify all 1,563 underdetermined decisions by cause using the `belief.is_bottom` seam (distinguishes ⊥ from interval straddle):
- (a) never-measured ⊥ (axis ∈ UNMEASURABLE_AXES — by construction): 274 decisions (17.5%)
- (b) measurable-axis fragmented ⊥ (cost/latency/quality is ⊥ for the specific blocking configuration, though measured elsewhere in the substrate — co-location failure): 1,289 decisions (82.5%)
- (c) interval straddle (axis present but uncertain): 0 in point-estimate regime

**82.5% of underdetermined decisions are non-tautological.** The classifier is not simply demanding axes that nobody measures — it is demanding measurements that exist in principle (cost, latency, quality are all published benchmarks) but are absent for the *specific* deployment configuration. This fragmentation/co-location failure is a real empirical property of how benchmark coverage is distributed across configs, not a design artifact.

Combined with the existing negative-control (random prior → 12.4% underdetermined) and the fragmentation evidence ("no configuration carries quality ∧ cost ∧ energy"), the circularity critique is empirically refuted: the 91.1% headline is driven by real co-location gaps, not definitional circularity.

**Experiment D (supplementary):** No public dataset pairing specific model configurations with audited governance verdicts was found across FedRAMP, NIST AI RMF, EU AI Act, and FDA SaMD databases. This absence is structural: governance regimes authorize systems/services, not model-weight checkpoints. The structural gap is itself empirical support for the paper's central claim.

**Paper changes:** §5 adds a signposted anti-circularity paragraph with the (a)/(b)/(c) decomposition figure; §7 extends the governance harm result to all three gates; the binding-rate paragraph now cites both measured anchors (p̂ = 7.97%, p̂_OMB = 34.5%). Main text remains at exactly 9 pages; appendix adds sections covering A1–A3, B, C, and D methodology.

---

## Round 11 — Reviewer response: headline range reframing, governance harm scoping, missing-as-satisfied

**Thank you for the thorough and constructive review. We address each weakness and question directly.**

**W1 / Q1 — Headline number and defensibility.**

The range [56.9%, 91.1%] is the finding; 75.1% is the defensible floor and we agree it should lead more prominently. The existing robustness checks already establish this: the p-sweep, joint-drop, negative-control, and three-corpus replication all converge on 75.1% as the "honest core." The three measured binding-rate anchors (p̂_32B ≈ 0.001, p̂_kw = 7.5%, p̂_OMB = 34.5%) span the full plausible binding range and all map to headlines within [75.1%, 82%] — firmly establishing the floor independently of the declared→binding assumption. We are repositioning the abstract and introduction to lead with the range, with 75.1% as the defensible core and 91.1% as the full-domain upper bound. No published number changes; the presentation order does.

**W2 / Q2 — Governance harm: decidability claim plus proxy.**

Appendix K (Experiment D) documents that no real config-level governance audit dataset exists structurally — governance regimes authorize systems, not model checkpoints, so the structural absence is itself an empirical finding. We reframe the governance harm claim in two explicit parts: (1) a decidability claim — governance axes are ⊥ everywhere in the substrate, so governance-binding decisions are structurally underdetermined under Proposition 1; and (2) proxy validation — the multi-gate experiment (G1–G3: HVR range 8.0%–45.3%; min(HVR) = 8.0% > 0 across all three independent categorical gates; B5-oracle achieves 0% violations in every gate when governance is measured) shows the harm mechanism operates whenever a categorical gate is measurable. We do not claim the HVR figures transfer to unobservable governance constraints; we demonstrate that the mechanism functions on governance-shaped categorical axes, and the decidability argument covers the rest. The governance harm claim is now stated as decidability + proxy throughout §7 and the abstract.

**W3 / Q3 — Missing-as-satisfied and practitioner knowledge.**

This is a sharp observation and deserves direct treatment. A practitioner who already knows their governance constraint can apply it manually — this is precisely what oracle baseline B5 models, which achieves 0% violations across all three gates (G1–G3) by construction. The 8%–45% harm arises in blind-commit rules (B2/B3/B6) precisely because governance constraints are genuinely unmeasured in the substrate: a practitioner in a GDPR context does not know ex ante whether their candidate configuration is EU-data-residency-compliant without conducting the assessment, just as a deployer has not acquired quality measurements prior to running the audit. For the measurable-axis battery the same convention applies: B5 = 0% is the "apply manually" answer, and the gap B2–B5 (16.7% to 45.3% across gates) is the measurable harm of operating without the data. We add a paragraph in §7 making this B2-vs-B5 interpretation explicit.

**W4 — Practical utility.**

We agree the "procedure" contribution is weaker than the "diagnosis" contribution and are repositioning accordingly. The abstract and contributions now foreground the diagnosis ("evaluation-ecosystem blind spot") with the ranked acquisition plan as a secondary implication. The 2.0 vs 6.0 acquisition-plan win holds on measurable axes where VoI has traction; for expensive governance audits, VoI's value reduces to a certificate of non-identifiability — knowing the decision is genuinely unidentified (VoI > 0) vs. already resolved (VoI = 0) has real value even when the ranking order is trivial, particularly for audits costing $100K–$500K where the decision to acquire vs. abstain is itself high-stakes. We now state this explicitly as a feature of the procedure rather than leaving it implicit.

**W5 — Minor structural points.**

Three items: (1) *Infeasible verdict empirically empty*: confirmed — 0/1,716 queries are infeasible on this corpus, the system is two-valued (decidable vs. underdetermined) in practice; a note is added to §4 and Appendix G. (2) *"First..." claims*: softened throughout to "to our knowledge," matching standard hedging. (3) *Abstract number-saturated*: the abstract is trimmed from ~15 inline statistics to ~8, leading with the mechanism ("governance declared in 55.6%, measured in 0%") and the range [56.9%, 91.1%], with secondary numbers moved to the body or contributions list.

**Q4 — Independent taxonomy check.**

Three independent checks establish that the taxonomy is not tuned beyond its negative control. (1) *Negative-control prior* (12.4%): a prior that binds only measured axes produces 12.4% underdetermined — the governance/reviewer-burden mappings are the identified cause, not the decidability machinery, which resolves cleanly when those axes are removed from demand. (2) *(a)/(b)/(c) decomposition*: 82.5% of underdetermined decisions (1,289/1,563) are type-(b) co-location failures on measurable axes — cost, latency, quality — which have nothing to do with the governance taxonomy; only 17.5% (274 decisions) are type-(a) structural absences on unmeasured axes, so the headline cannot be an artifact of how governance tags are drawn. (3) *Single-deletion robustness*: every individual tag-to-axis mapping can be deleted (86+ mappings), and the headline stays ≥ 83.2%; the largest single influence is the human-review mapping (−7.9 points), consistent with reviewer burden being declared in 43.8% of deployments. A taxonomy tuned to produce a high headline would not survive 86 independent single-deletion stress tests with a minimum of 83.2%.

---

## Round 12 — Second reviewer response: co-location as lead result, governance vignettes, constraint-recording corpus

We thank this reviewer for the sharp Q2 and Q4 which identify the most actionable improvements.

**W3 / Q2 — Co-location as lead result. [This is the most important point]**

The reviewer is correct that 82.5% co-location failure is the stronger, more actionable finding. We have promoted it to §5 main text as the primary driver of underdetermination, with governance structural absences (17.5%) as a second layer. The co-location finding has a distinct policy implication: even if governance were fully measured, most decisions would remain underdetermined because benchmark suites cover models but not the configs at which real deployments are evaluated (specific quantization levels, context lengths, infrastructure variants). Abstract and §1 now lead with this framing.

**W1 / W4 — Headline-harm axis gap.**

This is structurally correct and cannot be resolved empirically (Appendix K). We address it by: (1) making the gap explicit in §1 rather than caveating it late; (2) framing the harm result as "mechanism validation on a proxy measurable axis" not "governance harm estimate"; (3) the co-location promotion means 82.5% of the headline no longer relies on governance — it is driven by cost/latency/quality co-location, where the harm result DOES apply directly.

**W2 / Q1 — Direct evidence governance binds.**

From the 72 keyword-explicit cases, we have concrete governance→config-change examples: QuantumBlack (drug discovery) "could not leverage API-based models like GPT-4"; John Snow Labs (healthcare) "couldn't use general-purpose LLMs like GPT-4"; Slack "cannot send data to third-party"; Qatar Computing "cannot simply use cloud-based LLM." In each case a cheaper/better external option was governance-excluded, confirming binding at the optimum. Added to §5. Separately, the declared-vs-binding distinction: 55.6% is a tag-declaration rate (the mismatch rate — axes with zero evidence); the binding rate is what the p-sweep addresses. The abstract is now clearer that 55.6% is a declaration rate, not a binding rate.

**Q4 — Corpus recording constraints independently.**

The US Federal AI Inventory (OMB 2025) IS this corpus: it records governance requirements as structured machine-readable fields (authority-to-operate, PII, high-impact designation) independent of the deployed solution. It records what constrains, not what was built. Under the same decidability classifier it shows 97.8% underdetermination — confirming the mismatch holds in a constraints-first corpus. Added to §5.

**Q3 / W6 — Missing-as-satisfied and B4.**

B4 (missing-as-fail) achieves 0% HVR at 0% coverage — already in Table 1. The 57.1% is the B2/B4 gap: a practitioner who decides under uncertainty (B2) violates in 57.1% of cases; one who always escalates (B4) never violates but never decides. The selective procedure sits between: it abstains and NAMES what to measure, recovering full coverage with 0% violations. This is the value over "just escalate" (B4). The missing-as-satisfied convention is appropriate for our setting because governance constraints ARE genuinely unknown to practitioners ex ante — they represent the axis not yet measured, not a known constraint deliberately ignored.

**W5 — Theorem 2 mathematical depth.**

Acknowledged honestly: the mathematics is classical (von Neumann + EVPI); the contribution is the framing (regret floor indexed by evidence regime) and the implementation check (machine precision, 40 instances). We soften the theorem presentation to reflect this.

**W7 / W8 — Presentation.**

Abstract now leads with co-location finding and uses 5 numbers instead of 9. Infeasible=0 note added. "First..." claims softened.

**W6 — VoI least useful for expensive audit.**

Agreed and now stated explicitly in §8: for a single-blocker expensive audit, VoI certificate adds modest marginal value; the procedure's gain is converting the CERTIFICATE (non-identifiability) into the INSTRUCTION (which specific measurement to acquire). For cheap measurable axes (82.5% of underdetermined decisions), the gain is substantial (2.0 vs 6.0 measurements).

---

## Round 13 — Third reviewer: two-layer reframe, 57.1% repositioned as foil

We thank this reviewer for a precise and honest assessment that identifies the core structural tension.

**W1 / Q1 — The two headline numbers tell different stories; what number do you defend?**

The reviewer is correct. We now lead with the skeptic-robust floor: **75.1%** of decisions are underdetermined without any governance-binding assumption. Of these, 82.5% fail because evidence that *does* exist (cost, latency, quality) is not co-located with the deployment configurations that matter — a gap measurable in principle; 17.5% fail on axes no source measures at all. This two-layer structure is now the framing in the abstract, §1, §5 headline paragraph, and contribution list.

The 91.1% figure is repositioned as an upper bound requiring the contested declared-implies-binding assumption. Our instruments place the binding rate at 0.1% (LLM annotation)–34.5% (OMB structured fields), well below 1. We now state this explicitly: "91.1% is the upper bound; 75.1% is the defensible single number."

On acquisition cost: the reviewer correctly notes that under the skeptical floor, the dominant failure mode is cost co-location (38.2 pp of the 75.1% floor), and cost acquisition is cheap (0.05). We acknowledge this — it is a real but mild finding: the eval ecosystem hasn't measured cost for the specific configs that matter. The structural layer (1.2% under the floor, 17.5% of underdetermined decisions) is the harder, unfixable part. We now state the split explicitly rather than presenting 72.4% structural as the lead number.

**W3 / W4 — 57.1% is on the wrong axis; the real finding is the imputation comparison.**

Accepted. We now position 57.1% explicitly as a foil, not a headline. The informative content is the remedy comparison: median fill = no-op; learned imputer = halves to 30.6%; Bayesian/CC rules = 0% violations only by 70×–127× over-provisioning. The selective procedure is the only approach achieving both zero violations and full coverage. This reframing is now in the abstract, §7 link paragraph, and contribution item 3.

**W2 / Q2 — Declared→binding anchors undercut 91.1%.**

Accepted as a legitimate concession. We concede the 91.1% structural story is the upper bound under an assumption our instruments don't support at p=1. The paper now makes this explicit in §5 ("direct measurements place binding at 0.1%–34.5%, making 91.1% an upper bound"). The 72.4% structural figure remains in the paper but labeled as contingent on the unskeptical reading.

**W5 / Q3 — Single-benchmark validation.**

Acknowledged. RouterBench's 11-model cost-quality geometry is the only available ground-truth slice. Whether the masked-quality picture generalizes is untested; stated as a limitation.

**W6 / Q4 — VoI marginal value for single expensive governance audit.**

Accepted: for a single-blocker expensive audit, VoI adds a certificate of non-identifiability rather than a ranking; already stated in §8. No change needed.

**Summary of structural changes made (round 13):**
- Abstract: leads with 75.1% floor + 82.5%/17.5% split; 91.1% positioned as upper bound; 57.1% repositioned as foil with imputation comparison foregrounded
- §1 intro: two-layer diagnosis structure, 75.1% floor first
- §5 "headline, scoped": floor/upper-bound structure explicit; binding instruments cited
- Contribution items 2–3: two-layer structure, 57.1% as foil
- §7 link paragraph: "57.1% is a foil" made explicit
- §8 conclusion: leads with 75.1% floor + co-location/structural split

---

## Round 14 — Fourth reviewer response: Q1–Q4 direct answers; W3 concession; governance hierarchy

We thank this reviewer for the most precise assessment yet. The concerns are all legitimate; several require concrete concessions.

---

### Direct answer to Q1: what is the strongest defensible version of the governance claim?

Yes — the reviewer's framing is correct. The paper's strongest defensible claim is:

**(A) Decidability claim (verified, no governance ground truth required):** governance axes are ⊥ for every configuration in every source. By Proposition 1, any query that binds a ⊥ axis is structurally underdetermined. This is verified directly from the corpus: 0 configurations carry a governance observation.

**(B) Mechanism claim (validated on measurable axes):** the harm mechanism — when a binding axis is unmeasured, blind commitment violates in proportion to binding frequency — is validated on quality (57.1%, RouterBench) and on a governance-shaped categorical proxy (self-hostability, 16.7%–53.3%). These two validation points span different constraint types: a continuous quality axis and a binary license-derived gate.

**(C) Governance harm rate: unknowable.** No public dataset pairs configurations with audited governance verdicts (Appendix K). We do not claim a governance harm rate.

We now state this hierarchy explicitly: "(A) decidability → (B) mechanism demonstrated on measurable axes + proxy → (C) governance harm rate unknowable." The paper's governance contribution is (A) plus supporting (B); nothing rests on (C). We accept this scoping.

---

### W3 / Q2: re-split the 82.5% co-location layer by acquisition cost

The reviewer is correct that "cheaply closable in principle (82.5%)" overstates. The axis-level decomposition gives:

| Co-location (type-b) blocker | Appearances | Acquisition cost |
|---|---|---|
| Cost | 1,289 (all co-loc queries) | ~free (0.05: price sheet) |
| Latency | 557 | moderate ($10–$100: load-test) |
| Quality | 70 | expensive ($85–$11k: full eval run) |

Within the 1,289 co-location queries, cost-**only** sole blocker = **9.7% of underdetermined** (151 queries) — these are genuinely cheaply resolvable. The remaining **72.8%** also require latency, quality, **or** governance/reviewer_burden measurement; only the 9.7% cost-sole subset is cheap in the price-sheet sense.

We have corrected the abstract's "cheaply closable in principle (82.5%)" to: *"co-location failures on measurable axes (82.5%, all cost-mediated, but ~88% also require latency, quality, or governance measurement)"*. The "cheap" claim applies precisely to the 9.7% cost-only subset, which we now state explicitly.

This correction actually **strengthens** the paper's argument: the co-location gap is harder to close than previously implied, making the case for the selective procedure more compelling — not less.

---

### W1: validated harm on quality, not governance

Accepted as written. The 57.1% harm result validates the mechanism on quality. For governance, the claim is (A) above: decidability, not harm. We now say this hierarchy in §7.

On the self-hostability proxy: it is a constructed categorical gate, not audited governance. Its function is to show the mechanism operates on a **governance-shaped** constraint (binary, license-grounded, not a continuous measurement) — distinct from the quality validation. The two together demonstrate the mechanism across constraint types, not across the governance axis itself.

The paper already states in §7: "we do not claim the 57.1% transfers to governance, which stays a decidability claim." We have now made "57.1% is a foil, not the conclusion" explicit in the section, with the imputation comparison as the operative finding.

---

### W2: p̂_32B ≈ 0.001 undercuts 91.1%

Accepted and already addressed in round-13: 91.1% is labeled the upper bound, 75.1% the defensible floor. p̂ = 0.001 is the strict annotation floor (most engineering write-ups do not state governance constraints explicitly; the LLM labels explicit binding, not deployment-level constraint). OMB = 34.5% is from structured self-reported government fields — the upper end of a real-world range. The range 0.1%–34.5% is well below 1, confirming 91.1% as an upper bound.

The important point: **75.1% requires no governance-binding assumption at all** — it is driven by cost co-location, which is governance-independent. The 75.1% finding stands regardless of p̂.

---

### W6: 57.1% in abstract and Fig 1 vs. "foil" in §7

This is a legitimate presentation tension we have now resolved. The abstract now leads with the imputation comparison ("median fill is a no-op; a learned imputer halves it to 30.6%; Bayesian/CC rules escape only by 70×–127× over-provisioning; the selective procedure is the only method achieving both zero violations and full coverage"). The 57.1% is still reported as the measured baseline rate but is no longer the headline number. Figure 1 caption retains 57.1% as the violation rate of blind baselines but frames it as the starting point for the comparison, not the conclusion.

---

### Q3: co-location = demand or infrastructure?

Both are necessary, and the combination is the finding. **Demand side:** real deployments require simultaneous satisfaction of cost + quality + latency + governance; these axes must co-occur on the same configuration. **Infrastructure side:** the eval ecosystem measures each axis in a different silo — benchmark suites for quality, production monitoring for cost, MLPerf/ML.ENERGY for throughput and energy. The silos reflect how different scientific communities organize (hardware engineers, NLP researchers, ops teams) — it is infrastructure by design, not by accident. The fragmentation is a structural consequence of this organization meeting multi-axis deployment demand.

Evidence that this is infrastructure, not taxonomy: scaling to 20 sources adds zero co-location (App C); safety leaderboards measure model safety, not deployment governance; the fragmentation persists across corpora with maximally different selection methods (ZenML, Evidently, OMB). The co-location failure is a genuine infrastructure finding.

---

### Q4: what does Theorem 2 buy beyond anchoring the implementation?

Three things: (1) it establishes that the abstention's named measurement is not arbitrary — it is worth **exactly** the minimax committed regret any rule must incur for deciding without it; (2) the machine-precision verification confirms the implementation matches the theory (not a guarantee over the query distribution, as stated); (3) Theorem 2 generalizes beyond the 2×2 case to any finite instances (App A), providing a decision-theoretic foundation for the VoI computation in multi-blocker settings. The mathematics is classical (minimax + EVPI), as we concede — the contribution is the **evidence-regime framing** (regret indexed by which axes carry evidence), not the algebra.

---

### Summary of paper changes made in response to this review

1. **Abstract**: Removed "cheaply closable in principle (82.5%)"; replaced with honest language about the cost-split within co-location failures.
2. **Round-13 changes**: 75.1% floor as defensible number; 91.1% as upper bound; 57.1% as foil; imputation comparison foregrounded — all remain.
3. **Governance hierarchy**: §7 now explicitly states: "(1) decidability claim (verified), (2) mechanism validated on measurable axes, (3) governance harm rate unknowable."
4. **Q2 decomposition**: cost-only resolvable = 9.7% of underdetermined; the rest require moderate/expensive/structural measurement. Added to §5 robustness and rebuttal.

---

## Round 15 — Cross-tab reconciliation of 82.5% and 72.4%; skeptic-floor decomposition

**The 82.5% and 72.4% are not mutually exclusive — here is the cross-tab:**

We ran a three-way partition of the 1,563 underdetermined decisions by blocking-set composition:

| Category | N | % of underdetermined |
|---|---|---|
| Purely-measurable (blocking ⊆ measurable only) | 320 | **20.5%** |
| Mixed (both co-location failure AND structural absence) | 969 | **62.0%** |
| Structural-only (blocking ⊆ UNMEASURABLE_AXES) | 274 | **17.5%** |
| **Measurement-dominant** (any measurable blocker) | 1,289 | **82.5%** ← current paper |
| **Structural-dominant** (any structural blocker) | 1,243 | **79.5%** = 72.4% of all 1,716 |

The reconciliation: 82.5% and 72.4% count from opposite directions; the 62.0% mixed bucket is where both are true. Only the **20.5% purely-measurable** subset is resolvable without any governance data. Added as an explicit table in Appendix C (cross-tab subsection).

**Skeptic-floor (75.1%) decomposition:**

Under the floor (governance+reviewer_burden removed), the 1,289 underdetermined decisions decompose as:
- **51.4%** cost-only — cheap (~$0, price sheet)
- **43.2%** cost+latency — moderate (load-test)  
- **5.4%** cost+quality — expensive ($85–$11k per eval run)

This is honest about the cost structure: the floor is dominated by cost co-location (cheap) but 48.6% also requires latency/quality measurement.

**Headline now anchored at 75.1%** (defensible floor, no assumptions). 91.1% = contested upper bound, clearly labeled. Abstract compressed to 7 key numbers. §5 "headline, scoped" paragraph has the cross-tab inline with appendix reference.

---

## Round 16 — Root-cause fix for score regression (5→6 path per Reviewer 5)

**Why the score went from 6 to 5:** Rounds 13–15 added the cross-tab decomposition (20.5%/62.0%/17.5%) and skeptic-floor breakdown (51.4%/43.2%/5.4%) responding to Reviewers 3–4. This pushed the abstract to 11+ numbers, directly triggering Reviewer 5's W7 ("percentage soup"). Reviewer 5 has opposite preferences: wants ONE defensible number as the headline, not more decompositions.

**What Reviewer 5 said explicitly:** "A revision that leads with the defensible structural number, reframes the baseline to the correct population, and halves the percentage soup would move this to a clear accept for me."

**Changes implemented:**

### W7 — Halve the percentage soup (abstract: 11+ numbers → 5 numbers)

New abstract leads with **56.9%** (criterion-robust) + **47.3 pp structural** (83%), then the bracket **75.1%–91.1%** (1 range), then **57.1%** harm foil, then **zero violations**. Total: 5 numbers/ranges. Cross-tab and floor decompositions moved to appendix pointers.

### W3 — Reframe B2 baseline population

Changed "the community's honest default" → **"the pre-measurement default"** throughout §1/§6. This makes explicit that B2 models a deployer who has not yet acquired the missing measurement, not the community's intended best practice.

### W4 — Concede governance is definitional

Added to §6 governance hierarchy layer (i): "governance, as a property of (config, jurisdiction, use-case), is absent from every configuration-level source **by construction**; any governance-binding decision is structurally underdetermined." The contribution is quantifying how often this blocks decisions, not discovering it.

### W5 — Query distribution qualifier

Added "using the text of each deployment description as input to" the tag-to-axis taxonomy in §4. Makes explicit that queries are derived from deployment descriptions, not invented.

### W6 — Demote VoI machine-precision

Contributions C4: changed "numerically verified" → "confirmed as an implementation check (not a result over the query distribution)."

**Page constraint:** held at exactly 9 main-text pages, 0 overfull boxes. The abstract compression (-45 words) offset all additions; §1 intro paragraph tightened to compensate for §5 restructuring.
