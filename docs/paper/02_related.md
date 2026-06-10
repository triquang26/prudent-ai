# 2. Related Work

We position against three groups: the **evidence-improvers** we build on but differ from (they
sharpen the per-axis estimate; we ask whether the decision is identified at all), the two
**model papers** whose machinery we adapt (selective decision under uncertainty, and a limit
theorem), and a **different layer** (runtime serving) that is often mistaken for ours. Across
all three the distinction is the same: prior work optimizes or estimates *under an observed
objective*; we decide *under evidence that may not identify the decision*, and measure how often
it does not.

## 2.1 Evidence-improvers — better estimates, same identifiability assumption

**HELM** (Liang et al., 2211.09110) is holistic, multi-metric, per-model evaluation: it widens
the set of axes reported and is precisely the kind of *evidence input* our substrate ingests —
but it produces a richer estimate per model, not a decision procedure, and says nothing about
when the reported evidence suffices to identify a right-sizing choice. **HAL** (the Holistic
Agent Leaderboard, 2510.11977) is the nearest and most expensive threat: 21,730 rollouts at
~$40k giving per-cell accuracy, cost, and tokens — it makes the agent estimate far more reliable
and cost-aware, while we ask the orthogonal question of *when a deployment conclusion is valid
on the evidence at all*; HAL is simultaneously an evidence source, a threat, and a model paper
for our infrastructure framing. **AI Agents That Matter** (Kapoor et al., 2407.01502) shows
accuracy-only evaluation is misleading and argues for joint accuracy+cost Pareto analysis; we go
further by showing that even a *joint* accuracy+cost rule still answers queries it should abstain
on, because real deployments bind latency, energy, governance, and reviewer-burden — axes its
Pareto front never sees. **FrugalGPT** (Chen et al., 2305.05176; 98% cost reduction via cascades)
and **LLMSelector** (2502.14815; +5–70% accuracy via per-module selection) optimize a system
*under an objective the practitioner already observes*; our setting is the prior one in which the
objective itself (cost) or a binding constraint is ⊥ — 41.3% of real queries are blocked because
`cost` is unobserved, so there is no objective to frugally minimize. These methods are
complementary: once the binding axes are measured, frugal optimization is exactly what should run
on the decidable slice.

## 2.2 Model papers — selective decision and a limit theorem

**Trust or Escalate** (Jung, Brahman, Choi; 2407.18370, ICLR 2025 Oral) is our model paper for
the *method and guarantee*: it makes an LLM judge selectively trust its own verdict under a
calibrated confidence, abstaining when unsure, with a distribution-free guarantee
`P(agree | evaluate) ≥ 1−α` via fixed-sequence testing, and reports a coverage–agreement curve.
We adapt its selective-commit shape to right-sizing — `P(feasible ∧ min-sufficient | commit) ≥
1−α` calibrated on a ground-truth slice — and differ on two axes that the §3 delta makes precise:
our decided object is a **multi-constraint feasibility-and-minimality** decision under
missingness (strictly harder than selective binary agreement), and our abstention is
**informative** — it does not merely decline but names the field to measure next via VoI, so the
escalation carries a measurement instruction rather than a refusal. **Limits to scalable
evaluation** (ICLR 2025 Oral, OpenReview NO6Tv6QcDs) is our model paper for the *limit theorem*:
where they prove a debiasing shortcut cannot reduce labels past a bound because a judge no better
than the evaluated model cannot help, we prove that a rule restricted to an evidence regime `R`
cannot drive expected mis-sizing below a positive bound `Δ(R)` when the binding axis lies outside
`R` — *accuracy/cost evidence won't beat measuring the binding axis* — confirmed empirically by
the regime-ladder plateau (decidability flatlines at 8.9% once cost and latency are added because
no further query's binding axis is recoverable). The slogans are deliberately parallel; the area
moves from learning theory to identifiability under partial observation.

## 2.3 A different layer — runtime serving, not pre-deployment decidability

**Circinus** (2504.16397) is an SLO-aware *runtime* query planner and **Cascadia** (2506.04203;
cf. routing+cascading 2410.10347) optimizes the *online* choice of which system to run per
request. These operate at serving time, choosing among systems whose properties are taken as
given; we operate *pre-deployment* and *evidentially*, asking whether the evidence identifies the
right configuration to deploy in the first place. They assume the axes are known and minimize
over them at runtime; we measure that the deciding axes are often ⊥ before runtime begins. The
two layers compose — our decidable slice is exactly the set of deployments a runtime router can
safely take as resolved — but they answer different questions and should not be conflated.

## 2.4 Summary of position

Prior work makes the estimate of each axis better (HELM, HAL, AI Agents That Matter), optimizes a
system under an observed objective (FrugalGPT, LLMSelector), or routes at runtime among known
systems (Circinus, Cascadia). None asks the identifiability question — *does the evidence
determine the right-sizing decision* — and so none can measure that, on real traffic, 91.1% of
decisions are underdetermined and the cause is the structural absence of the deployment-gating
axes. We adapt the selective-commit guarantee of Trust or Escalate and the limit-theorem shape of
Limits to scalable evaluation to that question, and add an informative VoI-guided abstention that
neither possesses.
