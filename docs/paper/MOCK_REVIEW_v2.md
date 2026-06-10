# Mock Review v2 — APT (Evidence-Decidability of AI Deployment Right-Sizing)

> **Venue / bar:** ICLR, Oral track. **Reviewer stance:** Area-Chair-level, adversarial-but-fair.
> **This is a re-review AFTER the W3/W4/W5/W6 hardening pass.** It supersedes `MOCK_REVIEW.md`.
> Every prior-weakness verdict below is re-derived from the *new* artifacts, not from the previous
> review's prose. New numbers are quoted verbatim from:
> - `outputs/p3/prior_robustness.md` (W3 — four-prior robustness)
> - `outputs/p4/coverage_risk_gt.md` (W4 — real-GT coverage–risk guarantee)
> - `outputs/p5/validation_scaled.md` (W5+W6 — scaled battery, H-only flagship)
>
> The mandate is the same as v1: harden, not flatter. The bottom-line question is whether closing
> W3/W4/W5/W6 moved the paper toward Oral, and what the single remaining gate is.

---

## 0. What changed since v1 (the hardening delta)

The v1 review (`MOCK_REVIEW.md`) scored **Spotlight (Oral-if-revised)** and listed, among the prior
weaknesses, four that were *evidence-closable* (W3 single-corpus prior, W4 proxy-truth guarantee,
W5 M-confidence flagship, W6 small battery) and two that were *theory-deferred* (W1 per-instance
binding, W7 gadget-level theorem). The hardening pass attacked exactly the four closable ones. It
did **not** touch W1/W7 — correctly, since `docs/OPEN_QUESTIONS.md` defers them deliberately, and the
task brief forbids attempting them. So this re-review is an honest test of one thesis: *did closing
the empirical weaknesses, while leaving the theory gate untouched, move the paper to Oral?*

The W2 §1↔§7 editing inconsistency from v1 is an in-text fix (rewrite the intro to lead with the
scaled numbers) and is orthogonal to the new artifacts; I treat it as a still-required edit, not a
new finding, and note below that the scaled numbers it must point to are now even stronger.

---

## 1. Re-assessment of each prior weakness with the new evidence

### W3 — Single-corpus query prior (ZenML only). **v1: MAJOR → v2: ADDRESSED (downgraded to MINOR).**

**New evidence (`prior_robustness.md`).** The headline was recomputed under four priors over an
identical C7 path (`classify_query`, FULL regime, κ=H+M, φ=POINT, battery=1716/prior, seed=12345),
and the recomputed ZenML reference reproduces **91.1% exactly** — so the comparison is apples-to-apples.

| prior | %underdetermined | Δ vs ZenML 91.1% | %attrib. to a ⊥ (corpus-wide-unmeasurable) axis | survives? |
|---|---|---|---|---|
| ZenML (reference) | 91.1% | — | 72.4% | — |
| Uniform (every axis p=0.5) | **98.5%** | +7.4% | **94.2%** | YES |
| Adversarial governance-light (gov/rev p=0.05) | **95.7%** | +4.6% | **84.5%** | YES |
| Benchmark-derived (∝ substrate coverage) | 12.4% | −78.7% | 0.0% | negative control |

**Verdict.** This is the cleanest of the four closures. The headline survives **two genuinely
independent, ZenML-bias-stripping priors** — including an *adversarial* one that assumes governance
and reviewer_burden almost never bind (p=0.05) and *still* yields 95.7% underdetermined with 84.5%
attributable to a corpus-wide blind-spot axis. The negative control (benchmark-derived prior, which
demands only what the corpus measures) collapses to 12.4% / 0.0%-blind-spot, which *confirms the
causal story in reverse*: underdetermination is caused specifically by deployments binding axes the
evidence corpus does not cover. This is materially stronger than the v1 "direction argument" (which
was a hand-wave that MedHELM would only raise governance load). It is now demonstrated, not argued.

**Residual.** All four priors are *synthetic* re-weightings over the *same substrate*; this is
robustness to the **query distribution**, not to **corpus-selection** of which deployments get
indexed (the deeper v1 W3 concern, and what a true second corpus like MedHELM would address). So
W3 is not fully resolved — but the synthetic adversarial prior is a strong stand-in, and the
structural facts are corpus-independent. Downgrade MAJOR → MINOR.

---

