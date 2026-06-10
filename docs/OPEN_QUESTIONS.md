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
P3/Q2 closed the query distribution at the **distribution** level: the ZenML tag→axis
taxonomy says which axes are *salient* in a deployment (regulatory_compliance →
governance is salient). It does NOT yet establish which axis actually **binds at the
optimum** for a specific query — i.e. the axis whose constraint, if relaxed, changes
`x*`. The decidability/validation results currently treat the constrained axes as the
binding set. To make `bind(q)` rigorous per §1/§11-Q2, need: (a) a Pareto-structure
test that identifies the active constraint at the realized optimum on the GT slice,
(b) ideally a real per-deployment constraint trace (not tag-inferred). This is the
honest residual of Q2 and the main reviewer-attack surface ("are these really the
binding axes?"). [§11 Q2]

## Q3 — Real mis-sizing exceeds `Δ(R)` (empirical, partly P5)
Whether real leaderboard mis-sizing on the slice *exceeds* the theorem's `Δ(R)`
(because cost–latency–energy are correlated / heavy-tailed) is empirical confirmation,
NOT a corollary of the theorem. P5 shows the hidden-violation gap (categorical +
significant); still to do: quantify the *magnitude* of cost-regret (DV2) where the
masked axis binds and compare to `Δ(R)` directly. [§11 Q3 / §8.8]

## Q4 — Implemented VoI tracks `Δ(R)` on real data (partly done)
The identity `VoI(a*) = Δ(R)` is proven EXACT on the gadget (tests/test_procedure.py).
On real multi-axis-blocked queries the two-world VoI is a *bound*, and raw VoI ties
across co-blocking ⊥ axes (P4 finding) — the cost-aware VoI/cost ordering is what
discriminates. Open: a cleaner real-data demonstration that the implemented VoI
*numerically tracks* the achievable regret reduction (beyond the gadget + the V2
commit-correct 1.0-vs-0.2 signal). [§11 Q4]

## Also deferred
- Distribution-free guarantee on a TRUE held-out ground-truth slice (P5 currently
  calibrates on a richer-κ *proxy*; real-GT calibration is the honest P5-completion).
- V3 live deployment runs (vLLM energy + small human study for governance/burden) —
  stretch, resource-gated.
