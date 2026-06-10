# APT — Evidence-Decidability of AI Deployment Right-Sizing

**Paper assembly index.** This directory holds the paper in section files, read in order
`01 → 09`. Every number is regenerated from the frozen substrate `data/apt_substrate.db`
and the 1716-deployment query prior; reproduction instructions and the test gate are in
§9. Venue: **ICLR**, method-star framing (selective right-sizing + coverage guarantee +
limit theorem); model paper **Trust-or-Escalate** (arXiv 2407.18370).

## Abstract

Practitioners size AI deployments — which model, context, retrieval, orchestration — against
public evaluation evidence, on the tacit assumption that the open problem is *estimate
quality*. We flip the prior question to *sufficiency*: given the evidence that actually
exists, is a right-sizing decision *identified at all*? We formalize evidence-decidability
under partial observation, build an evidential substrate that stores observations with
provenance and derives missingness ($\bot$) from absence, and measure a decidability map over
real deployment traffic. On 1716 real LLM deployments, **91.1%** of right-sizing decisions are
evidence-*underdetermined*, and the cause is **structured**: a majority bind operational axes
— governance (55.6%), reviewer-burden (43.8%) — that are $\bot$ in **every** public corpus. We
then give a three-state selective procedure that **commits** only when the decision is
identified and otherwise **abstains informatively**, returning the blocking set and a
VoI-ranked instruction for what to measure next, with a distribution-free coverage guarantee
and an exact identity $\mathrm{VoI}(a^\*)=\Delta(R)=\delta\lambda/(\delta+\lambda)$ linking
acquisition value to the irreducible-regret floor. On biting slices, commit-while-blind
leaderboard rules hidden-violate on 100% of commits while our rule's hidden-violation rate is
0.0 — it refuses precisely when it cannot see.

## Section index

| § | File | Contents |
|---|---|---|
| 1 | [01_intro.md](01_intro.md) | Motivation, the sufficiency reframe, claims C1–C3, contributions |
| 2 | [02_related.md](02_related.md) | Positioning vs HELM, HAL, AI-Agents-That-Matter, FrugalGPT, Trust-or-Escalate |
| 3 | [03_formulation.md](03_formulation.md) | Problem formulation: archetypes, 8 axes, $\bot$, evidence-decidability |
| 4 | [04_system_data.md](04_system_data.md) | The evidential substrate, the C7 firewall, corpora, the real-traffic prior |
| 5 | [05_findings.md](05_findings.md) | **C1** — the decidability map; 91.1% underdetermined; structured missingness |
| 6 | [06_method.md](06_method.md) | **C3** — selective right-sizing: 3-state rule, VoI, coverage guarantee |
| 7 | [07_evaluation.md](07_evaluation.md) | **C2** — V1/V2 validation: selective HVR 0.0 vs B2/B3/B6 1.0; VoI lift |
| 8 | [08_threats.md](08_threats.md) | Threats, limitations, the structured-$\bot$ frontier, future work |
| 9 | [09_repro_talk.md](09_repro_talk.md) | Reproducibility, RAI metadata, and the talk outline |

## Venue note

- **Star:** the *method* — selective right-sizing with a distribution-free coverage guarantee
  and the $\mathrm{VoI}(a^\*)=\Delta(R)$ limit-theorem identity (ICLR method-paper shape).
- **Model paper:** **Trust or Escalate** (arXiv 2407.18370) — same selective/abstention shape;
  we extend it from a single quality axis to multi-axis right-sizing with *measured* hidden
  constraint violations and an explicit "what to measure next" instead of a mute decline.

## Current status — honest Go/No-Go

**HOLD-on-Oral.** The reframe (C1), the procedure with its guarantee (C3), and the
direction-correct validation (C2: selective hidden-violation 0.0 vs leaderboard 1.0; VoI pick
commit-correct 1.0 vs random 0.2) are all in place and reproducible (43/43 tests green, §9).
What is *not yet* oral-grade is **scaled significance**: the C2/C3 effects are demonstrated on
small biting slices (5 abstentions on the BFCL mask-quality case), and two honest no-bite cases
(RouterBench cross-benchmark confound; BFCL mask-latency) are reported as such, not hidden. The
go-decision is gated on scaling the biting slices to significance and closing the
governance/reviewer-burden evidence gap the map exposes; until then the position is a strong
poster with a credible path to oral, not an oral claim.
