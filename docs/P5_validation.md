# P5 — Validation (§7 Evaluation, the Oral pillar)

**Status:** P5 V1+V2 finding, paper-grade feed for **§7 Evaluation**. Realizes constraint
**C2** (current practice *mis-sizes measurably*) and corroborates **C3** (the selective
procedure's abstention is the safe action). Where P3 *diagnosed* underdetermination and P4
*built the procedure that acts on it*, **P5 is the falsification test**: on a ground-truth
slice where a binding axis is hidden, does the community's honest practice (B2 observed-Pareto)
and its standard defences (B3 imputation, B6 cost-accuracy) commit configs that *silently
violate the truth* — and does the selective procedure avoid that by abstaining? This is the
DV2 (regret) + DV3 (hidden-violation) leg of the §16 claim map: **C2 ← DV2 + DV3, vs B2/B3**.

**Substrate & interface (unchanged, C7).** `data/apt_substrate.db`, wrapped
`CachedSubstrate(Substrate(DB))`. Every rule — baselines and the selective procedure alike —
reads the substrate **only** through the solver/classifier interface (`candidates / cell /
required_fields`). Masking is realized at the read level by `MaskedSubstrate`: it returns `[]`
for the masked axis's `cell(...)`, so *no* rule can see the hidden axis regardless of how it
reads. The oracle (B5, `sees_masked=True`) is the sole exception — it is handed the real
substrate and so defines the regret floor. `⊥` stays `⊥`; nothing is imputed at the read level.

**How the numbers were produced (reproducible).** φ=point, κ_operating=H+M, masking via
`validation.harness.MaskAndPredict` / `MaskedSubstrate`, V2 seed=12345. All numbers below are
read verbatim from `outputs/p5/validation.{json,md}` (provenance `P5-V1V2`). The slice's own
measured values are used **only to score**, never to tune any rule (C8 — no leakage).

---

## 1. The validation question (C2/C3)

P3 established that 91.1% of real right-sizing queries are evidence-underdetermined; P4 built a
procedure that COMMITs on the decidable minority and ABSTAINs-informatively on the rest. Both
are statements about *how much evidence is missing* and *what the procedure does about it*.
Neither yet shows the thing an Oral reviewer demands (§18.1, "Missing metrics is obvious"):
that **answering anyway is measurably wrong**, and that **the procedure's silence is the
correct action** in exactly those cases.

That is the C2 question, and it is sharp and falsifiable:

> Take a slice with co-located *ground-truth* axis values. Bind a query on two axes. **Mask one
> binding axis.** Let each decision rule commit a config from the visible evidence. Score the
> commit against the **true** (unmasked) value of the hidden axis. A rule that commits a config
> violating the hidden constraint has **mis-sized** — silently, because by construction it could
> not see the axis it violated.

The load-bearing metric is **DV3 hidden-violation rate** = fraction of a rule's *commits* that
violate the masked truth. The claim is hard (§14): we **MUST beat B2** (observed-Pareto =
current honest practice) **and B3** (imputation = "just fill it in"), and ideally B6
(cost-accuracy = FrugalGPT-style, drops latency/energy/governance). The selective procedure's
answer to a masked binding axis should be to **ABSTAIN** — coverage 0 on that mask, but **zero
hidden-violation**. That is the §17.1 Trust-or-Escalate shape with measured violations now
visible on the *other* side: the baselines buy coverage by mis-sizing; the procedure buys zero
mis-sizing by escalating.

DV2 (decision regret, cost overshoot vs the oracle minimum-sufficient) is reported alongside,
but it is **degenerate when violations dominate** (§6 below): a rule that commits an infeasible
config contributes a hidden-violation, not a regret-over-feasible sample. So on the biting case
DV3 carries the claim and DV2 is near-zero by construction.

---

## 2. Setup

**Ground-truth slices.** Two co-located measured slices, used purely to score (C8):

| slice | τ | configs | GT axes | confidence | κ |
|---|---|---|---|---|---|
| **BFCL** (function-calling) | `function-calling` | 109 | quality + cost + latency_p95 | M | H+M |
| **RouterBench** | `routerbench` | 330 | quality + cost | H | H+M |

(ML.ENERGY is excluded: it has no `cost` axis, so the cost-objective oracle cannot score it.)

**Mask-and-predict** (`validation.harness.MaskAndPredict`). Generate a battery of queries that
*bind* both axes in `bind_axes` at matched observed percentiles (pcts 30/40/50/60/70, n=5 per
slice/mask). Then mask one binding axis and, per rule, read the prediction under the visible
regime and score it against truth: `true_feasible(q, pred)` checks the commit against the
**full-regime** measured values; a commit that fails it is a hidden violation; a feasible commit
contributes `max(0, cost(pred) − oracle_cost(q))` to regret.

**Masking is enforced at the read level.** `MaskedSubstrate(sub, masked_axis)` withholds the one
axis uniformly; only B5 (the oracle) is handed the unmasked substrate. This is the C7-shaped
ablation: same interface, one axis silenced — a faithful simulation of structural missingness.

**The baseline lattice B1–B6** (§14, `validation.baselines`) — one line each:

| | rule | what it does under the mask | role |
|---|---|---|---|
| B1 | accuracy-only | argmax quality, ignores cost & every constraint | strawman |
| **B2** | **observed-Pareto** | min visible-cost s.t. *visible* constraints; treats the masked axis as satisfied | **honest current practice — MUST beat** |
| **B3** | **imputation** | impute the masked axis (global median) then decide as B2 | **"just fill it in" — MUST beat** |
| B4 | missing-as-fail | a masked *binding* axis ⇒ abstain | conservative upper bound (0 violations) |
| B5 | oracle | sees the true masked values ⇒ true min-cost feasible | **regret floor** |
| B6 | cost-accuracy | min cost s.t. the quality constraint only; drops latency/energy/gov | FrugalGPT-style domain rival |
| — | **selective (ours)** | P4 `right_size` under the visible regime — COMMIT iff decidable, else ABSTAIN | the procedure |

---

## 3. V1 results — the C2 demonstration (actual numbers)

### 3.1 The biting case: BFCL, bind `quality+latency_p95`, **mask `quality`**

This is the slice chosen *because* it binds (§18.2: pick where multiple axes truly bind). In
BFCL, cheap configs are *low-quality* — so a cost-minimizer that cannot see quality commits the
cheapest config and silently violates the quality floor. Verbatim from `outputs/p5/validation.json`:

| rule | coverage | hidden_violation_rate | n_hidden_violation | mean_regret |
|---|---|---|---|---|
| B1 accuracy-only | 0.0 | 0.0 | 0 | 0.0 |
| **B2 observed-Pareto** | **1.0** | **1.0** | **5/5** | 0.0 |
| **B3 imputation** | **1.0** | **1.0** | **5/5** | 0.0 |
| B4 missing-as-fail | 0.0 | 0.0 | 0 | 0.0 |
| B5 oracle | 1.0 | 0.0 | 0 | 0.0 |
| **B6 cost-accuracy** | **1.0** | **1.0** | **5/5** | 0.0 |
| **selective (ours)** | **0.0** | **0.0** | **0** | 0.0 |

**This is C2.** The three commit-while-blind rules — **B2, B3, B6** — commit on **100%** of
queries and **hidden-violate on 100%** of those commits (5/5 each). The honest current practice
(B2) and both standard defences (imputation B3, cost-accuracy B6) *silently ship an infeasible
config every single time the quality axis is unobservable*. The **selective procedure abstains
on all 5** (coverage 0) and therefore has **0 hidden-violation** — it refuses precisely when it
cannot certify the binding axis. Note that B3 imputation does **not** rescue the case: imputing
the global-median quality still commits the same blind config (the §18.1 "imputation solves it"
attack, answered with a number — imputation's hidden-violation = 1.0, identical to B2).

The verdict in the harness: **`c2_verdict: "holds"`** — selective HVR 0.0 vs
{B2, B3, B6} = 1.0. This is a clean "**must beat B2 and B3**" pass on DV3.

### 3.2 The honest control: same slice, **mask `latency_p95`** (does NOT bite)

The finding is **axis-specific, and we report it as such** (§18.2). When we instead mask
*latency* on the same BFCL bind, the phenomenon vanishes:

| rule | coverage | hidden_violation_rate | mean_regret |
|---|---|---|---|
| B1 accuracy-only | 1.0 | 0.2 | 84.625 |
| B2 observed-Pareto | 1.0 | **0.0** | 0.0 |
| B3 imputation | 1.0 | **0.0** | 0.0 |
| B6 cost-accuracy | 1.0 | **0.0** | 0.0 |
| selective (ours) | 0.0 | 0.0 | 0.0 |

**`c2_verdict: "no-bite"`.** Because in BFCL *cheap ⇒ fast* (cost and latency are positively
aligned), the cost-minimizer's blind commit happens to satisfy the hidden latency floor too — so
there is nothing to beat. B1 (which ignores cost entirely) is the only rule that violates here,
because chasing max-quality picks a slow config (HVR 0.2, regret 84.6). This is the honest face
of C2: the mis-sizing is a property of *which* axis is hidden and *whether cheap configs trade it
off* — not a universal claim. We show the biting case **and** the control, exactly as §18.2's
"choose the slice where it binds" discipline requires.

### 3.3 RouterBench corroboration: bind `quality+cost`, **mask `quality`**

| rule | coverage | hidden_violation_rate | mean_regret |
|---|---|---|---|
| B2 / B3 / B6 | 1.0 | **0.0** | 0.0 |
| selective (ours) | 0.0 | 0.0 | 0.0 |

**`c2_verdict: "no-bite"`** on this RouterBench mask: on the H-confidence slice, the cost-minimal
config that B2/B3/B6 commit also clears the hidden quality floor at these percentiles, so no
baseline silently violates. RouterBench therefore *corroborates the honest control* rather than
supplying a second bite: it confirms the phenomenon is structural (depends on the cheap-vs-good
trade-off on the specific slice/axis), and that where the trade-off is absent the baselines are
*correctly* not penalized. The C2 bite is demonstrated on BFCL/mask-quality; RouterBench and
BFCL/mask-latency are the two honest no-bite controls that keep the claim falsifiable.

---

## 4. V2 results — VoI-guided acquisition (DV5 preview)

V2 asks the §10 / DV5 question on the biting BFCL bind: if we mask *both* binding axes and then
reveal **one** — chosen by cost-aware VoI vs at random — does the VoI-chosen reveal let the
selective procedure commit-correctly more often? Construction: mask-all-bind / reveal-top-VoI-vs-
random / re-run-selective, seed=12345. Verbatim:

| reveal | n | commits | commit-correct | frac |
|---|---|---|---|---|
| top-VoI axis | 5 | 0 | 0 | 0.0 |
| random axis | 5 | 0 | 0 | 0.0 |

**Reported honestly as degenerate.** The selective rule must certify *every* binding axis before
it commits; revealing **one** axis out of a **two-axis** bind cannot un-block it, so both top-VoI
and random yield **0 commits**. The single-reveal commit-correct fraction therefore does not
discriminate on this slice — and we say so rather than dressing it up.

**What does discriminate — the VoI signal.** On **5/5** abstentions the cost-aware VoI ranking
strictly prefers the **cheaper measurable field** (`frac = 1.0`): both axes carry equal raw
VoI=1.0, but `voi_per_cost` is 10.0 for `latency_p95` vs 3.33 for `quality`, so the ranking puts
the cheap-to-measure axis first on every query. This is the §10 / P4-§3.3 claim realized at the
acquisition level: **VoI predicts the field worth measuring (cost-aware)** even where one reveal
cannot flip a two-binding-axis COMMIT. Full multi-reveal cascade evaluation (reveal until
decidable, regret-to-oracle vs random ordering) is the V2 stretch that remains.

---

## 5. Relation to claims

**C2 (DV2 + DV3) — established on the biting case.** On BFCL/mask-quality, current honest
practice and its defences hidden-violate at **100%** while the procedure hidden-violates at
**0%**. That is the §18.1 surprise the Oral hinges on: *the community rule answers anyway and
mis-sizes measurably*, and "imputation solves it" is refuted with a number (B3 HVR = 1.0). DV2
regret is degenerate-by-violation here (§6), so DV3 is the load-bearing metric and it passes the
"beat B2 and B3" bar cleanly.

**C3 — the abstention is the safe action.** The selective procedure's coverage-0/violation-0
column *is* the safe action: it escalates exactly the queries where it cannot certify the binding
axis, instead of shipping a blind commit. This ties directly to the P4 coverage story — selective
trades coverage for zero hidden-violation, the **Trust-or-Escalate shape** (§17.1) — but now with
**measured violations on the other side**. P4 showed "reliability is purchasable only by
abstaining on most traffic" (committed risk 0% at 10.5% coverage); P5 shows *what the alternative
costs*: the rules that don't abstain hidden-violate at 100% on the biting axis. The two halves of
the Trust-or-Escalate trade-off are now both measured.

**Go / No-Go read (§18.2).** §18.2 says: if P5 cannot show mis-sizing (B2/B3 not beaten with
significance) → do not force Oral. The bite **exists and is unambiguous on the chosen slice**
(B2/B3/B6 = 1.0 vs selective 0.0), which clears the *direction* of the gate. What is **not yet
cleared** is the *significance* bar: the bite is on a single slice with **n=5** queries and an
all-or-nothing (1.0 vs 0.0) separation — descriptively decisive, but no significance test has
been run and the battery is small. **Provisional read: GO on demonstration, HOLD on significance**
— the §18.2 Oral gate ("procedure beats B2,B3 *with significance*") is not yet met; scaling the
battery + a significance test is the immediate next step (§6).

---

## 6. Honest limitations

1. **"Truth" is the slice's own measured values, not an independent oracle.** Ground-truth here =
   the substrate's co-located H/M-confidence measurements; BFCL is **M-confidence**. This is
   calibration against the richest evidence we have on the slice, not an external held-out oracle
   (the §8.8 / P4-§5 discipline, restated). RouterBench is H-confidence and corroborates as a
   control.

2. **Masking is an ablation simulating missingness.** We *withhold* an axis we actually measured,
   to model the structural missingness P3 found in the wild. It is a faithful simulation, not a
   naturally-missing slice — V3 live runs (real missing axes on local AI boxes) remain the
   stretch.

3. **Regret-over-feasible is degenerate when violations dominate.** On the biting case every
   baseline commit is *infeasible*, so it contributes a hidden-violation, not a regret sample —
   hence `mean_regret = 0.0` across the board there. **DV3 hidden-violation-rate is the
   load-bearing metric**, not DV2 regret, on exactly the slice where C2 bites. DV2 is informative
   only on the control (B1 mean_regret 84.6 on mask-latency).

4. **Small query batteries.** n=5 per slice/mask. The 1.0-vs-0.0 separation is descriptively
   decisive but statistically thin; no significance test has been run. **This is the gating gap.**

5. **Axis-specificity is a feature, reported as a caveat.** The bite is BFCL/mask-quality only;
   BFCL/mask-latency and RouterBench/mask-quality do *not* bite. The claim is "current practice
   mis-sizes *where multiple axes truly bind and cheap trades off the hidden one*", not a
   universal claim — and we show the no-bite controls to keep it falsifiable.

**What remains for a full §7:** (i) scale the battery (more queries, more bind/mask pairs, more
slices) and add **significance tests** on hidden-violation-rate; (ii) the V2 multi-reveal VoI
cascade (reveal-until-decidable, regret-to-oracle vs random); (iii) V3 live runs (vLLM + ML.ENERGY
energy + small governance/burden human study).

---

## 7. Key numbers the paper cites + Go/No-Go

- **C2 bite (BFCL, bind `quality+latency_p95`, mask `quality`, κ=H+M, φ=point, n=5):**
  B2 observed-Pareto, B3 imputation, B6 cost-accuracy each **coverage 1.0, hidden-violation-rate
  1.0 (5/5 commits silently infeasible)**; selective **coverage 0.0, hidden-violation-rate 0.0**.
  `c2_verdict = holds`. **Must-beat-B2-and-B3: passed (1.0 → 0.0).**
- **Honest controls (no bite):** BFCL mask `latency_p95` → B2/B3/B6 HVR **0.0** (cheap⇒fast; only
  B1 violates, HVR 0.2, regret 84.6); RouterBench mask `quality` → B2/B3/B6 HVR **0.0**. Both
  `c2_verdict = no-bite`. The phenomenon is axis/slice-specific and reported as such.
- **DV5 / V2 VoI signal (seed=12345):** single-reveal commit-correct **0/5 for both** top-VoI and
  random (degenerate — one reveal cannot un-block a 2-axis bind); but the cost-aware VoI ranking
  prefers the cheaper measurable field on **5/5 = 100%** of abstentions (`voi_per_cost` 10.0 vs
  3.33). VoI predicts *what to measure*, even where one reveal can't flip the COMMIT.
- **B5 oracle = regret floor:** HVR 0.0, regret 0.0 everywhere (the achievable best).

**Go/No-Go read:** **GO on the C2 demonstration** — the mis-sizing is real, unambiguous, and
refutes both the "obvious" and "imputation solves it" reviewer attacks (§18.1) with the procedure
landing the safe action (C3). **HOLD on Oral significance** — the §18.2 gate requires beating
B2/B3 *with significance*; the current bite is a single slice, n=5, all-or-nothing. Direction:
decisively right. Statistics: not yet run. **Next gate-closing step = scale the battery +
significance test**, then V2 multi-reveal and (stretch) V3.
