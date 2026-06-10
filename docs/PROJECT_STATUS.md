# APT — PROJECT STATUS (full-plan view)

> **Toàn bộ plan ở một chỗ.** This document maps every master-plan
> (`docs/plan/APT_MASTER_Plan_and_Harness.md`) deliverable to its current status and the
> evidence that backs it. Numbers are cross-checked against the findings docs
> (`docs/P3_*`, `docs/P4_*`, `docs/P5_*`, `docs/paper/A1_ablation.md`,
> `docs/paper/MOCK_REVIEW.md`) and the vault DAG (`.experiments/nodes/`).
> **Snapshot:** branch `exp/eyfl2u-final-hardening` (P6 final-hardening, active). Date 2026-06-10.
>
> Legend: ✅ done · 🟡 partial / in-progress · ⛔ deferred (theory) · ⬜ scoped-out.

---

## 1. The 7 phases (P0–P6)

| Phase | Deliverable (master §15) | Status | Vault node | Evidence file(s) | Headline result |
|---|---|---|---|---|---|
| **P0** Formalize + chốt venue | §5–§11 formalism spine + intro + model paper + theorem *statement* | ✅ done | (pre-DAG; specs) | `docs/plan/APT_P0_formalism_spine.md`, `APT_MASTER_Plan_and_Harness.md` | 3-state feasibility (§7), non-identifiability (§8), guarantee (§9), VoI (§10), limit-theorem statement (§11). ICLR method-star, model paper Trust-or-Escalate. |
| **P1** Evidential substrate | FK-enforced schema, {dist/interval/⊥}+confidence+evidence_id per axis, immutable C7 interface, data dictionary | ✅ done | **1pc3v3** | `src/prudent_ai/substrate/`, `docs/data_dictionary.md` | 7/7 tests; `test_interface_invariance` (two solvers → byte-identical substrate-call multiset) proves C7. 1/8 axes from HELM-Lite seed, 7/8 ⊥. |
| **P2** Scoped extraction (4 regimes) | Populate substrate across R1–R4, report κ/error rate, coverage log | ✅ done | **d5fnki** | `src/prudent_ai/substrate/{bfcl,mlperf,mlenergy}/`, `scripts/seed_p2.py` | **5/8 axes**, **3392 obs / 182 configs**, 4 real sources, zero stubs. 3/8 (memory_hw, governance, reviewer_burden) structurally ⊥. |
| **P3** Decidability map (8 axes) | Decidability map + blind-spot characterization + CI/sensitivity (DV1) | ✅ done | **u483mt** (grid) + **ana6e6** (empirical prior, closes gate Q2) | `docs/P3_decidability_map.md`, `docs/P3_empirical_query_prior.md`, `docs/paper/A1_ablation.md` | **91.1% real-traffic underdetermined** (1716 ZenML deployments), 100% accuracy-only, decidability tops 8.9%; 72.4% blocked by a corpus-wide-⊥ axis. **Anchor of C1.** |
| **P4** Selective procedure + guarantee + VoI | 3-state rule + VoI ranking + coverage guarantee + coverage–risk curve (§6/§9/§10) | ✅ done | **8v9cvt** | `docs/P4_selective_procedure.md`, `src/prudent_ai/solver/{procedure,voi,guarantee,cache}.py` | COMMIT 8.9% / ABSTAIN 91.1% / INFEASIBLE 0%; **VoI(a*)=Δ(R) exact** (rel_tol 1e-9, 4 pts); guarantee risk 0% @ coverage 10.5% (α=0.05/0.10). **Realizes C3.** |
| **P5** Validation (Oral pillar, 4 axes) | V1 mask-and-predict vs B1–B6 + V2 VoI-acquisition + coverage–risk, with significance | ✅ done (V1+V2 + scaled); V3 ⛔ stretch | **4iezqz** (RouterBench GT data) → **jal8id** (V1/V2 pilot) → scaled in **worcj5** | `docs/P5_validation.md`, `outputs/p5/validation_scaled.{json,md}`, `docs/paper/07_evaluation.md` | **7 biting slices / 119 queries**: B2/B3/B6 HVR **0.882** vs selective **0.0**; gap **0.8824 [0.824, 0.941]**, McNemar **105/0**, **p≈0 SIGNIFICANT**. V2 VoI-lift 1.0 vs 0.2. **Proves C2.** |
| **P6** Write / ablation / rebuttal-proof / talk | Full paper, evidence-regime ablation, repro package, figures, mock review ≥ Oral bar | ✅ done (concrete) · 🟡 polish + theory-gap remain | **worcj5** (paper+scale) → **tfumqf** (figures+ablation+mock) → **eyfl2u** (final hardening, active) | `docs/paper/*.md` (10 §), `docs/paper/figures/*.png` (5), `docs/paper/A1_ablation.md`, `docs/paper/MOCK_REVIEW.md`, `REPRODUCE.md` | Paper drafted (~1786 lines), 5 figures from frozen data, ablation tied to limit theorem, mock review **Spotlight-leaning-Oral** (N8/S7/Sig8/C8). W2 fixed; W1/W7 deferred. |