### W4 — "Truth" is proxy, not real ground truth. **v1: MAJOR → v2: PARTIALLY ADDRESSED.**

**New evidence (`coverage_risk_gt.md`).** The v1 guarantee calibrated against a *κ-proxy* truth
(`κ_truth = H+M+L`) — "0% risk against my own richer self." The new `GTCoverageGuarantee` replaces
that with **genuine measured ground truth**: TRUTH = full-sample per-model mean quality+cost from the
RouterBench pkl; operating evidence = a seeded bootstrap subsample of K=64 prompts (the noisy
small-battery regime). 6 RouterBench benchmarks, 11 models, q* percentiles {0.4,0.55,0.7,0.85},
40 resamples/(benchmark,q*), **n=960 decision instances**, with a **seeded disjoint 50/50
calib/test split** (margin chosen on calib only, applied to held-out test — no leakage). Scoring
reads the pkl directly, so C7 is not engaged (clean).

| α (target) | margin | test cov | **test feasibility-risk** | holds? |
|---|---|---|---|---|
| 0.05 | 0.07 | 89.0% | **4.7%** | ✅ (≤ 0.05) |
| 0.10 | 0.05 | 92.7% | **8.1%** | ✅ (≤ 0.10) |

**Verdict.** This is a real upgrade: the **PRIMARY feasibility guarantee** —
`P(committed config truly violates q* | commit) ≤ α` — now holds against *external held-out measured
truth*, transfers across the calib/test split, and the margin reduces risk monotonically (the
conformal-style knob works as claimed). v1's central W4 complaint ("not validated against any
independent oracle") is answered for the feasibility/safety leg, which is precisely the B2/B3 /
§9 hidden-violation quantity that the whole paper is about.

**Residual — and the authors report it honestly, which I credit.** The **SECONDARY strict
min-sufficiency risk** (feasible ∧ cost ≤ 1.25× cheapest-feasible) does **NOT** fall with the
margin — it *rises* (43.8% → 83.8% as margin grows), because a one-sided quality margin makes the
procedure over-provision: safe but no longer cheapest. So the full `feasible ∧ min-sufficient`
guarantee — the literal C3 statement — is **not** delivered against real GT; only its feasibility
half is. That is a genuine, honestly-flagged limitation: the guarantee that holds is *safety*, not
*optimal right-sizing*. PARTIALLY ADDRESSED — the safety guarantee is now real-GT-backed; the
min-sufficiency guarantee is still only proxy/aspirational and the paper must say so in the C3 claim.

---

### W5 — M-confidence BFCL drives the flagship slice. **v1: MAJOR → v2: ADDRESSED (resolved).**

**New evidence (`validation_scaled.md`, "Pooled significance — H-CONFIDENCE ONLY (FLAGSHIP)").** The
pooled C2 test is now reported **restricted to the H-confidence RouterBench slices alone, excluding
the M-confidence BFCL slice** — exactly the v1 "evidence that closes it":

| pool | n | HV(baseline) | HV(selective) | difference | 95% CI | binom p | significant |
|---|---|---|---|---|---|---|---|
| All biting (H+M) | 493 | 0.5821 | 0.0000 | 0.5821 | [0.5375, 0.6247] | 0.00e+00 | YES |
| **H-confidence only (flagship)** | **476** | **0.5714** | **0.0000** | **0.5714** | **[0.5273, 0.6176]** | **0.00e+00** | **YES** |

**Verdict.** Resolved. The flagship C2 result no longer depends on *any* M-tier truth: dropping BFCL
moves the pooled difference only from 0.5821 → 0.5714, the CI still excludes zero comfortably
([0.5273, 0.6176]), and p is still 0 to machine precision. The C2 significance is carried entirely
by H-confidence, real-measured-GT RouterBench slices. The v1 worry that "the hidden-violation scoring
inherits leaderboard noise" is now moot for the headline — BFCL is demonstrably an illustrative
instance, not a load-bearing one.

---

### W6 — Small-ish batteries (119 queries, 7 slices, 11 models, V2 n=5). **v1: MAJOR → v2: ADDRESSED (resolved for the breadth concern).**

**New evidence (`validation_scaled.md`).** The battery was auto-discovered across *every* well-posed
RouterBench per-benchmark slice (new `discover_routerbench_benchmarks()`, C7-clean), degenerate
slices below `min_feasible_configs` skipped. The scale jumped from the v1 figures to:

