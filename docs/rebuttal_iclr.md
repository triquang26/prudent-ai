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