**Phase summary:** P0–P5 done; P6 concrete deliverables done. Post-hardening nodes closed
**every empirical attack surface**: `zh6apu` (W11: positive COMMIT validated + V2-lift
n=527), `c90ge4` (W1: per-instance binding Pareto-recovered, `bite⟺binding` 1.0), `mfxhvu`
(W4-residual min-sufficiency guarantee + Q3 regret>Δ(R) + W2), `ksmbut` (V3 prospective
live-eval). The **theory** gate (W7/Q1) is now **substantially addressed** by `2o35sq`
(`docs/theory/W7_closure_characterization.md`): `cl(R)` proven a closure operator, the
multi-axis characterization rigorous under the value reading, the limit theorem sharpened
to cl(R)-restricted rules + general VoI corollary — Opus-authored, orchestrator
adversarially-verified. Three honest theory checkpoints remain for a human collaborator
((G3) form-regularity, `Bind*` vs `bind(θ*)`, the monotone-discontinuous edge) plus the C1
magnitude on binding-unrecoverable ⊥ axes; **none blocks C1–C3**. The "drop the theorem /
NeurIPS-ED fallback" is no longer forced.

---

## 2. The 3 claims (C1 / C2 / C3)

| Claim | Statement (master §1) | DV that proves it | Status | Headline number | Significance |
|---|---|---|---|---|---|
| **C1** (measurement) | On real deployment traffic, many right-sizing decisions are **evidence-underdetermined** due to **structured** missingness (all 8 axes). | **DV1** (P3, decidability map over the empirical ZenML prior) | ✅ evidenced | **91.1% underdetermined** (1563/1716) at full regime; 100% accuracy-only; **72.4%** blocked by a corpus-wide-⊥ axis | 95% CI [89.7, 92.4]; κ-robust (≥89.3%); tag-drop-one robust (≥83.2%); grid→empirical **Δ +5.4%** (sharpens, not cherry-picks) |
| **C2** (x>y, gây đau) | Leaderboard-style rules **answer anyway** and **mis-size measurably** (4 measurable axes). | **DV2** (regret) + **DV3** (hidden-violation), P5 V1, vs B2/B3 | ✅ evidenced, **SIGNIFICANT** | hidden-violation **0.882** (B2=B3=B6) vs selective **0.0**, gap **0.8824** across 7 slices / 119 queries | **95% CI [0.8235, 0.9412]** excl. 0; **McNemar 105/0**; one-sided exact-binomial **p≈0**; every slice individually significant. (DV2 regret degenerate-by-violation → DV3 carries it; W10.) **W1 empirical-closed** (node `c90ge4`): the biting axes are Pareto-certified binding per-instance, `bite⟺binding` agreement **1.0**, so the gap is on *truly*-binding axes not declared. |
| **C3** (method) | 3-state selective procedure + **VoI** + **coverage guarantee** — abstain *informatively* (name the field to measure), commit only when ≥1−α correct. | **DV4** (coverage–risk) + **DV5** (VoI-lift) + **DV8** (regret), P4 + P5 V2 + commit-validation | ✅ evidenced, **real-GT calibrated** | VoI(a*)=Δ(R) exact; **feasibility ∧ min-sufficiency both guaranteed on real held-out GT** (min-suff 4.9%@α=0.05 via band); V2 VoI **1.0 vs 0.129** (n=527, McNemar 459/0); **positive COMMIT validated** (527, feasible 1.0, min-suff 1.0); real regret > Δ(R) (Q3) | VoI=Δ(R) rel_tol 1e-9; **W11 closed** (`zh6apu`), **W4 residual closed** (`mfxhvu`: min-suff band), **Q3 closed** (`mfxhvu`) |