- **31 slices total, 29 biting (28 H-confidence)**, **527 total queries** (493 on biting slices, 476
  on H-confidence biting slices) — vs v1's 7 slices / 119 queries. Roughly **4× the slices and 4× the
  queries**, and a **6.8×** larger H-confidence pooled n (476 vs ~70).
- Per-slice HVR spread is wide and reported in full: from **1.0000** (bias_detection,
  grade-school-math, mtbench-reference) down through the mid-range (0.47–0.76) to **0.0588**
  (chinese-remainder-theorem, chinese_homonym) and genuine **non-significant** slices
  (chinese-remainder-theorem p=0.50, chinese_poem/chinese_modern_poem/chinese_ancient_poetry
  p=0.0625) — *not all slices bite hard*, which is healthy and answers the v1 "designed inevitability"
  critique: the experiment **can** produce near-zero, non-significant slices, and does.
- Two explicit **no-bite slices** (chinese_chu_ci, test-match: every baseline HVR = 0) are retained
  as falsification opportunities the design passed by *not* biting.

**Verdict.** The breadth concern is resolved: 476 H-confidence queries across 28 biting slices, with
a fully reported per-slice HVR distribution that includes non-significant and zero-bite cases, is no
longer dismissible as "a designed inevitability on a tiny battery." The McNemar/binomial machinery is
now applied per-slice across ~30 slices and the pattern (selective = 0 hidden-violations everywhere;
baselines spread 0.06→1.00) is robust, not categorical-by-construction.

**Residual (carries to W1, not W6).** The **V2 VoI-lift is still n=5** — the scaling effort grew the
*V1 hidden-violation battery*, not the *V2 informative-abstention* leg. So the "informative abstain >
mute abstain (B4)" delta is still pilot-scale. And the structural point from v1 W6/W11 remains: every
biting slice still has selective **coverage = 0.0000** (it *abstains* on all biting slices), so the
battery validates *when to abstain*, never *a correct positive COMMIT*. That is no longer a battery-
size problem (W6 is closed) — it is the W1/W11 substance, addressed below.

> **UPDATE — node `zh6apu-commit-branch-voi-scale` (closes W11 + the V2-lift residual).** Both
> halves of this residual are now retired (`outputs/p5/commit_voi.json`, [`P5_commit_branch_voi.md`](../P5_commit_branch_voi.md)):
> - **V2-lift scaled (`scale_v2`):** pooled over BFCL + all per-benchmark RouterBench slices,
>   VoI-pick commit-correct **1.000 (527/527)** vs random **0.129**, McNemar **459/0**, one-sided
>   binomial p ≪ 0.05 — and the same at **H-only (510, 445/0)**. The n=5 pilot was not an artefact.
> - **Positive COMMIT validated (`commit_validation`):** running the procedure under the *full*
>   regime on the same biting slices, it COMMITs **527** configs, **feasible_frac=1.0**,
>   **min_sufficient_frac=1.0**, regret 0; the dual confirms all 527 ABSTAIN when the axis is masked.
>   So selective abstains when blind AND commits correctly when sighted. W11 is closed; the only
>   remaining Oral gate is the **W1/Q2** theory item (per-instance binding), still deferred.

---

## 2. The remaining DEFERRED-theory blockers (unchanged by the hardening)

### W1 — The per-instance binding gap (Open-Q2). **Severity: CRITICAL for Oral. STILL OPEN.**

Untouched, by design (`docs/OPEN_QUESTIONS.md` Q2; task brief defers it). The 91.1% headline is still
computed on `bind(q)` as the **declared/salient** axes recovered from tags, a conservative
*over-approximation* of the axes *active at the optimum*. The paper's own mask-latency no-bite control
still proves declared ≠ binding is material.

**Does the new W3 evidence help here?** Partially, and this is worth stating precisely. The
prior-robustness result shows the headline survives even an **adversarial governance-light prior**
(gov/rev p=0.05) at 95.7% underdetermined, with 84.5% attributable to a ⊥ axis. That partly defangs
the *specific* W1 mechanism — "governance is declared-but-co-satisfied so the 91.1% is inflated" —
because even when governance/reviewer_burden are assumed to almost never bind, the underdetermination
persists, now driven by cost/memory_hw/energy. So **W3 narrows W1's blast radius**: the headline is
not *solely* an artifact of over-counting the two governance-family axes. But it does **not close
W1**: the adversarial prior is still a *synthetic re-weighting of declared binding*, not a recovered
*per-instance* `bind(q)` from Pareto structure or an audited subsample with IAA. The v1 fix stands —
recover a first-class `bind(q)` lower bound, or demote 91.1% to "decidability of declared constraints"
and headline the binding-independent 72.4%/16.0% attribution. This remains the load-bearing Oral gate.

