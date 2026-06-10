# APT — Open theory questions (deferred, to revisit)

> Deferred deliberately so concrete work (figures, ablation, validation scaling,
> repro, mock review) can proceed. These are the theory items that need a careful
> pass (and likely a theory collaborator) before an ICLR-Oral theory claim is firm.
> None of them block the measurement (C1) or the empirical validation (C2); they
> sharpen the limit-theorem half (the ICLR "theorem" pillar, master plan §11).

## Q1 — Closure characterization `cl(R)` in full generality (§8.6)
The gadget-level limit theorem (§8.2–§8.5) stands: off-regime binding ⇒ irreducible
regret–coverage tradeoff `Δ(R)=δλ/(δ+λ)`. The *non-routine* part is the
characterization **`q` decidable under `R` ⇔ `bind(q) ⊆ cl(R)`** where `cl(R)` is
the certifiable closure (axes that are known monotone/deterministic functions of
`R` under the fixed context, with the map itself in `E`). Open: make `cl(R)` clean
and non-trivial for **general closure operators + multi-axis binding**. The
gadget-level version is enough for the necessity claim; the full characterization
is the candidate theory-collaborator task. If it cannot be made clean → drop the
theorem, fall back to NeurIPS-ED (measurement-as-thesis needs no theorem). [§11 Q1]

## Q2 — Binding axis operational at the PER-INSTANCE level (the deeper gate)
**Status: empirical half CLOSED on the GT/measurable axes (node `c90ge4`); the
corpus-wide-⊥ half stays unrecoverable by construction.**

P3/Q2 closed the query distribution at the **distribution** level: the ZenML tag→axis
taxonomy says which axes are *salient* in a deployment (regulatory_compliance →
governance is salient). The deeper gate was whether a *declared* constraint actually
**binds at the optimum** for a specific query — the axis whose constraint, if relaxed,
changes `x*`.

**Done (a):** the Pareto-structure active-constraint test is implemented —
`bind(q) = { a : min_cost(q without a) < min_cost(q) }`
(`src/prudent_ai/validation/binding.py`, `docs/W1_per_instance_binding.md`,
`outputs/p5/w1_binding.json`). On all V1 biting slices + a non-binding control, the C2
bite tracks Pareto-binding **exactly**: `bite ⟺ binding` agreement **1.0** (287 binding
& bite, 257 non-binding & no-bite, 0 off-diagonal); C2 on the certified-binding subset
B2 1.0 vs selective 0.0. So the C2 biting axes are *recovered* binding, not declared —
the main reviewer attack ("are these really the binding axes?") is answered where GT
exists.

**Remaining residual.** (b) a real per-deployment constraint trace (not tag-inferred) is
still ideal but not blocking. And the binding test is **only recoverable where GT
exists** (the measurable axes) — for the corpus-wide-⊥ axes (governance, reviewer_burden,
memory_hw) there is no data to drop-test, so the **C1 91.1% magnitude** continues to lead
with the binding-INDEPENDENT 72.4%/16.0% attribution rather than a per-instance
recovery. This node strengthens C2/C3, not the C1 headline. [§11 Q2]

## Q3 — Real mis-sizing exceeds `Δ(R)` — **CLOSED** (node `mfxhvu`)
Whether real leaderboard mis-sizing on the slice *exceeds* the theorem's `Δ(R)` is
empirical confirmation, NOT a corollary. **Done** (`src/prudent_ai/analysis/regret_delta.py`,
`docs/W4_minsuff_Q3_regret.md` §2, `outputs/p4/q3_regret.json`): the §8.2 gadget is
instantiated with real RouterBench geometry (δ = price of caution = cost(min-cost-feasible)
− cost(global-cheapest); λ = declared violation penalty), giving the real-calibrated floor
`Δ(R)=δλ/(δ+λ)`. On **41/41** biting slices `Δ(R) ≤ min(δ,λ)` — both naive rules
(cost-min regret λ, over-provisioner regret δ) strictly exceed the floor; the closed-form
Δ(R) matches the proven gadget minimax to 8.7e-19. The real cost stake is concrete: mean
**overshoot_rel = 0.748** (over-provisioning to guarantee feasibility costs ~75% more than
the cheapest infeasible config). The selective procedure pays 0 by abstaining; the Δ(R) it
would pay is the acquirable VoI. [§11 Q3 / §8.8]

## Q4 — Implemented VoI tracks `Δ(R)` on real data (partly done)
The identity `VoI(a*) = Δ(R)` is proven EXACT on the gadget (tests/test_procedure.py).
On real multi-axis-blocked queries the two-world VoI is a *bound*, and raw VoI ties
across co-blocking ⊥ axes (P4 finding) — the cost-aware VoI/cost ordering is what
discriminates. Open: a cleaner real-data demonstration that the implemented VoI
*numerically tracks* the achievable regret reduction (beyond the gadget + the V2
commit-correct 1.0-vs-0.2 signal). [§11 Q4]

## Also deferred
- ~~Distribution-free guarantee on a TRUE held-out ground-truth slice~~ — **DONE**:
  feasibility (node `eyfl2u`, `coverage_risk_gt`) and **min-sufficiency** (node `mfxhvu`,
  two-sided band, `minsuff_guarantee`) both calibrated on real held-out RouterBench GT.
- V3 live deployment runs (vLLM energy + small human study for governance/burden) —
  stretch, resource-gated. *(A prospective prompt-split "live" evaluation on real
  RouterBench traffic is the achievable surrogate — see node `mfxhvu`'s child.)*