**Claim→proof map (master §16.241):** C1 ← DV1 (P3, 8 axes) · C2 ← DV2+DV3 (P5 V1, 4 axes, vs B2/B3) · C3 ← DV4+DV5 (P4+P5 V2). All three have working, significance-backed (C1/C2) or exact-identity (C3) evidence.

---

## 3. DV1–DV5 (master §16) — measured?

| DV | Construct | Measured? | Value | Where |
|---|---|---|---|---|
| **DV1** decidability | % decidable / underdetermined / infeasible under E | ✅ yes | **8.9% / 91.1% / 0%** (real prior, full regime); 0/100/0 accuracy-only | `docs/P3_empirical_query_prior.md` §3.2; `outputs/p3/empirical_prior_map.json` |
| **DV2** decision regret | cost overshoot vs true min-sufficient | 🟡 measured-but-degenerate | **0.0** on biting slices (blind commits are *infeasible*, contribute a violation not a regret-overshoot); informative only on control (B1 regret 84.6 mask-latency) | `docs/P5_validation.md` §3, §6.3; W10 in mock review |
| **DV3** hidden-violation rate | % baseline commits that silently violate the masked truth | ✅ yes — **load-bearing** | selective **0.0** vs B2/B3/B6 **0.882** pooled (per-slice 0.71–1.00) | `docs/P5_validation.md` §3, §7; `outputs/p5/validation_scaled.json`; `docs/paper/07_evaluation.md` |
| **DV4** coverage–risk | coverage at guarantee 1−α (feasible **∧ min-sufficient**) | ✅ yes, **real held-out GT** | feasibility test-risk ≤ α @ cov **89%** (node `eyfl2u`); **min-sufficiency** test-risk ≤ α via two-sided band (node `mfxhvu`): **4.9% @ α=0.05**, cov 12.7% (vs 65.8% one-sided) | `docs/W4_minsuff_Q3_regret.md` §1; `outputs/p4/{coverage_risk_gt,minsuff_guarantee}.json` |
| **DV8** regret vs Δ(R) | real mis-sizing magnitude vs the theorem floor (Q3) | ✅ yes | **Δ(R) ≤ min(δ,λ) on 41/41** biting slices; mean over-provision premium **0.748**; closed-form = proven gadget minimax (gap 8.7e-19) | `docs/W4_minsuff_Q3_regret.md` §2; `outputs/p4/q3_regret.json` |
| **DV9** prospective live-eval | commits generalize to held-out FUTURE traffic (V3) | ✅ yes (prompt-split surrogate) | blind cost-min **36.6%** live-violation vs selective **14.4%** (m=0.05) / **3.8%** (m=0.10); live-violation monotone ↓ in margin, 960 queries | `docs/V3_live_eval.md`; `outputs/p5/v3_live.json` |
| **DV5** VoI lift | regret reduction measuring top-VoI vs random | ✅ yes, **SIGNIFICANT (n=527)** | V2 scaled: VoI-pick commit-correct **1.000 (527/527)** vs random **0.129**, McNemar **459/0**, p≪0.05 (H-only 510, 445/0); P4 cost-aware VoI/cost lift 1.03× | `docs/P5_commit_branch_voi.md` §2; `outputs/p5/commit_voi.json` (`scale_v2`) |
| **DV6** COMMIT validity | positive COMMIT feasible + min-sufficient on biting slices (W11) | ✅ yes | **527 commits**, feasible_frac **1.0**, min_sufficient_frac **1.0**, regret 0; dual: same 527 ABSTAIN when blind | `docs/P5_commit_branch_voi.md` §1; `outputs/p5/commit_voi.json` (`commit_validation`) |
| **DV7** per-instance binding | C2 bite is on *Pareto-certified* binding axes, not declared (W1) | ✅ yes | **bite⟺binding agreement 1.0** (287 bind&bite / 257 nonbind&no-bite / 0 off-diag); C2 on certified-binding subset B2 1.0 vs sel 0.0; latency control 0.0 binding | `docs/W1_per_instance_binding.md`; `outputs/p5/w1_binding.json` (`binding_certification`) |