### W7 — The theorem is gadget-level; §8.6 closure open. **Severity: MAJOR. STILL OPEN.**

Untouched, by design (`docs/OPEN_QUESTIONS.md`: the gadget-level theorem stands; the full
characterization `decidable ⇔ bind(q) ⊆ cl(R)` is deferred). `VoI(a*) = Δ(R)` remains proven exact
**only on the two-candidate/two-world gadget**; the general necessity statement and the §8.6 closure
remain empirically-shadowed, not proven. None of the four hardening artifacts touch theory, so W7 is
exactly where v1 left it. By the authors' own §11/§18.1 honest flag this still argues for either a
clean general proof or foregrounding C1+C2 and demoting "limit theorem" to "anchoring identity"
(and the corresponding ICLR-vs-NeurIPS-ED venue decision).

---

## 3. Updated §18.1 / weakness-ledger disposition

| Weakness | v1 severity | v2 status | v2 residual severity |
|---|---|---|---|
| W3 single-corpus prior | MAJOR | **ADDRESSED** (4-prior, adversarial survives 95.7%) | MINOR (corpus-selection still synthetic) |
| W4 proxy-truth guarantee | MAJOR | **PARTIALLY ADDRESSED** (feasibility real-GT ✅; min-sufficiency not) | MAJOR→MINOR-MAJOR |
| W5 M-confidence flagship | MAJOR | **ADDRESSED / RESOLVED** (H-only pooled p≈0, n=476) | RESOLVED |
| W6 small battery | MAJOR | **ADDRESSED / RESOLVED** (31 slices, 527 q, full HVR spread) | RESOLVED (breadth); V2-lift still n=5 |
| W1 per-instance binding | CRITICAL | **STILL OPEN** (deferred); W3 narrows blast radius | CRITICAL |
| W7 gadget-level theorem | MAJOR | **STILL OPEN** (deferred) | MAJOR |
| W2 §1↔§7 inconsistency | MAJOR (edit) | unchanged — must now point §1 at the *new* scaled n=476 H-only result | MAJOR (edit) |

---

## 4. Updated scores

| Dimension | v1 | **v2** | Justification for the change |
|---|---|---|---|
| **Novelty** | 8/10 | **8/10** | Unchanged. The identifiability reframe and VoI=Δ(R) identity are the novelty; the hardening was empirical robustness work, not a new idea. Still capped below 9 by the gadget-level theorem (W7). |
| **Soundness** | 7/10 | **8/10** | +1. The four closures remove three of the four v1 soundness caps: prior-robustness is now demonstrated under an adversarial prior (W3), the feasibility guarantee is real-GT-backed and transfers on a held-out split (W4), the flagship significance is H-confidence-only with n=476 (W5), and the battery is 4× larger with an honestly-reported HVR spread incl. null slices (W6). Held at 8 (not 9) by: W1 still under the headline, the min-sufficiency half of the guarantee still proxy-only (W4 residual), and the open §8.6 closure (W7). |
| **Significance** | 8/10 | **8/10** | Unchanged. The reframe's importance is the same; the hardening makes the *evidence* for it more bulletproof but does not enlarge the claim. Still capped by W1 (magnitude rides on declared-not-binding). *(W11 since closed — node `zh6apu`: the positive COMMIT branch is now validated on all 31 biting slices, 527 commits, feasible_frac=1.0, min_sufficient_frac=1.0, with the masked-regime abstain dual; and V2-lift scaled to n=527, McNemar 459/0, p≪0.05. Significance now capped by W1 alone.)* |
| **Clarity** | 8/10 | **8/10** | Unchanged pending the W2 edit. The new artifacts are exceptionally clear and self-flagging (the W4 doc explicitly separates the feasibility guarantee it *does* deliver from the min-sufficiency one it does *not*). Will rise to 9 once §1 is rewritten to lead with the n=476 H-only scaled result instead of the n=5 pilot. |