---

## 4. Baseline lattice B1–B6 (master §14)

All implemented as `DecisionRule.decide()` over the same C7 interface (`validation/baselines.py`).

| | Baseline | Implemented? | Role | Measured behaviour (biting slices) |
|---|---|---|---|---|
| **B1** | accuracy-only ranking | ✅ | strawman | abstains/ignores cost on the biting mask (HVR 0.0 there; HVR 0.2, regret 84.6 on mask-latency control) |
| **B2** | observed-Pareto (lờ missingness) | ✅ | **honest current practice — MUST beat** | **HVR 0.882** (commits a blind config every time) — beaten |
| **B3** | imputation (median/model) | ✅ | **"just fill it in" — MUST beat** | **HVR 0.882 ≡ B2** (imputing the median commits the same blind config — the sharpest rebuttal) — beaten |
| **B4** | missing-as-fail (conservative) | ✅ | upper bound: 0 hidden-violation, abstains | abstains → HVR 0.0 (delta of *ours* over B4 = the **informative** VoI abstention; W11) |
| **B5** | oracle-full-evidence | ✅ | **regret floor** | sees masked truth → HVR 0.0, commits the true min-sufficient (configs exist; blind rules can't find them) |
| **B6** | HAL/FrugalGPT cost-accuracy frontier | ✅ | domain rival (drops latency/energy/gov) | **HVR 0.882 ≡ B2** — beaten |

**"Claim cứng" check (§14):** hidden-violation(proc)=0 ≪ B2/B3/B6=0.882 ✅; VoI-lift top>random (1.0 vs 0.2) ✅. `regret(proc)<regret(B2)` is vacuous (DV2 degenerate) — DV3 carries the hard claim.

---

## 5. Data regimes / sources (master §13)

| Source | Regime | Status | Axes contributed | Confidence | Role |
|---|---|---|---|---|---|
| **HELM Lite** | R1 model-quality | ✅ ingested | quality, latency_p95 | M (leaderboard) | P1 seed + general-qa evidence input |
| **BFCL** | R2 agent+cost | ✅ ingested | quality, cost, latency_p95 | **M** | function-calling τ; the (M-confidence) **illustrative** C2 biting slice (W5) |
| **MLPerf Inference** v5.0 | R3 serving/latency | ✅ ingested | throughput, latency_p95 | M | inference-serving τ |
| **ML.ENERGY** | R4 energy | ✅ ingested | energy, throughput, latency_p95 | M | energy axis; excluded from V1 (no cost axis → cost-oracle can't score) |
| **RouterBench** (GT) | +routing | ✅ ingested | quality + cost **co-located** | **H (measured)** | the **flagship H-confidence validation** slice — 6 per-benchmark biting slices carry the C2 significance |
| **ZenML LLMOps DB** (prior) | query-dist | ✅ ingested | — (1716 deployments → query prior) | — | the empirical query prior; closes gate Q2 (distribution level) |
| **HAL** | R2 agent+cost | ⬜ scoped-out | — | — | only 380 *encrypted* raw-trace zips, no reachable aggregate → disproportionate for V1. Documented future source / nearest-threat model paper, **not silent debt** (node 4iezqz) |
| **MedHELM** (prior) | query-dist + gov blind-spot | 🟡 gated | — | — | **HTTP 401** (access-gated) at snapshot → prior is ZenML-only (W3). A medical/high-gov corpus would *raise* the 55.6% governance load → ZenML is conservative |

Substrate totals after P5 data: **4052 observations / 512 configs / 4 τ** (general-qa, function-calling, inference-serving, routerbench). 5/8 axes carry evidence; memory_hw, governance, reviewer_burden ⊥ everywhere (miss-rate 1.000).

**Update (node `zdnpkh`): +MedHELM via the generalized `helm_suite` seam.** Now **6 sources / 4557 obs / 5 τ** (+`medical-qa`, 9 configs); +198 quality + 307 latency obs (quality kept strictly [0,1]; jury-rated 1–5 clinical scenarios skipped, logged). **§13 governance blind-spot test confirmed:** even MedHELM (clinical, Stanford Health Care) reports **0 governance / 0 reviewer_burden / 0 memory_hw** — the 3 hard-to-observe axes stay structurally ⊥ in the governance-heaviest domain, *strengthening* C1. More HELM suites (capabilities/classic/mmlu/safety/air-bench) plug in via one `SuiteSpec`+`SourceSpec` line each.
**Axis split (§13):** decidability map (C1) uses all 8 axes; x>y validation (C2/C3) runs only the 4 measurable axes where GT exists.

---

## 6. §18.1 reviewer-attack ledger — disposition

From `docs/paper/MOCK_REVIEW.md` (Area-Chair-level adversarial review). Disposition: **closed** / **mitigated** / **open-theory**.

| §18.1 attack | Disposition | Evidence |
|---|---|---|
| "Missing metrics is obvious" | **closed** | C2 is decision-level mis-sizing, not cell-level missingness; HVR 0.882 vs 0.0, significant |
| "'Undecidable' overclaiming" | **closed (resolved)** | reframed as non-identifiability (§8) via completions; bootstrap CIs anchor it statistically |
| "Just chance-constrained opt with a label" | **mitigated (minor)** | novelty is the 3-state + VoI-on-evidential-substrate + the decidability *measurement*, not the solver |
| "Imputation solves it" | **closed (strongly)** | B3 HVR ≡ B2 (0.882) — imputing the median commits the identical blind config |
| "Guarantee = ported selective classification" | **mitigated (minor)** | multi-constraint object (feasibility ∧ min-sufficiency), evidence-regime-indexed, informative abstention (VoI) |
| "Limit theorem trivial" | **open-theory (W7)** | VoI=Δ(R) exact only on a 2-world gadget; general necessity + §8.6 closure `decidable⇔bind(q)⊆cl(R)` empirically-shadowed, not proven → deferred (Q1, `OPEN_QUESTIONS.md`); honest flag = downgrade theorem or retreat to NeurIPS-ED |
| "HAL already did this" | **mitigated (minor, W12)** | HAL improves the *estimate*; APT asks *when a conclusion is valid on evidence*. HAL still zero governance/burden/memory_hw → ⊥-driven 72.4% headline unaffected. Asserted, not yet stress-tested (HAL not ingested) |
| "No real deployment" | **open / mitigated (W4, W9)** | guarantee on proxy-truth not held-out GT (W4); mask-and-predict *simulates* missingness (W9). C2 *direction* scored vs unmasked measured value. V3 live runs = honest next step |
| "Governance/burden never validated" | **reframed (the C1 finding) + mitigated (W9)** | their absence *is* C1 (⊥ everywhere, bind 55.6%/43.8%); validation necessarily runs on the 4 measurable axes; mechanism transfers by the structural argument |

**New attacks raised by the mock review** (beyond §18.1): W1 per-instance binding gap (**CRITICAL, open-theory** → Q2); W2 §1↔§7 number inconsistency (**MAJOR — FIXED**, §1 now leads with the scaled numbers); W3 single-corpus prior; W5 M-confidence BFCL flagship; W6 small battery; W11 COMMIT branch rarely exercised. W3/W5/W6 are the targets of the active `eyfl2u` hardening node.

---

## 7. The vault DAG (all nodes in order)

Linear chain, one node per phase-step, each a `completed` experiment except the active leaf:

```
1pc3v3  (P1 evidential-substrate, ✅)
  └─ d5fnki  (P2 scoped-extraction, ✅)
       └─ u483mt  (P3 decidability-map / grid, ✅)
            └─ ana6e6  (P3 empirical-query-prior — closes gate Q2, ✅)
                 └─ 8v9cvt  (P4 selective-procedure + VoI + guarantee, ✅)
                      └─ 4iezqz  (P5 validation-data / RouterBench GT, ✅)
                           └─ jal8id  (P5 validation-v1 / V1+V2 pilot, ✅)
                                └─ worcj5  (P6 paper + scale-to-significance, ✅)
                                     └─ tfumqf  (P6 figures + ablation + mock-review, ✅)
                                          └─ eyfl2u  (P6 final-hardening, ACTIVE ← current branch)
```

10 nodes, all on `exp/<id>-<slug>` branches off `triquang26/prudent-ai`. The current branch is `exp/eyfl2u-final-hardening`.

---

## 8. Open items

### Deferred theory (`docs/OPEN_QUESTIONS.md`) — DO NOT attempt without a theory pass / collaborator

| Item | What | Maps to | Status |
|---|---|---|---|
| **W1 / Q2** | Per-instance binding: tags give *salient*/declared axes, not the axis that **binds at the optimum**. The 91.1% is computed on a conservative over-approximation. | mock-review **W1 (CRITICAL for Oral)** | ⛔ deferred. Mitigation on record: promote the binding-independent attribution (72.4%/16.0%) + structural facts; a Pareto-recovered/audited `bind(q)` lower bound would close it |
| **W7 / Q1** | Closure characterization `cl(R)` + general necessity lower bound in full generality (`decidable ⇔ bind(q) ⊆ cl(R)`). Gadget-level identity stands; general theorem open. | mock-review **W7 (MAJOR)** | ⛔ deferred. Honest flag (§11/§18.1): if not clean → drop theorem, retreat to NeurIPS-ED |
| **Q3** | Whether real mis-sizing magnitude *exceeds* Δ(R) (cost–latency–energy correlation). | §8.8 / §11 Q3 | ⛔ deferred (empirical, partly P5; DV2 degenerate so magnitude not yet vs Δ(R)) |
| **Q4** | Implemented VoI *numerically tracks* achievable regret reduction on real data (beyond the gadget + V2 1.0-vs-0.2). | §11 Q4 | ⛔ deferred |
| — | Distribution-free guarantee on a **true held-out** GT slice (currently proxy-κ). | W4 | 🟡 in scope for `eyfl2u` (real-GT calibration) |
| — | V3 live deployment runs (vLLM energy + small governance/burden human study). | §15 P5 V3 | ⛔ stretch, resource-gated |

### Remaining presentation polish (in scope for the active `eyfl2u` node)

- **W5** — foreground the 6 **H-confidence RouterBench** slices as flagship; report pooled significance restricted to them (drop M-confidence BFCL to illustration).
- **W6** — scale the validation battery to *all* RouterBench benchmark slices for larger n; scale V2 beyond n=5 so the informative-abstention delta over B4 is significant.
- **W4** — calibrate the coverage guarantee on a real held-out GT slice instead of the κ-proxy.
- **W3** — show the decidability headline is robust to an alternative non-ZenML (uniform/benchmark-derived) query prior.
- Re-run the adversarial mock review with the strengthened numbers; update intro/findings/evaluation + affected figures.
- `/exp-publish` blocked: `gh` CLI not yet installed/authenticated on this host.

---

## Bottom line

The 7-phase harness is complete end-to-end (P1→P6) with reproducible, significance-backed
evidence for all three claims: **C1** — 91.1% of real-traffic right-sizing decisions are
evidence-underdetermined (1716 ZenML deployments, 72.4% blocked by a corpus-wide-⊥ axis,
κ- and tag-robust); **C2** — leaderboard-style rules silently mis-size on 88.2% of commits
versus 0% for the selective procedure across 7 biting slices / 119 queries, significant
(95% CI [0.82, 0.94], McNemar 105/0, p≈0, every slice individually), with imputation refuted
by a number (B3≡B2); and **C3** — a 3-state selective procedure whose informative abstention
names the field to measure, anchored by the exact identity VoI(a*)=Δ(R), under a
coverage guarantee (0% risk at ~10.5% coverage on proxy-truth). Against the Oral bar
(§3/§18.2 = sharp reframe × surprising measurement × validation beating B2/B3 with
significance × theorem+guarantee), the first three legs are met convincingly; the
independent mock review places the work at **Spotlight leaning Oral-if-revised**, with the
only gaps being (i) the deferred theory — the per-instance binding over-approximation (W1)
and the gadget-level limit theorem (W7), both honestly logged in `OPEN_QUESTIONS.md` and
either downgradeable to a clean anchoring identity or a retreat to NeurIPS-ED per the §11
honest flag — and (ii) presentation hardening (W3–W6: H-confidence flagship, bigger battery,
real-GT calibration, second corpus) now being executed in the active `eyfl2u` node. Direction:
decisively right; statistics on C1/C2: significant; the residual is theory-pass + polish, not a
flaw in the measurement or the validation.