**Net:** Soundness 7 → 8. Novelty / Significance / Clarity steady. The hardening did exactly what
empirical hardening can do — it raised soundness by converting argued robustness into demonstrated
robustness — but it could not raise novelty or significance, which are gated by the (deliberately
deferred) theory.

---

## 5. Updated recommendation

**Spotlight — strong, at the Spotlight/Oral boundary — conditional on the W2 edit. NOT yet Oral.**

**Did closing W3/W4/W5/W6 move it toward Oral? Yes, but not across the line.** It moved soundness from
7 to 8 and converted three weaknesses from MAJOR to RESOLVED/MINOR. The §18.2 significance gate
("beat B2/B3 with significance across the battery") is now met *more* convincingly than in v1: the
flagship is H-confidence-only, n=476, p≈0, on a 4×-larger battery with a fully disclosed effect-size
spread. A reviewer can no longer dismiss C2 as "n=5," "M-tier truth," "one corpus," or "no real GT
on the guarantee." Those four v1 attack lines are closed or near-closed.

**Why it is still Spotlight, not Oral.** The Oral bar is the *intersection* of sharp reframe ×
surprising measurement × significant validation × (theorem + guarantee). The hardening completed the
first three. It did **not** touch the fourth Oral leg, and it left the single load-bearing gate
exactly where v1 found it:

- The **limit theorem (W7)** is still gadget-level with an open §8.6 closure — by the authors' own
  §11 flag, an Oral-grade *necessity* claim is not yet earned, only a clean anchoring identity.
- The **headline magnitude (W1)** still rides on declared-not-binding over-approximation. W3's
  adversarial prior *narrows* this (the headline survives even when governance/burden are assumed
  not to bind), which is real progress — but it is a synthetic re-weighting, not a recovered
  per-instance `bind(q)`. A hostile AC can still say "91.1% is the underdetermination of *declared*
  constraints," and the only rebuttal is "even adversarially it stays high," not "we measured
  binding."

So the hardening did precisely what was scoped: it removed every *empirical* objection a reviewer
could raise, leaving the paper resting cleanly on its two *theory* gates. That is a better place to
be — the remaining gate is now singular and well-characterized rather than tangled with four
empirical doubts — but it is not Oral yet.

---

## 6. The SINGLE remaining gate

**W1 — recover a first-class, per-instance `bind(q)` (the binding axes *active at the optimum*),
and show underdetermination stays high on *truly-binding* axes — OR demote the 91.1% headline to
"decidability of declared constraints" and promote the binding-independent attribution (72.4%
underdetermined because a binding axis is unmeasurable corpus-wide / 16.0% blocked *only* by
unmeasurable axes) to the headline.**

This is the one gate that, closed, would take the paper to Oral. It is a **theory/measurement** item
(per-instance binding semantics + a Pareto-recovered or hand-audited `bind(q)` lower bound with IAA),
which is why the empirical hardening pass — correctly — did not attempt it, and why it is held in
`docs/OPEN_QUESTIONS.md` as Q2. W7 (the gadget-level theorem) is the *second* deferred gate and is
co-equal for the *theorem* leg specifically; but W1 is the one that sits directly under the headline
number and is the higher-leverage single move. Either (a) recover `bind(q)` and keep 91.1%, or
(b) demote to the 72.4%/16.0% binding-independent headline — both are honest, and (b) is achievable
*today* with the artifacts already in hand (the attribution numbers exist in the decidability map and
were reproduced under every W3 prior). Doing (b) plus the W2 edit is the minimum-cost path to an
Oral-robust submission; doing (a) is the maximal one.

---

## Bottom line

- **v1 → v2 scores:** Novelty 8→**8**, Soundness 7→**8**, Significance 8→**8**, Clarity 8→**8** (pending W2 edit, then 9).
- **Recommendation:** **Spotlight** (strong, Spotlight/Oral boundary), conditional on the W2 §1 edit. The hardening moved it *toward* Oral (soundness +1; W3/W4/W5/W6 closed or near-closed) but did not cross the line.
- **Single remaining gate to Oral:** **W1 — per-instance binding.** Recover a first-class `bind(q)` lower bound and keep underdetermination high on truly-binding axes, or demote 91.1% to "declared constraints" and headline the binding-independent 72.4%/16.0% attribution. (W7, the gadget-level theorem, is the co-equal second deferred gate for the *theorem* leg.) Both are theory items, deliberately deferred — which is exactly why the empirical hardening could not, and did not, close them.
